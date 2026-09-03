"""PUCT tree search over piece placements, guided by the V-network.

AlphaZero-style: no random rollouts — the DQN V-function evaluates leaf
boards. The root uses the soft-drop candidate placements from
:func:`tetris.ai.candidates.get_candidate_states`; deeper levels use
cheap hard-drop-only enumeration (the same approximation as the greedy
look-ahead). Piece types beyond the preview queue are sampled uniformly
from the injected ``rng`` so searches are reproducible.

Nodes are plain dicts (no classes) to keep ``docs/class_diagram.md``
untouched: ``{"children": None | list, "grid", "queue", "prior",
"visits", "value_sum"}``.
"""

from __future__ import annotations

import math
import random
from collections.abc import Callable, Sequence
from typing import Any, TypeAlias

import numpy as np

from tetris.ai.candidates import Placement, hard_drop_y_batch, iter_column_positions
from tetris.ai.rewards import extract_features_batch, place_and_clear_batch
from tetris.game.shapes import SHAPES_TYPES

C_PUCT: float = 1.5
TERMINAL_VALUE: float = -1.0

ValuesFn = Callable[[np.ndarray], np.ndarray]

# Tree node: children (None = unexpanded, [] = terminal), grid, piece queue,
# root prior, visit count, accumulated value.
_Node: TypeAlias = dict[str, Any]


def _priors(pick_values: np.ndarray) -> np.ndarray:
    """Root priors: softmax over El-Tetris values, scale-free."""
    v = np.asarray(pick_values, dtype=np.float64)
    std = v.std()
    if std > 0:
        v = (v - v.mean()) / std
    e = np.exp(v - np.max(v))
    return e / e.sum()


def _expand(
    grid: np.ndarray,
    queue: Sequence[str],
    values_fn: ValuesFn,
    rng: random.Random,
) -> tuple[list[_Node], float]:
    """Create the children of a node: hard-drop placements of the next piece.

    Returns ``(children, backprop_value)`` where the value is the mean V of
    the boards one placement deeper, or ``TERMINAL_VALUE`` when no
    placement fits (top-out).
    """
    piece = queue[0] if queue else rng.choice(SHAPES_TYPES)
    next_piece = queue[1] if len(queue) > 1 else "I"
    shapes: list[list[tuple[int, int]]] = []
    xs: list[int] = []
    for shape, _rot, px in iter_column_positions(piece):
        shapes.append(shape)
        xs.append(px)
    if not shapes:
        return [], TERMINAL_VALUE
    pys = hard_drop_y_batch(grid, shapes, xs)
    grids, lines = place_and_clear_batch(grid, shapes, xs, [int(y) for y in pys])
    feats = extract_features_batch(grids, lines, [next_piece] * len(shapes))
    child_values = values_fn(feats)
    prior = 1.0 / len(shapes)
    children: list[_Node] = [
        {
            "children": None,
            "grid": grids[i],
            "queue": list(queue[1:]),
            "prior": prior,
            "visits": 0,
            "value_sum": 0.0,
        }
        for i in range(len(shapes))
    ]
    return children, float(np.mean(child_values))


def mcts_select(
    values_fn: ValuesFn,
    base_grid: np.ndarray,
    placements: Sequence[Placement],
    pick_values: np.ndarray,
    upcoming_types: Sequence[str],
    hold_piece_type: str | None,
    iterations: int,
    rng: random.Random,
    c_puct: float = C_PUCT,
) -> int:
    """Pick a root placement index via PUCT tree search.

    Args:
        values_fn: batched V evaluation, ``(N, 17)`` features -> ``(N,)`` values.
        base_grid: current board grid.
        placements: root candidate placements (soft-drop enumeration).
        pick_values: per-placement El-Tetris values -> root priors.
        upcoming_types: known piece sequence after the current piece
            (``[next, *preview]``); hold candidates with an empty hold shift
            this queue by one, mirroring ``get_candidate_states``.
        hold_piece_type: currently held piece type (``None`` = empty hold).
        iterations: search budget (one tree walk + one expansion each).
        rng: piece-type sampling beyond the preview queue.
        c_puct: exploration constant.

    Returns:
        Index into ``placements`` (most-visited root child).
    """
    n = len(placements)
    if n <= 1:
        return 0
    grids, _lines = place_and_clear_batch(
        base_grid,
        [p.shape for p in placements],
        [p.px for p in placements],
        [p.py for p in placements],
    )
    queues = [
        list(upcoming_types[1:]) if (p.hold and hold_piece_type is None) else list(upcoming_types) for p in placements
    ]
    priors = _priors(pick_values)
    root_children: list[_Node] = [
        {
            "children": None,
            "grid": grids[i],
            "queue": queues[i],
            "prior": float(priors[i]),
            "visits": 0,
            "value_sum": 0.0,
        }
        for i in range(n)
    ]
    root: _Node = {"children": root_children, "visits": 0}

    for _ in range(iterations):
        node = root
        path: list[_Node] = []
        while node["children"]:
            child = max(
                node["children"],
                key=lambda ch: (
                    (ch["value_sum"] / ch["visits"] if ch["visits"] else 0.0)
                    + c_puct * ch["prior"] * math.sqrt(node["visits"]) / (1 + ch["visits"])
                ),
            )
            node = child
            path.append(node)
        # Leaf. First visit expands it; the backprop value is the mean V of
        # the boards one placement deeper (no rollouts). A terminal leaf
        # (top-out, expanded to no children) keeps TERMINAL_VALUE forever.
        if node["children"] is None:
            node["children"], value = _expand(node["grid"], node["queue"], values_fn, rng)
        else:
            value = TERMINAL_VALUE
        node["visits"] += 1
        node["value_sum"] += value
        root["visits"] += 1
        for ancestor in path[:-1]:
            ancestor["visits"] += 1
            ancestor["value_sum"] += value

    best = root_children[0]["visits"]
    best_idx = 0
    for i in range(1, n):
        if root_children[i]["visits"] > best:
            best = root_children[i]["visits"]
            best_idx = i
    return best_idx
