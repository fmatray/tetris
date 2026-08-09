"""Board grid and collision/line-clear logic."""

import random

from tetris.game.tetromino import Tetromino
from tetris.settings import BOARD_HEIGHT, BOARD_WIDTH, GRAY, SHAPES


class Board:
    """The Tetris playfield grid.

    Owns cell occupancy, collision validation, piece locking, line
    clearing, and handicap setup. Returns cleared-row data so callers
    can drive visual effects.
    """

    def __init__(self) -> None:
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
        for bx, by in shape:
            x = tetromino.x + bx + dx
            y = tetromino.y + by + dy
            if x < 0 or x >= BOARD_WIDTH or y >= BOARD_HEIGHT:
                return False
            if y >= 0 and self.grid[y][x] is not None:
                return False
        return True

    def lock_tetromino(self, tetromino: Tetromino) -> tuple[int, list[tuple[int, list]]]:
        """Lock *tetromino* into the grid and clear completed lines.

        Returns ``(lines_cleared, cleared_rows_data)`` where each row datum
        is ``(row_index, list_of_cell_colors)`` for particle effects.
        """
        for x, y in tetromino.get_blocks():
            if y >= 0:
                self.grid[y][x] = tetromino.color
        return self.clear_lines()

    def hard_drop(self, tetromino: Tetromino) -> int:
        """Drop *tetromino* to the lowest valid position. Returns distance fallen."""
        distance = 0
        while self.is_valid_move(tetromino, dy=1):
            tetromino.move(0, 1)
            distance += 1
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

    def clear_lines(self) -> tuple[int, list[tuple[int, list]]]:
        """Remove completed rows and return their data.

        Returns ``(lines_cleared, cleared_rows_data)``.
        """
        cleared_rows_data: list[tuple[int, list]] = []
        for y in range(BOARD_HEIGHT):
            if all(self.grid[y][x] is not None for x in range(BOARD_WIDTH)):
                cleared_rows_data.append((y, list(self.grid[y])))

        lines_cleared = len(cleared_rows_data)
        if lines_cleared > 0:
            new_grid = [
                row
                for row in self.grid
                if not all(cell is not None for cell in row)
            ]
            for _ in range(lines_cleared):
                new_grid.insert(0, [None for _ in range(BOARD_WIDTH)])
            self.grid = new_grid

        return lines_cleared, cleared_rows_data