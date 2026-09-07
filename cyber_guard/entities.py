"""Game entities: enemies, towers, projectiles and visual particles."""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple

import pygame

from .config import COLORS, ENEMY_TYPES, PATH_POINTS, TOWER_TYPES
from .ui import font, text

Vec2 = pygame.math.Vector2


def distance_point_to_segment(point: Vec2, start: Vec2, end: Vec2) -> float:
    segment = end - start
    length_squared = segment.length_squared()
    if length_squared == 0:
        return point.distance_to(start)
    t = max(0.0, min(1.0, (point - start).dot(segment) / length_squared))
    return point.distance_to(start + segment * t)


class Enemy:
    """An attacker that follows the fixed campus-network route."""

    next_id = 1

    def __init__(self, kind: str, wave_number: int) -> None:
        data = ENEMY_TYPES[kind]
        self.id = Enemy.next_id
        Enemy.next_id += 1
        self.kind = kind
        self.name = str(data["name"])
        self.pos = Vec2(PATH_POINTS[0])
        self.path_index = 0
        scale = 1.0 + (wave_number - 1) * 0.13
        self.max_hp = float(data["hp"]) * scale
        self.hp = self.max_hp
        self.base_speed = float(data["speed"]) * min(1.20, 1.0 + (wave_number - 1) * 0.022)
        self.reward = int(float(data["reward"]) * (1.0 + (wave_number - 1) * 0.035))
        self.base_damage = int(data["damage"])
        self.radius = int(data["radius"])
        self.color = data["color"]
        self.slow_factor = 1.0
        self.slow_timer = 0.0
        self.flash_timer = 0.0
        self.dead = False
        self.escaped = False
        self.distance_travelled = 0.0

    @property
    def progress(self) -> float:
        return self.path_index * 10000.0 + self.distance_travelled

    def update(self, dt: float) -> None:
        if self.dead or self.escaped:
            return
        self.flash_timer = max(0.0, self.flash_timer - dt)
        if self.slow_timer > 0:
            self.slow_timer -= dt
        else:
            self.slow_factor = 1.0

        remaining = self.base_speed * self.slow_factor * dt
        while remaining > 0 and not self.escaped:
            if self.path_index >= len(PATH_POINTS) - 1:
                self.escaped = True
                return
            target = Vec2(PATH_POINTS[self.path_index + 1])
            gap = target - self.pos
            distance = gap.length()
            if distance <= remaining:
                self.pos = target
                remaining -= distance
                self.distance_travelled += distance
                self.path_index += 1
                if self.path_index >= len(PATH_POINTS) - 1:
                    self.escaped = True
            else:
                self.pos += gap.normalize() * remaining
                self.distance_travelled += remaining
                remaining = 0

    def take_damage(self, amount: float) -> bool:
        if self.dead:
            return False
        self.hp -= amount
        self.flash_timer = 0.10
        if self.hp <= 0:
            self.hp = 0
            self.dead = True
            return True
        return False

    def apply_slow(self, factor: float, duration: float) -> None:
        self.slow_factor = min(self.slow_factor, factor)
        self.slow_timer = max(self.slow_timer, duration)

    def draw(self, surface: pygame.Surface) -> None:
        x, y = int(self.pos.x), int(self.pos.y)
        color = COLORS["white"] if self.flash_timer > 0 else self.color
        shadow = pygame.Surface((self.radius * 4, self.radius * 4), pygame.SRCALPHA)
        pygame.draw.circle(shadow, (*self.color, 38), (self.radius * 2, self.radius * 2), self.radius + 8)
        surface.blit(shadow, (x - self.radius * 2, y - self.radius * 2))

        if self.kind == "packet":
            points = [(x, y - self.radius), (x + self.radius, y), (x, y + self.radius), (x - self.radius, y)]
            pygame.draw.polygon(surface, color, points)
            pygame.draw.polygon(surface, COLORS["black"], points, 2)
        elif self.kind == "bot":
            rect = pygame.Rect(x - self.radius, y - self.radius, self.radius * 2, self.radius * 2)
            pygame.draw.rect(surface, color, rect, border_radius=5)
            pygame.draw.line(surface, COLORS["black"], (x - 6, y), (x + 6, y), 2)
            pygame.draw.circle(surface, COLORS["black"], (x - 6, y - 5), 2)
            pygame.draw.circle(surface, COLORS["black"], (x + 6, y - 5), 2)
        elif self.kind == "worm":
            for index in range(3):
                pygame.draw.circle(surface, color, (x - index * 8, y + index * 3), self.radius - index * 3)
            pygame.draw.circle(surface, COLORS["black"], (x + 5, y - 5), 3)
        else:
            pygame.draw.circle(surface, color, (x, y), self.radius)
            pygame.draw.circle(surface, COLORS["black"], (x, y), self.radius - 8, 3)
            pygame.draw.line(surface, COLORS["white"], (x - 10, y), (x + 10, y), 3)
            pygame.draw.line(surface, COLORS["white"], (x, y - 10), (x, y + 10), 3)

        if self.slow_timer > 0:
            pygame.draw.circle(surface, COLORS["magenta"], (x, y), self.radius + 5, 2)

        bar_width = self.radius * 2 + 10
        bar_rect = pygame.Rect(x - bar_width // 2, y - self.radius - 12, bar_width, 5)
        pygame.draw.rect(surface, (33, 43, 56), bar_rect, border_radius=3)
        fill_width = int(bar_rect.width * max(0.0, self.hp / self.max_hp))
        if fill_width:
            pygame.draw.rect(surface, COLORS["green"], (bar_rect.x, bar_rect.y, fill_width, 5), border_radius=3)


class Tower:
    """A placeable defense node with upgradeable combat statistics."""

    next_id = 1

    def __init__(self, kind: str, pos: Tuple[int, int]) -> None:
        data = TOWER_TYPES[kind]
        self.id = Tower.next_id
        Tower.next_id += 1
        self.kind = kind
        self.pos = Vec2(pos)
        self.level = 1
        self.cooldown = random.random() * 0.25
        self.angle = 0.0
        self.target: Optional[Enemy] = None
        self.kills = 0
        self.shots = 0
        self.total_damage = 0.0
        self.pulse = 0.0
        self.color = data["color"]

    @property
    def data(self):
        return TOWER_TYPES[self.kind]

    @property
    def attack_range(self) -> float:
        return float(self.data["range"]) * (1.0 + (self.level - 1) * 0.09)

    @property
    def damage(self) -> float:
        return float(self.data["damage"]) * (1.0 + (self.level - 1) * 0.42)

    @property
    def fire_rate(self) -> float:
        return float(self.data["fire_rate"]) * (0.88 ** (self.level - 1))

    @property
    def upgrade_cost(self) -> int:
        return int(float(self.data["cost"]) * (0.65 + self.level * 0.25))

    @property
    def sell_value(self) -> int:
        invested = float(self.data["cost"])
        for level in range(1, self.level):
            invested += float(self.data["cost"]) * (0.65 + level * 0.25)
        return int(invested * 0.67)

    def choose_target(self, enemies: Sequence[Enemy]) -> Optional[Enemy]:
        candidates = [
            enemy
            for enemy in enemies
            if not enemy.dead and not enemy.escaped and self.pos.distance_to(enemy.pos) <= self.attack_range
        ]
        return max(candidates, key=lambda item: item.progress, default=None)

    def update(self, dt: float, enemies: Sequence[Enemy], projectiles: List["Projectile"]) -> None:
        self.cooldown = max(0.0, self.cooldown - dt)
        self.pulse = max(0.0, self.pulse - dt)
        self.target = self.choose_target(enemies)
        if self.target:
            direction = self.target.pos - self.pos
            self.angle = math.atan2(direction.y, direction.x)
            if self.cooldown <= 0:
                projectiles.append(Projectile(self, self.target))
                self.cooldown = self.fire_rate
                self.pulse = 0.14
                self.shots += 1

    def upgrade(self) -> None:
        if self.level < 3:
            self.level += 1
            self.pulse = 0.6

    def draw(self, surface: pygame.Surface, selected: bool = False) -> None:
        x, y = int(self.pos.x), int(self.pos.y)
        if selected:
            layer = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
            pygame.draw.circle(layer, (*self.color, 25), (x, y), int(self.attack_range))
            pygame.draw.circle(layer, (*self.color, 90), (x, y), int(self.attack_range), 2)
            surface.blit(layer, (0, 0))

        base_radius = 23 + (3 if self.pulse > 0 else 0)
        pygame.draw.circle(surface, (9, 18, 30), (x + 3, y + 5), base_radius + 3)
        pygame.draw.circle(surface, (25, 45, 65), (x, y), base_radius)
        pygame.draw.circle(surface, self.color, (x, y), base_radius, 3)

        barrel = Vec2(math.cos(self.angle), math.sin(self.angle)) * 23
        pygame.draw.line(surface, self.color, (x, y), (x + int(barrel.x), y + int(barrel.y)), 7)
        pygame.draw.circle(surface, COLORS["white"], (x, y), 7)
        text(surface, str(self.data["short"]), (x, y + 1), 12, COLORS["black"], True, "center")

        for index in range(self.level):
            pygame.draw.circle(surface, COLORS["green"], (x - 9 + index * 9, y + 31), 3)


class Projectile:
    def __init__(self, tower: Tower, target: Enemy) -> None:
        self.tower = tower
        self.pos = tower.pos.copy()
        self.target = target
        self.speed = float(tower.data["projectile_speed"])
        self.damage = tower.damage
        self.color = tower.color
        self.alive = True
        self.trail: List[Vec2] = []

    def update(self, dt: float, enemies: Sequence[Enemy]) -> List[Enemy]:
        if not self.alive:
            return []
        if self.target.dead or self.target.escaped:
            self.alive = False
            return []
        gap = self.target.pos - self.pos
        distance = gap.length()
        self.trail.append(self.pos.copy())
        self.trail = self.trail[-5:]
        if distance <= self.speed * dt + self.target.radius:
            self.alive = False
            victims = [self.target]
            if self.tower.kind == "firewall":
                splash = float(self.tower.data.get("splash", 0))
                victims = [enemy for enemy in enemies if not enemy.dead and enemy.pos.distance_to(self.target.pos) <= splash]
            for enemy in victims:
                enemy.take_damage(self.damage)
                self.tower.total_damage += self.damage
                if self.tower.kind == "quarantine":
                    enemy.apply_slow(
                        float(self.tower.data["slow_factor"]),
                        float(self.tower.data["slow_duration"]),
                    )
            return victims
        if distance:
            self.pos += gap.normalize() * self.speed * dt
        return []

    def draw(self, surface: pygame.Surface) -> None:
        for index, point in enumerate(self.trail):
            alpha = int(30 + 25 * index)
            layer = pygame.Surface((14, 14), pygame.SRCALPHA)
            pygame.draw.circle(layer, (*self.color, alpha), (7, 7), max(1, index + 1))
            surface.blit(layer, (int(point.x) - 7, int(point.y) - 7))
        pygame.draw.circle(surface, self.color, (int(self.pos.x), int(self.pos.y)), 5)
        pygame.draw.circle(surface, COLORS["white"], (int(self.pos.x), int(self.pos.y)), 2)


@dataclass
class Particle:
    pos: Vec2
    velocity: Vec2
    color: Tuple[int, int, int]
    life: float = 0.65
    max_life: float = 0.65
    radius: float = 5.0

    def update(self, dt: float) -> None:
        self.life -= dt
        self.pos += self.velocity * dt
        self.velocity *= 0.94

    def draw(self, surface: pygame.Surface) -> None:
        if self.life <= 0:
            return
        alpha = max(0, min(255, int(255 * self.life / self.max_life)))
        size = max(1, int(self.radius * self.life / self.max_life))
        layer = pygame.Surface((size * 4, size * 4), pygame.SRCALPHA)
        pygame.draw.circle(layer, (*self.color, alpha), (size * 2, size * 2), size)
        surface.blit(layer, (int(self.pos.x) - size * 2, int(self.pos.y) - size * 2))


@dataclass
class FloatingText:
    value: str
    pos: Vec2
    color: Tuple[int, int, int]
    life: float = 0.9

    def update(self, dt: float) -> None:
        self.life -= dt
        self.pos.y -= 28 * dt

    def draw(self, surface: pygame.Surface) -> None:
        if self.life <= 0:
            return
        image = font(16, True).render(self.value, True, self.color)
        image.set_alpha(max(0, min(255, int(255 * self.life / 0.9))))
        surface.blit(image, image.get_rect(center=(int(self.pos.x), int(self.pos.y))))


def burst(pos: Vec2, color: Tuple[int, int, int], count: int = 10) -> List[Particle]:
    particles = []
    for _ in range(count):
        angle = random.random() * math.tau
        speed = random.uniform(35, 120)
        particles.append(
            Particle(pos.copy(), Vec2(math.cos(angle), math.sin(angle)) * speed, color, radius=random.uniform(3, 7))
        )
    return particles
