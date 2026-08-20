"""Tests for Board: collision, locking, line clearing, handicap."""

import pytest

from tetris.game.board import Board
from tetris.game.shapes import get_shape_rot, num_shape_rot
from tetris.game.tetromino import Tetromino
from tetris.settings import BOARD_HEIGHT, BOARD_WIDTH


@pytest.fixture
def board():
    return Board()


@pytest.fixture
def piece():
    return Tetromino("I")


# --- is_valid_move --------------------------------------------------


def test_empty_board_valid_spawn(board, piece):
    """A new piece at spawn position is valid on an empty board."""
    assert board.is_valid_move(piece) is True


def test_collision_with_floor(board, piece):
    """Piece at the bottom row cannot move further down."""
    piece.y = BOARD_HEIGHT - 1
    # Move down off the bottom — the I-piece spans multiple rows
    assert board.is_valid_move(piece, dy=1) is False


def test_collision_with_wall(board, piece):
    """Piece cannot move beyond the left wall."""
    piece.x = -1
    assert board.is_valid_move(piece) is False


def test_collision_with_locked_block(board):
    """Piece cannot overlap a locked cell."""
    blocker = Tetromino("O")
    blocker.x = 0
    blocker.y = BOARD_HEIGHT - 2
    board.lock_tetromino(blocker)
    # An O-piece at the same position should be invalid
    other = Tetromino("O")
    other.x = 0
    other.y = BOARD_HEIGHT - 2
    assert board.is_valid_move(other) is False


def test_is_valid_move_with_rotation(board):
    """The rotation parameter selects the correct shape."""
    t = Tetromino("T")
    # T-piece rotation 1 should be valid at spawn
    assert board.is_valid_move(t, rotation=1) is True
    # Rotation 2 as well
    assert board.is_valid_move(t, rotation=2) is True


# --- lock_tetromino -------------------------------------------------


def test_lock_tetromino_fills_grid(board):
    """After locking, the piece's cells are occupied in the grid."""
    o = Tetromino("O")
    o.x = 0
    o.y = BOARD_HEIGHT - 2
    board.lock_tetromino(o)
    # O-piece occupies (0, H-2), (1, H-2), (0, H-1), (1, H-1)
    assert board.grid[BOARD_HEIGHT - 2][0] is not None
    assert board.grid[BOARD_HEIGHT - 2][1] is not None
    assert board.grid[BOARD_HEIGHT - 1][0] is not None
    assert board.grid[BOARD_HEIGHT - 1][1] is not None


# --- clear_lines ----------------------------------------------------


def test_clear_lines_removes_full_rows(board):
    """Fill the bottom row, lock a piece, and verify the row is cleared."""
    # Fill bottom row except one cell
    for x in range(BOARD_WIDTH - 1):
        board.grid[BOARD_HEIGHT - 1][x] = (255, 0, 0)
    # Place an O-piece to fill the last 2 cells (but O is 2 wide)
    # Instead, fill the last cell manually and test clear_lines directly
    board.grid[BOARD_HEIGHT - 1][BOARD_WIDTH - 1] = (255, 0, 0)
    cleared, data = board.clear_lines()
    assert cleared == 1
    assert len(data) == 1


def test_clear_lines_returns_data(board):
    """clear_lines returns (count, row_data) tuple."""
    cleared, data = board.clear_lines()
    assert cleared == 0
    assert data == []


def test_clear_lines_no_full_rows(board):
    """No lines cleared when the board is incomplete."""
    board.grid[BOARD_HEIGHT - 1][0] = (255, 0, 0)
    cleared, _data = board.clear_lines()
    assert cleared == 0


# --- apply_handicap -------------------------------------------------


def test_apply_handicap_level_0(board):
    """Level 0 handicap leaves the board empty."""
    board.apply_handicap(0)
    for y in range(BOARD_HEIGHT):
        for x in range(BOARD_WIDTH):
            assert board.grid[y][x] is None


def test_apply_handicap_level_3(board):
    """Level 3 fills 6 bottom rows with partial gray blocks."""
    board.apply_handicap(3)
    # Rows above the filled zone should be empty
    for y in range(BOARD_HEIGHT - 7):
        for x in range(BOARD_WIDTH):
            assert board.grid[y][x] is None
    # The bottom rows should have at least some gray cells
    gray_count = sum(
        1 for y in range(BOARD_HEIGHT - 6, BOARD_HEIGHT) for x in range(BOARD_WIDTH) if board.grid[y][x] is not None
    )
    assert gray_count > 0


# --- try_rotate -----------------------------------------------------


def test_try_rotate_t_cw_success(board):
    """T-piece rotates CW from rotation 0 to rotation 1."""
    t = Tetromino("T")
    t.x = 3
    t.y = 5
    assert board.try_rotate(t, 1) is True
    assert t.rotation == 1
    # shape should match rotation 1
    assert t.shape == get_shape_rot("T", 1)


def test_try_rotate_blocked_returns_false(board):
    """Rotation that cannot fit even with wall kicks returns False and leaves piece unchanged."""
    t = Tetromino("T")
    t.x = 0
    t.y = BOARD_HEIGHT - 3
    # T rot0→rot1 kicks: [(0,0),(-1,0),(-1,1),(0,-2),(-1,-2)]
    # rot1 shape: [(1,0),(1,1),(2,1),(1,2)]
    # Block every cell each kick position would occupy so none fits.
    kicks = [(0, 0), (-1, 0), (-1, 1), (0, -2), (-1, -2)]
    for dx, dy in kicks:
        for bx, by in get_shape_rot("T", 1):
            cx, cy = t.x + dx + bx, t.y - dy + by
            if 0 <= cx < BOARD_WIDTH and 0 <= cy < BOARD_HEIGHT:
                board.grid[cy][cx] = (255, 0, 0)
    from_rot = t.rotation
    result = board.try_rotate(t, 1)
    assert result is False
    assert t.rotation == from_rot


def test_try_rotate_wall_kick(board):
    """SRS wall kick moves piece when direct rotation is blocked."""
    t = Tetromino("T")
    t.x = 0
    t.y = 5
    # Block the direct-rotation cell (1,5) so kick (0,0) fails
    board.grid[5][1] = (255, 0, 0)
    # Kick (-1,0) shifts left to x=-1, which fits
    result = board.try_rotate(t, 1)
    assert result is True
    assert t.rotation == 1
    assert t.x == -1  # wall-kicked left
    assert board.is_valid_move(t) is True


def test_try_rotate_o_piece(board):
    """O-piece rotation succeeds (it has only one shape)."""
    o = Tetromino("O")
    o.x = 4
    o.y = 5
    assert board.try_rotate(o, 1) is True
    assert o.rotation == 1 % num_shape_rot("O")


# --- is_tspin -------------------------------------------------------


def test_is_tspin_with_three_corners_filled(board):
    """T-piece with 3 of 4 corners filled is a T-spin."""
    t = Tetromino("T")
    t.rotation = 0
    t.x = 0
    t.y = BOARD_HEIGHT - 3
    # T at rotation 0: center at (1, H-2); corners at (0,H-3),(2,H-3),(0,H-1),(2,H-1)
    # Fill 3 of the 4 corners (leave one empty)
    board.grid[BOARD_HEIGHT - 3][0] = (255, 0, 0)
    board.grid[BOARD_HEIGHT - 1][0] = (255, 0, 0)
    board.grid[BOARD_HEIGHT - 1][2] = (255, 0, 0)
    assert board.is_tspin(t) is True


def test_is_tspin_non_t_piece_returns_false(board):
    """A non-T piece never reports a T-spin."""
    s = Tetromino("S")
    s.x = 0
    s.y = BOARD_HEIGHT - 3
    assert board.is_tspin(s) is False


def test_is_tspin_fewer_than_three_corners(board):
    """T-piece with only 2 corners filled is not a T-spin."""
    t = Tetromino("T")
    t.rotation = 0
    t.x = 0
    t.y = BOARD_HEIGHT - 3
    # Only fill 2 corners
    board.grid[BOARD_HEIGHT - 3][0] = (255, 0, 0)
    board.grid[BOARD_HEIGHT - 1][0] = (255, 0, 0)
    assert board.is_tspin(t) is False


def test_is_tspin_wall_counts_as_filled(board):
    """Walls (out-of-bounds corners) count as filled for T-spin detection."""
    t = Tetromino("T")
    t.rotation = 0
    # Place so some corners are off-board (x=-1 gives cx=0; corner cx-1=-1 is wall)
    t.x = -1
    t.y = 5
    # Two corners are walls (left side), fill one more on the right
    board.grid[5 + 2][1] = (255, 0, 0)  # (cx+1, cy+1) = (1, 7)
    assert board.is_tspin(t) is True


# --- hard_drop ------------------------------------------------------


def test_hard_drop_to_bottom(board):
    """A piece hard-drops to the lowest valid row on an empty board."""
    o = Tetromino("O")
    o.x = 0
    o.y = 0
    distance = board.hard_drop(o)
    # O-piece is 2 rows tall; bottom cell lands at BOARD_HEIGHT-1
    assert o.y == BOARD_HEIGHT - 2
    assert distance == BOARD_HEIGHT - 2


def test_hard_drop_onto_existing_blocks(board):
    """A piece hard-drops onto existing blocks, stopping above them."""
    # Place a single block at column 0, bottom row
    board.grid[BOARD_HEIGHT - 1][0] = (255, 0, 0)
    board.grid[BOARD_HEIGHT - 2][0] = (255, 0, 0)
    o = Tetromino("O")
    o.x = 0
    o.y = 0
    board.hard_drop(o)
    # O-piece (2 tall) should land so its bottom rests on top of the stack
    assert o.y == BOARD_HEIGHT - 4


def test_hard_drop_under_overhang(board):
    """A piece already under an overhang drops down, not up through it."""
    # Overhang: blocks at column 1, rows 10-11; column 0 is open below
    board.grid[10][1] = (255, 0, 0)
    board.grid[11][1] = (255, 0, 0)
    # I-piece horizontal at y=15, well below the overhang
    i = Tetromino("I")
    i.x = 0
    i.y = 15
    distance = board.hard_drop(i)
    # Piece must not move up; it should drop to the bottom
    assert i.y >= 15
    assert distance >= 0


# --- lock_tetromino with line clear ---------------------------------


def test_lock_tetromino_clears_lines(board):
    """Locking a piece that completes a row triggers a line clear."""
    # Fill bottom row except cols 0,1
    for x in range(2, BOARD_WIDTH):
        board.grid[BOARD_HEIGHT - 1][x] = (255, 0, 0)
    o = Tetromino("O")
    o.x = 0
    o.y = BOARD_HEIGHT - 2
    cleared, _data = board.lock_tetromino(o)
    assert cleared == 1


def test_lock_tetromino_no_clear(board):
    """Locking a piece that does not complete a row clears nothing."""
    o = Tetromino("O")
    o.x = 5
    o.y = 0
    board.hard_drop(o)
    cleared, _data = board.lock_tetromino(o)
    assert cleared == 0
