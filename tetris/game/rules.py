"""Pure game-rule functions operating on any grid (list or numpy).

All read-only functions use ``bool(grid[y][x])`` as the universal occupancy
check — ``None``→False, ``0.0``→False, ``(r,g,b)``→True, ``1.0``→True.
Works for both ``list[list[tuple|None]]`` (Board) and ``np.ndarray`` (AI sim).
"""

from __future__ import annotations

import numpy as np

from tetris.game.tetromino import SHAPES
from tetris.settings import (
    BOARD_HEIGHT,
    BOARD_WIDTH,
)

# --- SRS wall kick data (https://tetris.wiki/Super_Rotation_System) -----
# Format: {(from_state, to_state): [(dx, dy), ...]}
# dx: horizontal offset, dy: vertical offset (positive = up, screen y inverted)
SRS_KICKS_JLSTZ: dict[tuple[int, int], list[tuple[int, int]]] = {
    (0, 1): [(0, 0), (-1, 0), (-1, 1), (0, -2), (-1, -2)],
    (1, 0): [(0, 0), (1, 0), (1, -1), (0, 2), (1, 2)],
    (1, 2): [(0, 0), (1, 0), (1, -1), (0, 2), (1, 2)],
    (2, 1): [(0, 0), (-1, 0), (-1, 1), (0, -2), (-1, -2)],
    (2, 3): [(0, 0), (1, 0), (1, 1), (0, -2), (1, -2)],
    (3, 2): [(0, 0), (-1, 0), (-1, -1), (0, 2), (-1, 2)],
    (3, 0): [(0, 0), (-1, 0), (-1, -1), (0, 2), (-1, 2)],
    (0, 3): [(0, 0), (1, 0), (1, 1), (0, -2), (1, -2)],
}
SRS_KICKS_I: dict[tuple[int, int], list[tuple[int, int]]] = {
    (0, 1): [(0, 0), (-2, 0), (1, 0), (-2, -1), (1, 2)],
    (1, 0): [(0, 0), (2, 0), (-1, 0), (2, 1), (-1, -2)],
    (1, 2): [(0, 0), (-1, 0), (2, 0), (-1, 2), (2, -1)],
    (2, 1): [(0, 0), (1, 0), (-2, 0), (1, -2), (-2, 1)],
    (2, 3): [(0, 0), (2, 0), (-1, 0), (2, 1), (-1, -2)],
    (3, 2): [(0, 0), (1, 0), (-2, 0), (1, 2), (-2, -1)],
    (3, 0): [(0, 0), (1, 0), (-2, 0), (1, -2), (-2, 1)],
    (0, 3): [(0, 0), (-1, 0), (2, 0), (-1, 2), (2, -1)],
}


def is_occupied(grid, x: int, y: int) -> bool:
    """True if grid cell (x, y) is filled or out of bounds (floor/wall)."""
    if x < 0 or x >= BOARD_WIDTH or y < 0 or y >= BOARD_HEIGHT:
        return False
    return bool(grid[y][x])


def shape_fits(grid, shape, x: int, y: int) -> bool:
    """Check if *shape* fits at (x, y) without collision.

    Cells above the board (y < 0) are always valid (spawn area).
    """
    for bx, by in shape:
        cx, cy = x + bx, y + by
        if cx < 0 or cx >= BOARD_WIDTH or cy >= BOARD_HEIGHT:
            return False
        if cy >= 0 and is_occupied(grid, cx, cy):
            return False
    return True


def try_rotation(grid, piece_type: str, from_rot: int, to_rot: int, x: int, y: int) -> tuple[int, int] | None:
    """Try SRS wall kicks for rotation. Returns (x, y) of first valid kick, or None."""
    if piece_type == "O":
        return (x, y) if shape_fits(grid, SHAPES[piece_type][to_rot], x, y) else None
    kicks = SRS_KICKS_I if piece_type == "I" else SRS_KICKS_JLSTZ
    key = (from_rot % len(SHAPES[piece_type]), to_rot % len(SHAPES[piece_type]))
    for dx, dy in kicks.get(key, [(0, 0)]):
        nx, ny = x + dx, y - dy  # screen y inverted: positive kick_dy = up
        if shape_fits(grid, SHAPES[piece_type][to_rot], nx, ny):
            return (nx, ny)
    return None


def hard_drop_y(grid, shape, x: int, start_y: int = 0) -> int:
    """Find the lowest y where *shape* fits at column *x* on *grid*.

    Scans downward from *start_y* (the piece's current row). This prevents
    a piece already under an overhang from being teleported on top of it.
    """
    py = start_y
    while True:
        if not shape_fits(grid, shape, x, py):
            return py - 1 if py > start_y else start_y
        py += 1


def place_cells(grid, shape, x: int, y: int, value) -> None:
    """Write *value* at each shape cell. Mutates grid in place.

    Works for list grids (value=tuple) and numpy arrays (value=1.0).
    """
    if isinstance(grid, np.ndarray):
        xs = np.array([x + bx for bx, _ in shape])
        ys = np.array([y + by for _, by in shape])
        valid = (xs >= 0) & (xs < BOARD_WIDTH) & (ys >= 0) & (ys < BOARD_HEIGHT)
        grid[ys[valid], xs[valid]] = value
        return
    for bx, by in shape:
        cx, cy = x + bx, y + by
        if 0 <= cx < BOARD_WIDTH and 0 <= cy < BOARD_HEIGHT:
            grid[cy][cx] = value


def find_full_rows(grid) -> list[int]:
    """Return row indices that are fully occupied."""
    if isinstance(grid, np.ndarray):
        return list(np.where((grid > 0).all(axis=1))[0])
    return [y for y in range(BOARD_HEIGHT) if all(bool(grid[y][x]) for x in range(BOARD_WIDTH))]
