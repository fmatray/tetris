"""Shared bot move machinery, reused by AIState and DellacherieState.

``BotMovesMixin`` is stateless with respect to the FSM: it only depends
on the host ``GameState`` providing the attributes/methods listed in
the mixin docstring. This keeps the bot states independent of each
other while guaranteeing a single implementation of candidate
enumeration and BFS move replay.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

from tetris.ai.candidates import Placement, get_candidate_states
from tetris.ai.rewards import board_to_grid

if TYPE_CHECKING:
    from tetris.game.board import Board
    from tetris.game.tetromino import Tetromino


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
