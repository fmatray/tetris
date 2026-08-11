"""Scoring rules — standard Tetris Guideline points, pure functions."""

from tetris.settings import LINE_CLEAR_POINTS


class ScoreEngine:
    """Standard Guideline scoring: line clears × level, combos, drop bonuses."""

    @staticmethod
    def line_clear_points(lines_cleared: int, level: int) -> int:
        """Base line-clear award: LINE_CLEAR_POINTS[lines] × (level + 1)."""
        return LINE_CLEAR_POINTS.get(lines_cleared, 0) * (level + 1)

    @staticmethod
    def combo_points(combo_count: int, level: int) -> int:
        """Combo bonus: 50 × combo_count × (level + 1). Zero if combo_count <= 0."""
        if combo_count <= 0:
            return 0
        return 50 * combo_count * (level + 1)

    @staticmethod
    def soft_drop_points(cells: int) -> int:
        """1 point per cell soft-dropped."""
        return cells

    @staticmethod
    def hard_drop_points(cells: int) -> int:
        """2 points per cell hard-dropped."""
        return 2 * cells