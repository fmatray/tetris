"""MCP player state: external agent plays via HTTP tool calls.

The game is frozen between ``play()`` calls — gravity does NOT advance
unless ``frames > 0`` in the request. This gives the external agent full
control over game timing.
"""

from __future__ import annotations

import queue
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import pygame

from tetris.game.board import Board
from tetris.game.stats import GameStats
from tetris.game.tetromino import Tetromino
from tetris.logger import get_logger
from tetris.settings import HUD_POSITIONS, SPEED_MODES
from tetris.states.game import GameConfig, GameState, _drop_interval
from tetris.states.simulator import build_board_repr, simulate_actions
from tetris.visuals.particles import ParticleSystem

if TYPE_CHECKING:
    from tetris.audio import AudioManager
    from tetris.game.piece_provider import PieceProvider
    from tetris.mcp_server import TetrisMCPServer
    from tetris.states.base import State
    from tetris.states.menu import MenuState

_logger = get_logger("mcp")


@dataclass(frozen=True)
class MCPConfig:
    """Configuration for the MCP player state."""

    port: int


class MCPState(GameState):
    """External MCP agent plays the game via HTTP tool calls.

    Inherits board/pieces/rendering from :class:`GameState`. The game is
    frozen between ``play()`` calls: ``update()`` polls ``_action_queue``
    and only advances gravity when a request contains ``frames > 0``.
    """

    def __init__(
        self,
        screen: pygame.Surface,
        font: pygame.font.Font,
        audio: AudioManager,
        config: GameConfig,
        mcp_config: MCPConfig,
        piece_provider: PieceProvider | None = None,
        menu: MenuState | None = None,
        start_server: bool = True,
    ) -> None:
        super().__init__(screen, font, audio, config, piece_provider, menu)
        self.player_type = "MCP"
        self.mcp_config = mcp_config
        self._handicap = config.handicap
        self._action_queue: queue.Queue[tuple[list[str], int, queue.Queue[dict[str, Any]], bool]] = queue.Queue()
        self._server: TetrisMCPServer | None = None
        self._last_tool_call: dict[str, Any] | None = None
        self._last_snapshot: dict[str, Any] | None = None
        if start_server:
            self._start_server()

    def _start_server(self) -> None:
        from tetris.mcp_server import get_server

        self._server = get_server(self.mcp_config.port)
        self._server.attach(self._action_queue)
        _logger.debug("MCP server attached on port %d", self.mcp_config.port)

    def _stop_server(self) -> None:
        if self._server is not None:
            self._server.detach()
            _logger.debug("MCP server detached (kept running)")
        self._server = None

    def _reset_game(self) -> None:
        """Reset all game state for a fresh game (called via ``start_game`` tool)."""
        self.game_over = False
        self.paused = False
        self.drop_time = 0.0
        self.down_pressed = False
        self._lock_timer = 0.0
        self._lock_resets = 0
        self._grounded = False
        self._last_level = 0
        self._pending_level_up = False
        self.pieces.reset()
        self.board = Board()
        self.board.apply_handicap(self._handicap)
        self.current_piece = Tetromino(self.pieces.next_type())
        self.next_piece = Tetromino(self.pieces.next_type())
        self.preview_pieces = [Tetromino(self.pieces.next_type()) for _ in range(max(0, self.preview_count - 1))]
        self.hold_piece = None
        self._can_hold = True
        self.stats = GameStats()
        self.current_speed = _drop_interval(0, SPEED_MODES[self.speed_mode])

    def _board_snapshot(
        self, action_results: list[str] | None = None, lines_cleared: int | None = None
    ) -> dict[str, Any]:
        """Return current board state as a dict for the MCP client."""
        repr_grid, holes, overhangs = build_board_repr(self.board)
        snap: dict[str, Any] = {
            "board": repr_grid,
            "current_piece": self.current_piece.type,
            "next_piece": self.next_piece.type,
            "preview_pieces": [p.type for p in self.preview_pieces],
            "hold_piece": self.hold_piece.type if self.hold_piece else None,
            "can_hold": self._can_hold,
            "score": self.stats.score,
            "lines": self.stats.total_lines,
            "level": self.stats.level,
            "game_over": self.game_over,
            "holes": holes,
            "overhangs": overhangs,
        }
        if action_results is not None:
            snap["action_results"] = action_results
        if lines_cleared is not None:
            snap["lines_cleared"] = lines_cleared
        return snap

    def update(self, dt: float, particles: ParticleSystem) -> State | None:
        """Poll action queue; game frozen when empty.

        Processes all pending requests this frame (lowers latency when the
        client floods). Top-out does NOT leave MCP — the snapshot reports
        ``game_over`` and the client calls ``start_game`` to reset. Only an
        explicit ``quit`` request returns to the menu.
        """
        quit_requested = False
        while True:
            try:
                actions, frames, result_queue, simulate = self._action_queue.get_nowait()
            except queue.Empty:
                break
            if simulate:
                snapshot = simulate_actions(self, actions, frames, dt)
                self._last_tool_call = {"actions": actions, "frames": frames, "simulate": True}
                self._last_snapshot = snapshot
                result_queue.put(snapshot)
                continue
            if "quit" in actions:
                quit_requested = True
                result_queue.put(self._board_snapshot())
                continue
            action_results: list[str] = []
            try:
                before = self.stats.total_lines
                action_results = self._execute_actions(actions)
                lines_cleared = max(0, self.stats.total_lines - before)
                for _ in range(frames):
                    if self.game_over:
                        break
                    super().update(dt, particles)
                snapshot = self._board_snapshot(action_results, lines_cleared)
            except Exception as exc:  # noqa: BLE001  # one bad request must not kill the server
                if self.board is not None:
                    repr_grid, holes, overhangs = build_board_repr(self.board)
                else:
                    repr_grid, holes, overhangs = [], 0, 0
                snapshot = {
                    "error": str(exc),
                    "game_over": self.game_over,
                    "board": repr_grid,
                    "holes": holes,
                    "overhangs": overhangs,
                }
            self._last_tool_call = {"actions": actions, "frames": frames, "results": action_results}
            self._last_snapshot = snapshot
            result_queue.put(snapshot)
        if quit_requested:
            return self._do_game_over()
        return None

    def _do_game_over(self) -> State:
        """Stop server and return to menu (no GameOverState for MCP)."""
        self.audio.stop_music()
        self._stop_server()
        _logger.debug(
            "MCP game over | score=%d, lines=%d, level=%d",
            self.stats.score,
            self.stats.total_lines,
            self.stats.level,
        )
        if self.menu is not None:
            return self.menu
        from tetris.states.menu import MenuState

        return MenuState(self.screen, self.font, self.audio)

    def draw(self, screen: pygame.Surface, *, particles: ParticleSystem | None = None) -> None:
        """Render the board + debug HUD (if debug mode)."""
        if particles is not None:
            self.renderer.render_frame(self, particles)
        if self.debug:
            draw_mcp_hud(screen, self.font, self)


def draw_mcp_hud(screen: pygame.Surface, font: pygame.font.Font, state: MCPState) -> None:
    """Render MCP debug info: server status, port, last tool call, last snapshot."""
    x, y = HUD_POSITIONS["mcp_hud"]
    lines: list[str] = []
    server_status = "Actif" if state._server is not None else "Arrêté"
    lines.append(f"MCP (127.0.0.1:{state.mcp_config.port}) — {server_status}")
    if state._last_tool_call is not None:
        tc = state._last_tool_call
        lines.append(f"Actions: {', '.join(tc['actions']) or '(aucune)'}")
        lines.append(f"Frames: {tc['frames']}")
        results = tc.get("results")
        if results:
            lines.append(f"Résultats: {', '.join(results)}")
        else:
            lines.append(f"Résultats: {'(simulation)' if tc.get('simulate') else '(aucune)'}")
    if state._last_snapshot is not None:
        snap = state._last_snapshot
        lines.append(f"Score: {snap['score']}  Lignes: {snap['lines']}  Niveau: {snap['level']}")
        lines.append(f"Game Over: {'Oui' if snap['game_over'] else 'Non'}")
    for i, text in enumerate(lines):
        surf = font.render(text, True, (200, 200, 200))
        screen.blit(surf, (x, y + i * 28))
