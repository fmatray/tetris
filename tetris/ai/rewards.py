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


def board_to_grid_with_piece(board, piece) -> np.ndarray:
    """Convert a ``Board`` into a 0/1 grid including the falling piece's cells."""
    grid = board_to_grid(board)
    for bx, by in piece.get_blocks():
        if 0 <= by < BOARD_HEIGHT and 0 <= bx < BOARD_WIDTH:
            grid[by][bx] = 1.0
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
    """Build the full 220-dim state vector (AI.md §2.5).

    Layout: [board_with_piece(200), current_piece(7), next_piece(7),
             orientation(4), piece_x_norm(1), piece_y_norm(1)]
    """
    grid = board_to_grid_with_piece(board, current_piece).flatten()  # 200
    cur = one_hot_piece(current_piece.type)  # 7
    nxt = one_hot_piece(next_piece.type)  # 7
    rot = one_hot_rotation(current_piece.type, current_piece.rotation)  # 4
    pos = np.array([current_piece.x / BOARD_WIDTH, current_piece.y / BOARD_HEIGHT], dtype=np.float32)  # 2
    return np.concatenate([grid, cur, nxt, rot, pos])  # 220


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

    Combines line-clear bonuses with structural penalties to give dense
    feedback. Hole penalty is delta-based (new holes minus old holes) so
    the agent learns which actions create holes rather than inheriting
    a constant penalty for pre-existing holes.
    """
    if game_over:
        return -10.0

    reward = 0.0
    reward += 50.0 * lines_cleared
    reward += 5.0 * lines_cleared * lines_cleared

    # Delta-based hole penalty: punish only NEW holes created
    old_holes = count_holes(prev_grid)
    new_holes = count_holes(new_grid)
    holes_created = max(0, new_holes - old_holes)
    reward -= 5.0 * holes_created

    # Small residual on absolute holes so the agent still wants to clear
    # existing holes over time, but the signal is dominated by delta
    reward -= 0.1 * new_holes

    height = aggregate_height(new_grid)
    bumps = bumpiness(new_grid)

    reward -= 0.05 * height
    reward -= 0.1 * bumps

    if step_survived:
        reward += 1.0
    return reward