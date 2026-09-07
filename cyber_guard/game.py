"""Main game loop and rendering for Campus Cyber Guard."""

from __future__ import annotations

import json
import math
import random
from collections import deque
from pathlib import Path
from typing import Deque, Dict, List, Optional, Sequence, Tuple

import pygame

from .config import (
    COLORS,
    DEMO_TOWERS,
    ENEMY_TYPES,
    FPS,
    GRID_SIZE,
    HEIGHT,
    MAP_WIDTH,
    PATH_POINTS,
    PATH_WIDTH,
    SAVE_FILE,
    TITLE,
    TOWER_TYPES,
    WAVES,
    WIDTH,
)
from .entities import Enemy, FloatingText, Particle, Projectile, Tower, Vec2, burst, distance_point_to_segment
from .ui import Button, font, rounded_panel, text, wrap_lines


class CyberGuardGame:
    """Owns state transitions, input, simulation, persistence and rendering."""

    def __init__(self, headless: bool = False, demo: bool = False) -> None:
        pygame.init()
        pygame.font.init()
        self.headless = headless
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        pygame.display.set_caption(TITLE)
        self.clock = pygame.time.Clock()
        self.running = True
        self.state = "menu"
        self.paused = False
        self.show_help = False
        self.demo_mode = demo
        self.demo_elapsed = 0.0
        self.demo_actions_done: set = set()
        self.demo_callout = ""
        self.demo_callout_timer = 0.0

        self.high_score = self.load_high_score()
        self.stars = self.make_stars(76)
        self.menu_buttons = {
            "start": Button((470, 420, 340, 58), "开始防御", COLORS["cyan"], "ENTER"),
            "demo": Button((470, 493, 340, 52), "观看自动演示", COLORS["magenta"], "D"),
            "help": Button((470, 558, 340, 48), "玩法说明", COLORS["amber"], "H"),
        }
        self.tower_buttons = {
            "scanner": Button((978, 190, 284, 72), "", COLORS["cyan"], "1"),
            "firewall": Button((978, 272, 284, 72), "", COLORS["amber"], "2"),
            "quarantine": Button((978, 354, 284, 72), "", COLORS["magenta"], "3"),
        }
        self.wave_button = Button((978, 548, 284, 52), "启动下一波", COLORS["green"], "SPACE")
        self.skill_button = Button((978, 612, 284, 52), "全网应急扫描  60⚡", COLORS["red"], "E")
        self.reset_game()
        if demo:
            self.start_game(demo=True)

    @staticmethod
    def make_stars(count: int) -> Sequence[Tuple[int, int, int]]:
        generator = random.Random(202409)
        return [(generator.randrange(WIDTH), generator.randrange(HEIGHT), generator.choice((1, 1, 1, 2))) for _ in range(count)]

    @staticmethod
    def load_high_score() -> int:
        try:
            return int(json.loads(SAVE_FILE.read_text(encoding="utf-8")).get("high_score", 0))
        except (FileNotFoundError, ValueError, TypeError, json.JSONDecodeError):
            return 0

    def save_high_score(self) -> None:
        if self.score <= self.high_score:
            return
        self.high_score = self.score
        SAVE_FILE.parent.mkdir(parents=True, exist_ok=True)
        SAVE_FILE.write_text(json.dumps({"high_score": self.high_score}, ensure_ascii=False, indent=2), encoding="utf-8")

    def reset_game(self) -> None:
        self.money = 320
        self.base_health = 20
        self.max_base_health = 20
        self.energy = 70.0
        self.score = 0
        self.combo = 0
        self.wave_index = 0
        self.wave_active = False
        self.wave_cleared_timer = 0.0
        self.spawn_queue: Deque[Tuple[str, float]] = deque()
        self.spawn_timer = 0.0
        self.enemies: List[Enemy] = []
        self.towers: List[Tower] = []
        self.projectiles: List[Projectile] = []
        self.particles: List[Particle] = []
        self.floating_texts: List[FloatingText] = []
        self.rewarded_enemy_ids: set = set()
        self.selected_build: Optional[str] = None
        self.selected_tower: Optional[Tower] = None
        self.message = "选择防御节点并部署到地图空地"
        self.message_timer = 4.0
        self.shake_timer = 0.0
        self.scan_flash = 0.0
        self.total_kills = 0
        self.total_leaks = 0

    def start_game(self, demo: bool = False) -> None:
        self.reset_game()
        self.state = "play"
        self.demo_mode = demo
        self.demo_elapsed = 0.0
        self.demo_actions_done = set()
        self.demo_callout = ""
        self.demo_callout_timer = 0.0
        if demo:
            self.money = 760
            self.base_health = 30
            self.max_base_health = 30
            self.message = "自动演示：系统将依次部署、升级并启动波次"
            self.message_timer = 5.0

    def run(self) -> None:
        while self.running:
            dt = min(0.05, self.clock.tick(FPS) / 1000.0)
            self.handle_events()
            self.update(dt)
            self.draw()
            pygame.display.flip()
        pygame.quit()

    def record_demo(
        self,
        output_path: Path,
        duration: float,
        fps: int,
        screenshot_dir: Optional[Path] = None,
    ) -> None:
        """Run deterministic headless gameplay and encode it to an MP4."""
        import imageio.v2 as imageio
        import numpy as np

        output_path = output_path.resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        if screenshot_dir:
            screenshot_dir = screenshot_dir.resolve()
            screenshot_dir.mkdir(parents=True, exist_ok=True)
        capture_times = {7: "01_部署防御节点.png", 22: "02_波次战斗.png", 40: "03_应急扫描与升级.png"}
        captured = set()
        total_frames = int(duration * fps)
        writer = imageio.get_writer(
            str(output_path),
            fps=fps,
            codec="libx264",
            quality=8,
            macro_block_size=None,
            ffmpeg_log_level="warning",
        )
        try:
            for frame_index in range(total_frames):
                for event in pygame.event.get():
                    if event.type == pygame.QUIT:
                        self.running = False
                self.update(1.0 / fps)
                self.draw()
                elapsed_second = int(frame_index / fps)
                if screenshot_dir and elapsed_second in capture_times and elapsed_second not in captured:
                    pygame.image.save(self.screen, str(screenshot_dir / capture_times[elapsed_second]))
                    captured.add(elapsed_second)
                pixels = pygame.surfarray.array3d(self.screen)
                frame = np.transpose(pixels, (1, 0, 2))
                writer.append_data(frame)
        finally:
            writer.close()
            pygame.quit()

    def handle_events(self) -> None:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
                continue
            if event.type == pygame.KEYDOWN:
                self.handle_key(event.key)
            if event.type == pygame.MOUSEBUTTONDOWN:
                self.handle_click(event.button, event.pos)

    def handle_key(self, key: int) -> None:
        if self.state == "menu":
            if key in (pygame.K_RETURN, pygame.K_SPACE):
                self.start_game()
            elif key == pygame.K_d:
                self.start_game(demo=True)
            elif key == pygame.K_h:
                self.show_help = not self.show_help
            elif key == pygame.K_ESCAPE:
                if self.show_help:
                    self.show_help = False
                else:
                    self.running = False
            return

        if self.state in ("won", "lost"):
            if key in (pygame.K_RETURN, pygame.K_r):
                self.start_game()
            elif key == pygame.K_ESCAPE:
                self.state = "menu"
            return

        if key == pygame.K_ESCAPE:
            if self.show_help:
                self.show_help = False
            elif self.selected_build or self.selected_tower:
                self.selected_build = None
                self.selected_tower = None
            else:
                self.state = "menu"
        elif key == pygame.K_p:
            self.paused = not self.paused
        elif key == pygame.K_h:
            self.show_help = not self.show_help
        elif key == pygame.K_SPACE:
            self.start_wave()
        elif key == pygame.K_e:
            self.activate_scan()
        elif key == pygame.K_1:
            self.choose_build("scanner")
        elif key == pygame.K_2:
            self.choose_build("firewall")
        elif key == pygame.K_3:
            self.choose_build("quarantine")
        elif key == pygame.K_u:
            self.upgrade_selected()
        elif key == pygame.K_x:
            self.sell_selected()

    def handle_click(self, button: int, pos: Tuple[int, int]) -> None:
        if button == 3:
            self.selected_build = None
            self.selected_tower = None
            return
        if button != 1:
            return
        if self.show_help:
            self.show_help = False
            return
        if self.state == "menu":
            if self.menu_buttons["start"].hit(pos):
                self.start_game()
            elif self.menu_buttons["demo"].hit(pos):
                self.start_game(demo=True)
            elif self.menu_buttons["help"].hit(pos):
                self.show_help = True
            return
        if self.state in ("won", "lost"):
            self.start_game()
            return
        if self.demo_mode:
            return

        for kind, item in self.tower_buttons.items():
            if item.hit(pos):
                self.choose_build(kind)
                return
        can_wave = not self.wave_active and self.wave_index < len(WAVES)
        if self.wave_button.hit(pos, can_wave):
            self.start_wave()
            return
        if self.skill_button.hit(pos, self.energy >= 60 and bool(self.enemies)):
            self.activate_scan()
            return
        if self.selected_tower:
            upgrade_rect = pygame.Rect(655, 651, 122, 40)
            sell_rect = pygame.Rect(790, 651, 122, 40)
            if upgrade_rect.collidepoint(pos):
                self.upgrade_selected()
                return
            if sell_rect.collidepoint(pos):
                self.sell_selected()
                return
        if pos[0] < MAP_WIDTH:
            clicked_tower = next((tower for tower in reversed(self.towers) if tower.pos.distance_to(pos) <= 28), None)
            if clicked_tower:
                self.selected_tower = clicked_tower
                self.selected_build = None
            elif self.selected_build:
                self.place_tower(self.selected_build, self.snap_position(pos))
            else:
                self.selected_tower = None

    def choose_build(self, kind: str) -> None:
        self.selected_build = kind
        self.selected_tower = None
        self.set_message("已选择{}：点击地图空地部署".format(TOWER_TYPES[kind]["name"]))

    @staticmethod
    def snap_position(pos: Tuple[int, int]) -> Tuple[int, int]:
        return (
            int(round(pos[0] / GRID_SIZE) * GRID_SIZE),
            int(round(pos[1] / GRID_SIZE) * GRID_SIZE),
        )

    def is_valid_build(self, pos: Tuple[int, int]) -> bool:
        point = Vec2(pos)
        if pos[0] < 32 or pos[0] > MAP_WIDTH - 32 or pos[1] < 48 or pos[1] > HEIGHT - 48:
            return False
        if any(point.distance_to(tower.pos) < 58 for tower in self.towers):
            return False
        clearance = PATH_WIDTH / 2 + 34
        for start, end in zip(PATH_POINTS, PATH_POINTS[1:]):
            if distance_point_to_segment(point, Vec2(start), Vec2(end)) < clearance:
                return False
        return True

    def place_tower(self, kind: str, pos: Tuple[int, int], free: bool = False) -> bool:
        cost = int(TOWER_TYPES[kind]["cost"])
        if not self.is_valid_build(pos):
            self.set_message("这里距离传输链路太近，无法部署", COLORS["red"])
            return False
        if not free and self.money < cost:
            self.set_message("资源点不足，需要 {}".format(cost), COLORS["red"])
            return False
        if not free:
            self.money -= cost
        tower = Tower(kind, pos)
        self.towers.append(tower)
        self.selected_tower = tower
        self.selected_build = None
        self.particles.extend(burst(tower.pos, tower.color, 14))
        self.set_message("{} 部署完成".format(TOWER_TYPES[kind]["name"]), COLORS["green"])
        return True

    def upgrade_selected(self, free: bool = False) -> bool:
        tower = self.selected_tower
        if not tower:
            return False
        if tower.level >= 3:
            self.set_message("节点已达到最高等级")
            return False
        cost = tower.upgrade_cost
        if not free and self.money < cost:
            self.set_message("升级资源不足，需要 {}".format(cost), COLORS["red"])
            return False
        if not free:
            self.money -= cost
        tower.upgrade()
        self.particles.extend(burst(tower.pos, COLORS["green"], 18))
        self.set_message("{} 升至 Lv.{}".format(tower.data["name"], tower.level), COLORS["green"])
        return True

    def sell_selected(self) -> bool:
        tower = self.selected_tower
        if not tower:
            return False
        value = tower.sell_value
        self.money += value
        self.towers.remove(tower)
        self.particles.extend(burst(tower.pos, COLORS["amber"], 12))
        self.selected_tower = None
        self.set_message("节点已回收，返还 {} 资源点".format(value), COLORS["amber"])
        return True

    def start_wave(self) -> bool:
        if self.wave_active or self.wave_index >= len(WAVES):
            return False
        definition = WAVES[self.wave_index]
        self.wave_index += 1
        self.wave_active = True
        self.spawn_queue.clear()
        speed_factor = 0.62 if self.demo_mode else 1.0
        for kind, count, interval in definition:
            for _ in range(count):
                self.spawn_queue.append((kind, interval * speed_factor))
        self.spawn_timer = 0.0
        self.set_message("第 {} 波入侵开始".format(self.wave_index), COLORS["red"])
        return True

    def activate_scan(self, free: bool = False) -> bool:
        if not self.enemies:
            self.set_message("当前没有可扫描目标")
            return False
        if not free and self.energy < 60:
            self.set_message("能量不足", COLORS["red"])
            return False
        if not free:
            self.energy -= 60
        damage = 68 + self.wave_index * 5
        for enemy in self.enemies:
            if not enemy.dead:
                enemy.take_damage(damage)
                enemy.apply_slow(0.35, 1.0)
                self.particles.extend(burst(enemy.pos, COLORS["cyan"], 5))
        self.scan_flash = 0.55
        self.set_message("应急扫描完成：全体目标受到 {} 点伤害".format(damage), COLORS["cyan"])
        return True

    def set_message(self, value: str, color: Tuple[int, int, int] = COLORS["white"]) -> None:
        self.message = value
        self.message_color = color
        self.message_timer = 2.8

    def update(self, dt: float) -> None:
        self.message_timer = max(0.0, self.message_timer - dt)
        self.demo_callout_timer = max(0.0, self.demo_callout_timer - dt)
        self.scan_flash = max(0.0, self.scan_flash - dt)
        self.shake_timer = max(0.0, self.shake_timer - dt)
        if self.state != "play" or self.paused or self.show_help:
            return

        if self.demo_mode:
            self.update_demo(dt)

        self.energy = min(100.0, self.energy + dt * 2.6)
        if self.wave_active and self.spawn_queue:
            self.spawn_timer -= dt
            if self.spawn_timer <= 0:
                kind, interval = self.spawn_queue.popleft()
                self.enemies.append(Enemy(kind, self.wave_index))
                self.spawn_timer = interval

        for enemy in self.enemies:
            enemy.update(dt)
        for tower in self.towers:
            tower.update(dt, self.enemies, self.projectiles)

        for projectile in list(self.projectiles):
            victims = projectile.update(dt, self.enemies)
            for victim in victims:
                if victim.dead and victim.id not in self.rewarded_enemy_ids:
                    projectile.tower.kills += 1
            if not projectile.alive:
                self.projectiles.remove(projectile)

        self.resolve_enemies()
        for particle in self.particles:
            particle.update(dt)
        self.particles = [particle for particle in self.particles if particle.life > 0]
        for label in self.floating_texts:
            label.update(dt)
        self.floating_texts = [label for label in self.floating_texts if label.life > 0]

        if self.wave_active and not self.spawn_queue and not self.enemies:
            self.wave_active = False
            self.wave_cleared_timer = 1.2
            reward = 42 + self.wave_index * 9
            self.money += reward
            self.energy = min(100, self.energy + 18)
            self.score += 100 * self.wave_index
            self.set_message("第 {} 波已清除，奖励 {} 资源点".format(self.wave_index, reward), COLORS["green"])
            if self.wave_index >= len(WAVES):
                self.finish_game(True)
        self.wave_cleared_timer = max(0.0, self.wave_cleared_timer - dt)

    def resolve_enemies(self) -> None:
        survivors = []
        for enemy in self.enemies:
            if enemy.dead:
                if enemy.id not in self.rewarded_enemy_ids:
                    self.rewarded_enemy_ids.add(enemy.id)
                    self.combo += 1
                    multiplier = 1.0 + min(2, self.combo // 6) * 0.5
                    reward = int(enemy.reward * multiplier)
                    self.money += reward
                    self.score += int(enemy.reward * 10 * multiplier)
                    self.total_kills += 1
                    self.floating_texts.append(FloatingText("+{}".format(reward), enemy.pos.copy(), COLORS["green"]))
                    self.particles.extend(burst(enemy.pos, enemy.color, 12 if enemy.kind != "boss" else 30))
                continue
            if enemy.escaped:
                self.base_health -= enemy.base_damage
                self.total_leaks += 1
                self.combo = 0
                self.shake_timer = 0.35
                self.floating_texts.append(FloatingText("核心 -{}".format(enemy.base_damage), Vec2(900, 575), COLORS["red"]))
                if self.base_health <= 0:
                    self.base_health = 0
                    self.finish_game(False)
                continue
            survivors.append(enemy)
        self.enemies = survivors

    def finish_game(self, won: bool) -> None:
        self.state = "won" if won else "lost"
        self.save_high_score()

    def update_demo(self, dt: float) -> None:
        self.demo_elapsed += dt
        scripted = [
            (0.8, "tower0", lambda: self.demo_place(0, "先部署扫描节点：射速快，适合拦截异常包")),
            (2.2, "tower1", lambda: self.demo_place(1, "防火墙伤害高，并能造成范围攻击")),
            (3.6, "tower2", lambda: self.demo_place(2, "隔离沙箱可减速，为其他节点争取时间")),
            (5.0, "wave", lambda: self.demo_start_wave("启动第一波：敌人按预设链路前往核心服务器")),
            (12.0, "tower3", lambda: self.demo_place(3, "补充扫描节点，形成交叉火力")),
            (17.0, "upgrade", lambda: self.demo_upgrade("消耗资源升级节点，提升伤害与范围")),
            (23.0, "scan", lambda: self.demo_scan("能量满后发动全网扫描，紧急压低敌方血量")),
            (29.0, "tower4", lambda: self.demo_place(4, "根据路线拐点继续调整防御布局")),
            (38.0, "upgrade2", lambda: self.demo_upgrade("节点最高可升到 3 级，并统计击杀与伤害")),
            (46.0, "summary", lambda: self.show_demo_callout("项目包含波次、三类敌人、技能、升级、计分与存档", 5.5)),
        ]
        for timestamp, key, action in scripted:
            if self.demo_elapsed >= timestamp and key not in self.demo_actions_done:
                self.demo_actions_done.add(key)
                action()

        # Continue showing new waves after the scripted introduction.
        if (
            self.demo_elapsed > 7
            and not self.wave_active
            and not self.enemies
            and self.wave_index < len(WAVES)
            and self.wave_cleared_timer <= 0
        ):
            self.start_wave()

        # Give the demo enough resources to display all mechanics without
        # changing the balancing of normal play.
        self.money = max(self.money, 180)

    def demo_place(self, index: int, callout: str) -> None:
        kind, pos = DEMO_TOWERS[index]
        if self.place_tower(kind, pos, free=True):
            self.show_demo_callout(callout)

    def demo_start_wave(self, callout: str) -> None:
        self.start_wave()
        self.show_demo_callout(callout)

    def demo_upgrade(self, callout: str) -> None:
        if self.towers:
            candidate = min(self.towers, key=lambda tower: tower.level)
            self.selected_tower = candidate
            self.upgrade_selected(free=True)
            self.show_demo_callout(callout)

    def demo_scan(self, callout: str) -> None:
        if self.enemies:
            self.activate_scan(free=True)
        self.show_demo_callout(callout)

    def show_demo_callout(self, value: str, duration: float = 3.8) -> None:
        self.demo_callout = value
        self.demo_callout_timer = duration

    def draw(self) -> None:
        self.screen.fill(COLORS["bg"])
        if self.state == "menu":
            self.draw_menu()
        else:
            self.draw_game()
            if self.state in ("won", "lost"):
                self.draw_result()
        if self.show_help:
            self.draw_help()

    def draw_menu(self) -> None:
        for x, y, radius in self.stars:
            pygame.draw.circle(self.screen, (29, 61, 91), (x, y), radius)
        # Decorative network arcs.
        layer = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        pygame.draw.circle(layer, (*COLORS["cyan"], 28), (640, 225), 165, 2)
        pygame.draw.circle(layer, (*COLORS["magenta"], 22), (640, 225), 205, 2)
        self.screen.blit(layer, (0, 0))
        for angle in range(0, 360, 45):
            radians = math.radians(angle)
            end = (640 + int(math.cos(radians) * 185), 225 + int(math.sin(radians) * 120))
            pygame.draw.line(self.screen, COLORS["grid"], (640, 225), end, 1)
            pygame.draw.circle(self.screen, COLORS["cyan" if angle % 90 == 0 else "magenta"], end, 5)
        pygame.draw.circle(self.screen, COLORS["panel_alt"], (640, 225), 68)
        pygame.draw.circle(self.screen, COLORS["cyan"], (640, 225), 68, 3)
        pygame.draw.rect(self.screen, COLORS["cyan"], (614, 220, 52, 42), 3, border_radius=6)
        pygame.draw.arc(self.screen, COLORS["cyan"], (620, 186, 40, 54), math.pi, math.tau, 3)

        text(self.screen, "校园网络防线", (640, 325), 54, COLORS["white"], True, "center")
        text(self.screen, "CAMPUS CYBER GUARD", (640, 371), 18, COLORS["cyan"], True, "center")
        text(self.screen, "部署 · 升级 · 防守核心服务器", (640, 397), 17, COLORS["muted"], False, "center")
        mouse = pygame.mouse.get_pos()
        for button in self.menu_buttons.values():
            button.draw(self.screen, mouse)
        text(self.screen, "最高得分  {:,}".format(self.high_score), (640, 640), 18, COLORS["amber"], True, "center")
        text(self.screen, "Python + Pygame  |  v1.0", (640, 675), 14, COLORS["muted"], False, "center")

    def draw_game(self) -> None:
        offset = (0, 0)
        if self.shake_timer > 0:
            offset = (random.randint(-4, 4), random.randint(-3, 3))
        map_surface = pygame.Surface((MAP_WIDTH, HEIGHT))
        self.draw_map(map_surface)
        for tower in self.towers:
            tower.draw(map_surface, tower is self.selected_tower)
        for enemy in self.enemies:
            enemy.draw(map_surface)
        for projectile in self.projectiles:
            projectile.draw(map_surface)
        for particle in self.particles:
            particle.draw(map_surface)
        for label in self.floating_texts:
            label.draw(map_surface)
        self.screen.blit(map_surface, offset)
        self.draw_panel()
        self.draw_top_hud()
        self.draw_selected_info()
        if self.demo_mode:
            self.draw_demo_overlay()
        if self.paused:
            layer = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            layer.fill((2, 6, 14, 180))
            self.screen.blit(layer, (0, 0))
            text(self.screen, "系统已暂停", (WIDTH // 2, HEIGHT // 2 - 10), 42, COLORS["white"], True, "center")
            text(self.screen, "按 P 继续", (WIDTH // 2, HEIGHT // 2 + 40), 18, COLORS["cyan"], False, "center")
        if self.scan_flash > 0:
            alpha = int(100 * self.scan_flash / 0.55)
            layer = pygame.Surface((MAP_WIDTH, HEIGHT), pygame.SRCALPHA)
            layer.fill((*COLORS["cyan"], alpha))
            self.screen.blit(layer, (0, 0))

    def draw_map(self, surface: pygame.Surface) -> None:
        surface.fill(COLORS["map"])
        for x in range(0, MAP_WIDTH, GRID_SIZE):
            pygame.draw.line(surface, COLORS["grid"], (x, 0), (x, HEIGHT), 1)
        for y in range(0, HEIGHT, GRID_SIZE):
            pygame.draw.line(surface, COLORS["grid"], (0, y), (MAP_WIDTH, y), 1)

        path_points = [(int(x), int(y)) for x, y in PATH_POINTS]
        pygame.draw.lines(surface, COLORS["path_edge"], False, path_points, PATH_WIDTH + 8)
        pygame.draw.lines(surface, COLORS["path"], False, path_points, PATH_WIDTH)
        for start, end in zip(path_points, path_points[1:]):
            sx, sy = start
            ex, ey = end
            length = max(1, int(math.dist(start, end)))
            for step in range(24, length, 46):
                ratio = step / length
                cx = int(sx + (ex - sx) * ratio)
                cy = int(sy + (ey - sy) * ratio)
                pygame.draw.circle(surface, (54, 112, 139), (cx, cy), 2)

        rounded_panel(surface, pygame.Rect(18, 58, 110, 36), COLORS["panel"], COLORS["cyan"], 8, 1)
        text(surface, "外网入口", (73, 76), 15, COLORS["cyan"], True, "center")
        rounded_panel(surface, pygame.Rect(842, 537, 104, 76), COLORS["panel"], COLORS["red"], 10, 2)
        text(surface, "核心", (894, 553), 14, COLORS["red"], True, "center")
        text(surface, "服务器", (894, 578), 16, COLORS["white"], True, "center")
        for index, point in enumerate(PATH_POINTS[1:-1], 1):
            pygame.draw.circle(surface, COLORS["path_edge"], (int(point[0]), int(point[1])), 7)
            text(surface, str(index), (int(point[0]), int(point[1])), 10, COLORS["black"], True, "center")

        if self.selected_build and not self.demo_mode:
            mouse = pygame.mouse.get_pos()
            if mouse[0] < MAP_WIDTH:
                snapped = self.snap_position(mouse)
                valid = self.is_valid_build(snapped)
                color = TOWER_TYPES[self.selected_build]["color"] if valid else COLORS["red"]
                layer = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
                pygame.draw.circle(layer, (*color, 25), snapped, int(TOWER_TYPES[self.selected_build]["range"]))
                pygame.draw.circle(layer, (*color, 110), snapped, 25)
                pygame.draw.circle(layer, (*color, 180), snapped, 25, 2)
                surface.blit(layer, (0, 0))

    def draw_top_hud(self) -> None:
        rounded_panel(self.screen, pygame.Rect(18, 14, 920, 44), (7, 16, 29), (38, 66, 87), 12, 1)
        items = [
            ("核心", "{}/{}".format(self.base_health, self.max_base_health), COLORS["green"] if self.base_health > 8 else COLORS["red"]),
            ("资源", str(self.money), COLORS["amber"]),
            ("能量", "{}%".format(int(self.energy)), COLORS["cyan"]),
            ("波次", "{}/{}".format(self.wave_index, len(WAVES)), COLORS["white"]),
            ("连击", "x{}".format(self.combo), COLORS["magenta"]),
            ("得分", "{:,}".format(self.score), COLORS["white"]),
        ]
        x = 38
        for label, value, color in items:
            text(self.screen, label, (x, 25), 13, COLORS["muted"])
            text(self.screen, value, (x + 46, 21), 20, color, True)
            x += 145

    def draw_panel(self) -> None:
        pygame.draw.rect(self.screen, COLORS["panel"], (MAP_WIDTH, 0, WIDTH - MAP_WIDTH, HEIGHT))
        pygame.draw.line(self.screen, (42, 71, 96), (MAP_WIDTH, 0), (MAP_WIDTH, HEIGHT), 2)
        text(self.screen, "防御控制台", (978, 24), 28, COLORS["white"], True)
        text(self.screen, "DEFENSE CONSOLE", (980, 58), 12, COLORS["cyan"], True)

        # Threat progress.
        rounded_panel(self.screen, pygame.Rect(978, 91, 284, 76), COLORS["panel_alt"], (45, 68, 90), 10, 1)
        text(self.screen, "当前威胁", (992, 103), 13, COLORS["muted"])
        threat = len(self.enemies) + len(self.spawn_queue)
        text(self.screen, "{} 个目标".format(threat), (1248, 101), 16, COLORS["red"] if threat else COLORS["green"], True, "topright")
        bar = pygame.Rect(992, 135, 256, 10)
        pygame.draw.rect(self.screen, (34, 45, 60), bar, border_radius=5)
        max_threat = max(1, 18 + self.wave_index * 2)
        fill = min(1.0, threat / max_threat)
        if fill:
            pygame.draw.rect(self.screen, COLORS["red"], (bar.x, bar.y, int(bar.width * fill), bar.height), border_radius=5)

        mouse = pygame.mouse.get_pos()
        for kind, button in self.tower_buttons.items():
            data = TOWER_TYPES[kind]
            enabled = self.money >= int(data["cost"]) or self.demo_mode
            button.draw(self.screen, mouse, enabled)
            if self.selected_build == kind:
                pygame.draw.rect(self.screen, data["color"], button.rect, 3, border_radius=10)
            pygame.draw.circle(self.screen, data["color"], (1005, button.rect.centery), 19, 3)
            text(self.screen, str(data["short"]), (1005, button.rect.centery), 14, data["color"], True, "center")
            text(self.screen, str(data["name"]), (1038, button.rect.y + 11), 18, COLORS["white"], True)
            text(self.screen, str(data["description"]), (1038, button.rect.y + 38), 13, COLORS["muted"])
            text(self.screen, "{} 资源".format(data["cost"]), (1248, button.rect.y + 10), 13, COLORS["amber"], True, "topright")

        text(self.screen, "战术操作", (978, 459), 15, COLORS["muted"], True)
        rounded_panel(self.screen, pygame.Rect(978, 484, 284, 46), COLORS["panel_alt"], (45, 68, 90), 10, 1)
        wave_text = "战斗中" if self.wave_active else ("全部完成" if self.wave_index >= len(WAVES) else "等待启动")
        text(self.screen, wave_text, (992, 496), 17, COLORS["red"] if self.wave_active else COLORS["green"], True)
        text(self.screen, "敌人 {}".format(len(self.enemies)), (1248, 497), 14, COLORS["muted"], False, "topright")

        can_wave = not self.wave_active and self.wave_index < len(WAVES)
        self.wave_button.draw(self.screen, mouse, can_wave and not self.demo_mode)
        self.skill_button.draw(self.screen, mouse, self.energy >= 60 and bool(self.enemies) and not self.demo_mode)

        text(self.screen, "P 暂停   H 帮助   ESC 返回", (1120, 692), 13, COLORS["muted"], False, "center")

    def draw_selected_info(self) -> None:
        if not self.selected_tower or self.state != "play":
            if self.message_timer > 0:
                rounded_panel(self.screen, pygame.Rect(24, 653, 590, 42), (7, 16, 29), (43, 70, 91), 10, 1)
                text(self.screen, self.message, (40, 664), 16, getattr(self, "message_color", COLORS["white"]), True)
            return
        tower = self.selected_tower
        rect = pygame.Rect(24, 626, 902, 72)
        rounded_panel(self.screen, rect, (7, 16, 29), tower.color, 12, 1)
        text(self.screen, "{}  Lv.{}".format(tower.data["name"], tower.level), (42, 639), 19, tower.color, True)
        stats = "伤害 {:.0f}   范围 {:.0f}   击杀 {}   累计伤害 {:.0f}".format(
            tower.damage, tower.attack_range, tower.kills, tower.total_damage
        )
        text(self.screen, stats, (42, 668), 14, COLORS["muted"])
        upgrade_rect = pygame.Rect(655, 641, 122, 42)
        sell_rect = pygame.Rect(790, 641, 122, 42)
        rounded_panel(self.screen, upgrade_rect, COLORS["panel_alt"], COLORS["green"], 8, 1)
        rounded_panel(self.screen, sell_rect, COLORS["panel_alt"], COLORS["amber"], 8, 1)
        upgrade_label = "已满级" if tower.level >= 3 else "升级 {}  [U]".format(tower.upgrade_cost)
        text(self.screen, upgrade_label, upgrade_rect.center, 14, COLORS["green"], True, "center")
        text(self.screen, "出售 {}  [X]".format(tower.sell_value), sell_rect.center, 14, COLORS["amber"], True, "center")

    def draw_demo_overlay(self) -> None:
        rounded_panel(self.screen, pygame.Rect(26, 74, 158, 34), (10, 20, 35), COLORS["magenta"], 17, 1)
        pygame.draw.circle(self.screen, COLORS["red"], (43, 91), 5)
        text(self.screen, "自动演示模式", (56, 82), 14, COLORS["white"], True)
        if self.demo_callout_timer > 0:
            rect = pygame.Rect(190, 76, 710, 58)
            rounded_panel(self.screen, rect, (8, 18, 32), COLORS["cyan"], 12, 2)
            text(self.screen, self.demo_callout, rect.center, 18, COLORS["white"], True, "center")

    def draw_result(self) -> None:
        layer = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        layer.fill((2, 7, 16, 205))
        self.screen.blit(layer, (0, 0))
        rect = pygame.Rect(330, 145, 620, 430)
        accent = COLORS["green"] if self.state == "won" else COLORS["red"]
        rounded_panel(self.screen, rect, COLORS["panel"], accent, 22, 3)
        title_value = "防御成功" if self.state == "won" else "核心失守"
        subtitle = "校园网络恢复正常运行" if self.state == "won" else "调整布局后再次尝试"
        text(self.screen, title_value, (640, 215), 48, accent, True, "center")
        text(self.screen, subtitle, (640, 262), 18, COLORS["muted"], False, "center")
        text(self.screen, "最终得分", (640, 322), 16, COLORS["muted"], False, "center")
        text(self.screen, "{:,}".format(self.score), (640, 365), 48, COLORS["white"], True, "center")
        text(self.screen, "清除 {}    漏网 {}    防御节点 {}".format(self.total_kills, self.total_leaks, len(self.towers)), (640, 430), 17, COLORS["white"], True, "center")
        text(self.screen, "ENTER 重新开始   ·   ESC 返回主页", (640, 520), 16, COLORS["cyan"], True, "center")

    def draw_help(self) -> None:
        layer = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        layer.fill((2, 7, 16, 225))
        self.screen.blit(layer, (0, 0))
        rect = pygame.Rect(190, 72, 900, 580)
        rounded_panel(self.screen, rect, COLORS["panel"], COLORS["cyan"], 20, 2)
        text(self.screen, "玩法说明", (240, 111), 34, COLORS["white"], True)
        text(self.screen, "目标：在恶意程序抵达核心服务器前将其清除", (240, 159), 18, COLORS["cyan"], True)

        columns = [
            ("1  扫描节点", "低费用、高射速，适合清除成群的异常包。", COLORS["cyan"]),
            ("2  防火墙", "单次伤害高，命中时会对附近目标造成范围伤害。", COLORS["amber"]),
            ("3  隔离沙箱", "命中后降低目标速度，可延长整条火力链输出时间。", COLORS["magenta"]),
        ]
        y = 214
        for heading, description, color in columns:
            pygame.draw.circle(self.screen, color, (259, y + 14), 10)
            text(self.screen, heading, (283, y), 20, color, True)
            text(self.screen, description, (283, y + 31), 15, COLORS["muted"])
            y += 82

        pygame.draw.line(self.screen, (48, 70, 91), (240, 469), (1040, 469), 1)
        shortcuts = [
            "鼠标左键：部署/选择节点",
            "U / X：升级或出售所选节点",
            "SPACE：启动下一波",
            "E：消耗 60 能量发动全网扫描",
            "P：暂停    H：帮助    ESC：取消/返回",
        ]
        for index, line in enumerate(shortcuts):
            x = 250 + (index % 2) * 410
            yy = 493 + (index // 2) * 43
            text(self.screen, line, (x, yy), 15, COLORS["white"] if index < 4 else COLORS["muted"], index < 4)
        text(self.screen, "点击任意位置关闭", (640, 623), 14, COLORS["cyan"], False, "center")
