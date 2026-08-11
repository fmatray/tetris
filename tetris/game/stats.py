"""Mutable running game statistics (score, lines, level, combo)."""

from tetris.game.scoring import ScoreEngine
from tetris.settings import LINES_PER_LEVEL


class GameStats:
    """Tracks score, total lines, level, combo, and piece count."""

    def __init__(self) -> None:
        self.score = 0
        self.total_lines = 0
        self.level = 0
        self.piece_count = 0
        self.combo = -1

    def on_piece_locked(self, lines_cleared: int) -> None:
        self.total_lines += lines_cleared
        self.level = self.total_lines // LINES_PER_LEVEL
        self.score += ScoreEngine.line_clear_points(lines_cleared, self.level)
        if lines_cleared > 0:
            self.combo += 1
            if self.combo > 0:
                self.score += ScoreEngine.combo_points(self.combo, self.level)
        else:
            self.combo = -1
        self.piece_count += 1

    def add_soft_drop(self, cells: int) -> None:
        self.score += ScoreEngine.soft_drop_points(cells)

    def add_hard_drop(self, cells: int) -> None:
        self.score += ScoreEngine.hard_drop_points(cells)