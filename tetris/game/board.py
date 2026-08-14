"""Board grid and collision/line-clear logic."""

import random

from tetris.game.tetromino import Tetromino
from tetris.settings import (
    BOARD_HEIGHT,
    BOARD_WIDTH,
    GRAY,
    SHAPES,
    SRS_KICKS_I,
    SRS_KICKS_JLSTZ,
)


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
        for bx, by in shape:
            x = tetromino.x + bx + dx
            y = tetromino.y + by + dy
            if x < 0 or x >= BOARD_WIDTH or y >= BOARD_HEIGHT:
                return False
            if y >= 0 and self.grid[y][x] is not None:
                return False
        return True

    def try_rotate(self, tetromino: Tetromino, direction: int) -> bool:
        """Attempt rotation with SRS wall kicks. Returns True if rotated."""
        piece_type = tetromino.type
        shapes = SHAPES[piece_type]
        from_rot = tetromino.rotation % len(shapes)
        to_rot = (from_rot + direction) % len(shapes)
        new_shape = shapes[to_rot]
        # O-piece doesn't kick
        if piece_type == "O":
            if self.is_valid_move(tetromino, rotation=to_rot):
                tetromino.rotation = to_rot
                tetromino.shape = new_shape
                return True
            return False
        kicks = SRS_KICKS_I if piece_type == "I" else SRS_KICKS_JLSTZ
        key = (from_rot, to_rot)
        for dx, dy in kicks.get(key, [(0, 0)]):
            nx = tetromino.x + dx
            ny = tetromino.y - dy  # screen y inverted: positive kick_dy = up
            if self._shape_fits(new_shape, nx, ny):
                tetromino.x = nx
                tetromino.y = ny
                tetromino.rotation = to_rot
                tetromino.shape = new_shape
                return True
        return False

    def _shape_fits(self, shape, x: int, y: int) -> bool:
        """Check if shape fits at (x, y) without collision."""
        for bx, by in shape:
            cx = x + bx
            cy = y + by
            if cx < 0 or cx >= BOARD_WIDTH or cy >= BOARD_HEIGHT:
                return False
            if cy >= 0 and self.grid[cy][cx] is not None:
                return False
        return True

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