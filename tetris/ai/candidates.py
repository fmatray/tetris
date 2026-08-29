"""Candidate placement generation for the DQN agent.

Pure functions — take a grid + piece metadata, return placements/features.
No pygame, no FSM, no instance state.
"""

from __future__ import annotations

from collections.abc import Iterator

import numpy as np

from tetris.ai.rewards import (
    el_tetris_value_batch,
    extract_features_batch,
    place_and_clear_batch,
)
from tetris.game import rules
from tetris.game.rules import try_rotation
from tetris.game.shapes import SHAPES_TYPES, get_shape_rot, num_shape_rot
from tetris.settings import BOARD_HEIGHT, BOARD_WIDTH

from typing import NamedTuple


class Placement(NamedTuple):
    """A piece placement: piece type, rotation, column, row, hold flag, move sequence.

    shape is derivable: get_shape_rot(piece_type, rot).
    moves is the list of atomic actions ("left", "right", "soft_drop",
    "rot_cw", "rot_ccw") to reach this placement from spawn.
    """

    piece_type: str
    rot: int
    px: int
    py: int
    hold: bool
    moves: list[str]

    @property
    def shape(self) -> list[tuple[int, int]]:
        """Cell offsets for this placement's piece type and rotation."""
        return get_shape_rot(self.piece_type, self.rot)


NUM_ROTATIONS = 4


def _iter_column_positions_uncached(
    piece_type: str,
) -> Iterator[tuple[list[tuple[int, int]], int, int]]:
    """Yield (shape, rot, px) for every (rotation, column) that fits the board width."""
    num_rots = num_shape_rot(piece_type)
    for rot in range(NUM_ROTATIONS):
        if rot >= num_rots:
            continue
        shape = get_shape_rot(piece_type, rot)
        min_bx = min(bx for bx, _ in shape)
        max_bx = max(bx for bx, _ in shape)
        for col in range(BOARD_WIDTH):
            px = col - min_bx
            if px + max_bx >= BOARD_WIDTH:
                continue
            yield shape, rot, px


# ponytail: unbounded dict — only 7 piece types × fixed columns, so this is safe
_COLUMN_POSITIONS: dict[str, list[tuple[list[tuple[int, int]], int, int]]] = {
    pt: list(_iter_column_positions_uncached(pt)) for pt in SHAPES_TYPES
}


def iter_column_positions(
    piece_type: str,
) -> Iterator[tuple[list[tuple[int, int]], int, int]]:
    """Yield (shape, rot, px) for every (rotation, column) that fits the board width."""
    yield from _COLUMN_POSITIONS[piece_type]


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
    all_bx_arr = np.array([bx for shape in shapes for bx, _ in shape], dtype=np.int32)
    all_by_arr = np.array([by for shape in shapes for _, by in shape], dtype=np.int32)
    shape_idx_arr = np.repeat(np.arange(len(shapes), dtype=np.int32), [len(s) for s in shapes])
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


def _landing_heights(
    shapes: list[list[tuple[int, int]]],
    pys: list[int],
) -> np.ndarray:
    """El-Tetris landing height: distance from floor to piece centroid.

    BOARD_HEIGHT - py - centroid_offset, where centroid_offset is the
    mean row of the piece's own cells (min_by + max_by + 1) / 2.
    """
    centroids = np.array(
        [(min(by for _, by in s) + max(by for _, by in s) + 1) / 2 for s in shapes],
        dtype=np.float64,
    )
    return BOARD_HEIGHT - np.asarray(pys, dtype=np.float64) - centroids


def best_next_placement(grid: np.ndarray, piece_type: str) -> np.ndarray:
    """Simulate best placement of next piece on grid (2-piece look-ahead).

    Uses hard-drop for speed — look-ahead only needs approximate board quality.
    Batches all (rotation, column) candidates and evaluates El-Tetris
    (higher = better) in one vectorized pass.
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
    sim_grids, lines_cleared = place_and_clear_batch(grid, v_shapes, v_xs, v_pys)
    vals = el_tetris_value_batch(sim_grids, _landing_heights(v_shapes, v_pys), lines_cleared)
    best_idx = int(np.argmax(vals))
    return sim_grids[best_idx]


def soft_drop_placements(
    grid,
    piece_type: str,
) -> list[Placement]:
    """Enumerate ALL reachable placements via BFS over (x, y, rotation).

    Returns list of Placement — every position the piece can reach by
    moving left/right, soft-dropping, and rotating (with SRS wall kicks).
    Each placement carries the move sequence to reach it from spawn.
    This includes placements under overhangs that hard-drop cannot reach.
    """
    # ponytail: numpy scalar indexing (grid[y][x]) is ~5× slower than list
    # indexing. Convert once — amortized over ~750 shape_fits calls.
    if isinstance(grid, np.ndarray):
        grid = grid.tolist()
    num_rots = num_shape_rot(piece_type)
    spawn_x = BOARD_WIDTH // 2 - 2
    spawn_y = 0
    # BFS: state = (x, y, rot). Track shortest path of moves to each state.
    start = (spawn_x, spawn_y, 0)
    visited: dict[tuple[int, int, int], list[str]] = {start: []}
    frontier: list[tuple[int, int, int]] = [start]
    placements: list[Placement] = []
    seen_placements: set[tuple[int, int, int]] = set()

    while frontier:
        x, y, rot = frontier.pop()
        moves = visited[(x, y, rot)]
        shape = get_shape_rot(piece_type, rot)

        # Try left
        nx = (x - 1, y, rot)
        if rules.shape_fits(grid, shape, x - 1, y) and nx not in visited:
            visited[nx] = moves + ["left"]
            frontier.append(nx)

        # Try right
        nx = (x + 1, y, rot)
        if rules.shape_fits(grid, shape, x + 1, y) and nx not in visited:
            visited[nx] = moves + ["right"]
            frontier.append(nx)

        # Try soft drop (y+1)
        nx = (x, y + 1, rot)
        if rules.shape_fits(grid, shape, x, y + 1):
            if nx not in visited:
                visited[nx] = moves + ["soft_drop"]
                frontier.append(nx)
        else:
            # Can't drop further — this is a landing position
            key = (x, y, rot)
            if key not in seen_placements:
                seen_placements.add(key)
                placements.append(Placement(piece_type, rot, x, y, False, moves))

        # Try rotations CW and CCW
        for direction in (1, -1):
            to_rot = (rot + direction) % num_rots
            result = try_rotation(grid, piece_type, rot, to_rot, x, y)
            if result:
                nx = (*result, to_rot)
                if nx not in visited:
                    label = "rot_cw" if direction == 1 else "rot_ccw"
                    visited[nx] = moves + [label]
                    frontier.append(nx)

    return placements


def gen_placements(base_grid: np.ndarray, piece_type: str) -> Iterator[Placement]:
    """Yield Placement for all valid placements of a piece type.

    Uses soft-drop BFS exclusively — records the move sequence for each
    placement so the executor can replay it exactly.
    """
    yield from soft_drop_placements(base_grid, piece_type)


def get_candidate_states(
    base_grid: np.ndarray,
    current_piece_type: str,
    hold_piece_type: str | None,
    next_piece_type: str,
    preview_piece_types: list[str],
    can_hold: bool,
    lookahead: bool,
    lookahead_depth: int,
) -> tuple[np.ndarray, list[int], np.ndarray, list[Placement]]:
    """Enumerate valid placements, simulate drop + line clear, extract features.

    Returns (candidate_states[N,17], action_ids[N], el_tetris_values[N],
    placements). action_id = placement index (0..N-1). el_tetris_values
    are per-candidate El-Tetris evaluation values (bot pick + AI warm-start
    prior). Includes hold candidates when ``can_hold`` is True.

    Batched: collects all placements first, then runs place_and_clear_batch,
    lookahead, extract_features_batch, and el_tetris_value_batch in two
    vectorized passes instead of per-candidate scalar calls.
    """
    upcoming_types = [next_piece_type] + preview_piece_types

    all_placements: list[Placement] = []
    all_shapes: list[list[tuple[int, int]]] = []
    all_next_piece_types: list[str] = []

    # Non-hold candidates: place current piece
    for p in gen_placements(base_grid, current_piece_type):
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
        for p in gen_placements(base_grid, hold_piece_type):
            all_placements.append(Placement(p.piece_type, p.rot, p.px, p.py, True, p.moves))
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

    # Batch feature extraction + El-Tetris selection values
    candidates = extract_features_batch(sim_grids, lines_cleared, all_next_piece_types)
    pick_values = el_tetris_value_batch(sim_grids, _landing_heights(all_shapes, all_pys), lines_cleared)

    actions = list(range(len(all_placements)))
    return candidates, actions, pick_values, all_placements
