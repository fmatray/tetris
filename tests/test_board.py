"""Tests for Board: collision, locking, line clearing, handicap."""

import pytest

from tetris.game.board import Board
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
        1
        for y in range(BOARD_HEIGHT - 6, BOARD_HEIGHT)
        for x in range(BOARD_WIDTH)
        if board.grid[y][x] is not None
    )
    assert gray_count > 0