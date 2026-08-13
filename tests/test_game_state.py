"""Tests for GameState game-over transitions (normal drop, soft drop, hard drop)."""

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

pygame.init()
pygame.mixer.init()

from tetris.audio import AudioManager
from tetris.game.board import Board
from tetris.settings import BOARD_HEIGHT, BOARD_WIDTH
from tetris.states.game import GameState
from tetris.visuals.particles import ParticleSystem

GRAY = (128, 128, 128)


def _make_game():
    screen = pygame.Surface((640, 480))
    font = pygame.font.Font(None, 24)
    audio = AudioManager(sound_volume=0, music_volume=0)
    return GameState(screen, font, audio, handicap=0, sound_volume=0, music_volume=0)


def _fill_all_but_col0(board: Board) -> None:
    """Fill every cell in columns 1+ so no line clears (col 0 stays empty).

    Any piece whose blocks fall in columns 1+ can't be placed → game_over.
    """
    for y in range(BOARD_HEIGHT):
        for x in range(1, BOARD_WIDTH):
            board.grid[y][x] = GRAY


def test_game_over_via_hard_drop():
    """Hard drop that blocks the next spawn must transition to GameOverState.

    Regression: _hard_drop set game_over during handle_event, but update()
    early-returned on ``self.game_over`` before reaching the transition code,
    so the game froze instead of showing the game-over screen.
    """
    game = _make_game()
    particles = ParticleSystem()
    _fill_all_but_col0(game.board)

    # Current piece spawns at x=3; its blocks are in columns 3+, which are full.
    # hard_drop can't move it down. lock_tetromino overwrites those cells.
    # No line clears (col 0 still empty). Next piece spawns at x=3 → collides.
    game._hard_drop()

    assert game.game_over, "Hard drop should have triggered game_over"

    result = game.update(16, particles)
    assert result is not None, "update() must return a transition when game_over is True"
    assert type(result).__name__ == "GameOverState"


def test_game_over_via_normal_drop():
    """Normal gravity drop that blocks the next spawn must transition to GameOverState."""
    game = _make_game()
    particles = ParticleSystem()
    _fill_all_but_col0(game.board)

    # _tick tries to move the piece down; if it can't, it locks and spawns next.
    # Same outcome as hard drop: piece locks, next piece collides → game_over.
    game._tick(particles)

    assert game.game_over, "Normal drop should have triggered game_over"

    result = game.update(16, particles)
    assert result is not None, "update() must return a transition when game_over is True"
    assert type(result).__name__ == "GameOverState"