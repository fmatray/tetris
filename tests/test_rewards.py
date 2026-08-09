"""Tests for reward function and board heuristics."""

import numpy as np

from tetris.ai.rewards import (
    aggregate_height,
    bumpiness,
    compute_reward,
    count_holes,
)
from tetris.settings import BOARD_HEIGHT, BOARD_WIDTH


def _empty_grid():
    return np.zeros((BOARD_HEIGHT, BOARD_WIDTH), dtype=int)


def _grid_with_row(row, value=1):
    grid = _empty_grid()
    grid[row, :] = value
    return grid


# --- count_holes ----------------------------------------------------

def test_count_holes_empty():
    assert count_holes(_empty_grid()) == 0


def test_count_holes_with_blocks():
    """All empty cells below a filled cell in a column are holes."""
    grid = _empty_grid()
    grid[5, 3] = 1  # filled at row 5, column 3
    # All 14 cells from row 6 to row 19 in column 3 are holes
    assert count_holes(grid) == 14


def test_count_holes_multiple():
    grid = _empty_grid()
    grid[2, 0] = 1  # block at row 2, col 0 → 17 holes (rows 3-19)
    grid[2, 5] = 1  # block at row 2, col 5 → 17 holes (rows 3-19)
    assert count_holes(grid) == 34


# --- aggregate_height -----------------------------------------------

def test_aggregate_height_empty():
    assert aggregate_height(_empty_grid()) == 0


def test_aggregate_height_with_blocks():
    grid = _empty_grid()
    grid[10, 0] = 1  # height 10 in column 0
    grid[5, 3] = 1   # height 15 in column 3
    # aggregate_height sums (BOARD_HEIGHT - topmost_filled_row)
    expected = (BOARD_HEIGHT - 10) + (BOARD_HEIGHT - 5)
    assert aggregate_height(grid) == expected


# --- bumpiness ------------------------------------------------------

def test_bumpiness_flat():
    """A flat surface has zero bumpiness."""
    grid = _grid_with_row(BOARD_HEIGHT - 1)
    assert bumpiness(grid) == 0

def test_bumpiness_uneven():
    grid = _empty_grid()
    grid[BOARD_HEIGHT - 1, 0] = 1  # height 1
    grid[BOARD_HEIGHT - 3, 1] = 1  # height 3
    # bumpiness = |1-3| + |3-0| + |0-0|*7 = 5
    assert bumpiness(grid) == 5


# --- compute_reward -------------------------------------------------

def test_compute_reward_game_over():
    assert compute_reward(0, _empty_grid(), _empty_grid(), True, False) == -10.0


def test_compute_reward_line_clear():
    prev = _empty_grid()
    new = _empty_grid()
    r = compute_reward(1, prev, new, False, True)
    # 50*1 + 5*1 + 1 (step_survived) = 56
    assert r == 56.0


def test_compute_reward_hole_penalty():
    prev = _empty_grid()
    new = _empty_grid()
    new[5, 3] = 1  # creates a hole at (6, 3)
    r = compute_reward(0, prev, new, False, True)
    # 1 (step_survived) - 5 (1 hole created) - 0.1*1 (residual) - 0.05*height - 0.1*bumps
    assert r < 0  # net penalty


def test_compute_reward_step_survived():
    r = compute_reward(0, _empty_grid(), _empty_grid(), False, True)
    assert r == 1.0


def test_compute_reward_no_step_survived():
    r = compute_reward(0, _empty_grid(), _empty_grid(), False, False)
    assert r == 0.0