"""Game constants and balancing data.

All content assets are drawn by Pygame. Keeping the data here makes it easy to
adjust difficulty without touching the game loop.
"""

from __future__ import annotations

from pathlib import Path

WIDTH = 1280
HEIGHT = 720
MAP_WIDTH = 960
PANEL_WIDTH = WIDTH - MAP_WIDTH
FPS = 60
TITLE = "校园网络防线 | Campus Cyber Guard"

ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data"
SAVE_FILE = DATA_DIR / "save_data.json"

# The route taken by hostile packets. Segments are intentionally axis-aligned
# so collision and drawing stay readable for beginners.
PATH_POINTS = [
    (-40, 112),
    (165, 112),
    (165, 280),
    (385, 280),
    (385, 92),
    (620, 92),
    (620, 365),
    (830, 365),
    (830, 575),
    (1000, 575),
]
PATH_WIDTH = 58
GRID_SIZE = 48

# Palette: deep navy canvas with cyan, amber and magenta accents.
COLORS = {
    "bg": (7, 15, 31),
    "map": (10, 24, 43),
    "panel": (12, 20, 36),
    "panel_alt": (18, 31, 52),
    "grid": (23, 48, 70),
    "path": (28, 56, 78),
    "path_edge": (46, 99, 125),
    "cyan": (55, 225, 255),
    "blue": (70, 132, 255),
    "green": (55, 229, 146),
    "amber": (255, 191, 71),
    "red": (255, 89, 112),
    "magenta": (229, 91, 255),
    "white": (235, 244, 255),
    "muted": (137, 158, 184),
    "black": (3, 8, 18),
}

TOWER_TYPES = {
    "scanner": {
        "name": "扫描节点",
        "short": "S",
        "description": "高速识别普通数据包",
        "cost": 90,
        "range": 155,
        "damage": 11,
        "fire_rate": 0.34,
        "projectile_speed": 510,
        "color": COLORS["cyan"],
    },
    "firewall": {
        "name": "防火墙",
        "short": "F",
        "description": "重击并造成小范围伤害",
        "cost": 135,
        "range": 132,
        "damage": 35,
        "fire_rate": 0.86,
        "projectile_speed": 390,
        "splash": 42,
        "color": COLORS["amber"],
    },
    "quarantine": {
        "name": "隔离沙箱",
        "short": "Q",
        "description": "降低恶意程序移动速度",
        "cost": 120,
        "range": 148,
        "damage": 8,
        "fire_rate": 0.72,
        "projectile_speed": 430,
        "slow_factor": 0.50,
        "slow_duration": 1.8,
        "color": COLORS["magenta"],
    },
}

ENEMY_TYPES = {
    "packet": {
        "name": "异常包",
        "hp": 62,
        "speed": 77,
        "reward": 17,
        "damage": 1,
        "radius": 13,
        "color": (95, 210, 255),
    },
    "bot": {
        "name": "僵尸进程",
        "hp": 138,
        "speed": 54,
        "reward": 26,
        "damage": 2,
        "radius": 17,
        "color": (255, 131, 87),
    },
    "worm": {
        "name": "蠕虫病毒",
        "hp": 280,
        "speed": 39,
        "reward": 42,
        "damage": 3,
        "radius": 20,
        "color": (230, 90, 255),
    },
    "boss": {
        "name": "勒索核心",
        "hp": 1050,
        "speed": 28,
        "reward": 180,
        "damage": 8,
        "radius": 28,
        "color": (255, 74, 103),
    },
}

# Each tuple is (enemy kind, count, seconds between spawns).
WAVES = [
    [("packet", 7, 0.78)],
    [("packet", 9, 0.62), ("bot", 2, 1.00)],
    [("packet", 7, 0.54), ("bot", 5, 0.78)],
    [("bot", 7, 0.67), ("worm", 2, 1.10)],
    [("packet", 12, 0.38), ("worm", 4, 0.85)],
    [("bot", 10, 0.48), ("worm", 5, 0.72)],
    [("packet", 10, 0.32), ("bot", 8, 0.48), ("worm", 5, 0.68)],
    [("packet", 8, 0.28), ("worm", 5, 0.58), ("boss", 1, 0.10)],
]

DEMO_TOWERS = [
    ("scanner", (278, 176)),
    ("firewall", (490, 188)),
    ("quarantine", (510, 445)),
    ("scanner", (725, 468)),
    ("firewall", (715, 260)),
]
