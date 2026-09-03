"""Imitation warm-start: pre-train the V-network from human placements.

Replays recorded human games (see ``tetris.game.imitation``), enumerates
the candidate placements the AI would consider at each move, and pushes
the V-value of the placement the human chose above the alternatives with a
softmax cross-entropy ranking loss. Best-effort: un-replayable moves are
skipped, a missing log is a no-op, and pretraining never crashes startup.
"""

from __future__ import annotations

import numpy as np
import torch

from tetris.ai.agent import DQNAgent
from tetris.ai.candidates import gen_placements, get_candidate_states
from tetris.game.imitation import read_placements
from tetris.game.rules import hard_drop_y, place_cells
from tetris.game.shapes import get_shape_rot
from tetris.logger import get_logger

_logger = get_logger("imitation")

# Softmax temperature for the ranking loss. Higher = softer push.
_TAU = 1.0
_PIECE_TYPES = frozenset({"I", "J", "L", "O", "S", "T", "Z"})


def imitation_pretrain(
    agent: DQNAgent,
    path: str | None = None,
    epochs: int = 3,
) -> int:
    """Pre-train ``agent`` from recorded human placements.

    Rebuilds each recorded game board move by move, enumerates the
    placements the AI would consider at that point, and trains the
    V-network with a ranking loss so that ``V(chosen board)`` outranks all
    alternatives.

    Args:
        agent: The agent whose online net receives the gradients.
        path: Placements JSONL path (default: the shared ``PLACEMENTS_PATH``).
        epochs: Passes over the recorded games.

    Returns:
        Number of moves trained on (0 if the log is missing or empty).
    """
    records = read_placements() if path is None else read_placements(path)
    if not records:
        _logger.debug("No placement records — imitation warm-start skipped")
        return 0

    games = _split_games(records)
    trained = 0
    net = agent.online_net
    was_training = net.training
    net.train()
    try:
        for _ in range(epochs):
            for moves in games:
                trained += _train_one_game(agent, net, moves)
    except Exception:  # best-effort: never crash agent startup
        _logger.exception("Imitation warm-start failed — skipping")
        return trained
    finally:
        if not was_training:
            net.eval()
    _logger.debug("Imitation warm-start trained on %d moves", trained)
    return trained


def _split_games(records: list[dict]) -> list[list[dict]]:
    """Group records into games: each starts at a ``type: "game"`` header."""
    games: list[list[dict]] = []
    current: list[dict] = []
    for rec in records:
        if rec.get("type") == "game":
            if current:
                games.append(current)
            current = []
        else:
            current.append(rec)
    if current:
        games.append(current)
    return games


def _train_one_game(agent: DQNAgent, net, moves: list[dict]) -> int:
    """Replay one game on a fresh empty grid and train on each move.

    Returns the number of moves trained on. Moves whose recorded
    placement is not among the enumerated candidates (reconstruction
    drift) are skipped, never fatal.
    """
    trained = 0
    grid = np.zeros((22, 10), dtype=np.int8)
    for move in moves:
        piece = move.get("piece")
        if piece not in _PIECE_TYPES:
            continue
        rot = move.get("rot", 0)
        x = move.get("x", 0)
        if _train_one_move(agent, net, grid, piece, rot, x):
            trained += 1
        _apply_placement(grid, piece, rot, x)
    return trained


def _train_one_move(
    agent: DQNAgent,
    net,
    grid: np.ndarray,
    piece: str,
    rot: int,
    x: int,
) -> bool:
    """Ranking-loss update: push V(chosen) above all candidate alternatives.

    Returns True if the move was trained on, False if the recorded
    placement was not among the enumerated candidates (skipped).
    """
    if not any(p.rot == rot and p.px == x for p in gen_placements(grid, piece)):
        return False
    candidates, _, _, placements = get_candidate_states(
        grid, piece, None, "I", [], can_hold=False, lookahead=False, lookahead_depth=1
    )
    if len(candidates) == 0:
        return False
    chosen = next(
        (i for i, p in enumerate(placements) if p.rot == rot and p.px == x and not p.hold),
        None,
    )
    states = torch.as_tensor(candidates, dtype=torch.float32, device=agent.device)
    values = net(states).squeeze(-1)  # (N,)
    target = torch.tensor([chosen], dtype=torch.long, device=agent.device)
    loss = torch.nn.functional.cross_entropy(values.unsqueeze(0) / _TAU, target)
    agent.optimizer.zero_grad()
    loss.backward()
    torch.nn.utils.clip_grad_norm_(net.parameters(), 1.0)
    agent.optimizer.step()
    return True


def _apply_placement(grid: np.ndarray, piece: str, rot: int, x: int) -> None:
    """Apply one recorded placement to the reconstruction grid."""
    shape = get_shape_rot(piece, rot)
    y = hard_drop_y(grid, shape, x)
    if y < 0:
        return
    place_cells(grid, shape, x, y, 1)
    full = (grid != 0).all(axis=1)
    if full.any():
        cleared = grid[~full]
        grid[...] = np.vstack([np.zeros((int(full.sum()), grid.shape[1]), dtype=grid.dtype), cleared])
