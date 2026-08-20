"""Candidate placement generation for the DQN agent.

Pure functions — take a grid + piece metadata, return placements/features.
No pygame, no FSM, no instance state.
"""

from __future__ import annotations

from collections.abc import Iterator

import numpy as np

from tetris.ai.rewards import (
    dellacherie_value_batch,
    extract_features_batch,
    place_and_clear_batch,
)
from tetris.game import rules
from tetris.game.rules import hard_drop_y, try_rotation
from tetris.game.tetromino import SHAPES
from tetris.settings import BOARD_HEIGHT, BOARD_WIDTH

from typing import NamedTuple


class Placement(NamedTuple):
    """A piece placement: piece type, rotation, column, row, hold flag.

    shape is derivable: SHAPES[piece_type][rot].
    """

    piece_type: str
    rot: int
    px: int
    py: int
    hold: bool

    @property
    def shape(self) -> list[tuple[int, int]]:
        """Cell offsets for this placement's piece type and rotation."""
        return SHAPES[self.piece_type][self.rot]


NUM_ROTATIONS = 4


def iter_column_positions(
    piece_type: str,
) -> Iterator[tuple[list[tuple[int, int]], int, int]]:
    """Yield (shape, rot, px) for every (rotation, column) that fits the board width."""
    num_rots = len(SHAPES[piece_type])
    for rot in range(NUM_ROTATIONS):
        if rot >= num_rots:
            continue
        shape = SHAPES[piece_type][rot]
        min_bx = min(bx for bx, _ in shape)
        max_bx = max(bx for bx, _ in shape)
        for col in range(BOARD_WIDTH):
            px = col - min_bx
            if px < 0 or px + max_bx >= BOARD_WIDTH:
                continue
            yield shape, rot, px


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


def best_next_placement(grid: np.ndarray, piece_type: str) -> np.ndarray:
    """Simulate best placement of next piece on grid (2-piece look-ahead).

    Uses hard-drop for speed — look-ahead only needs approximate board quality.
    Batches all (rotation, column) candidates and evaluates Dellacherie
    in one vectorized pass.
    """
    shapes: list[list[tuple[int, int]]] = []
    x_positions: list[int] = []
    for shape, _rot, px in iter_column_positions(piece_type):
        shapes.append(shape)
        x_positions.append(px)
    if not shapes:
        return grid
    py_batch = hard_drop_y_batch(grid, shapes, x_positions)
    valid = py_batch >= 0
    if not valid.any():
        return grid
    v_shapes = [s for s, v in zip(shapes, valid) if v]
    v_xs = [x for x, v in zip(x_positions, valid) if v]
    v_pys = [int(y) for y, v in zip(py_batch, valid) if v]
    sim_grids, _ = place_and_clear_batch(grid, v_shapes, v_xs, v_pys)
    vals = dellacherie_value_batch(sim_grids)
    best_idx = int(np.argmin(vals))
    return sim_grids[best_idx]


def soft_drop_placements(
    grid,
    piece_type: str,
) -> list[Placement]:
    """Enumerate ALL reachable placements via BFS over (x, y, rotation).

    Returns list of Placement — every position the piece can reach by
    moving left/right, soft-dropping, and rotating (with SRS wall kicks).
    This includes placements under overhangs that hard-drop cannot reach.
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
    placements: list[Placement] = []
    seen_placements: set[tuple[int, int, int]] = set()

    while frontier:
        x, y, rot = frontier.pop()
        shape = SHAPES[piece_type][rot]

        # Try left
        if rules.shape_fits(grid, shape, x - 1, y) and (x - 1, y, rot) not in visited:
            visited.add((x - 1, y, rot))
            frontier.append((x - 1, y, rot))

        # Try right
        if rules.shape_fits(grid, shape, x + 1, y) and (x + 1, y, rot) not in visited:
            visited.add((x + 1, y, rot))
            frontier.append((x + 1, y, rot))

        # Try soft drop (y+1)
        if rules.shape_fits(grid, shape, x, y + 1):
            if (x, y + 1, rot) not in visited:
                visited.add((x, y + 1, rot))
                frontier.append((x, y + 1, rot))
        else:
            # Can't drop further — this is a landing position
            key = (x, y, rot)
            if key not in seen_placements:
                seen_placements.add(key)
                placements.append(Placement(piece_type, rot, x, y, False))

        # Try rotations CW and CCW
        for direction in (1, -1):
            to_rot = (rot + direction) % num_rots
            result = try_rotation(grid, piece_type, rot, to_rot, x, y)
            if result and (*result, to_rot) not in visited:
                visited.add((*result, to_rot))
                frontier.append((*result, to_rot))

    return placements


def gen_placements(base_grid: np.ndarray, piece_type: str, soft_drop: bool) -> Iterator[Placement]:
    """Yield Placement for all valid placements of a piece type."""
    if soft_drop:
        yield from soft_drop_placements(base_grid, piece_type)
    else:
        for shape, rot, px in iter_column_positions(piece_type):
            if not rules.shape_fits(base_grid, shape, px, 0):
                continue
            py = hard_drop_y(base_grid, shape, px)
            if py < 0:
                continue
            yield Placement(piece_type, rot, px, py, False)


def get_candidate_states(
    base_grid: np.ndarray,
    current_piece_type: str,
    hold_piece_type: str | None,
    next_piece_type: str,
    preview_piece_types: list[str],
    can_hold: bool,
    soft_drop: bool,
    lookahead: bool,
    lookahead_depth: int,
) -> tuple[np.ndarray, list[int], np.ndarray, list[Placement]]:
    """Enumerate valid placements, simulate drop + line clear, extract features.

    Returns (candidate_states[N,17], action_ids[N], dellacherie_values[N],
    placements). action_id = placement index (0..N-1). Includes hold
    candidates when ``can_hold`` is True.

    Batched: collects all placements first, then runs place_and_clear_batch,
    lookahead, extract_features_batch, and dellacherie_value_batch in two
    vectorized passes instead of per-candidate scalar calls.
    """
    upcoming_types = [next_piece_type] + preview_piece_types

    all_placements: list[Placement] = []
    all_shapes: list[list[tuple[int, int]]] = []
    all_next_piece_types: list[str] = []

    # Non-hold candidates: place current piece
    for p in gen_placements(base_grid, current_piece_type, soft_drop):
        all_placements.append(p)
        all_shapes.append(p.shape)
        all_next_piece_types.append(upcoming_types[0] if upcoming_types else "I")

    # Hold candidates (if can hold): place the held/next piece instead
    if can_hold:
        if hold_piece_type is not None:
            hold_upcoming = upcoming_types
        else:
            # No held piece: current → hold, next → current, preview shifts.
            hold_upcoming = preview_piece_types
            hold_piece_type = next_piece_type
        for p in gen_placements(base_grid, hold_piece_type, soft_drop):
            all_placements.append(Placement(p.piece_type, p.rot, p.px, p.py, True))
            all_shapes.append(p.shape)
            all_next_piece_types.append(hold_upcoming[0] if hold_upcoming else "I")

    if not all_placements:
        return (
            np.empty((0, 17), dtype=np.float32),
            [],
            np.empty(0, dtype=np.float32),
            [],
        )

    # Batch place + clear
    all_pxs = [p.px for p in all_placements]
    all_pys = [p.py for p in all_placements]
    sim_grids, lines_cleared = place_and_clear_batch(base_grid, all_shapes, all_pxs, all_pys)

    # Lookahead (per-candidate — each depends on its own sim_grid)
    if lookahead:
        for i in range(len(all_placements)):
            for pt in upcoming_types[:lookahead_depth]:
                sim_grids[i] = best_next_placement(sim_grids[i], pt)

    # Batch feature extraction + Dellacherie
    candidates = extract_features_batch(sim_grids, lines_cleared, all_next_piece_types)
    dellacherie_values = dellacherie_value_batch(sim_grids)

    actions = list(range(len(all_placements)))
    return candidates, actions, dellacherie_values, all_placements
