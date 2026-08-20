"""Tetromino piece model."""

import random

from tetris.game.shapes import SHAPES, SHAPES_TYPES
from tetris.settings import BOARD_WIDTH, SHAPES_COLORS


class Tetromino:
    """A falling Tetris piece.

    Holds a type, color, rotation index, and board position. Knows its
    current block coordinates but nothing about the board or collision.
    """

    def __init__(self, piece_type: str | None = None) -> None:
        """Create a tetromino at spawn position.

        Args:
            piece_type: Piece key into ``SHAPES`` (see ``tetris.game.shapes``).
                If ``None``, a random type is chosen.
        """
        self.type = piece_type if piece_type is not None else random.choice(SHAPES_TYPES)
        self.color = SHAPES_COLORS[self.type]
        self.rotation = 0
        self.x = BOARD_WIDTH // 2 - 2
        self.y = 0
        self.shape = self.get_current_shape()

    def get_current_shape(self):
        """Return the block-offset list for the current rotation."""
        shapes = SHAPES[self.type]
        return shapes[self.rotation % len(shapes)]

    def rotate(self, direction: int = 1) -> None:
        """Advance the rotation index and refresh ``self.shape``.

        Args:
            direction: ``+1`` for CW, ``-1`` for CCW. Wraps modulo rotation count.
        """
        self.rotation += direction
        self.shape = self.get_current_shape()

    def move(self, dx: int, dy: int) -> None:
        """Shift the piece by ``(dx, dy)`` board cells.

        Args:
            dx: Horizontal displacement (positive = right).
            dy: Vertical displacement (positive = down).
        """
        self.x += dx
        self.y += dy

    def get_blocks(self):
        """Return absolute board coordinates of every cell in the piece."""
        return [(self.x + bx, self.y + by) for bx, by in self.shape]
