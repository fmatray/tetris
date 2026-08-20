"""Tests for Tetromino: type, shape, rotation, movement."""

from tetris.game.tetromino import SHAPES, Tetromino


def test_default_type_is_valid():
    t = Tetromino()
    assert t.type in SHAPES


def test_explicit_type():
    t = Tetromino("I")
    assert t.type == "I"


def test_get_blocks_returns_coordinates():
    t = Tetromino("O")
    blocks = t.get_blocks()
    # O-piece has 4 blocks
    assert len(blocks) == 4
    # Each block is (x+bx, y+by)
    for bx, by in blocks:
        assert isinstance(bx, int)
        assert isinstance(by, int)


def test_rotate_changes_shape():
    t = Tetromino("T")
    initial_shape = t.shape
    t.rotate(1)
    assert t.shape != initial_shape or len(SHAPES["T"]) == 1


def test_rotate_wraps_around():
    t = Tetromino("T")
    shapes = SHAPES["T"]
    # Rotate enough times to cycle back
    for _ in range(len(shapes)):
        t.rotate(1)
    # After a full cycle, shape should match the initial rotation
    t2 = Tetromino("T")
    assert t.shape == t2.shape


def test_move_updates_position():
    t = Tetromino("I")
    initial_x = t.x
    initial_y = t.y
    t.move(2, 3)
    assert t.x == initial_x + 2
    assert t.y == initial_y + 3
