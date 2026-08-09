"""Tests for GameStats: score, level, piece count tracking."""

from tetris.game.stats import GameStats
from tetris.settings import LINES_PER_LEVEL


def test_initial_stats():
    stats = GameStats()
    assert stats.score == 0
    assert stats.total_lines == 0
    assert stats.level == 0
    assert stats.piece_count == 0


def test_on_piece_locked_updates_score():
    stats = GameStats()
    stats.on_piece_locked(2)
    assert stats.score == 220  # 2*100 + 20 bonus
    assert stats.total_lines == 2


def test_level_progression():
    stats = GameStats()
    # Clear LINES_PER_LEVEL lines across multiple pieces
    for _ in range(LINES_PER_LEVEL):
        stats.on_piece_locked(1)
    assert stats.level == 1
    assert stats.total_lines == LINES_PER_LEVEL


def test_piece_count_increments():
    stats = GameStats()
    stats.on_piece_locked(0)
    stats.on_piece_locked(1)
    stats.on_piece_locked(0)
    assert stats.piece_count == 3