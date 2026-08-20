"""Tetromino shape data — SRS rotation states for all 7 piece types."""

# Tetromino shapes — SRS rotation states (0=spawn, 1=CW, 2=180, 3=CCW).
# Coordinate convention: (col, row) within a 4×4 (I) or 3×3 (others) box.
SHAPES: dict[str, list[list[tuple[int, int]]]] = {
    "I": [
        [(0, 1), (1, 1), (2, 1), (3, 1)],
        [(2, 0), (2, 1), (2, 2), (2, 3)],
        [(0, 2), (1, 2), (2, 2), (3, 2)],
        [(1, 0), (1, 1), (1, 2), (1, 3)],
    ],
    "O": [[(0, 0), (1, 0), (0, 1), (1, 1)]],
    "T": [
        [(1, 0), (0, 1), (1, 1), (2, 1)],
        [(1, 0), (1, 1), (2, 1), (1, 2)],
        [(0, 1), (1, 1), (2, 1), (1, 2)],
        [(0, 1), (1, 1), (1, 0), (1, 2)],
    ],
    "S": [
        [(1, 0), (2, 0), (0, 1), (1, 1)],
        [(1, 0), (1, 1), (2, 1), (2, 2)],
        [(1, 1), (2, 1), (0, 2), (1, 2)],
        [(0, 0), (0, 1), (1, 1), (1, 2)],
    ],
    "Z": [
        [(0, 0), (1, 0), (1, 1), (2, 1)],
        [(2, 0), (2, 1), (1, 1), (1, 2)],
        [(0, 1), (1, 1), (1, 2), (2, 2)],
        [(1, 0), (1, 1), (0, 1), (0, 2)],
    ],
    "J": [
        [(0, 0), (0, 1), (1, 1), (2, 1)],
        [(1, 0), (2, 0), (1, 1), (1, 2)],
        [(0, 1), (1, 1), (2, 1), (2, 2)],
        [(1, 0), (1, 1), (0, 2), (1, 2)],
    ],
    "L": [
        [(2, 0), (0, 1), (1, 1), (2, 1)],
        [(1, 0), (1, 1), (1, 2), (2, 2)],
        [(0, 1), (1, 1), (2, 1), (0, 2)],
        [(0, 0), (1, 0), (1, 1), (1, 2)],
    ],
}

SHAPES_TYPES = list(SHAPES.keys())  # ["I", "O", "T", "S", "Z", "J", "L"]


def num_shape_rot(piece_type: str) -> int:
    """Number of rotation states for *piece_type*."""
    return len(SHAPES[piece_type])


def get_shape_rot(piece_type: str, rot: int) -> list[tuple[int, int]]:
    """Cell offsets for *piece_type* at rotation index *rot*."""
    return SHAPES[piece_type][rot]
