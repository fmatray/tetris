"""Tests for GameStats: score, level, combo, piece count tracking."""

from tetris.game.stats import ClearCounts, GameStats
from tetris.settings import LINES_PER_LEVEL


def test_initial_stats():
    stats = GameStats()
    assert stats.score == 0
    assert stats.total_lines == 0
    assert stats.level == 0
    assert stats.piece_count == 0
    assert stats.combo == -1


def test_on_piece_locked_updates_score():
    stats = GameStats()
    stats.on_piece_locked(2)
    assert stats.score == 300  # 300 × 1 (level 0)
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


def test_combo_resets_on_no_clear():
    stats = GameStats()
    stats.on_piece_locked(1)  # combo 0, score 100
    stats.on_piece_locked(1)  # combo 1, score 100 + 100 + 50 = 250
    stats.on_piece_locked(0)  # combo resets to -1, no score
    assert stats.combo == -1
    assert stats.score == 250


def test_combo_bonus_accumulates():
    stats = GameStats()
    stats.on_piece_locked(1)  # combo 0 → 100
    stats.on_piece_locked(1)  # combo 1 → 100 + 50 = 150
    stats.on_piece_locked(1)  # combo 2 → 100 + 100 = 200
    assert stats.score == 100 + 150 + 200


def test_soft_drop_score():
    stats = GameStats()
    stats.add_soft_drop(10)
    assert stats.score == 10


def test_hard_drop_score():
    stats = GameStats()
    stats.add_hard_drop(10)
    assert stats.score == 20


# --- ClearCounts ---


def test_clear_counts_initial():
    cc = ClearCounts()
    assert cc.single == 0
    assert cc.double == 0
    assert cc.triple == 0
    assert cc.tetris == 0
    assert cc.total == 0


def test_clear_counts_add_single():
    cc = ClearCounts()
    cc.add(1)
    assert cc.single == 1
    assert cc.total == 1


def test_clear_counts_add_double():
    cc = ClearCounts()
    cc.add(2)
    assert cc.double == 1


def test_clear_counts_add_triple():
    cc = ClearCounts()
    cc.add(3)
    assert cc.triple == 1


def test_clear_counts_add_tetris():
    cc = ClearCounts()
    cc.add(4)
    assert cc.tetris == 1


def test_clear_counts_add_zero_noop():
    cc = ClearCounts()
    cc.add(0)
    assert cc.total == 0


def test_clear_counts_accumulate():
    cc = ClearCounts()
    cc.add(1)
    cc.add(4)
    cc.add(1)
    cc.add(2)
    assert cc.single == 2
    assert cc.double == 1
    assert cc.tetris == 1
    assert cc.triple == 0
    assert cc.total == 4


def test_stats_clear_counts_on_lock():
    stats = GameStats()
    stats.on_piece_locked(1)
    stats.on_piece_locked(4)
    stats.on_piece_locked(2)
    stats.on_piece_locked(0)
    stats.on_piece_locked(3)
    assert stats.clear_counts.single == 1
    assert stats.clear_counts.double == 1
    assert stats.clear_counts.triple == 1
    assert stats.clear_counts.tetris == 1


def test_stats_clear_counts_per_instance():
    """Each GameStats gets its own ClearCounts (default_factory)."""
    a = GameStats()
    b = GameStats()
    a.on_piece_locked(1)
    assert b.clear_counts.single == 0
