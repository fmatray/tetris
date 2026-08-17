"""Reward function and board feature extraction for the DQN agent.

All functions operate on raw board data (numpy grid + piece metadata)
and return scalar floats. They are pure — no side effects — keeping
them easy to unit-test and reuse.
"""

from __future__ import annotations

import numpy as np

from tetris.game.rules import find_full_rows, place_cells
from tetris.settings import BOARD_HEIGHT, BOARD_WIDTH, SHAPES

PIECE_TYPES = list(SHAPES.keys())  # ["I", "O", "T", "S", "Z", "J", "L"]

# Number of features in the DT-20 state vector (10 board + 7 next-piece one-hot).
FEATURE_SIZE = 17

# Normalization constants for DT-20 features (empirical mean/std).
# Indices: [lines_cleared, holes, aggregate_height, bumpiness, max_height,
#           row_transitions, column_transitions, wells, hole_depth,
#           rows_with_holes, *one_hot_piece(7)]
FEATURE_MEANS = np.array([
    0.5,   # lines_cleared: 0-4
    5.0,   # holes: 0-50
    50.0,  # aggregate_height: 0-200
    5.0,   # bumpiness: 0-40
    10.0,  # max_height: 0-20
    30.0,  # row_transitions: 0-40
    20.0,  # column_transitions: 0-40
    5.0,   # wells: 0-40
    5.0,   # hole_depth: 0-20
    5.0,   # rows_with_holes: 0-20
    0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0,  # one_hot: 7 entries, already 0/1
], dtype=np.float32)

FEATURE_STDS = np.array([
    1.0,   # lines_cleared
    10.0,  # holes
    40.0,  # aggregate_height
    5.0,   # bumpiness
    5.0,   # max_height
    10.0,  # row_transitions
    10.0,  # column_transitions
    5.0,   # wells
    5.0,   # hole_depth
    5.0,   # rows_with_holes
    1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0,  # one_hot: 7 entries, keep binary
], dtype=np.float32)

# PBRS scaling: cap potential-based reward shaping contribution.
PBRS_SCALE = 0.1

# Reward weights (AI.md §4) — named for readability, values unchanged.
LINE_CLEAR_REWARD = 50.0
LINE_CLEAR_BONUS = 5.0
HOLE_CREATED_PENALTY = 5.0
HOLE_TOTAL_PENALTY = 0.1
HEIGHT_PENALTY = 0.5
BUMPINESS_PENALTY = 0.3
WELL_PENALTY = 0.5
SURVIVAL_REWARD = 1.0
GAME_OVER_PENALTY = 50.0

# Dellacherie feature weights for PBRS potential function (AI.md §4).
# Excludes landing_height/eroded_cells (placement-specific, not board-state).
DELLACHERIE_WEIGHTS: dict[str, float] = {
    "row_transitions": -3.418893,
    "column_transitions": -9.336683,
    "holes": -7.899265,
    "wells": -3.385597,
    "hole_depth": -0.192486,
    "rows_with_holes": -0.106548,
}


def board_to_grid(board) -> np.ndarray:
    """Convert a ``Board`` instance into a 0/1 numpy array (H×W)."""
    grid = np.zeros((BOARD_HEIGHT, BOARD_WIDTH), dtype=np.float32)
    for y in range(BOARD_HEIGHT):
        for x in range(BOARD_WIDTH):
            if board.grid[y][x] is not None:
                grid[y][x] = 1.0
    return grid


def one_hot_piece(piece_type: str) -> np.ndarray:
    """7-element one-hot encoding of a piece type."""
    vec = np.zeros(len(PIECE_TYPES), dtype=np.float32)
    vec[PIECE_TYPES.index(piece_type)] = 1.0
    return vec


# --- Board heuristics (AI.md §4.1) -----------------------------------


def column_heights(grid: np.ndarray) -> np.ndarray:
    """Height of each column (topmost filled cell per column).

    Returns a (BOARD_WIDTH,) int array. Empty column → 0.
    """
    mask = grid > 0
    first_row = np.argmax(mask, axis=0)  # first True row per column (0 if none)
    return (BOARD_HEIGHT - first_row) * mask.any(axis=0)


def compute_height_metrics(grid: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Compute column-level data once for all height-dependent heuristics.

    Returns (mask, first_row, heights):
      - mask: (H, W) boolean grid
      - first_row: (W,) row index of topmost filled cell per column (0 if empty)
      - heights: (W,) column heights (0 if empty)
    """
    mask = grid > 0
    first_row = np.argmax(mask, axis=0)
    heights = (BOARD_HEIGHT - first_row) * mask.any(axis=0)
    return mask, first_row, heights


def max_height(grid: np.ndarray, heights: np.ndarray | None = None) -> int:
    """Height of the tallest column."""
    if heights is None:
        heights = column_heights(grid)
    return int(heights.max())


def count_holes(grid: np.ndarray, mask: np.ndarray | None = None,
                first_row: np.ndarray | None = None) -> int:
    """Empty cells with at least one filled cell above them."""
    if mask is None:
        mask = grid > 0
    if first_row is None:
        first_row = np.argmax(mask, axis=0)
    # Vectorized: for each column, count empty cells below the topmost filled cell.
    total = 0
    for x in range(BOARD_WIDTH):
        if not mask[:, x].any():
            continue
        total += int((~mask[first_row[x]:, x]).sum())
    return total


def aggregate_height(grid: np.ndarray, heights: np.ndarray | None = None) -> int:
    """Sum of column heights (topmost filled cell per column)."""
    if heights is None:
        heights = column_heights(grid)
    return int(heights.sum())


def bumpiness(grid: np.ndarray, heights: np.ndarray | None = None) -> int:
    """Sum of absolute height differences between adjacent columns."""
    if heights is None:
        heights = column_heights(grid)
    return int(np.abs(np.diff(heights)).sum())


def row_transitions(grid: np.ndarray) -> int:
    """Count horizontal filled↔empty transitions per row.

    Walls (left/right edges) treated as filled.
    """
    b = (grid > 0).astype(np.int8)
    transitions = np.abs(b[:, :-1] - b[:, 1:]).sum()
    transitions += np.abs(1 - b[:, 0]).sum()   # left wall
    transitions += np.abs(b[:, -1] - 1).sum()  # right wall
    return int(transitions)


def column_transitions(grid: np.ndarray) -> int:
    """Count vertical filled↔empty transitions per column.

    Floor (bottom) treated as filled.
    """
    b = (grid > 0).astype(np.int8)
    transitions = np.abs(b[:-1, :] - b[1:, :]).sum()
    transitions += np.abs(b[-1, :] - 1).sum()  # floor (bottom) treated as filled
    return int(transitions)


def wells(grid: np.ndarray, heights: np.ndarray | None = None) -> int:
    """Cumulative well depth: Σ depth*(depth+1)//2 per column.

    A well is a column lower than both neighbors. Edge columns treat
    the wall as BOARD_HEIGHT (infinite height).
    """
    if heights is None:
        heights = column_heights(grid)
    total = 0
    for i in range(BOARD_WIDTH):
        left = heights[i - 1] if i > 0 else BOARD_HEIGHT
        right = heights[i + 1] if i < BOARD_WIDTH - 1 else BOARD_HEIGHT
        depth = max(0, int(min(left, right) - heights[i]))
        total += depth * (depth + 1) // 2
    return total


def hole_depth(grid: np.ndarray, mask: np.ndarray | None = None,
               first_row: np.ndarray | None = None) -> int:
    """Max holes in any single column below the first filled cell."""
    if mask is None:
        mask = grid > 0
    if first_row is None:
        first_row = np.argmax(mask, axis=0)
    max_depth = 0
    for x in range(BOARD_WIDTH):
        col_mask = mask[:, x]
        if not col_mask.any():
            continue
        depth = int((~col_mask[first_row[x]:]).sum())
        max_depth = max(max_depth, depth)
    return max_depth


def rows_with_holes(grid: np.ndarray, mask: np.ndarray | None = None,
                    first_row: np.ndarray | None = None) -> int:
    """Count rows containing at least one hole cell."""
    if mask is None:
        mask = grid > 0
    if first_row is None:
        first_row = np.argmax(mask, axis=0)
    holes_per_col = np.zeros_like(mask)
    for x in range(BOARD_WIDTH):
        col_mask = mask[:, x]
        if not col_mask.any():
            continue
        holes_per_col[first_row[x]:, x] = ~col_mask[first_row[x]:]
    return int(np.any(holes_per_col, axis=1).sum())


def normalize_features(features: np.ndarray) -> np.ndarray:
    """Standardize DT-20 features: (features - FEATURE_MEANS) / FEATURE_STDS."""
    return ((features - FEATURE_MEANS) / FEATURE_STDS).astype(np.float32)




def extract_features(
    grid: np.ndarray,
    lines_cleared: int,
    next_piece_type: str,
    mask: np.ndarray | None = None,
    first_row: np.ndarray | None = None,
    heights: np.ndarray | None = None,
) -> np.ndarray:
    """Build the 17-dim DT-20 feature vector (AI.md §2).

    Layout: [lines_cleared, holes, aggregate_height, bumpiness, max_height,
             row_transitions, column_transitions, wells, hole_depth,
             rows_with_holes, *one_hot_piece(next_piece_type)]

    Optional precomputed metrics (mask, first_row, heights) avoid redundant
    passes when the caller already has them from ``compute_height_metrics``.
    """
    if mask is None or first_row is None or heights is None:
        m, fr, h = compute_height_metrics(grid)
        mask = m if mask is None else mask
        first_row = fr if first_row is None else first_row
        heights = h if heights is None else heights
    features = np.array([
        lines_cleared,
        count_holes(grid, mask, first_row),
        aggregate_height(grid, heights),
        bumpiness(grid, heights),
        max_height(grid, heights),
        row_transitions(grid),
        column_transitions(grid),
        wells(grid, heights),
        hole_depth(grid, mask, first_row),
        rows_with_holes(grid, mask, first_row),
    ], dtype=np.float32)
    return normalize_features(np.concatenate([features, one_hot_piece(next_piece_type)]))

def dellacherie_value(
    grid: np.ndarray,
    heights: np.ndarray | None = None,
    mask: np.ndarray | None = None,
    first_row: np.ndarray | None = None,
) -> float:
    """Weighted sum of board features using Dellacherie weights (AI.md §4).

    Excludes landing_height/eroded_cells (placement-specific, not
    board-state). Empty grid → 0.0.
    """
    if not (grid > 0).any():
        return 0.0
    if heights is None or mask is None or first_row is None:
        m, fr, h = compute_height_metrics(grid)
        heights = h if heights is None else heights
        mask = m if mask is None else mask
        first_row = fr if first_row is None else first_row
    return (
        DELLACHERIE_WEIGHTS["row_transitions"] * row_transitions(grid)
        + DELLACHERIE_WEIGHTS["column_transitions"] * column_transitions(grid)
        + DELLACHERIE_WEIGHTS["holes"] * count_holes(grid, mask, first_row)
        + DELLACHERIE_WEIGHTS["wells"] * wells(grid, heights)
        + DELLACHERIE_WEIGHTS["hole_depth"] * hole_depth(grid, mask, first_row)
        + DELLACHERIE_WEIGHTS["rows_with_holes"] * rows_with_holes(grid, mask, first_row)
    )

def dellacherie_value_batch(grids: np.ndarray) -> np.ndarray:
    """Batch Dellacherie evaluation for N grids at once.

    Vectorized version of :func:`dellacherie_value` — computes all 6
    board heuristics in a single numpy pass over stacked grids.

    Args:
        grids: ``(N, H, W)`` array of board states.

    Returns:
        ``(N,)`` float array of Dellacherie values. Empty grids → 0.0.
    """
    N = grids.shape[0]
    mask = grids > 0                                   # (N, H, W)
    non_empty = mask.any(axis=(1, 2))                   # (N,)
    if not non_empty.any():
        return np.zeros(N, dtype=np.float64)
    any_filled = mask.any(axis=1)                       # (N, W)
    first_row = np.argmax(mask, axis=1)                # (N, W)
    heights = (BOARD_HEIGHT - first_row) * any_filled    # (N, W)
    row_idx = np.arange(BOARD_HEIGHT).reshape(1, BOARD_HEIGHT, 1)
    below_first = row_idx >= first_row[:, None, :]      # (N, H, W)
    holes = below_first & ~mask & any_filled[:, None, :]
    holes_count = holes.sum(axis=(1, 2))                # (N,)
    binary = mask.astype(np.int8)
    row_trans = np.abs(binary[:, :, :-1] - binary[:, :, 1:]).sum(axis=(1, 2))
    row_trans += np.abs(1 - binary[:, :, 0]).sum(axis=1)    # left wall
    row_trans += np.abs(binary[:, :, -1] - 1).sum(axis=1)   # right wall
    col_trans = np.abs(binary[:, :-1, :] - binary[:, 1:, :]).sum(axis=(1, 2))
    col_trans += np.abs(binary[:, -1, :] - 1).sum(axis=1)   # floor
    left_h = np.empty_like(heights)
    right_h = np.empty_like(heights)
    left_h[:, 0] = BOARD_HEIGHT
    left_h[:, 1:] = heights[:, :-1]
    right_h[:, -1] = BOARD_HEIGHT
    right_h[:, :-1] = heights[:, 1:]
    well_depth = np.maximum(0, np.minimum(left_h, right_h) - heights)
    wells_score = (well_depth * (well_depth + 1) // 2).sum(axis=1)
    holes_per_col = holes.sum(axis=1)                   # (N, W)
    hole_depth_score = holes_per_col.max(axis=1)         # (N,)
    rows_with_holes_count = holes.any(axis=2).sum(axis=1)
    vals = (
        DELLACHERIE_WEIGHTS["row_transitions"] * row_trans
        + DELLACHERIE_WEIGHTS["column_transitions"] * col_trans
        + DELLACHERIE_WEIGHTS["holes"] * holes_count
        + DELLACHERIE_WEIGHTS["wells"] * wells_score
        + DELLACHERIE_WEIGHTS["hole_depth"] * hole_depth_score
        + DELLACHERIE_WEIGHTS["rows_with_holes"] * rows_with_holes_count
    )
    return vals * non_empty


# --- Simulation helpers (AI.md §3) -----------------------------------


def place_and_clear(
    grid: np.ndarray, shape: list[tuple[int, int]], px: int, py: int
) -> tuple[np.ndarray, int]:
    """Place shape cells on a copy of grid, clear full lines.

    Returns (new_grid, lines_cleared).
    """
    new_grid = grid.copy()
    place_cells(new_grid, shape, px, py, 1.0)
    full_rows = find_full_rows(new_grid)
    if full_rows:
        lines_cleared = len(full_rows)
        keep = [y for y in range(BOARD_HEIGHT) if y not in full_rows]
        new_grid = np.vstack([
            np.zeros((lines_cleared, BOARD_WIDTH), dtype=grid.dtype),
            new_grid[keep],
        ])
    else:
        lines_cleared = 0
    return new_grid, lines_cleared

def place_and_clear_batch(
    grid: np.ndarray,
    shapes: list[list[tuple[int, int]]],
    x_positions: list[int],
    y_positions: list[int],
) -> tuple[np.ndarray, np.ndarray]:
    """Batch place + line-clear for N placements on the same base grid.

    Returns ``(grids[N, H, W], lines_cleared[N])``.
    """
    N = len(shapes)
    batch = np.repeat(grid[np.newaxis], N, axis=0)
    for i in range(N):
        place_cells(batch[i], shapes[i], x_positions[i], y_positions[i], 1.0)
    mask = batch > 0
    full = mask.all(axis=2)                                # (N, H)
    lines = full.sum(axis=1).astype(np.int32)               # (N,)
    grids_out = np.empty_like(batch)
    for i in range(N):
        if lines[i] == 0:
            grids_out[i] = batch[i]
        else:
            keep = ~full[i]
            cleared = np.vstack([
                np.zeros((int(lines[i]), BOARD_WIDTH), dtype=batch.dtype),
                batch[i][keep],
            ])
            grids_out[i] = cleared
    return grids_out, lines


# --- Reward (AI.md §4) -----------------------------------------------


def compute_reward(
    lines_cleared: int,
    prev_grid: np.ndarray,
    new_grid: np.ndarray,
    game_over: bool,
    step_survived: bool,
    gamma: float = 0.97,
) -> float:
    """Reward shaping per AI.md §4.

    Combines line-clear bonuses with structural penalties to give dense
    feedback. Hole penalty is delta-based (new holes minus old holes) so
    the agent learns which actions create holes rather than inheriting
    a constant penalty for pre-existing holes.

    PBRS term: γ·Φ(new) - Φ(prev) where Φ is the Dellacherie board value.
    Applied to ALL transitions (including game_over). For empty grids
    Φ=0 so PBRS=0 — existing tests pass unchanged.
    """
    if game_over:
        # PBRS applies even on game_over
        phi_prev = dellacherie_value(prev_grid)
        phi_new = dellacherie_value(new_grid)
        return -GAME_OVER_PENALTY + PBRS_SCALE * (gamma * phi_new - phi_prev)

    # Compute column-level data once per grid — reused by all height-dependent heuristics.
    prev_mask, prev_fr, _ = compute_height_metrics(prev_grid)
    new_mask, new_fr, new_heights = compute_height_metrics(new_grid)

    reward = 0.0
    reward += LINE_CLEAR_REWARD * lines_cleared
    reward += LINE_CLEAR_BONUS * lines_cleared * lines_cleared

    # Delta-based hole penalty: punish only NEW holes created
    old_holes = count_holes(prev_grid, prev_mask, prev_fr)
    new_holes = count_holes(new_grid, new_mask, new_fr)
    holes_created = max(0, new_holes - old_holes)
    reward -= HOLE_CREATED_PENALTY * holes_created

    # Small residual on absolute holes so the agent still wants to clear
    # existing holes over time, but the signal is dominated by delta
    reward -= HOLE_TOTAL_PENALTY * new_holes

    height = aggregate_height(new_grid, new_heights)
    bumps = bumpiness(new_grid, new_heights)

    reward -= HEIGHT_PENALTY * height
    reward -= BUMPINESS_PENALTY * bumps
    reward -= WELL_PENALTY * wells(new_grid, new_heights)
    if step_survived:
        reward += SURVIVAL_REWARD

    # PBRS shaping term
    phi_prev = dellacherie_value(prev_grid, mask=prev_mask, first_row=prev_fr)
    phi_new = dellacherie_value(new_grid, new_heights, new_mask, new_fr)
    reward += PBRS_SCALE * (gamma * phi_new - phi_prev)

    return reward

