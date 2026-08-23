"""MCP server exposing Tetris tools to external clients via HTTP.

The server runs on a daemon thread. Tool/resource calls enqueue requests
to :class:`~tetris.states.mcp.MCPState` via a shared ``queue.Queue`` and
block on a per-call ``result_queue`` for the board snapshot.

This module is deliberately separate from the state: future MCP tools
unrelated to Tetris gameplay can be added here without touching state code.
"""

from __future__ import annotations

import json
import queue
import threading
from typing import Any

from mcp.server.fastmcp import FastMCP

from tetris.settings import MCP_SERVER_PORT


def _shapes_payload() -> dict[str, Any]:
    """Full shape/kick geometry for external clients (no source access needed)."""
    from tetris.game.shapes import SHAPES
    from tetris.game.rules import SRS_KICKS_JLSTZ, SRS_KICKS_I
    from tetris.settings import BOARD_WIDTH, BOARD_HEIGHT, HIDDEN_ROWS, VISIBLE_ROWS

    kicks = {
        name: {f"{f}->{t}": offsets for (f, t), offsets in data.items()}
        for name, data in (("JLSTZ", SRS_KICKS_JLSTZ), ("I", SRS_KICKS_I))
    }
    return {
        "shapes": SHAPES,
        "srs_kicks": kicks,
        "spawn": {"x": BOARD_WIDTH // 2 - 2, "y": 0},
        "board": {
            "width": BOARD_WIDTH,
            "height": BOARD_HEIGHT,
            "hidden_rows": HIDDEN_ROWS,
            "visible_rows": VISIBLE_ROWS,
        },
        "coordinate_convention": (
            "cells (col,row) in piece box; absolute=(piece.x+col,piece.y+row); board y=0 top, y increases downward"
        ),
    }


class TetrisMCPServer:
    """MCP server exposing ``play`` tool and board/rules resources.

    Communication with :class:`MCPState` is one-directional via
    ``action_queue``: each tool/resource call puts a tuple
    ``(actions, frames, result_queue, simulate)`` onto the queue, then blocks on
    ``result_queue.get()`` until the main thread processes the request.
    """

    def __init__(
        self,
        action_queue: queue.Queue[tuple[list[str], int, queue.Queue[dict[str, Any]], bool]],
        port: int = MCP_SERVER_PORT,
    ) -> None:
        self._action_queue = action_queue
        self._port = port
        self._thread: threading.Thread | None = None
        self._mcp: FastMCP | None = None
        self._setup_mcp()

    def _setup_mcp(self) -> None:
        self._mcp = FastMCP("tetris-mcp", host="127.0.0.1", port=self._port)

        @self._mcp.tool()
        def play(actions: list[str], frames: int = 0) -> dict[str, Any]:
            """Execute actions on the Tetris board, advance frames, return board state.

            Args:
                actions: Action names to execute. Valid: ``left``, ``right``,
                    ``rotate_cw``, ``rotate_ccw``, ``soft_drop``, ``hard_drop``,
                    ``hold``. Also ``start_game`` (reset) and ``quit`` (leave MCP).
                frames: Number of game frames (~16ms each) to advance after
                    actions. Drives gravity and lock delay. ``0`` = execute
                    actions only with no time passing.

            Returns:
                Board snapshot dict with keys: ``board`` (grid of
                0=empty, 1=filled, "X"=hole (unreachable covered empty),
                "O"=overhang (reachable covered empty)), ``holes`` (int),
                ``overhangs`` (int), ``current_piece``, ``next_piece``,
                ``preview_pieces``, ``hold_piece``, ``can_hold``,
                ``score``, ``lines``, ``level``, ``game_over``,
                ``action_results``, ``lines_cleared``.
                On processing error: ``error``, ``game_over``, ``board``,
                ``holes``, ``overhangs``.
            """
            result_q: queue.Queue[dict[str, Any]] = queue.Queue()
            self._action_queue.put((actions, frames, result_q, False))
            return result_q.get()  # blocks until MCPState processes

        @self._mcp.tool()
        def simulate(actions: list[str], frames: int = 0) -> dict[str, Any]:
            """Preview the result of actions WITHOUT modifying the game.

            Identical arguments to ``play``. Runs the same action/gravity logic
            on a throwaway copy of the board, so the real game state is
            unchanged — use it to test a move sequence before committing it
            with ``play``.

            The preview is bounded to the pieces the game already knows (the
            current falling piece, ``next_piece``, and the preview pieces). If a
            sequence would need a piece beyond that horizon, the result is
            ``{"error": "horizon exceeded: ..."}`` rather than inventing future
            pieces. ``quit`` is ignored (simulation never leaves MCP).

            Args:
                actions: Action names (same valid set as ``play``).
                frames: Gravity/lock frames to advance (~16ms each), default 0.

            Returns:
                Board snapshot dict with the same keys as ``play``: ``board``
                (0/1/"X"/"O"), ``holes``, ``overhangs``, ``current_piece``,
                ``next_piece``, ``preview_pieces``, ``hold_piece``, ``can_hold``,
                ``score``, ``lines``, ``level``, ``game_over``,
                ``action_results``, ``lines_cleared``. On a horizon error,
                returns ``{"error": "..."}``.
            """
            result_q: queue.Queue[dict[str, Any]] = queue.Queue()
            self._action_queue.put((actions, frames, result_q, True))
            return result_q.get()

        @self._mcp.tool()
        def start_game() -> dict[str, Any]:
            """Reset the board and start a fresh game.

            Clears all locked pieces, resets score/lines/level to zero,
            spawns new pieces, and returns the initial board snapshot.
            """
            result_q: queue.Queue[dict[str, Any]] = queue.Queue()
            self._action_queue.put((["start_game"], 0, result_q, False))
            return result_q.get()

        @self._mcp.tool()
        def quit() -> dict[str, Any]:
            """Stop the MCP session and return to the menu."""
            result_q: queue.Queue[dict[str, Any]] = queue.Queue()
            self._action_queue.put((["quit"], 0, result_q, False))
            return result_q.get()

        @self._mcp.resource("board://state")
        def board_state() -> str:
            """Current board state without advancing the game (0 actions, 0 frames)."""
            result_q: queue.Queue[dict[str, Any]] = queue.Queue()
            self._action_queue.put(([], 0, result_q, False))
            return json.dumps(result_q.get())

        @self._mcp.resource("tetris://rules")
        def rules() -> str:
            """Tetris game rules and available actions."""
            from tetris.game.shapes import SHAPES_TYPES
            from tetris.states.mcp import MCPState

            return json.dumps(
                {
                    "actions": list(MCPState._ACTIONS.keys()),
                    "board_size": "10x20 visible (22 with hidden buffer)",
                    "pieces": SHAPES_TYPES,
                    "scoring": "standard Tetris guideline",
                    "board_markers": "filled=1, empty=0, hole='X' (unreachable covered), overhang='O' (reachable covered)",
                    "shapes_resource": "tetris://shapes",
                }
            )

        @self._mcp.resource("tetris://shapes")
        def shapes_resource() -> str:
            """Full shape rotation data, SRS kicks, spawn, and board geometry."""
            return json.dumps(_shapes_payload())

    def start(self) -> None:
        """Launch the MCP server on a daemon thread."""
        if self._thread is not None or self._mcp is None:
            return
        mcp = self._mcp
        self._thread = threading.Thread(
            target=mcp.run,
            kwargs={"transport": "streamable-http"},
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        """Soft stop — daemon thread dies with the process.

        FastMCP has no clean shutdown API for the streamable-http transport.
        Setting ``_mcp = None`` prevents further tool registrations; the
        daemon thread is harmless once the process exits.
        """
        self._mcp = None
        self._thread = None
