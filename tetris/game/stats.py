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
        self.b2b = False  # True if last clear was Tetris or T-Spin

    def on_piece_locked(self, lines_cleared: int, tspin: bool = False) -> None:
        self.total_lines += lines_cleared
        self.level = self.total_lines // LINES_PER_LEVEL
        # Determine if this clear is a B2B-eligible clear (Tetris or T-Spin)
        is_tetris = lines_cleared == 4
        is_b2b_clear = is_tetris or (tspin and lines_cleared > 0)
        if tspin:
            base = ScoreEngine.tspin_points(lines_cleared, self.level)
        else:
            base = ScoreEngine.line_clear_points(lines_cleared, self.level)
        # Apply B2B bonus
        if is_b2b_clear and self.b2b:
            base += ScoreEngine.b2b_bonus(base)
        self.score += base
        if lines_cleared > 0:
            self.combo += 1
            if self.combo > 0:
                self.score += ScoreEngine.combo_points(self.combo, self.level)
        else:
            self.combo = -1
        self.b2b = is_b2b_clear
        self.piece_count += 1

    def add_soft_drop(self, cells: int) -> None:
        self.score += ScoreEngine.soft_drop_points(cells)

    def add_hard_drop(self, cells: int) -> None:
        self.score += ScoreEngine.hard_drop_points(cells)