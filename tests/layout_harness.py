"""Layout regression harness — invariant assertions on text blits.

Catches the d33393f bug class (FR/ES HUD text overflowing the screen or
overlapping other text) without pixel goldens. Deterministic, headless.

Usage: draw a state to a ``RecordingScreen`` with a ``RecordingFont``, then
assert every text blit lands in bounds and text rects do not overlap.
"""

from __future__ import annotations

import pygame

SCREEN_W = 1500
SCREEN_H = 800
# Two texts whose rects overlap by less than this (px) are tolerated —
# same-position re-renders (HUD refresh) overlap by 0..epsilon.
OVERLAP_TOLERANCE = 1

# id(rendered surface) -> (text, width, height). Surfaces carry no __dict__,
# so metrics live here. Safe while the surface is alive (ids are unique
# among live objects, and only live surfaces can be blitted).
# ponytail: id reuse by a dead surface's replacement could alias a record;
# swap for surface subclassing if that ever bites.
_RENDERED: dict[int, tuple[str, int, int]] = {}


class RecordingFont(pygame.font.Font):
    """Font subclass whose ``render`` logs text metrics to the registry.

    ``pygame.font.Font`` is a C type: monkeypatching ``render`` fails, but
    subclassing works.
    """

    def render(self, text: str | bytes | None, antialias: bool, color, bgcolor=None, wraplength=0):
        surface = super().render(text, antialias, color, bgcolor, wraplength)
        _RENDERED[id(surface)] = (str(text), surface.get_width(), surface.get_height())
        return surface


class RecordingScreen(pygame.Surface):
    """``pygame.Surface`` subclass that records text blits.

    A state under test draws to this screen exactly as it would to the
    display; every blit passes through to the real surface, and blits of
    font-rendered surfaces (tagged by ``RecordingFont``) are logged with
    their position and size.
    """

    def __init__(self, size=(SCREEN_W, SCREEN_H), flags=0, depth=32) -> None:
        super().__init__(size, flags, depth)
        # Text blit records: (text, x, y, w, h)
        self.text_blits: list[tuple[str, int, int, int, int]] = []

    def blit(self, source, dest=(0, 0), area=None, special_flags=0):
        metrics = _RENDERED.get(id(source))
        if metrics is not None:
            x, y = RecordingScreen._dest_xy(dest)
            text, w, h = metrics
            self.text_blits.append((text, x, y, w, h))
            _RENDERED.pop(id(source), None)  # consume record: one blit each
        return super().blit(source, dest, area, special_flags)

    @staticmethod
    def _dest_xy(dest) -> tuple[int, int]:
        if isinstance(dest, pygame.Rect):
            return dest.x, dest.y
        return int(dest[0]), int(dest[1])


def assert_layout_in_bounds(screen: RecordingScreen) -> None:
    """Every text blit must sit fully inside the screen."""
    w, h = screen.get_size()
    problems = []
    for text, x, y, tw, th in screen.text_blits:
        if x < 0 or y < 0 or x + tw > w or y + th > h:
            problems.append(f"text {text!r} at ({x},{y}) size ({tw}x{th}) exceeds screen {w}x{h}")
    assert not problems, "Out-of-bounds text blits:\n" + "\n".join(problems)


def assert_no_text_overlap(screen: RecordingScreen) -> None:
    """No two text blits' rects may overlap (beyond re-render tolerance).

    Identical text at the same origin is a HUD refresh, not a collision.
    """
    problems = []
    blits = screen.text_blits
    for i in range(len(blits)):
        for j in range(i + 1, len(blits)):
            t1, x1, y1, w1, h1 = blits[i]
            t2, x2, y2, w2, h2 = blits[j]
            if t1 == t2 and x1 == x2 and y1 == y2:
                continue
            ox = min(x1 + w1, x2 + w2) - max(x1, x2)
            oy = min(y1 + h1, y2 + h2) - max(y1, y2)
            if ox > OVERLAP_TOLERANCE and oy > OVERLAP_TOLERANCE:
                problems.append(
                    f"{t1!r} at ({x1},{y1},{w1}x{h1}) overlaps {t2!r} at ({x2},{y2},{w2}x{h2}) by ({ox}x{oy})"
                )
    assert not problems, "Overlapping text blits:\n" + "\n".join(problems)
