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


class TetrisMCPServer:
    """MCP server exposing ``play`` tool and board/rules resources.

    Communication with :class:`MCPState` is one-directional via
    ``action_queue``: each tool/resource call puts a tuple
    ``(actions, frames, result_queue)`` onto the queue, then blocks on
    ``result_queue.get()`` until the main thread processes the request.
    """

    def __init__(
        self,
        action_queue: queue.Queue[tuple[list[str], int, queue.Queue[dict[str, Any]]]],
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
                    ``hold``.
                frames: Number of game frames (~16ms each) to advance after
                    actions. Drives gravity and lock delay. ``0`` = execute
                    actions only with no time passing.

            Returns:
                Board snapshot dict with keys: ``board`` (0/1 grid),
                ``current_piece``, ``next_piece``, ``preview_pieces``,
                ``hold_piece``, ``can_hold``, ``score``, ``lines``,
                ``level``, ``game_over``, ``action_results``.
            """
            result_q: queue.Queue[dict[str, Any]] = queue.Queue()
            self._action_queue.put((actions, frames, result_q))
            return result_q.get()  # blocks until MCPState processes

        @self._mcp.tool()
        def start_game() -> dict[str, Any]:
            """Reset the board and start a fresh game.

            Clears all locked pieces, resets score/lines/level to zero,
            spawns new pieces, and returns the initial board snapshot.
            """
            result_q: queue.Queue[dict[str, Any]] = queue.Queue()
            self._action_queue.put((["start_game"], 0, result_q))
            return result_q.get()

        @self._mcp.resource("board://state")
        def board_state() -> str:
            """Current board state without advancing the game (0 actions, 0 frames)."""
            result_q: queue.Queue[dict[str, Any]] = queue.Queue()
            self._action_queue.put(([], 0, result_q))
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
                }
            )

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
