"""Pure game-rule functions operating on any grid (list or numpy).

All read-only functions use ``bool(grid[y][x])`` as the universal occupancy
check — ``None``→False, ``0.0``→False, ``(r,g,b)``→True, ``1.0``→True.
Works for both ``list[list[tuple|None]]`` (Board) and ``np.ndarray`` (AI sim).
"""

from __future__ import annotations

import numpy as np

from tetris.settings import (
    BOARD_HEIGHT,
    BOARD_WIDTH,
    SHAPES,
    SRS_KICKS_I,
    SRS_KICKS_JLSTZ,
)


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


def hard_drop_y_batch(
    grid: np.ndarray,
    shapes: list[list[tuple[int, int]]],
    x_positions: list[int],
) -> np.ndarray:
    """Batch hard-drop: landing y for N (shape, x) pairs on the same grid.

    Replaces the per-piece while-loop with a column-height lookup. Returns
    ``(N,)`` int array. Matches :func:`hard_drop_y` for all valid placements.
    """
    mask = np.asarray(grid) > 0
    col_tops = np.argmax(mask, axis=0).astype(np.int32)
    col_tops[~mask.any(axis=0)] = BOARD_HEIGHT
    # Flatten all (shape, cell) pairs into parallel arrays for vectorized min.
    all_bx: list[int] = []
    all_by: list[int] = []
    all_shape_idx: list[int] = []
    for i, shape in enumerate(shapes):
        for bx, by in shape:
            all_bx.append(bx)
            all_by.append(by)
            all_shape_idx.append(i)
    all_bx_arr = np.array(all_bx, dtype=np.int32)
    all_by_arr = np.array(all_by, dtype=np.int32)
    shape_idx_arr = np.array(all_shape_idx, dtype=np.int32)
    all_cx = np.array(x_positions, dtype=np.int32)[shape_idx_arr] + all_bx_arr

    valid = (all_cx >= 0) & (all_cx < BOARD_WIDTH)
    cell_y = np.where(
        valid,
        col_tops[np.clip(all_cx, 0, BOARD_WIDTH - 1)] - all_by_arr - 1,
        BOARD_HEIGHT,
    )
    cell_y[~valid] = -1
    results = np.full(len(shapes), BOARD_HEIGHT, dtype=np.int32)
    np.minimum.at(results, shape_idx_arr, cell_y)
    # Shapes with any invalid cx → -1
    invalid_shape = np.zeros(len(shapes), dtype=bool)
    np.logical_or.at(invalid_shape, shape_idx_arr, ~valid)
    results[invalid_shape] = -1
    results = np.maximum(results, 0)
    return results


def soft_drop_placements(
    grid,
    piece_type: str,
) -> list[tuple[list[tuple[int, int]], int, int, int]]:
    """Enumerate ALL reachable placements via BFS over (x, y, rotation).

    Returns list of (shape, px, py, rotation) tuples — every position the
    piece can reach by moving left/right, soft-dropping, and rotating (with
    SRS wall kicks). This includes placements under overhangs that hard-drop
    cannot reach.
    """
    # ponytail: numpy scalar indexing (grid[y][x]) is ~5× slower than list
    # indexing. Convert once — amortized over ~750 shape_fits calls.
    if isinstance(grid, np.ndarray):
        grid = grid.tolist()
    num_rots = len(SHAPES[piece_type])
    spawn_x = BOARD_WIDTH // 2 - 2
    spawn_y = 0
    # ponytail: BFS frontier — state = (x, y, rot). O(W*H*4) states.
    visited: set[tuple[int, int, int]] = set()
    frontier: list[tuple[int, int, int]] = [(spawn_x, spawn_y, 0)]
    visited.add((spawn_x, spawn_y, 0))
    placements: list[tuple[list[tuple[int, int]], int, int, int]] = []
    seen_placements: set[tuple[int, int, int]] = set()

    while frontier:
        x, y, rot = frontier.pop()
        shape = SHAPES[piece_type][rot]

        # Try left
        if shape_fits(grid, shape, x - 1, y) and (x - 1, y, rot) not in visited:
            visited.add((x - 1, y, rot))
            frontier.append((x - 1, y, rot))

        # Try right
        if shape_fits(grid, shape, x + 1, y) and (x + 1, y, rot) not in visited:
            visited.add((x + 1, y, rot))
            frontier.append((x + 1, y, rot))

        # Try soft drop (y+1)
        if shape_fits(grid, shape, x, y + 1):
            if (x, y + 1, rot) not in visited:
                visited.add((x, y + 1, rot))
                frontier.append((x, y + 1, rot))
        else:
            # Can't drop further — this is a landing position
            key = (x, y, rot)
            if key not in seen_placements:
                seen_placements.add(key)
                placements.append((shape, x, y, rot))

        # Try rotations CW and CCW
        for direction in (1, -1):
            to_rot = (rot + direction) % num_rots
            result = try_rotation(grid, piece_type, rot, to_rot, x, y)
            if result and (*result, to_rot) not in visited:
                visited.add((*result, to_rot))
                frontier.append((*result, to_rot))

    return placements


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
