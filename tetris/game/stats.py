"""Mutable running game statistics (score, lines, level)."""

from tetris.settings import LINES_PER_LEVEL
from tetris.game.scoring import ScoreEngine


class GameStats:
    """Tracks score, total lines cleared, and current level.

    Level advances every ``LINES_PER_LEVEL`` lines. Score is updated
    via :class:`ScoreEngine` so the bonus table stays encapsulated.
    """

    def __init__(self) -> None:
        self.score = 0
        self.total_lines = 0
        self.level = 0

    def add_lines(self, lines_cleared: int) -> None:
        self.total_lines += lines_cleared
        self.level = self.total_lines // LINES_PER_LEVEL
        self.score += ScoreEngine.score_for(lines_cleared)