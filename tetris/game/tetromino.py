"""Tetromino piece model."""

import random

from tetris.settings import BOARD_WIDTH, SHAPES, SHAPES_COLORS


class Tetromino:
    """A falling Tetris piece.

    Holds a type, color, rotation index, and board position. Knows its
    current block coordinates but nothing about the board or collision.
    """

    def __init__(self) -> None:
        self.type = random.choice(list(SHAPES.keys()))
        self.color = SHAPES_COLORS[self.type]
        self.rotation = 0
        self.x = BOARD_WIDTH // 2 - 2
        self.y = 0
        self.shape = self.get_current_shape()

    def get_current_shape(self):
        shapes = SHAPES[self.type]
        return shapes[self.rotation % len(shapes)]

    def rotate(self, direction: int = 1) -> None:
        self.rotation += direction
        self.shape = self.get_current_shape()

    def move(self, dx: int, dy: int) -> None:
        self.x += dx
        self.y += dy

    def get_blocks(self):
        return [(self.x + bx, self.y + by) for bx, by in self.shape]