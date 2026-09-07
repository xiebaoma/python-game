"""Small reusable Pygame UI helpers."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Dict, Iterable, Optional, Sequence, Tuple

import pygame

from .config import COLORS


def _font_candidates() -> Iterable[Path]:
    return (
        Path("/System/Library/Fonts/PingFang.ttc"),
        Path("/System/Library/Fonts/STHeiti Light.ttc"),
        Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
    )


@lru_cache(maxsize=32)
def font(size: int, bold: bool = False) -> pygame.font.Font:
    chosen: Optional[str] = None
    for path in _font_candidates():
        if path.exists():
            chosen = str(path)
            break
    result = pygame.font.Font(chosen, size)
    result.set_bold(bold)
    return result


def text(
    surface: pygame.Surface,
    value: str,
    pos: Tuple[int, int],
    size: int = 20,
    color: Tuple[int, int, int] = COLORS["white"],
    bold: bool = False,
    anchor: str = "topleft",
) -> pygame.Rect:
    image = font(size, bold).render(value, True, color)
    rect = image.get_rect()
    setattr(rect, anchor, pos)
    surface.blit(image, rect)
    return rect


def rounded_panel(
    surface: pygame.Surface,
    rect: pygame.Rect,
    fill: Tuple[int, int, int],
    border: Optional[Tuple[int, int, int]] = None,
    radius: int = 14,
    width: int = 1,
) -> None:
    pygame.draw.rect(surface, fill, rect, border_radius=radius)
    if border:
        pygame.draw.rect(surface, border, rect, width=width, border_radius=radius)


def glow_circle(
    surface: pygame.Surface,
    center: Tuple[int, int],
    radius: int,
    color: Tuple[int, int, int],
    core: int = 5,
) -> None:
    layer = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
    for extra, alpha in ((16, 18), (9, 30), (4, 50)):
        pygame.draw.circle(layer, (*color, alpha), center, radius + extra)
    surface.blit(layer, (0, 0))
    pygame.draw.circle(surface, color, center, radius)
    pygame.draw.circle(surface, COLORS["white"], center, max(1, core))


class Button:
    def __init__(
        self,
        rect: Sequence[int],
        label: str,
        accent: Tuple[int, int, int] = COLORS["cyan"],
        hotkey: str = "",
    ) -> None:
        self.rect = pygame.Rect(rect)
        self.label = label
        self.accent = accent
        self.hotkey = hotkey

    def draw(self, surface: pygame.Surface, mouse_pos: Tuple[int, int], enabled: bool = True) -> None:
        hover = enabled and self.rect.collidepoint(mouse_pos)
        fill = COLORS["panel_alt"] if enabled else (24, 31, 43)
        border = self.accent if hover else (54, 75, 96)
        rounded_panel(surface, self.rect, fill, border, 10, 2 if hover else 1)
        label_color = COLORS["white"] if enabled else (92, 103, 118)
        text(surface, self.label, self.rect.center, 18, label_color, True, "center")
        if self.hotkey:
            text(surface, self.hotkey, (self.rect.right - 10, self.rect.top + 7), 12, border, True, "topright")

    def hit(self, pos: Tuple[int, int], enabled: bool = True) -> bool:
        return enabled and self.rect.collidepoint(pos)


def wrap_lines(value: str, max_chars: int) -> Sequence[str]:
    """Simple CJK-friendly wrapping used by overlay cards."""
    lines = []
    current = ""
    for char in value:
        current += char
        if len(current) >= max_chars or char == "\n":
            lines.append(current.rstrip("\n"))
            current = ""
    if current:
        lines.append(current)
    return lines
