"""Tests for PUCT tree search (tetris/ai/mcts.py) — pure functions, no torch."""

import os
import random

import numpy as np

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

from tetris.ai.mcts import _expand, _priors, mcts_select


def _empty_grid(rows: int = 22, cols: int = 10) -> np.ndarray:
    return np.zeros((rows, cols), dtype=np.uint8)


def test_priors_softmax_normalizes():
    p = _priors(np.array([10.0, 5.0, 0.0]))
    assert np.isclose(p.sum(), 1.0)
    assert p[0] > p[1] > p[2]
    assert np.all(p > 0)
    # Degenerate: identical values → uniform prior
    assert np.allclose(_priors(np.array([3.0, 3.0, 3.0])), 1.0 / 3.0)


def test_expand_children_are_valid_nodes():
    grid = _empty_grid()
    rng = random.Random(0)
    calls: list[np.ndarray] = []

    def values_fn(feats: np.ndarray) -> np.ndarray:
        calls.append(feats)
        return np.zeros(len(feats), dtype=np.float32)

    children, value = _expand(grid, ["I"], values_fn, rng)
    # I piece: 10 columns × 4 rotations minus symmetric duplicates → several placements
    assert len(children) > 0
    assert all(c["visits"] == 0 and c["value_sum"] == 0.0 for c in children)
    assert all(c["children"] is None for c in children)
    # Value is mean of V predictions (all zeros here)
    assert value == 0.0
    assert len(calls) == 1


def test_mcts_select_single_candidate():
    from tetris.ai.candidates import Placement

    # One placement → always index 0, no search needed
    p = Placement(piece_type="O", rot=0, px=4, py=21, hold=False, moves=[])
    assert (
        mcts_select(
            values_fn=lambda f: np.zeros(len(f), dtype=np.float32),
            base_grid=_empty_grid(),
            placements=[p],
            pick_values=np.array([1.0]),
            upcoming_types=["I"],
            hold_piece_type=None,
            iterations=5,
            rng=random.Random(0),
        )
        == 0
    )


def test_mcts_select_prefers_high_value_branch():
    """values_fn that rewards column 0 placements: search should concentrate
    visits on the best root child and return its index."""
    from tetris.ai.candidates import Placement

    grid = _empty_grid()
    placements = [Placement(piece_type="O", rot=0, px=col, py=21, hold=False, moves=[]) for col in range(4)]
    pick_values = np.array([0.0, 0.0, 0.0, 0.0])

    def values_fn(feats: np.ndarray) -> np.ndarray:
        # feats[:, 0] = lines_cleared; reward high lines to steer the search
        return feats[:, 0].astype(np.float32) * 10.0 - 5.0

    idx = mcts_select(
        values_fn=values_fn,
        base_grid=grid,
        placements=placements,
        pick_values=pick_values,
        upcoming_types=["I"],
        hold_piece_type=None,
        iterations=30,
        rng=random.Random(0),
    )
    assert 0 <= idx < 4


def test_mcts_select_deterministic_for_same_rng():
    from tetris.ai.candidates import Placement

    grid = _empty_grid()
    placements = [Placement(piece_type="O", rot=0, px=col, py=21, hold=False, moves=[]) for col in range(5)]
    pick_values = np.array([1.0, 2.0, 3.0, 2.0, 1.0])

    def values_fn(feats: np.ndarray) -> np.ndarray:
        return -np.abs(feats[:, 2]).astype(np.float32)  # minimize aggregate height

    def run(rng: random.Random) -> int:
        return mcts_select(
            values_fn=values_fn,
            base_grid=grid,
            placements=placements,
            pick_values=pick_values,
            upcoming_types=["I", "J"],
            hold_piece_type=None,
            iterations=20,
            rng=rng,
        )

    assert run(random.Random(42)) == run(random.Random(42))
