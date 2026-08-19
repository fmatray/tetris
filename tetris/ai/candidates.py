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
from tetris.game.rules import hard_drop_y, hard_drop_y_batch, soft_drop_placements
from tetris.settings import BOARD_WIDTH, SHAPES

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


def gen_placements(
    base_grid: np.ndarray, piece_type: str, soft_drop: bool
) -> Iterator[tuple[list[tuple[int, int]], int, int, int]]:
    """Yield (shape, px, py, rot) for all valid placements of a piece type."""
    if soft_drop:
        yield from soft_drop_placements(base_grid, piece_type)
    else:
        for shape, rot, px in iter_column_positions(piece_type):
            if not rules.shape_fits(base_grid, shape, px, 0):
                continue
            py = hard_drop_y(base_grid, shape, px)
            if py < 0:
                continue
            yield (shape, px, py, rot)


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
) -> tuple[np.ndarray, list[int], np.ndarray, list[tuple[int, int, int, bool]]]:
    """Enumerate valid placements, simulate drop + line clear, extract features.

    Returns (candidate_states[N,17], action_ids[N], dellacherie_values[N],
    placements). action_id = placement index (0..N-1). Placements stored as
    [(rot, px, py, hold), ...]. Includes hold candidates when ``can_hold`` is
    True.

    Batched: collects all placements first, then runs place_and_clear_batch,
    lookahead, extract_features_batch, and dellacherie_value_batch in two
    vectorized passes instead of per-candidate scalar calls.
    """
    upcoming_types = [next_piece_type] + preview_piece_types

    all_shapes: list[list[tuple[int, int]]] = []
    all_pxs: list[int] = []
    all_pys: list[int] = []
    all_rots: list[int] = []
    all_holds: list[bool] = []
    all_next_piece_types: list[str] = []

    # Non-hold candidates: place current piece
    for shape, px, py, rot in gen_placements(base_grid, current_piece_type, soft_drop):
        all_shapes.append(shape)
        all_pxs.append(px)
        all_pys.append(py)
        all_rots.append(rot)
        all_holds.append(False)
        all_next_piece_types.append(upcoming_types[0] if upcoming_types else "I")

    # Hold candidates (if can hold): place the held/next piece instead
    if can_hold:
        if hold_piece_type is not None:
            # Swap: current → hold, held → current. Next unchanged.
            hold_upcoming = upcoming_types
        else:
            # No held piece: current → hold, next → current, preview shifts.
            hold_upcoming = preview_piece_types
            hold_piece_type = next_piece_type
        for shape, px, py, rot in gen_placements(base_grid, hold_piece_type, soft_drop):
            all_shapes.append(shape)
            all_pxs.append(px)
            all_pys.append(py)
            all_rots.append(rot)
            all_holds.append(True)
            all_next_piece_types.append(hold_upcoming[0] if hold_upcoming else "I")

    if not all_shapes:
        return (
            np.empty((0, 17), dtype=np.float32),
            [],
            np.empty(0, dtype=np.float32),
            [],
        )

    placements = list(zip(all_rots, all_pxs, all_pys, all_holds))

    # Batch place + clear
    sim_grids, lines_cleared = place_and_clear_batch(base_grid, all_shapes, all_pxs, all_pys)

    # Lookahead (per-candidate — each depends on its own sim_grid)
    if lookahead:
        for i in range(len(all_shapes)):
            for pt in upcoming_types[:lookahead_depth]:
                sim_grids[i] = best_next_placement(sim_grids[i], pt)

    # Batch feature extraction + Dellacherie
    candidates = extract_features_batch(sim_grids, lines_cleared, all_next_piece_types)
    dellacherie_values = dellacherie_value_batch(sim_grids)

    actions = list(range(len(all_shapes)))
    return candidates, actions, dellacherie_values, placements
