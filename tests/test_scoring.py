"""Tests for ScoreEngine scoring rules."""

from tetris.game.scoring import ScoreEngine


def test_score_0_lines():
    assert ScoreEngine.score_for(0) == 0


def test_score_1_line():
    assert ScoreEngine.score_for(1) == 100


def test_score_2_lines():
    assert ScoreEngine.score_for(2) == 220


def test_score_3_lines():
    assert ScoreEngine.score_for(3) == 350


def test_score_4_lines():
    assert ScoreEngine.score_for(4) == 500


def test_score_5_lines():
    """Bonus only applies to 1-4; 5 lines gets base only."""
    assert ScoreEngine.score_for(5) == 500