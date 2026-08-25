"""MCP server exposing Tetris tools to external clients via HTTP.

The server runs on a daemon thread. Tool/resource calls enqueue requests
to :class:`~tetris.states.mcp.MCPState` via a shared ``queue.Queue`` and
block on a per-call ``result_queue`` for the board snapshot.

This module is deliberately separate from the state: future MCP tools
unrelated to Tetris gameplay can be added here without touching state code.

The server is a process-wide singleton (see :func:`get_server`): it is
created and bound exactly once, and stays up for the whole process lifetime.
Individual :class:`MCPState` instances attach/detach their action queue
instead of creating/destroying the server. This avoids ``Errno 48``
("address already in use") when the game is quit and restarted within the
same process — the previous design rebuilt and re-bound the server on every
entry into MCP mode.
"""

from __future__ import annotations

import json
import queue
import threading
from typing import Any

from mcp.server.fastmcp import FastMCP

from tetris.settings import MCP_SERVER_PORT
from tetris.states.simulator import ENUMERATE_COMMAND


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


_server_instance: TetrisMCPServer | None = None


def get_server(port: int = MCP_SERVER_PORT) -> TetrisMCPServer:
    """Return the process-wide MCP server, creating it on first call.

    The server lives for the whole process so it never has to re-bind the
    port. Individual :class:`MCPState` instances attach/detach their action
    queue via :meth:`TetrisMCPServer.attach` / :meth:`detach`.
    """
    global _server_instance
    if _server_instance is None:
        _server_instance = TetrisMCPServer(port=port)
    return _server_instance


class TetrisMCPServer:
    """MCP server exposing ``play`` tool and board/rules resources.

    Communication with :class:`MCPState` is one-directional via
    ``_action_queue``: each tool/resource call puts a tuple
    ``(actions, frames, result_queue, simulate)`` onto the queue, then blocks on
    ``result_queue.get()`` until the main thread processes the request.

    The queue is ``None`` when no MCP game is currently active (e.g. the app
    is in a menu) — tool/resource calls then return a clear error instead of
    blocking forever.
    """

    def __init__(
        self,
        port: int = MCP_SERVER_PORT,
    ) -> None:
        self._port = port
        self._action_queue: queue.Queue[tuple[list[str], int, queue.Queue[dict[str, Any]], bool]] | None = None
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
            if self._action_queue is None:
                return {"error": "no active MCP game", "game_over": True, "board": [], "holes": 0, "overhangs": 0}
            result_q: queue.Queue[dict[str, Any]] = queue.Queue()
            self._action_queue.put((actions, frames, result_q, False))
            return result_q.get()

        @self._mcp.tool()
        def simulate(actions: list[str], frames: int = 0) -> dict[str, Any]:
            """Preview the result of actions WITHOUT modifying the game.

            Identical arguments to ``play``. Runs the same action/gravity logic
            on a throwaway copy of the board, so the real game state is
            unchanged — use it to test a move sequence before committing it
            with ``play``.

            The preview is bounded to the pieces the game already knows (the
            current falling piece, ``next_piece``, and the preview pieces). The
            simulation drains those known pieces and returns ``next_piece: null``
            once exhausted, rather than inventing future pieces. Requesting more
            drops than known pieces returns ``{"error": "horizon exceeded: ..."}``.
            ``quit`` is ignored (simulation never leaves MCP).

            Args:
                actions: Action names (same valid set as ``play``).
                frames: Gravity/lock frames to advance (~16ms each), default 0.

            Returns:
                Board snapshot dict with the same keys as ``play``: ``board``
                (0/1/"X"/"O"), ``holes``, ``overhangs``, ``current_piece``,
                ``next_piece``, ``preview_pieces``, ``hold_piece``, ``can_hold``,
                ``score``, ``lines``, ``level``, ``game_over``,
                ``action_results``, ``lines_cleared``, ``locked_pieces``
                (list of piece types locked during the simulation, in lock order;
                simulate only). On a horizon error,
                returns ``{"error": "..."}``.
            """
            if self._action_queue is None:
                return {"error": "no active MCP game", "game_over": True, "board": [], "holes": 0, "overhangs": 0}
            result_q: queue.Queue[dict[str, Any]] = queue.Queue()
            self._action_queue.put((actions, frames, result_q, True))
            return result_q.get()

        @self._mcp.tool()
        def enumerate_drops() -> dict[str, Any]:
            """Enumerate every final board from rotating/shifting/hard-dropping the
            current piece. Returns {"piece_type": str|None, "boards": [...]} where each
            board is a simulate-format snapshot plus its "actions" list, de-duplicated
            and ranked by (lines_cleared desc, holes asc, overhangs asc, stack height
            asc). Never mutates the real game.
            """
            if self._action_queue is None:
                return {"error": "no active MCP game", "game_over": True, "boards": [], "piece_type": None}
            result_q: queue.Queue[dict[str, Any]] = queue.Queue()
            self._action_queue.put((ENUMERATE_COMMAND, 0, result_q, True))
            return result_q.get()

        @self._mcp.tool()
        def start_game() -> dict[str, Any]:
            """Reset the board and start a fresh game.

            Clears all locked pieces, resets score/lines/level to zero,
            spawns new pieces, and returns the initial board snapshot.
            """
            if self._action_queue is None:
                return {"error": "no active MCP game", "game_over": True, "board": [], "holes": 0, "overhangs": 0}
            result_q: queue.Queue[dict[str, Any]] = queue.Queue()
            self._action_queue.put((["start_game"], 0, result_q, False))
            return result_q.get()

        @self._mcp.tool()
        def quit() -> dict[str, Any]:
            """Stop the MCP session and return to the menu."""
            if self._action_queue is None:
                return {"error": "no active MCP game", "game_over": True, "board": [], "holes": 0, "overhangs": 0}
            result_q: queue.Queue[dict[str, Any]] = queue.Queue()
            self._action_queue.put((["quit"], 0, result_q, False))
            return result_q.get()

        @self._mcp.resource("board://state")
        def board_state() -> str:
            """Current board state without advancing the game (0 actions, 0 frames)."""
            if self._action_queue is None:
                return json.dumps({"error": "no active MCP game"})
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

    def attach(self, action_queue: queue.Queue[tuple[list[str], int, queue.Queue[dict[str, Any]], bool]]) -> None:
        """Bind the active game's action queue and ensure the server is up."""
        self._action_queue = action_queue
        self.start()

    def detach(self) -> None:
        """Unbind the active game's queue (server keeps running)."""
        self._action_queue = None

    def start(self) -> None:
        """Launch the MCP server once on a daemon thread (idempotent)."""
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
        """Persistent server: detaches the active game but stays bound.

        The daemon thread and its socket live until the process exits; there
        is no clean uvicorn shutdown API for the streamable-http transport,
        and keeping the server up is the desired behaviour.
        """
        self.detach()
