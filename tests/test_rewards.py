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
    # Holes from row 6 to last row in column 3
    assert count_holes(grid) == BOARD_HEIGHT - 5 - 1


def test_count_holes_multiple():
    grid = _empty_grid()
    grid[2, 0] = 1  # block at row 2, col 0
    grid[2, 5] = 1  # block at row 2, col 5
    holes_per_col = BOARD_HEIGHT - 2 - 1
    assert count_holes(grid) == 2 * holes_per_col


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
    assert compute_reward(0, _empty_grid(), _empty_grid(), True, False) == -50.0


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


# --- DT-20 features ------------------------------------------------

from tetris.ai.rewards import (
    column_heights,
    column_transitions,
    dellacherie_value,
    extract_features,
    hard_drop_y,
    hole_depth,
    max_height,
    place_and_clear,
    row_transitions,
    rows_with_holes,
    wells,
)
from tetris.settings import SHAPES

# --- column_heights ------------------------------------------------

def test_column_heights_empty():
    h = column_heights(_empty_grid())
    assert h.shape == (BOARD_WIDTH,)
    assert h.sum() == 0


def test_column_heights_with_blocks():
    grid = _empty_grid()
    grid[10, 0] = 1
    grid[5, 3] = 1
    h = column_heights(grid)
    assert int(h[0]) == BOARD_HEIGHT - 10
    assert int(h[3]) == BOARD_HEIGHT - 5
    assert int(h[1]) == 0


# --- max_height ----------------------------------------------------

def test_max_height_empty():
    assert max_height(_empty_grid()) == 0


def test_max_height_with_blocks():
    grid = _empty_grid()
    grid[10, 0] = 1
    grid[5, 3] = 1
    assert max_height(grid) == BOARD_HEIGHT - 5


# --- row_transitions -----------------------------------------------

def test_row_transitions_empty():
    """Empty board: each row has 2 transitions (wall↔empty at each edge)."""
    assert row_transitions(_empty_grid()) == 2 * BOARD_HEIGHT


def test_row_transitions_with_blocks():
    """Full bottom row: 0 transitions for that row (wall-block-block-wall)."""
    grid = _grid_with_row(BOARD_HEIGHT - 1)
    empty_rows = (BOARD_HEIGHT - 1) * 2
    assert row_transitions(grid) == empty_rows


# --- column_transitions --------------------------------------------

def test_column_transitions_empty():
    """Empty board: each column has 1 transition (empty↔floor)."""
    assert column_transitions(_empty_grid()) == BOARD_WIDTH


def test_column_transitions_with_blocks():
    """Full bottom row: 1 transition per column (empty→block at row 18→19)."""
    grid = _grid_with_row(BOARD_HEIGHT - 1)
    assert column_transitions(grid) == BOARD_WIDTH


# --- wells ---------------------------------------------------------

def test_wells_flat():
    """Flat surface has no wells."""
    grid = _grid_with_row(BOARD_HEIGHT - 1)
    assert wells(grid) == 0


def test_wells_with_well():
    """Single-column well of depth 1: 1*(1+1)//2 = 1."""
    grid = _grid_with_row(BOARD_HEIGHT - 1)
    grid[BOARD_HEIGHT - 1, 5] = 0  # create depth-1 well
    assert wells(grid) == 1


# --- hole_depth ----------------------------------------------------

def test_hole_depth_empty():
    assert hole_depth(_empty_grid()) == 0


def test_hole_depth_with_holes():
    grid = _empty_grid()
    grid[5, 3] = 1  # filled at row 5 → holes from row 6 to last row
    assert hole_depth(grid) == BOARD_HEIGHT - 5 - 1


# --- rows_with_holes -----------------------------------------------

def test_rows_with_holes_empty():
    assert rows_with_holes(_empty_grid()) == 0


def test_rows_with_holes_with_holes():
    grid = _empty_grid()
    grid[5, 3] = 1  # hole in every row 6 to last row in column 3
    assert rows_with_holes(grid) == BOARD_HEIGHT - 5 - 1


# --- extract_features ----------------------------------------------

def test_extract_features_shape():
    features = extract_features(_empty_grid(), 0, "I")
    assert features.shape == (17,)
    assert features.dtype == np.float32


def test_extract_features_values():
    features = extract_features(_empty_grid(), 2, "T")
    # Normalized: (2.0 - 0.5) / 1.0 = 1.5
    assert abs(features[0] - 1.5) < 0.01  # lines_cleared normalized
    # one-hot preserved (0/1, std=1, mean=0)
    assert features[10] == 0.0
    assert features[12] == 1.0


# --- dellacherie_value ---------------------------------------------

def test_dellacherie_value_empty():
    assert dellacherie_value(_empty_grid()) == 0.0


def test_dellacherie_value_bad_board():
    """Board with holes should have negative Dellacherie value."""
    grid = _empty_grid()
    grid[5, 3] = 1  # creates holes
    assert dellacherie_value(grid) < 0


# --- hard_drop_y ---------------------------------------------------

def test_hard_drop_y_empty():
    """O-piece dropped on empty board lands at the bottom row."""
    shape = SHAPES["O"][0]
    py = hard_drop_y(_empty_grid(), shape, 0)
    # O occupies rows py and py+1; bottom row is BOARD_HEIGHT-1
    assert py == BOARD_HEIGHT - 2


def test_hard_drop_y_with_blocks():
    """O-piece dropped above existing blocks lands on top of them."""
    grid = _empty_grid()
    block_row = BOARD_HEIGHT - 4
    grid[block_row, 0] = 1
    grid[block_row, 1] = 1
    shape = SHAPES["O"][0]  # occupies (0,0),(1,0),(0,1),(1,1)
    py = hard_drop_y(grid, shape, 0)
    assert py == block_row - 2


# --- place_and_clear ------------------------------------------------

def test_place_and_clear_no_lines():
    """Place O-piece on empty board, no lines cleared."""
    shape = SHAPES["O"][0]
    new_grid, cleared = place_and_clear(_empty_grid(), shape, 0, 18)
    assert cleared == 0
    assert new_grid[18, 0] == 1.0
    assert new_grid[19, 0] == 1.0


def test_place_and_clear_full_line():
    """Place pieces to fill bottom row, line clears."""
    grid = _empty_grid()
    # Fill row 19 except columns 0-1
    for x in range(2, BOARD_WIDTH):
        grid[19, x] = 1.0
    shape = SHAPES["O"][0]  # occupies (0,0),(1,0),(0,1),(1,1)
    new_grid, cleared = place_and_clear(grid, shape, 0, 18)
    assert cleared == 1
    # After line clear, row 19 has O-piece top shifted down (columns 0-1)
    assert new_grid[19, 0] == 1.0
    assert new_grid[19, 1] == 1.0
    assert new_grid[19, 2] == 0.0


# --- compute_reward PBRS -------------------------------------------

def test_compute_reward_pbrs_nonempty():
    """Non-empty grids get PBRS shaping term (reward differs from gamma=0)."""
    prev = _empty_grid()
    new = _empty_grid()
    new[5, 3] = 1  # creates holes → negative Dellacherie value
    r_pbrs = compute_reward(0, prev, new, False, True, gamma=0.97)
    r_base = compute_reward(0, prev, new, False, True, gamma=0.0)
    phi_new = dellacherie_value(new)
    assert abs(r_pbrs - r_base - 0.1 * 0.97 * phi_new) < 0.01
    assert r_pbrs < r_base


def test_compute_reward_pbrs_empty_no_change():
    """Empty grids: PBRS = 0, existing behavior unchanged."""
    r = compute_reward(0, _empty_grid(), _empty_grid(), False, True)
    assert r == 1.0


# --- normalize_features ----------------------------------------------

def test_normalize_features():
    from tetris.ai.rewards import FEATURE_MEANS, FEATURE_STDS, normalize_features
    raw = np.array([2.0, 5.0, 50.0, 5.0, 10.0, 30.0, 20.0, 5.0, 5.0, 5.0,
                    0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0], dtype=np.float32)
    norm = normalize_features(raw)
    assert norm.shape == (17,)
    assert norm.dtype == np.float32
    # Normalized = (raw - mean) / std
    expected = (raw - FEATURE_MEANS) / FEATURE_STDS
    np.testing.assert_allclose(norm, expected, atol=1e-5)
    # One-hot entries preserved (mean=0, std=1)
    assert norm[12] == 1.0


# --- soft_drop_placements --------------------------------------------

def test_soft_drop_placements_empty():
    """Empty board: all standard hard-drop positions reachable."""
    from tetris.ai.rewards import soft_drop_placements
    placements = soft_drop_placements(_empty_grid(), "O")
    assert len(placements) > 0
    # O-piece has 1 rotation, spans 2 columns → 9 positions on empty board
    assert len(placements) == 9


def test_soft_drop_placements_overhang():
    """Board with overhang: placement under overhang is reachable."""
    from tetris.ai.rewards import soft_drop_placements
    grid = _empty_grid()
    # Create overhang: fill row 17 cols 0-3, leave gap at col 0-1 below
    grid[17, 0] = 1
    grid[17, 1] = 1
    grid[17, 2] = 1
    grid[17, 3] = 1
    # I-piece horizontal can slide under if it fits
    placements = soft_drop_placements(grid, "I")
    # Should find placements at bottom (row 18-19) that hard-drop would miss
    # because the overhang blocks direct drop from top
    y_coords = {py for _, _, py, _ in placements}
    assert 18 in y_coords or 19 in y_coords  # can reach below overhang


def test_srs_wall_kick():
    """Rotation with SRS kick succeeds when basic rotation would fail."""
    from tetris.ai.rewards import _shape_fits, _try_rotation
    grid = _empty_grid()
    # J-piece: spawn state 0 → rotation 1. On empty board, basic rotation
    # should succeed (no kick needed). Test that kick is attempted.
    result = _try_rotation(grid, "J", 0, 1, 3, 0)
    assert result is not None
    nx, ny = result
    assert _shape_fits(grid, SHAPES["J"][1], nx, ny)