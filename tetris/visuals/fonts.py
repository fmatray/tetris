"""Centralized font management and text layout constants.

One font family (Arial), two sizes:
- Large 32px **bold** — page titles only.
- Small 24px normal — all other text (body, HUD, tables, instructions).

Layout constants ensure consistent vertical positioning across every screen:
- ``TITLE_Y``      — y of the page title (large font).
- ``CONTENT_Y``    — y where content begins below the title.
- ``LINE_HEIGHT_SMALL``  — row spacing when using the small font.
- ``INSTRUCTIONS_Y``     — y of the bottom navigation hint.

Fonts are created lazily (pygame must be initialised first) and cached.
"""

from __future__ import annotations

import pygame

from tetris.settings import SCREEN_HEIGHT

_FONT_FAMILY = "Arial"
_LARGE_SIZE = 32
_SMALL_SIZE = 24

# --- Layout constants (pixels) ------------------------------------------
TITLE_Y = 50
CONTENT_Y = 120

LINE_HEIGHT_SMALL = 32
INSTRUCTIONS_Y = SCREEN_HEIGHT - 50

_large_font: pygame.font.Font | None = None
_small_font: pygame.font.Font | None = None


def get_large_font() -> pygame.font.Font:
    """Return the cached large bold font (titles only)."""
    global _large_font
    if _large_font is None:
        _large_font = pygame.font.SysFont(_FONT_FAMILY, _LARGE_SIZE, bold=True)
    return _large_font


def get_small_font() -> pygame.font.Font:
    """Return the cached small normal font (all non-title text)."""
    global _small_font
    if _small_font is None:
        _small_font = pygame.font.SysFont(_FONT_FAMILY, _SMALL_SIZE, bold=False)
    return _small_font
