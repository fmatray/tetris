"""Mutable running game statistics (score, lines, level, combo, clear counts)."""

from dataclasses import dataclass, field

from tetris.game.scoring import ScoreEngine
from tetris.settings import LINES_PER_LEVEL


@dataclass
class ClearCounts:
    """Per-game counts of single, double, triple, and tetris line clears."""

    single: int = 0
    double: int = 0
    triple: int = 0
    tetris: int = 0

    @property
    def total(self) -> int:
        """Total number of line-clearing events."""
        return self.single + self.double + self.triple + self.tetris

    def add(self, lines_cleared: int) -> None:
        """Increment the counter matching ``lines_cleared`` (1–4). No-op for 0."""
        match lines_cleared:
            case 1:
                self.single += 1
            case 2:
                self.double += 1
            case 3:
                self.triple += 1
            case 4:
                self.tetris += 1


@dataclass
class GameStats:
    """Tracks score, total lines, level, combo, B2B, clear counts, and piece count."""

    score: int = 0
    total_lines: int = 0
    level: int = 0
    piece_count: int = 0
    combo: int = -1
    b2b: bool = False  # True if last clear was Tetris or T-Spin
    clear_counts: ClearCounts = field(default_factory=ClearCounts)

    def on_piece_locked(self, lines_cleared: int, tspin: bool = False) -> None:
        """Update score, lines, level, combo, and B2B after a piece locks.

        Applies T-Spin bonus, B2B chain multiplier, and combo points via
        :class:`~tetris.game.scoring.ScoreEngine`.

        Args:
            lines_cleared: Number of lines cleared by this placement (0–4).
            tspin: Whether the placement was a T-Spin.
        """
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
            self.clear_counts.add(lines_cleared)
        else:
            self.combo = -1
        self.b2b = is_b2b_clear
        self.piece_count += 1

    def add_soft_drop(self, cells: int) -> None:
        """Award soft-drop bonus points.

        Args:
            cells: Number of cells the piece was soft-dropped.
        """
        self.score += ScoreEngine.soft_drop_points(cells)

    def add_hard_drop(self, cells: int) -> None:
        """Award hard-drop bonus points.

        Args:
            cells: Number of cells the piece was hard-dropped.
        """
        self.score += ScoreEngine.hard_drop_points(cells)
