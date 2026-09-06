"""Shared bot move machinery, reused by AIState and ElTetrisState.

``BotMovesMixin`` is stateless with respect to the FSM: it only depends
on the host ``GameState`` providing the attributes/methods listed in
the mixin docstring. This keeps the bot states independent of each
other while guaranteeing a single implementation of candidate
enumeration and BFS move replay.
"""

from __future__ import annotations

import random
from typing import TYPE_CHECKING

import numpy as np

from tetris.settings import BOARD_WIDTH, RESERVE_COLUMN_PENALTY
from tetris.ai.candidates import Placement, get_candidate_states
from tetris.ai.rewards import board_to_grid


if TYPE_CHECKING:
    from tetris.game.board import Board
    from tetris.game.tetromino import Tetromino


def level_select(
    values: np.ndarray,
    misstep: float,
    temp: float,
    rng: random.Random,
) -> int:
    """Argmax with level-based misstep.

    With probability ``misstep`` (skill degradation), sample the placement
    from a softmax over z-normalized values at temperature ``temp`` instead
    of taking the argmax. Scale-free: z-normalization makes ``temp`` work
    for any value range (El-Tetris heuristic or V-network).
    """
    if len(values) < 2 or misstep <= 0.0:
        return int(np.argmax(values))
    if rng.random() < misstep:
        z = (values - values.mean()) / (values.std() + 1e-9)
        e = np.exp(z / temp - np.max(z / temp))
        probs = e / e.sum()
        return int(rng.choices(range(len(values)), weights=probs, k=1)[0])
    return int(np.argmax(values))


class BotMovesMixin:
    """Candidate enumeration + BFS move replay for autonomous players.
    Host contract — the host ``GameState`` must provide:

    - ``board``: :class:`~tetris.game.board.Board`
    - ``current_piece``, ``hold_piece``, ``preview_pieces``, ``next_piece``:
      piece pipeline attributes from ``GameState``
    - ``_can_hold``: bool (hold available this lock)
    - ``lookahead``: bool, ``lookahead_depth``: int (planning horizon)
    - ``_hold()``: hold-swap method from ``GameState``
    - ``_candidate_placements: list[Placement]``: initialized by the host
    - ``_pick_values: np.ndarray``: per-candidate El-Tetris values, set by
      ``_get_candidate_states`` — hosts use it to pick a placement
    """

    # Column reservation is a bot-only strategy (ElTetrisState). AIState
    # shares this mixin but must NOT reserve a column — its warm-start
    # priors and MCTS root priors use the raw El-Tetris values, and any
    # penalty would shift AI training/playing behavior.
    _reserve_column: bool = False
    # Committed reservation column, chosen from board state by the host
    # (ElTetrisState); None = reservation off. Only read when
    # ``_reserve_column`` is True, so AIState never touches it.
    _reserved_column: int | None = None

    if TYPE_CHECKING:
        # Host contract declarations — satisfied by the GameState host.
        board: Board
        current_piece: Tetromino
        hold_piece: Tetromino | None
        next_piece: Tetromino
        preview_pieces: list[Tetromino]
        _can_hold: bool
        lookahead: bool
        lookahead_depth: int
        _candidate_placements: list[Placement]
        _pick_values: np.ndarray

        def _hold(self) -> None: ...

    def _get_candidate_states(self) -> tuple[np.ndarray, list[int], np.ndarray]:
        """Enumerate valid placements, simulate, extract features.

        Delegates to :func:`tetris.ai.candidates.get_candidate_states`.
        Stores placements in ``self._candidate_placements`` and per-candidate
        El-Tetris values in ``self._pick_values``.
        """
        hold_type = self.hold_piece.type if self.hold_piece is not None else None
        preview_types = [p.type for p in self.preview_pieces]
        candidates, actions, pick_values, placements = get_candidate_states(
            base_grid=board_to_grid(self.board),
            current_piece_type=self.current_piece.type,
            hold_piece_type=hold_type,
            next_piece_type=self.next_piece.type,
            preview_piece_types=preview_types,
            can_hold=self._can_hold,
            lookahead=self.lookahead,
            lookahead_depth=self.lookahead_depth,
        )
        self._candidate_placements = placements
        self._pick_values = pick_values
        # Column reservation (bot-only): penalize non-I placements whose
        # filled cells touch the committed column, so the bot keeps that
        # column open for I-pieces and scores tetrises. The column is
        # chosen from board state by the host (ElTetrisState) and may be
        # None (no clean column -> reservation off). Placement-level rule
        # (board features are constant across candidates in a step, so
        # eval-only tweaks cannot flip the argmax). I-pieces exempt.
        if self._reserve_column:
            col = self._reserved_column
            if col is not None:
                for i, p in enumerate(placements):
                    if p.piece_type != "I" and any(col == p.px + cx for cx, _ in p.shape):
                        pick_values[i] += RESERVE_COLUMN_PENALTY
        return candidates, actions, pick_values

    def _execute_move_sequence(self, action: int) -> None:
        """Replay the placement's recorded move sequence (from BFS path).

        Guarantees the piece reaches the exact (px, py, rot) that the
        evaluation saw — no execution mismatch.
        """
        p = self._candidate_placements[action]

        if p.hold:
            self._hold()

        piece = self.current_piece

        # BFS paths start from spawn (x=3, y=0, rot=0). Gravity may have
        # pre-fallen the piece during the decision delay — snap it back to
        # the BFS start state so the recorded path replays exactly. The
        # board is unchanged since enumeration (same frame), so every
        # BFS-accepted move is still valid.
        piece.x, piece.y, piece.rotation = BOARD_WIDTH // 2 - 2, 0, 0
        piece.shape = piece.get_current_shape()

        for move in p.moves:
            if move == "left":
                if self.board.is_valid_move(piece, dx=-1):
                    piece.move(-1, 0)
            elif move == "right":
                if self.board.is_valid_move(piece, dx=1):
                    piece.move(1, 0)
            elif move == "soft_drop":
                if self.board.is_valid_move(piece, dy=1):
                    piece.move(0, 1)
            elif move == "rot_cw":
                self.board.try_rotate(piece, 1)
            elif move == "rot_ccw":
                self.board.try_rotate(piece, -1)
