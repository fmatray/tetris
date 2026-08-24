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
from tetris.ai.candidates import enumerate_hard_drop_actions

ENUMERATE_COMMAND = ["__enumerate_drops__"]


class NullAudio:
    """No-op audio sink so simulation runs without SFX side effects."""

    def __getattr__(self, _name: str) -> Any:
        return lambda *_a: None


class SimulationError(RuntimeError):
    """Raised when a simulation needs a piece beyond the known horizon."""


class _PreviewProvider:
    """Piece source for simulation.

    The real ``PieceProvider`` is never advanced or copied. During a
    simulation the only provider calls are preview-tail refills for pieces
    BEYOND the known horizon (current + next + previews), which are
    genuinely unknown — so ``next_type`` returns ``None`` to signal
    "no known piece". The spawn/hold logic drains the preview to empty
    instead of inventing future pieces. When the known pieces are fully
    exhausted, ``next_piece`` becomes ``None`` and a further action that needs
    an active piece raises :class:`SimulationError`.
    """

    def __init__(self, generator_name: str) -> None:
        self._generator_name = generator_name

    def next_type(self) -> str | None:
        return None

    def reset(self) -> None:
        pass

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
    piece + ``next_piece`` + previews) are never invented: the preview drains to
    empty and ``next_piece`` becomes ``None``. Acting with no active piece raises
    :class:`SimulationError`, which is caught and returned as ``{"error": ...}``.
    The real ``PieceProvider`` is
    never advanced or deep-copied (a replay stand-in is used instead). Frame
    advancement reuses ``GameState.update`` on the copy (audio stubbed,
    particles suppressed).
    """
    saved_audio = state.audio
    state.audio = NullAudio()  # type: ignore[assignment]
    saved = {k: getattr(state, k) for k in SIM_FIELDS}
    saved_locked = state.locked_pieces
    state.locked_pieces = []
    particles = ParticleSystem()
    try:
        for k in SIM_FIELDS:
            if k == "pieces":
                continue  # replaced with a replay stand-in, not deep-copied
            setattr(state, k, copy.deepcopy(getattr(state, k)))
        # The real game already knows current + next + previews; anything the
        # provider yields during the sim is a refill BEYOND that horizon and is
        # unknown. _PreviewProvider returns None so the spawn/hold logic drains
        # the preview to empty instead of inventing future pieces.
        gen_name = getattr(state.pieces, "_generator_name", "unknown")
        state.pieces = _PreviewProvider(gen_name)  # type: ignore[assignment]
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
            "current_piece": state.current_piece.type if state.current_piece else None,
            "next_piece": state.next_piece.type if state.next_piece else None,
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
            "locked_pieces": list(state.locked_pieces),
        }
    finally:
        for k in SIM_FIELDS:
            setattr(state, k, saved[k])
        state.audio = saved_audio
        state.locked_pieces = saved_locked


def _board_aggregate_height(repr_grid: list) -> int:
    """Sum of column heights (filled cell == 1). Lower = flatter/lower stack."""
    total = 0
    for x in range(BOARD_WIDTH):
        for y in range(BOARD_HEIGHT):
            if repr_grid[y][x] == 1:
                total += BOARD_HEIGHT - y
                break
    return total


def _board_bumpiness(repr_grid: list) -> int:
    heights = []
    for x in range(BOARD_WIDTH):
        h = 0
        for y in range(BOARD_HEIGHT):
            if repr_grid[y][x] == 1:
                h = BOARD_HEIGHT - y
                break
        heights.append(h)
    return sum(abs(heights[i] - heights[i + 1]) for i in range(BOARD_WIDTH - 1))


def _dedup_and_rank(entries: list[tuple[list[str], dict]]) -> list[dict]:
    seen: set = set()
    unique: list[tuple[list[str], dict]] = []
    for actions, snap in entries:
        key = tuple(tuple(row) for row in snap["board"])
        if key in seen:
            continue
        seen.add(key)
        unique.append((actions, snap))

    def sort_key(item: tuple[list[str], dict]):
        _actions, snap = item
        lines = snap.get("lines_cleared") or 0
        return (
            -lines,  # (1) most lines cleared
            snap.get("overhangs", 0),  # (2) fewest overhangs
            snap.get("holes", 0),  # (3) fewest holes
            _board_aggregate_height(snap["board"]),  # (4) lowest/flattest stack
            _board_bumpiness(snap["board"]),  # (4) tiebreak: smoothest
        )

    unique.sort(key=sort_key)
    return [{"actions": actions, **snap} for actions, snap in unique]


def enumerate_drops(state: GameState, dt: float) -> dict:
    """Enumerate all hard-drop final boards for the current piece.

    Returns {"piece_type": str|None, "boards": [ {**simulate_snapshot, "actions": [...]}, ... ]}
    ranked by _dedup_and_rank. Each board is a simulate_actions snapshot, so the
    schema matches `simulate` exactly; only `actions` is added.
    """
    piece = state.current_piece
    assert piece is not None
    entries: list[tuple[list[str], dict]] = []
    for actions, _ in enumerate_hard_drop_actions(state.board, piece):
        snap = simulate_actions(state, actions, 0, dt)
        if "error" in snap:
            continue
        entries.append((actions, snap))
    return {"piece_type": piece.type, "boards": _dedup_and_rank(entries)}
