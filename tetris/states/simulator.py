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
from tetris.game.rules import (
    find_full_rows,
    find_holes,
    find_overhangs,
    hard_drop_y,
    place_cells,
    shape_fits,
)
from tetris.game.shapes import get_shape_rot, num_shape_rot
from tetris.game.tetromino import Tetromino
from tetris.settings import BOARD_HEIGHT, BOARD_WIDTH
from tetris.states.game import GameState
from tetris.visuals.particles import ParticleSystem

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
            before = state.stats.total_lines
            action_results = state._execute_actions(actions)
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
            "clear_counts": {
                "single": state.stats.clear_counts.single,
                "double": state.stats.clear_counts.double,
                "triple": state.stats.clear_counts.triple,
                "tetris": state.stats.clear_counts.tetris,
            },
            "seed": state.seed,
            "holes": holes,
            "overhangs": overhangs,
            **_board_feature_dict(repr_grid, lines_cleared, holes, overhangs),
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


def _board_max_height(repr_grid: list) -> int:
    """Tallest column height (filled cell == 1)."""
    h = 0
    for x in range(BOARD_WIDTH):
        for y in range(BOARD_HEIGHT):
            if repr_grid[y][x] == 1:
                h = max(h, BOARD_HEIGHT - y)
                break
    return h


def _board_hole_depth(repr_grid: list) -> int:
    """Max hole count in any single column (X markers)."""
    depth = 0
    for x in range(BOARD_WIDTH):
        col_holes = sum(1 for y in range(BOARD_HEIGHT) if repr_grid[y][x] == "X")
        depth = max(depth, col_holes)
    return depth


def _merit(lines_cleared: int, holes: int, overhangs: int, agg_height: int, bumpiness: int) -> float:
    """Weighted board-quality score. lines×1000 dominates in normal play."""
    return lines_cleared * 1000 - holes * 120 - overhangs * 10 - agg_height * 0.8 - bumpiness * 1.5


def _board_feature_dict(repr_grid: list, lines_cleared: int | None, holes: int, overhangs: int) -> dict[str, Any]:
    """The 5 exposed board-feature metrics, computed wherever snapshots are assembled."""
    agg = _board_aggregate_height(repr_grid)
    bump = _board_bumpiness(repr_grid)
    return {
        "aggregate_height": agg,
        "bumpiness": bump,
        "max_height": _board_max_height(repr_grid),
        "hole_depth": _board_hole_depth(repr_grid),
        "merit": _merit(lines_cleared or 0, holes, overhangs, agg, bump),
    }


def _grid_merit(grid: list, lines_cleared: int) -> float:
    """Merit on a plain 0/1 grid (for lookahead on simulated boards)."""
    return _merit(
        lines_cleared,
        len(find_holes(grid)),
        len(find_overhangs(grid)),
        _board_aggregate_height(grid),
        _board_bumpiness(grid),
    )


def _hard_drop_outcomes(grid: list, piece_type: str) -> list[tuple[list, int]]:
    """All (resulting 0/1 grid, lines_cleared) from hard-dropping *piece_type* on *grid*."""
    outcomes = []
    for rot in range(num_shape_rot(piece_type)):
        shape = get_shape_rot(piece_type, rot)
        min_bx = min(bx for bx, _ in shape)
        max_bx = max(bx for bx, _ in shape)
        for col in range(BOARD_WIDTH):
            px = col - min_bx
            if px + max_bx >= BOARD_WIDTH:
                continue
            if not shape_fits(grid, shape, px, 0):
                continue
            py = hard_drop_y(grid, shape, px)
            if py < 0:
                continue
            sim = [row[:] for row in grid]
            place_cells(sim, shape, px, py, 1)
            full = find_full_rows(sim)
            for y in sorted(full, reverse=True):
                del sim[y]
                sim.insert(0, [0] * BOARD_WIDTH)
            outcomes.append((sim, len(full)))
    return outcomes


def _lookahead_merit(grid: list, piece_types: list[str], depth: int) -> float:
    """Best achievable merit after *depth* more hard-drop placements on *grid*."""
    if depth <= 0 or not piece_types:
        return _grid_merit(grid, 0)
    outcomes = _hard_drop_outcomes(grid, piece_types[0])
    if not outcomes:
        return _grid_merit(grid, 0)
    return max(_lookahead_merit(sim, piece_types[1:], depth - 1) for sim, _lines in outcomes)


def _dedup_and_rank(entries: list[tuple[list[str], dict]]) -> list[dict]:
    seen: set = set()
    unique: list[tuple[list[str], dict]] = []
    for actions, snap in entries:
        key = tuple(tuple(row) for row in snap["board"])
        if key in seen:
            continue
        seen.add(key)
        unique.append((actions, snap))
    # Ensure every snap has merit (defensive: direct callers may not precompute it)
    for _actions, snap in unique:
        if "merit" not in snap:
            agg = _board_aggregate_height(snap["board"])
            bump = _board_bumpiness(snap["board"])
            snap["merit"] = _merit(
                snap.get("lines_cleared") or 0, snap.get("holes", 0), snap.get("overhangs", 0), agg, bump
            )
    unique.sort(key=lambda item: -item[1]["merit"])
    return [{"actions": actions, **snap} for actions, snap in unique]


def _derive_actions(board: Board, piece: Tetromino, rot: int, px: int) -> list[str] | None:
    """Build [..., 'hard_drop'] to reach (rot, px). None if unreachable."""
    clone = copy.copy(piece)
    actions: list[str] = []
    num = num_shape_rot(piece.type)
    guard = 0
    while (clone.rotation % num) != rot:
        if not board.try_rotate(clone, +1):
            return None
        actions.append("rotate_cw")
        guard += 1
        if guard > num + 1:
            return None
    guard = 0
    while clone.x < px:
        if not board.is_valid_move(clone, dx=1):
            return None
        clone.move(1, 0)
        actions.append("right")
        guard += 1
        if guard > 10:
            return None
    while clone.x > px:
        if not board.is_valid_move(clone, dx=-1):
            return None
        clone.move(-1, 0)
        actions.append("left")
        guard += 1
        if guard > 10:
            return None
    actions.append("hard_drop")
    return actions


def enumerate_hard_drop_actions(board: Board, piece: Tetromino) -> list[list[str]]:
    """All replayable action lists that hard-drop *piece* on *board*.

    Enumerates (rotation, column) targets via game-rule helpers, then drives
    the engine (Board.try_rotate / is_valid_move / Tetromino.move) to build
    each action list from the piece's CURRENT rotation/position, so the list
    replays exactly through the real action handlers. Unreachable targets
    are skipped.
    """
    out: list[list[str]] = []
    num_rots = num_shape_rot(piece.type)
    for rot in range(num_rots):
        shape = get_shape_rot(piece.type, rot)
        min_bx = min(bx for bx, _ in shape)
        max_bx = max(bx for bx, _ in shape)
        for col in range(BOARD_WIDTH):
            px = col - min_bx
            if px + max_bx >= BOARD_WIDTH:
                continue
            if not shape_fits(board.grid, shape, px, 0):
                continue
            py = hard_drop_y(board.grid, shape, px)
            if py < 0:
                continue
            actions = _derive_actions(board, piece, rot, px)
            if actions is not None:
                out.append(actions)
    return out


def enumerate_drops(state: GameState, dt: float, depth: int = 1, hold: bool = True) -> dict:
    """Enumerate all hard-drop final boards for the current piece.

    Returns {"piece_type": str|None, "boards": [ {**simulate_snapshot, "actions": [...]}, ... ]}
    ranked by ``merit`` descending (weighted sum: lines×1000 − holes×120 − overhangs×10
    − aggregate_height×0.8 − bumpiness×1.5). Each board is a simulate_actions snapshot,
    so the schema matches ``simulate`` exactly; only ``actions`` is added.

    Args:
        depth: Look-ahead depth. 1 = no lookahead (default). 2 = current + next_piece.
            3 = current + next + 1 preview. Deeper placements evaluate the best
            subsequent hard-drop(s) and override ``merit`` with the resulting board's
            merit; the board/snapshot still shows the depth-1 result.
        hold: If True and the hold is available, also enumerate placements for the
            held piece (or next piece if hold is empty), prefixed with ``["hold"]``.
            Dedup collapses hold==non-hold identical boards (favors non-hold).
    """
    piece = state.current_piece
    # Future pieces for lookahead: from the ORIGINAL state (before simulate drains them)
    future_pieces = [
        t
        for t in [
            state.next_piece.type if state.next_piece else None,
            *(p.type for p in state.preview_pieces),
        ]
        if t is not None
    ]
    entries: list[tuple[list[str], dict]] = []
    for actions in enumerate_hard_drop_actions(state.board, piece):
        snap = simulate_actions(state, actions, 0, dt)
        if "error" in snap:
            continue
        entries.append((actions, snap))
    # Hold-aware candidates: swap to held piece (or next if hold empty), then enumerate
    if hold and state._can_hold:
        hold_type = state.hold_piece.type if state.hold_piece else (state.next_piece.type if state.next_piece else None)
        if hold_type:
            held_piece = Tetromino(hold_type)
            for actions in enumerate_hard_drop_actions(state.board, held_piece):
                hold_actions = ["hold"] + actions
                snap = simulate_actions(state, hold_actions, 0, dt)
                if "error" in snap:
                    continue
                entries.append((hold_actions, snap))
    # Lookahead: for depth > 1, override merit with best-achievable future board merit
    if depth > 1:
        for _actions, snap in entries:
            grid = [[1 if cell == 1 else 0 for cell in row] for row in snap["board"]]
            snap["merit"] = _lookahead_merit(grid, future_pieces, depth - 1)
    return {"piece_type": piece.type, "boards": _dedup_and_rank(entries)}
