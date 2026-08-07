"""Reward function and board feature extraction for the DQN agent.

All functions operate on raw board data (numpy grid + piece metadata)
and return scalar floats. They are pure — no side effects — keeping
them easy to unit-test and reuse.
"""

from __future__ import annotations

import numpy as np

from tetris.settings import BOARD_HEIGHT, BOARD_WIDTH, SHAPES


PIECE_TYPES = list(SHAPES.keys())  # ["I", "O", "T", "S", "Z", "J", "L"]


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


def one_hot_rotation(piece_type: str, rotation: int) -> np.ndarray:
    """4-element one-hot encoding of rotation index."""
    n_rotations = len(SHAPES[piece_type])
    idx = rotation % n_rotations
    vec = np.zeros(4, dtype=np.float32)
    vec[idx] = 1.0
    return vec


def extract_state(
    board, current_piece, next_piece
) -> np.ndarray:
    """Build the full 218-dim state vector (AI.md §2.5).

    Layout: [board(200), current_piece(7), next_piece(7), orientation(4)]
    """
    grid = board_to_grid(board).flatten()  # 200
    cur = one_hot_piece(current_piece.type)  # 7
    nxt = one_hot_piece(next_piece.type)  # 7
    rot = one_hot_rotation(current_piece.type, current_piece.rotation)  # 4
    return np.concatenate([grid, cur, nxt, rot])  # 218


# --- Board heuristics (AI.md §4.1) -----------------------------------


def count_holes(grid: np.ndarray) -> int:
    """Empty cells with at least one filled cell above them."""
    holes = 0
    for x in range(BOARD_WIDTH):
        col = grid[:, x]
        found_block = False
        for y in range(BOARD_HEIGHT):
            if col[y] > 0:
                found_block = True
            elif found_block:
                holes += 1
    return holes


def aggregate_height(grid: np.ndarray) -> int:
    """Sum of column heights (topmost filled cell per column)."""
    total = 0
    for x in range(BOARD_WIDTH):
        col = grid[:, x]
        for y in range(BOARD_HEIGHT):
            if col[y] > 0:
                total += BOARD_HEIGHT - y
                break
    return total


def bumpiness(grid: np.ndarray) -> int:
    """Sum of absolute height differences between adjacent columns."""
    heights = []
    for x in range(BOARD_WIDTH):
        col = grid[:, x]
        h = 0
        for y in range(BOARD_HEIGHT):
            if col[y] > 0:
                h = BOARD_HEIGHT - y
                break
        heights.append(h)
    return sum(abs(heights[i] - heights[i + 1]) for i in range(len(heights) - 1))


def compute_reward(
    lines_cleared: int,
    prev_grid: np.ndarray,
    new_grid: np.ndarray,
    game_over: bool,
    step_survived: bool,
) -> float:
    """Reward shaping per AI.md §4.

    Combines line-clear bonuses with structural penalties (holes,
    height, bumpiness) to give dense feedback even when no lines clear.
    """
    if game_over:
        return -1.0

    reward = 0.0
    reward += 1.0 * lines_cleared
    reward += 0.1 * lines_cleared * lines_cleared

    new_holes = count_holes(new_grid)
    prev_holes = count_holes(prev_grid)
    reward -= 0.5 * max(0, new_holes - prev_holes)

    height_delta = aggregate_height(new_grid) - aggregate_height(prev_grid)
    reward -= 0.2 * max(0, height_delta)

    bump_delta = bumpiness(new_grid) - bumpiness(prev_grid)
    reward -= 0.3 * max(0, bump_delta)

    if step_survived:
        reward += 0.01

    return reward