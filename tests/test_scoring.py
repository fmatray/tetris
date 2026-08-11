"""Tests for ScoreEngine scoring rules (standard Guideline)."""

from tetris.game.scoring import ScoreEngine


def test_line_clear_0_lines():
    assert ScoreEngine.line_clear_points(0, 0) == 0


def test_line_clear_single_level0():
    assert ScoreEngine.line_clear_points(1, 0) == 100


def test_line_clear_double_level0():
    assert ScoreEngine.line_clear_points(2, 0) == 300


def test_line_clear_triple_level0():
    assert ScoreEngine.line_clear_points(3, 0) == 500


def test_line_clear_tetris_level0():
    assert ScoreEngine.line_clear_points(4, 0) == 800


def test_line_clear_single_level2():
    assert ScoreEngine.line_clear_points(1, 2) == 300  # 100 × 3


def test_line_clear_tetris_level4():
    assert ScoreEngine.line_clear_points(4, 4) == 4000  # 800 × 5


def test_combo_0_or_negative():
    assert ScoreEngine.combo_points(0, 0) == 0
    assert ScoreEngine.combo_points(-1, 0) == 0


def test_combo_1_level0():
    assert ScoreEngine.combo_points(1, 0) == 50  # 50 × 1 × 1


def test_combo_3_level2():
    assert ScoreEngine.combo_points(3, 2) == 450  # 50 × 3 × 3


def test_soft_drop():
    assert ScoreEngine.soft_drop_points(5) == 5


def test_hard_drop():
    assert ScoreEngine.hard_drop_points(5) == 10