"""Board grid and collision/line-clear logic."""

import random
from typing import NamedTuple

from tetris.game import rules
from tetris.game.tetromino import Tetromino
from tetris.settings import (
    BOARD_HEIGHT,
    BOARD_WIDTH,
    GRAY,
    SHAPES,
)


class ClearedRow(NamedTuple):
    """A cleared row's index and cell colors (for particle effects)."""

    row_index: int
    cell_colors: list


class LineClearResult(NamedTuple):
    """Result of clearing completed lines."""

    lines_cleared: int
    cleared_rows: list[ClearedRow]


class Board:
    """The Tetris playfield grid.

    Owns cell occupancy, collision validation, piece locking, line
    clearing, and handicap setup. Returns cleared-row data so callers
    can drive visual effects.
    """

    def __init__(self) -> None:
        """Create an empty board with ``BOARD_HEIGHT`` rows × ``BOARD_WIDTH`` cols."""
        self.grid: list[list[tuple[int, int, int] | None]] = [
            [None for _ in range(BOARD_WIDTH)] for _ in range(BOARD_HEIGHT)
        ]

    def is_valid_move(self, tetromino: Tetromino, dx=0, dy=0, rotation=None) -> bool:
        """Check whether *tetromino* shifted by (dx, dy) fits on the board."""
        if rotation is not None:
            shapes = SHAPES[tetromino.type]
            shape = shapes[rotation % len(shapes)]
        else:
            shape = tetromino.shape
        return rules.shape_fits(self.grid, shape, tetromino.x + dx, tetromino.y + dy)

    def try_rotate(self, tetromino: Tetromino, direction: int) -> bool:
        """Attempt rotation with SRS wall kicks. Returns True if rotated."""
        shapes = SHAPES[tetromino.type]
        from_rot = tetromino.rotation % len(shapes)
        to_rot = (from_rot + direction) % len(shapes)
        result = rules.try_rotation(self.grid, tetromino.type, from_rot, to_rot, tetromino.x, tetromino.y)
        if result is not None:
            tetromino.x, tetromino.y = result
            tetromino.rotation = to_rot
            tetromino.shape = shapes[to_rot]
            return True
        return False

    def is_tspin(self, tetromino: Tetromino) -> bool:
        """Detect T-Spin using the 3-corner T rule.

        The T-piece center is at (x+1, y+1). At least 3 of the 4 diagonal
        corners around the center must be occupied (filled cell or wall).
        """
        if tetromino.type != "T":
            return False
        cx = tetromino.x + 1
        cy = tetromino.y + 1
        corners = [(cx - 1, cy - 1), (cx + 1, cy - 1), (cx - 1, cy + 1), (cx + 1, cy + 1)]
        filled = 0
        for x, y in corners:
            if x < 0 or x >= BOARD_WIDTH or y >= BOARD_HEIGHT:
                filled += 1  # wall counts as filled
            elif y >= 0 and self.grid[y][x] is not None:
                filled += 1
        return filled >= 3

    def lock_tetromino(self, tetromino: Tetromino) -> LineClearResult:
        """Lock *tetromino* into the grid and clear completed lines.

        Returns ``(lines_cleared, cleared_rows_data)`` where each row datum
        is ``(row_index, list_of_cell_colors)`` for particle effects.
        """
        rules.place_cells(self.grid, tetromino.shape, tetromino.x, tetromino.y, tetromino.color)
        return self.clear_lines()

    def hard_drop(self, tetromino: Tetromino) -> int:
        """Drop *tetromino* to the lowest valid position. Returns distance fallen."""
        py = rules.hard_drop_y(self.grid, tetromino.shape, tetromino.x, tetromino.y)
        distance = py - tetromino.y
        tetromino.y = py
        return distance

    def apply_handicap(self, level: int) -> None:
        """Pre-fill bottom rows with random gray blocks.

        Each handicap level adds two partial rows (3-7 random cells) so
        lines do not clear immediately. Level 0 leaves the board empty.
        """
        if level == 0:
            return

        num_rows = level * 2
        for y in range(BOARD_HEIGHT - 1, max(0, BOARD_HEIGHT - 1 - num_rows), -1):
            fill_count = random.randint(3, 7)
            cells = random.sample(range(BOARD_WIDTH), fill_count)
            for x in cells:
                self.grid[y][x] = GRAY

    def clear_lines(self) -> LineClearResult:
        """Remove completed rows and return their data.

        Returns ``(lines_cleared, cleared_rows_data)``.
        """
        full_rows = rules.find_full_rows(self.grid)
        cleared_rows = [ClearedRow(y, list(self.grid[y])) for y in full_rows]

        lines_cleared = len(cleared_rows)
        if lines_cleared > 0:
            new_grid = [row for row in self.grid if not all(cell is not None for cell in row)]
            for _ in range(lines_cleared):
                new_grid.insert(0, [None for _ in range(BOARD_WIDTH)])
            self.grid = new_grid

        return LineClearResult(lines_cleared, cleared_rows)
