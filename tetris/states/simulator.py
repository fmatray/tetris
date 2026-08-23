"""Generic, side-effect-free simulation of action sequences on a GameState.

Deep-copies the gameplay-mutable fields of a state, runs the same action
handlers and gravity/lock logic used by real play, and returns a board
snapshot dict — leaving the caller's state untouched.

This module is deliberately MCP-independent so it can be reused by future
upgrades (AI planning, non-MCP tools, etc.).
"""

from __future__ import annotations

import copy
from typing import Any

from tetris.game.board import Board
from tetris.settings import BOARD_HEIGHT, BOARD_WIDTH
from tetris.states.game import GameState
from tetris.visuals.particles import ParticleSystem


class NullAudio:
    """No-op audio sink so simulation runs without SFX side effects."""

    def __getattr__(self, _name: str) -> Any:
        return lambda *_a: None


class SimulationError(RuntimeError):
    """Raised when a simulation needs a piece beyond the known horizon."""


class _PreviewProvider:
    """Piece source for simulation.

    Replays exactly the pieces the real game *already knows* — the current
    falling piece plus ``next_piece`` and the preview pieces. Any spawn past
    that horizon raises :class:`SimulationError` (we must not invent future
    pieces). The real ``PieceProvider`` is never advanced or copied.
    """

    def __init__(self, known_types: list[str], generator_name: str) -> None:
        self._known = list(known_types)
        self._queue = list(known_types)
        self._generator_name = generator_name

    def next_type(self) -> str:
        if self._queue:
            return self._queue.pop(0)
        raise SimulationError("horizon exceeded: no known piece beyond current piece + previews")

    def reset(self) -> None:
        # A simulated start_game discards the known horizon; refuse further spawns.
        self._queue = []

    def save(self) -> None:
        pass


# Gameplay attributes mutated by action handlers and GameState.update.
SIM_FIELDS = (
    "board",
    "current_piece",
    "next_piece",
    "preview_pieces",
    "hold_piece",
    "_can_hold",
    "_lock_timer",
    "_lock_resets",
    "_grounded",
    "drop_time",
    "down_pressed",
    "stats",
    "_last_level",
    "_pending_level_up",
    "game_over",
    "pieces",
    "current_speed",
)


def build_board_repr(board: Board) -> tuple[list, int, int]:
    """Return ``(repr_grid, holes, overhangs)`` for a board.

    ``repr_grid`` is a 22x10 list of ``0`` (empty), ``1`` (filled),
    ``"X"`` (hole / unreachable covered empty), ``"O"`` (overhang / reachable
    covered empty).
    """
    holes = board.find_holes()
    overhangs = board.find_overhangs()
    repr_grid: list[list] = []
    for y in range(BOARD_HEIGHT):
        row: list = []
        for x in range(BOARD_WIDTH):
            if board.grid[y][x] is not None:
                row.append(1)
            elif (x, y) in holes:
                row.append("X")
            elif (x, y) in overhangs:
                row.append("O")
            else:
                row.append(0)
        repr_grid.append(row)
    return repr_grid, len(holes), len(overhangs)


def simulate_actions(state: GameState, actions: list[str], frames: int, dt: float) -> dict[str, Any]:
    """Run ``actions`` on a throwaway copy of ``state``; return a snapshot.

    ``state`` is never mutated. Pieces past the known horizon (current falling
    piece + ``next_piece`` + previews) raise :class:`SimulationError`, which is
    caught and returned as ``{"error": ...}``. The real ``PieceProvider`` is
    never advanced or deep-copied (a replay stand-in is used instead). Frame
    advancement reuses ``GameState.update`` on the copy (audio stubbed,
    particles suppressed).
    """
    saved_audio = state.audio
    state.audio = NullAudio()  # type: ignore[assignment]
    saved = {k: getattr(state, k) for k in SIM_FIELDS}
    particles = ParticleSystem()
    try:
        for k in SIM_FIELDS:
            if k == "pieces":
                continue  # replaced with a replay stand-in, not deep-copied
            setattr(state, k, copy.deepcopy(getattr(state, k)))
        # Horizon = current piece + (next_piece + preview_pieces) = preview_count + 1
        # known pieces. Beyond that we must not invent pieces, so the replay
        # stand-in only carries preview_count + 1 entries; exhausting it raises
        # SimulationError (handled by the caller). Future types are unknown, so
        # the stand-in repeats next_piece's type for the slots past the preview.
        known = [state.next_piece.type] * (state.preview_count + 1)
        gen_name = getattr(state.pieces, "_generator_name", "unknown")
        state.pieces = _PreviewProvider(known, gen_name)  # type: ignore[assignment]
        try:
            action_results = state._execute_actions(actions)
            before = state.stats.total_lines
            for _ in range(frames):
                if state.game_over:
                    break
                GameState.update(state, dt, particles)
            lines_cleared = max(0, state.stats.total_lines - before)
        except SimulationError as exc:
            return {"error": str(exc)}
        repr_grid, holes, overhangs = build_board_repr(state.board)
        return {
            "board": repr_grid,
            "current_piece": state.current_piece.type,
            "next_piece": state.next_piece.type,
            "preview_pieces": [p.type for p in state.preview_pieces],
            "hold_piece": state.hold_piece.type if state.hold_piece else None,
            "can_hold": state._can_hold,
            "score": state.stats.score,
            "lines": state.stats.total_lines,
            "level": state.stats.level,
            "game_over": state.game_over,
            "holes": holes,
            "overhangs": overhangs,
            "action_results": action_results,
            "lines_cleared": lines_cleared,
        }
    finally:
        for k in SIM_FIELDS:
            setattr(state, k, saved[k])
        state.audio = saved_audio
