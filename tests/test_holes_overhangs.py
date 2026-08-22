"""Tests for shared hole/overhang detection (rules + Board)."""

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import numpy as np

from tetris.game.board import Board
from tetris.game import rules
from tetris.game.rules import (
    _covered_cells,
    count_overhangs,
    find_holes,
    find_overhangs,
)


def _list_grid(rows):
    return [[(1 if c == "F" else 0) for c in r] for r in rows]


def _np_grid(rows):
    return np.array(_list_grid(rows))


# --- core definitions -------------------------------------------------


def test_holes_only():
    g = _list_grid(["FFF", ".F.", ".F."])
    assert find_holes(g) == {(0, 1), (0, 2), (2, 1), (2, 2)}
    assert find_overhangs(g) == set()


def test_overhang_only():
    g = _list_grid([".F.", ".F.", "..."])
    assert find_holes(g) == set()
    assert find_overhangs(g) == {(1, 2)}


def test_mixed():
    g = _list_grid(["FFF..", ".F..F", ".F..."])
    assert find_holes(g) == {(0, 1), (0, 2)}
    assert find_overhangs(g) == {(2, 1), (2, 2), (4, 2)}


def test_empty_and_full():
    assert find_holes([[0, 0], [0, 0]]) == set()
    assert find_overhangs([[0, 0], [0, 0]]) == set()
    assert find_holes([[1, 1], [1, 1]]) == set()
    assert find_overhangs([[1, 1], [1, 1]]) == set()


def test_holes_overhangs_partition_covered():
    g = _np_grid(["FFF..", ".F..F", ".F..."])
    covered = _covered_cells(g)
    h = find_holes(g)
    o = find_overhangs(g)
    assert h.isdisjoint(o)
    assert (h | o) == covered


def test_numpy_matches_list():
    rows = ["FFF..", ".F..F", ".F..."]
    gl, gn = _list_grid(rows), _np_grid(rows)
    assert find_holes(gl) == find_holes(gn)
    assert find_overhangs(gl) == find_overhangs(gn)
    assert count_overhangs(gl) == count_overhangs(gn) == 3


# --- Board wrappers ---------------------------------------------------


def test_board_find_holes_overhangs():
    board = Board()
    g = board.grid
    for y in range(22):
        g[y][0] = (255, 0, 0)
        g[y][1] = (255, 0, 0)
        g[y][2] = (255, 0, 0)
    # unreachable holes at bottom of capped columns 0/1
    g[21][0] = None
    g[21][1] = None
    # reachable overhang under a ledge in column 5
    g[0][5] = None
    g[1][5] = (0, 255, 0)
    for y in range(3, 22):
        g[y][5] = (0, 255, 0)
    assert board.find_holes() == {(0, 21), (1, 21)}
    assert board.find_overhangs() == {(5, 2)}
    assert board.find_holes() == rules.find_holes(g)
    assert board.find_overhangs() == rules.find_overhangs(g)
