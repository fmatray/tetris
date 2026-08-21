"""MCP player state: external agent plays via HTTP tool calls.

The game is frozen between ``play()`` calls — gravity does NOT advance
unless ``frames > 0`` in the request. This gives the external agent full
control over game timing.
"""

from __future__ import annotations

import queue
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, ClassVar

import pygame

from tetris.ai.rewards import board_to_grid
from tetris.logger import get_logger
from tetris.settings import HUD_POSITIONS
from tetris.states.game import GameConfig, GameState
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

    _ACTIONS: ClassVar[dict[str, str]] = {
        "left": "_move_left",
        "right": "_move_right",
        "rotate_cw": "_rotate_cw",
        "rotate_ccw": "_rotate_ccw",
        "soft_drop": "_soft_drop",
        "hard_drop": "_hard_drop",
        "hold": "_hold",
    }

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
        self._action_queue: queue.Queue[tuple[list[str], int, queue.Queue[dict[str, Any]]]] = queue.Queue()
        self._server: TetrisMCPServer | None = None
        self._last_tool_call: dict[str, Any] | None = None
        self._last_snapshot: dict[str, Any] | None = None
        if start_server:
            self._start_server()

    def _start_server(self) -> None:
        from tetris.mcp_server import TetrisMCPServer

        self._server = TetrisMCPServer(self._action_queue, self.mcp_config.port)
        self._server.start()
        _logger.debug("MCP server started on port %d", self.mcp_config.port)

    def _stop_server(self) -> None:
        if self._server is not None:
            self._server.stop()
            self._server = None
            _logger.debug("MCP server stopped")

    def _execute_actions(self, actions: list[str]) -> list[str]:
        """Dispatch each action name to the corresponding GameState handler."""
        results: list[str] = []
        for action in actions:
            handler_name = self._ACTIONS.get(action)
            if handler_name is not None:
                getattr(self, handler_name)()
                results.append("ok")
            else:
                results.append(f"unknown:{action}")
        return results

    def _board_snapshot(self, action_results: list[str] | None = None) -> dict[str, Any]:
        """Return current board state as a dict for the MCP client."""
        grid = board_to_grid(self.board)
        snap: dict[str, Any] = {
            "board": grid.astype(int).tolist(),
            "current_piece": self.current_piece.type,
            "next_piece": self.next_piece.type,
            "hold_piece": self.hold_piece.type if self.hold_piece else None,
            "can_hold": self._can_hold,
            "score": self.stats.score,
            "lines": self.stats.total_lines,
            "level": self.stats.level,
            "game_over": self.game_over,
        }
        if action_results is not None:
            snap["action_results"] = action_results
        return snap

    def update(self, dt: float, particles: ParticleSystem) -> State | None:
        """Poll action queue; if empty, game stays frozen (return None).

        If a request is pending: execute actions, advance ``frames`` ticks,
        return the board snapshot on the result queue, check game-over.
        """
        if self.game_over:
            return self._do_game_over()

        try:
            actions, frames, result_queue = self._action_queue.get_nowait()
        except queue.Empty:
            return None

        action_results = self._execute_actions(actions)
        self._last_tool_call = {"actions": actions, "frames": frames, "results": action_results}

        for _ in range(frames):
            if self.game_over:
                break
            super().update(dt, particles)

        snapshot = self._board_snapshot(action_results)
        self._last_snapshot = snapshot
        result_queue.put(snapshot)

        return self._do_game_over() if self.game_over else None

    def _do_game_over(self) -> State:
        """Stop server and return to menu (no GameOverState for MCP)."""
        self.audio.stop_music()
        self.pieces.save()
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
    lines.append(f"MCP: {server_status} :{state.mcp_config.port}")
    if state._last_tool_call is not None:
        tc = state._last_tool_call
        lines.append(f"Actions: {', '.join(tc['actions']) or '(aucune)'}")
        lines.append(f"Frames: {tc['frames']}")
        lines.append(f"Résultats: {', '.join(tc['results']) or '(aucune)'}")
    if state._last_snapshot is not None:
        snap = state._last_snapshot
        lines.append(f"Score: {snap['score']}  Lignes: {snap['lines']}  Niveau: {snap['level']}")
        lines.append(f"Game Over: {'Oui' if snap['game_over'] else 'Non'}")
    for i, text in enumerate(lines):
        surf = font.render(text, True, (200, 200, 200))
        screen.blit(surf, (x, y + i * 20))
