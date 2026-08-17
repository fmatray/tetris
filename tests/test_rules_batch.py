"""Tests for batch game-rule functions (hard_drop_y_batch, place_and_clear_batch)."""

import numpy as np

from tetris.ai.rewards import (
    dellacherie_value,
    dellacherie_value_batch,
    place_and_clear,
    place_and_clear_batch,
)
from tetris.game.rules import hard_drop_y, hard_drop_y_batch, shape_fits
from tetris.settings import BOARD_HEIGHT, BOARD_WIDTH, SHAPES


def _empty_grid():
    return np.zeros((BOARD_HEIGHT, BOARD_WIDTH), dtype=np.float32)


def _random_grid(rng, max_fill_rows=10):
    """Generate a random partially-filled board."""
    g = _empty_grid()
    fill_rows = int(rng.integers(1, max_fill_rows + 1))
    for y in range(BOARD_HEIGHT - fill_rows, BOARD_HEIGHT):
        for x in range(BOARD_WIDTH):
            if rng.random() > 0.3:
                g[y, x] = 1.0
    return g


def _enumerate_candidates(grid, piece_type):
    """Enumerate valid (shape, px) pairs for a piece type on a grid."""
    shapes = []
    x_positions = []
    num_rots = len(SHAPES[piece_type])
    for rot in range(num_rots):
        shape = SHAPES[piece_type][rot]
        min_bx = min(bx for bx, _ in shape)
        max_bx = max(bx for bx, _ in shape)
        for col in range(BOARD_WIDTH):
            px = col - min_bx
            if px < 0 or px + max_bx >= BOARD_WIDTH:
                continue
            if not shape_fits(grid, shape, px, 0):
                continue
            shapes.append(shape)
            x_positions.append(px)
    return shapes, x_positions


# --- hard_drop_y_batch ----------------------------------------------

def test_hard_drop_y_batch_empty():
    """All pieces on empty board land at correct rows."""
    grid = _empty_grid()
    shapes, xs = _enumerate_candidates(grid, "O")
    batch_pys = hard_drop_y_batch(grid, shapes, xs)
    scalar_pys = np.array([hard_drop_y(grid, s, x) for s, x in zip(shapes, xs)])
    assert np.array_equal(batch_pys, scalar_pys)


def test_hard_drop_y_batch_with_blocks():
    """Pieces land on top of existing blocks."""
    grid = _empty_grid()
    grid[BOARD_HEIGHT - 3:, :5] = 1.0
    shapes, xs = _enumerate_candidates(grid, "T")
    batch_pys = hard_drop_y_batch(grid, shapes, xs)
    scalar_pys = np.array([hard_drop_y(grid, s, x) for s, x in zip(shapes, xs)])
    assert np.array_equal(batch_pys, scalar_pys)


def test_hard_drop_y_batch_matches_scalar():
    """For all 7 piece types, all rotations, all columns: batch matches scalar."""
    rng = np.random.default_rng(42)
    for piece_type in SHAPES:
        for _ in range(20):
            grid = _random_grid(rng)
            shapes, xs = _enumerate_candidates(grid, piece_type)
            if not shapes:
                continue
            batch_pys = hard_drop_y_batch(grid, shapes, xs)
            scalar_pys = np.array([hard_drop_y(grid, s, x) for s, x in zip(shapes, xs)])
            assert np.array_equal(batch_pys, scalar_pys), (
                f"{piece_type}: {batch_pys} vs {scalar_pys}"
            )


def test_hard_drop_y_batch_empty_board_all_pieces():
    """Empty board: every piece type, every rotation, every column."""
    grid = _empty_grid()
    for piece_type in SHAPES:
        shapes, xs = _enumerate_candidates(grid, piece_type)
        batch_pys = hard_drop_y_batch(grid, shapes, xs)
        scalar_pys = np.array([hard_drop_y(grid, s, x) for s, x in zip(shapes, xs)])
        assert np.array_equal(batch_pys, scalar_pys), f"{piece_type} mismatch"


# --- place_and_clear_batch ------------------------------------------

def test_place_and_clear_batch_no_lines():
    """Place O-piece on empty board, no lines cleared."""
    grid = _empty_grid()
    shape = SHAPES["O"][0]
    shapes = [shape]
    xs = [0]
    pys = [hard_drop_y(grid, shape, 0)]
    batch_grids, batch_lines = place_and_clear_batch(grid, shapes, xs, pys)
    scalar_grid, scalar_lines = place_and_clear(grid, shape, xs[0], pys[0])
    assert batch_lines[0] == scalar_lines
    assert np.array_equal(batch_grids[0], scalar_grid)


def test_place_and_clear_batch_with_lines():
    """Place pieces to fill bottom row, line clears."""
    grid = _empty_grid()
    grid[BOARD_HEIGHT - 1, :8] = 1.0
    # O-piece fills columns 8-9, completing the bottom row
    shape = SHAPES["O"][0]
    xs = [8]
    py = hard_drop_y(grid, shape, 8)
    batch_grids, batch_lines = place_and_clear_batch(grid, [shape], xs, [py])
    scalar_grid, scalar_lines = place_and_clear(grid, shape, xs[0], py)
    assert int(batch_lines[0]) == int(scalar_lines)
    assert np.array_equal(batch_grids[0], scalar_grid)


def test_place_and_clear_batch_matches_scalar():
    """For all 7 piece types, batch matches scalar (grid + lines_cleared)."""
    rng = np.random.default_rng(42)
    for piece_type in SHAPES:
        for _ in range(20):
            grid = _random_grid(rng)
            shapes, xs = _enumerate_candidates(grid, piece_type)
            if not shapes:
                continue
            pys = [hard_drop_y(grid, s, x) for s, x in zip(shapes, xs)]
            batch_grids, batch_lines = place_and_clear_batch(grid, shapes, xs, pys)
            for i in range(len(shapes)):
                sg, sl = place_and_clear(grid, shapes[i], xs[i], pys[i])
                assert int(batch_lines[i]) == int(sl), f"{piece_type} lines mismatch"
                assert np.array_equal(batch_grids[i], sg), f"{piece_type} grid mismatch"


def test_place_and_clear_batch_preserves_input():
    """Base grid not mutated."""
    grid = _empty_grid()
    grid[BOARD_HEIGHT - 1, :5] = 1.0
    grid_copy = grid.copy()
    shape = SHAPES["I"][0]
    xs = [5]
    py = hard_drop_y(grid, shape, 5)
    place_and_clear_batch(grid, [shape], xs, [py])
    assert np.array_equal(grid, grid_copy)


# --- _best_next_placement batch equivalence -------------------------

def test_best_next_placement_batch_matches_scalar():
    """Batched _best_next_placement produces same result as scalar loop.

    Recreates the scalar logic and compares against the batch version
    used in AIState._best_next_placement for diverse board states.
    """
    rng = np.random.default_rng(123)
    for piece_type in SHAPES:
        for _ in range(10):
            grid = _random_grid(rng)
            # Scalar version
            best_grid_scalar = grid
            best_val = float("inf")
            num_rots = len(SHAPES[piece_type])
            for rot in range(num_rots):
                shape = SHAPES[piece_type][rot]
                min_bx = min(bx for bx, _ in shape)
                max_bx = max(bx for bx, _ in shape)
                for col in range(BOARD_WIDTH):
                    px = col - min_bx
                    if px < 0 or px + max_bx >= BOARD_WIDTH:
                        continue
                    py = hard_drop_y(grid, shape, px)
                    if py < 0:
                        continue
                    sim_grid, _ = place_and_clear(grid, shape, px, py)
                    val = dellacherie_value(sim_grid)
                    if val < best_val:
                        best_val = val
                        best_grid_scalar = sim_grid

            # Batch version
            shapes = []
            x_positions = []
            for rot in range(num_rots):
                shape = SHAPES[piece_type][rot]
                min_bx = min(bx for bx, _ in shape)
                max_bx = max(bx for bx, _ in shape)
                for col in range(BOARD_WIDTH):
                    px = col - min_bx
                    if px < 0 or px + max_bx >= BOARD_WIDTH:
                        continue
                    shapes.append(shape)
                    x_positions.append(px)
            if not shapes:
                assert np.array_equal(best_grid_scalar, grid)
                continue
            py_batch = hard_drop_y_batch(grid, shapes, x_positions)
            valid = py_batch >= 0
            if not valid.any():
                assert np.array_equal(best_grid_scalar, grid)
                continue
            v_shapes = [s for s, v in zip(shapes, valid) if v]
            v_xs = [x for x, v in zip(x_positions, valid) if v]
            v_pys = [int(y) for y, v in zip(py_batch, valid) if v]
            sim_grids, _ = place_and_clear_batch(grid, v_shapes, v_xs, v_pys)
            vals = dellacherie_value_batch(sim_grids)
            best_idx = int(np.argmin(vals))
            best_grid_batch = sim_grids[best_idx]

            assert np.array_equal(best_grid_batch, best_grid_scalar), (
                f"{piece_type}: batch and scalar produce different best grids"
            )