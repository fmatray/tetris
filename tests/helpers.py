"""Shared test helpers: screen, font, audio, GameConfig, board fill.

Import from test modules as ``from tests.helpers import ...``.
"""

from __future__ import annotations

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

pygame.init()
pygame.mixer.init()

from tetris.audio import AudioManager
from tetris.game.board import Board
from tetris.states.game import GameConfig


def make_screen() -> pygame.Surface:
    return pygame.Surface((640, 480))


def make_font() -> pygame.font.Font:
    return pygame.font.Font(None, 24)


def make_audio() -> AudioManager:
    return AudioManager(sound_volume=0, music_volume=0)


def make_game_config(preview_count: int = 3, **kwargs) -> GameConfig:
    """Standard GameConfig for tests; override any field via kwargs."""
    return GameConfig(
        handicap=0,
        sound_volume=0,
        music_volume=0,
        music_song="korobeiniki",
        debug=False,
        ghost_piece=True,
        preview_count=preview_count,
        speed_mode="normal",
        **kwargs,
    )


def fill_capped_columns(board: Board, cols=(0, 1, 2), rows: int = 22, clear_bottom: int = 2) -> None:
    """Fill columns solid, then clear bottom cells to create holes."""
    g = board.grid
    for y in range(rows):
        for c in cols:
            g[y][c] = (255, 0, 0)
    for c in cols[:clear_bottom]:
        g[rows - 1][c] = None
