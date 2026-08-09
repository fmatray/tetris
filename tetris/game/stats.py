"""Mutable running game statistics (score, lines, level)."""

from tetris.game.scoring import ScoreEngine
from tetris.settings import LINES_PER_LEVEL


class GameStats:
    """Tracks score, total lines cleared, and current level.

    Level advances every ``LINES_PER_LEVEL`` lines. Score is updated
    via :class:`ScoreEngine` so the bonus table stays encapsulated.
    """

    def __init__(self) -> None:
        self.score = 0
        self.total_lines = 0
        self.level = 0
        self.piece_count = 0

    def on_piece_locked(self, lines_cleared: int) -> None:
        self.total_lines += lines_cleared
        self.level = self.total_lines // LINES_PER_LEVEL
        self.score += ScoreEngine.score_for(lines_cleared)
        self.piece_count += 1