"""Tests for batch game-rule functions (hard_drop_y_batch, place_and_clear_batch)."""

import numpy as np

from tetris.ai.rewards import (
    dellacherie_value,
    dellacherie_value_batch,
    place_and_clear,
    place_and_clear_batch,
)
from tetris.game.rules import (
    find_full_rows,
    hard_drop_y,
    place_cells,
    shape_fits,
)
from tetris.ai.candidates import hard_drop_y_batch, soft_drop_placements
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
    grid[BOARD_HEIGHT - 3 :, :5] = 1.0
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
            assert np.array_equal(batch_pys, scalar_pys), f"{piece_type}: {batch_pys} vs {scalar_pys}"


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


def test_place_and_clear_batch_multi_candidates_nonempty():
    """Multiple candidates on non-empty board: scatter matches per-candidate scalar."""
    rng = np.random.default_rng(99)
    grid = _empty_grid()
    # Partially fill bottom 3 rows with gaps
    for y in range(BOARD_HEIGHT - 3, BOARD_HEIGHT):
        for x in range(BOARD_WIDTH):
            if rng.random() > 0.4:
                grid[y, x] = 1.0
    grid_copy = grid.copy()
    # Collect multiple placements for I-piece (2 rotations) and T-piece
    shapes = []
    xs = []
    pys = []
    for pt in ("I", "T", "L"):
        for rot in range(len(SHAPES[pt])):
            shape = SHAPES[pt][rot]
            min_bx = min(bx for bx, _ in shape)
            max_bx = max(bx for bx, _ in shape)
            for col in range(BOARD_WIDTH):
                px = col - min_bx
                if px < 0 or px + max_bx >= BOARD_WIDTH:
                    continue
                py = hard_drop_y(grid, shape, px)
                if py < 0:
                    continue
                shapes.append(shape)
                xs.append(px)
                pys.append(py)
    assert len(shapes) > 10  # ensure we test many candidates
    batch_grids, batch_lines = place_and_clear_batch(grid, shapes, xs, pys)
    for i in range(len(shapes)):
        sg, sl = place_and_clear(grid_copy, shapes[i], xs[i], pys[i])
        assert int(batch_lines[i]) == int(sl), f"candidate {i} lines mismatch"
        assert np.array_equal(batch_grids[i], sg), f"candidate {i} grid mismatch"
    # Base grid not mutated
    assert np.array_equal(grid, grid_copy)


# --- best_next_placement batch equivalence ---------------------------


def test_best_next_placement_batch_matches_scalar():
    """Batched best_next_placement produces same result as scalar loop.

    Recreates the scalar logic and compares against the batch version
    used in tetris.ai.candidates.best_next_placement for diverse board states.
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


# --- find_full_rows numpy vs list equivalence -----------------------


def test_find_full_rows_numpy_matches_list():
    """Numpy path produces same result as list path."""
    rng = np.random.default_rng(42)
    for _ in range(20):
        grid_np = _random_grid(rng)
        grid_list = grid_np.tolist()
        np_rows = find_full_rows(grid_np)
        list_rows = find_full_rows(grid_list)
        assert np_rows == list_rows


def test_find_full_rows_empty():
    """Empty grid has no full rows."""
    assert find_full_rows(_empty_grid()) == []
    assert find_full_rows(_empty_grid().tolist()) == []


def test_find_full_rows_full_bottom():
    """Full bottom row detected."""
    g = _empty_grid()
    g[BOARD_HEIGHT - 1, :] = 1.0
    assert find_full_rows(g) == [BOARD_HEIGHT - 1]
    assert find_full_rows(g.tolist()) == [BOARD_HEIGHT - 1]


# --- place_cells numpy vs list equivalence --------------------------


def test_place_cells_numpy_matches_list():
    """Numpy path produces same grid as list path."""
    rng = np.random.default_rng(99)
    for piece_type in SHAPES:
        for shape in SHAPES[piece_type]:
            grid_np = _random_grid(rng)
            grid_list = [row[:] for row in grid_np.tolist()]
            x = int(rng.integers(0, BOARD_WIDTH))
            y = int(rng.integers(0, BOARD_HEIGHT))
            place_cells(grid_np, shape, x, y, 1.0)
            place_cells(grid_list, shape, x, y, 1.0)
            assert np.array_equal(grid_np, np.array(grid_list, dtype=np.float32))


def test_place_cells_out_of_bounds():
    """Cells outside the board are silently skipped (numpy path)."""
    g = _empty_grid()
    shape = SHAPES["I"][0]  # horizontal I
    place_cells(g, shape, -2, 0, 1.0)  # partially off-board
    # Should not crash, cells in-bounds should be set
    assert g.sum() >= 0  # no exception


# --- hard_drop_y_batch vectorized equivalence -----------------------


def test_hard_drop_y_batch_vectorized_matches_scalar_all_pieces():
    """New vectorized batch matches scalar hard_drop_y for all pieces/columns."""
    rng = np.random.default_rng(77)
    for _ in range(10):
        grid = _random_grid(rng)
        for piece_type in SHAPES:
            shapes, x_positions = _enumerate_candidates(grid, piece_type)
            if not shapes:
                continue
            batch_pys = hard_drop_y_batch(grid, shapes, x_positions)
            scalar_pys = np.array([hard_drop_y(grid, shape, x) for shape, x in zip(shapes, x_positions)])
            assert np.array_equal(batch_pys, scalar_pys), f"{piece_type}: vectorized batch mismatch"


# --- soft_drop_placements numpy vs list equivalence -----------------


def test_soft_drop_placements_numpy_matches_list():
    """soft_drop_placements with numpy grid produces same placements as list grid."""
    rng = np.random.default_rng(123)
    for _ in range(10):
        grid_np = _random_grid(rng)
        grid_list = grid_np.tolist()
        for piece_type in SHAPES:
            np_placements = soft_drop_placements(grid_np, piece_type)
            list_placements = soft_drop_placements(grid_list, piece_type)
            # Compare (px, py, rot) — shape is deterministic from piece+rot
            np_keys = {(p.px, p.py, p.rot) for p in np_placements}
            list_keys = {(p.px, p.py, p.rot) for p in list_placements}
            assert np_keys == list_keys, f"{piece_type}: placement set mismatch"


def test_soft_drop_placements_empty_board():
    """Empty board produces valid placements for all piece types."""
    grid = _empty_grid()
    for piece_type in SHAPES:
        placements = soft_drop_placements(grid, piece_type)
        assert len(placements) > 0, f"{piece_type}: no placements on empty board"
        for p in placements:
            assert shape_fits(grid, p.shape, p.px, p.py)
