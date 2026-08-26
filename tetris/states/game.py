"""GameState: abstract base for gameplay states (human, AI, future MCP)."""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

if TYPE_CHECKING:
    from tetris.states.menu import MenuState

from dataclasses import dataclass


@dataclass(frozen=True)
class GameConfig:
    """Shared gameplay settings."""

    handicap: int
    sound_volume: int
    music_volume: int
    music_song: str
    debug: bool
    ghost_piece: bool
    preview_count: int
    speed_mode: str

    holes_overhangs_help: str = "none"
    seed: int | None = None


import random

import pygame

from tetris.audio import AudioManager
from tetris.game.board import Board, ClearedRow, LineClearResult
from tetris.game.piece_provider import PieceProvider
from tetris.game.stats import GameStats
from tetris.game.tetromino import Tetromino
from tetris.logger import get_logger
from tetris.settings import (
    BLOCK_SIZE,
    BOARD_OFFSET_X,
    BOARD_OFFSET_Y,
    DROP_BASE,
    DROP_MIN_INTERVAL,
    HIDDEN_ROWS,
    LOCK_DELAY_MS,
    LOCK_DELAY_RESETS,
    MUSIC_BASE_SPEED,
    MUSIC_MAX_SPEED,
    MUSIC_SPEED_PER_LEVEL,
    SOFT_DROP_FACTOR,
    SPEED_MODES,
)
from tetris.states.base import State
from tetris.visuals.particles import ParticleSystem
from tetris.visuals.renderer import Renderer

_logger = get_logger("game")


def _drop_interval(level: int, drop_step: float) -> float:
    """Seconds per row at the given level (Tetris Guideline gravity)."""
    if drop_step == 0:
        return 1.0
    base = max(DROP_MIN_INTERVAL, DROP_BASE - level * drop_step)
    return max(DROP_MIN_INTERVAL, base**level)


def _music_speed_for_level(level: int) -> float:
    """Music playback speed factor for the given level."""
    return min(MUSIC_BASE_SPEED + level * MUSIC_SPEED_PER_LEVEL, MUSIC_MAX_SPEED)


class GameState(State):
    """Abstract base for gameplay states (human, AI, future MCP).

    Provides shared game infrastructure: board, pieces, stats, movement
    primitives, lock delay, gravity, and rendering. Subclasses override
    ``handle_event`` and ``update`` for player-specific input. Do not
    instantiate directly — use :class:`HumanState` or :class:`AIState`.
    """

    paused: bool

    def __init__(
        self,
        screen: pygame.Surface,
        font: pygame.font.Font,
        audio: AudioManager,
        config: GameConfig,
        piece_provider: PieceProvider | None = None,
        menu: MenuState | None = None,
    ) -> None:
        """Initialize the shared game infrastructure.

        Sets up the board (with handicap), piece provider, lock-delay
        state, and the preview/hold piece queues. Subclasses handle
        keybind setup and DAS state.

        Args:
            screen: Pygame display surface.
            font: Font for HUD text.
            audio: Audio manager.
            config: Gameplay settings (handicap, sound, debug, etc.).
            piece_provider: Spawn controller (created if ``None``).
            menu: Parent :class:`MenuState` for settings access.
        """
        self.screen, self.font, self.audio = screen, font, audio
        self.audio.apply_settings(config.sound_volume, config.music_volume, config.music_song)
        self._last_level = 0
        self._pending_level_up = False
        self.menu = menu
        self.debug = config.debug
        self.ghost_piece = config.ghost_piece
        self.preview_count = config.preview_count

        self.holes_overhangs_help = config.holes_overhangs_help
        self.renderer = Renderer(screen, font)
        self.speed_mode = config.speed_mode
        self.seed: int | None = config.seed if config.seed is not None else random.randint(0, 999_999_999)
        rng = random.Random(self.seed)
        self.board = Board()
        self.board.apply_handicap(config.handicap, rng)
        if piece_provider is not None:
            self.pieces = PieceProvider(
                mode=piece_provider.mode,
                path=piece_provider.path,
                allowed_types=piece_provider.allowed_types,
                generator=piece_provider.generator,
                seed=self.seed,
            )
        else:
            self.pieces = PieceProvider(seed=self.seed)
        self.current_piece = Tetromino(self.pieces.next_type())
        self.next_piece = Tetromino(self.pieces.next_type())
        self.preview_pieces = [Tetromino(self.pieces.next_type()) for _ in range(max(0, config.preview_count - 1))]
        self.drop_time: float = 0.0
        self.stats = GameStats()
        self.current_speed = _drop_interval(0, SPEED_MODES[self.speed_mode])
        self.game_over: bool = False
        self.paused: bool = False
        self.down_pressed = False
        # Hold piece state
        self.hold_piece: Tetromino | None = None
        self._can_hold = True
        # Locked-piece history. Populated by _lock_and_spawn; the simulator
        # resets/restores it around each call. Harmless in real play.
        self.locked_pieces: list[str] = []
        # Lock delay state
        self._lock_timer: float = 0.0
        self._lock_resets: int = 0
        self._grounded: bool = False
        # Mute key (shared by all player types)
        from tetris.settings import DEFAULT_KEYBINDS

        kb = menu.keybinds if menu is not None else dict(DEFAULT_KEYBINDS)
        self._mute_key: int = kb["mute"]
        self.player_type: str = "Humain"

    # --- Input handlers (SLAP: one operation each) ---------------------

    def _move_left(self) -> None:
        if not self.paused and self.board.is_valid_move(self.current_piece, dx=-1):
            self.current_piece.move(-1, 0)
            self._on_piece_moved()

    def _move_right(self) -> None:
        if not self.paused and self.board.is_valid_move(self.current_piece, dx=1):
            self.current_piece.move(1, 0)
            self._on_piece_moved()

    def _on_piece_moved(self) -> None:
        """Reset lock delay when piece moves or rotates (SRS infinite spin)."""
        if self._grounded and self._lock_resets < LOCK_DELAY_RESETS:
            self._lock_timer = 0.0
            self._lock_resets += 1

    def _rotate_cw(self) -> None:
        if not self.paused and self.board.try_rotate(self.current_piece, 1):
            self.audio.play("rotate_cw")
            self._on_piece_moved()

    def _rotate_ccw(self) -> None:
        if not self.paused and self.board.try_rotate(self.current_piece, -1):
            self.audio.play("rotate_ccw")
            self._on_piece_moved()

    def _soft_drop(self) -> None:
        self.down_pressed = True
        self.audio.play("soft_drop")

    def _hard_drop(self) -> None:
        """Drop piece to bottom instantly, lock, and spawn next piece."""
        if self.paused:
            return
        if not self.current_piece:
            # Simulator horizon exceeded: no active piece to drop.
            from tetris.states.simulator import SimulationError

            raise SimulationError("horizon exceeded: no piece to act on")
        distance = self.board.hard_drop(self.current_piece)
        self.stats.add_hard_drop(distance)
        self._lock_and_spawn(hard_drop=True)

    def _hold(self) -> None:
        """Swap current piece with held piece. Can't hold twice per lock."""
        if self.paused or not self._can_hold:
            return
        if self.hold_piece is None:
            self.hold_piece = Tetromino(self.current_piece.type)
            self._advance_piece_pipeline()
        else:
            held_type = self.hold_piece.type
            self.hold_piece = Tetromino(self.current_piece.type)
            self.current_piece = Tetromino(held_type)
        self._can_hold = False
        self._lock_timer = 0.0
        self._lock_resets = 0
        self._grounded = False
        self.drop_time = 0
        self.down_pressed = False

    def _advance_piece_pipeline(self) -> None:
        """Move next_piece to current, refill from preview/pieces.

        Shared by ``_hold`` (hold empty → swap in next) and ``_lock_and_spawn``.
        When pieces are exhausted (simulator horizon), drains to ``None``.
        """
        self.current_piece = self.next_piece
        if self.preview_pieces:
            self.next_piece = self.preview_pieces.pop(0)
            refill: str | None = self.pieces.next_type()
            if refill is not None:
                self.preview_pieces.append(Tetromino(refill))
        else:
            refill: str | None = self.pieces.next_type()
            if refill is None:
                self.next_piece = None  # type: ignore[assignment]
                self.preview_pieces = []
            else:
                self.next_piece = Tetromino(refill)

    _ACTIONS: ClassVar[dict[str, str]] = {
        "left": "_move_left",
        "right": "_move_right",
        "rotate_cw": "_rotate_cw",
        "rotate_ccw": "_rotate_ccw",
        "soft_drop": "_soft_drop",
        "hard_drop": "_hard_drop",
        "hold": "_hold",
        "start_game": "_reset_game",
    }

    def _execute_actions(self, actions: list[str]) -> list[str]:
        """Dispatch each action name to the corresponding GameState handler.

        Generic across player types (human/AI/MCP); lifted from ``MCPState`` so
        the simulator can replay actions on any ``GameState``. ``start_game``
        maps to ``_reset_game`` (present only on states that support it; treated
        as unknown elsewhere).
        """
        results: list[str] = []
        for action in actions:
            if action == "hold" and not self._can_hold:
                results.append("blocked")
                continue
            handler_name = self._ACTIONS.get(action)
            if handler_name is not None:
                handler = getattr(self, handler_name, None)
                if handler is not None:
                    handler()
                    results.append("ok")
                else:
                    results.append(f"unknown:{action}")
            else:
                results.append(f"unknown:{action}")
        return results

    def _lock_and_spawn(self, hard_drop: bool = False) -> LineClearResult:
        """Lock current piece, update stats, spawn next. Returns (cleared, rows_data)."""
        locked_blocks = self.current_piece.get_blocks()
        hidden = HIDDEN_ROWS
        # Top-out: piece locked entirely above the visible field
        if all(y < hidden for _, y in locked_blocks):
            self.game_over = True
            self.audio.play("hard_drop")
            _logger.debug("Top out: %s locked above visible field", self.current_piece.type)
            return LineClearResult(0, [])
        tspin = self.board.is_tspin(self.current_piece)
        cleared, rows_data = self.board.lock_tetromino(self.current_piece)
        locked_type = self.current_piece.type
        self.locked_pieces.append(locked_type)
        self.stats.on_piece_locked(cleared, tspin=tspin)
        if cleared > 0:
            self.audio.play(f"clear_{cleared}")
        elif hard_drop:
            self.audio.play("hard_drop")
        else:
            self.audio.play("spawn")
        self._advance_piece_pipeline()
        self.down_pressed = False
        self._can_hold = True
        self._lock_timer = 0.0
        self._lock_resets = 0
        self._grounded = False
        if self.current_piece and not self.board.is_valid_move(self.current_piece):
            self.game_over = True
        _logger.debug("Locked %s, cleared %d", locked_type, cleared)
        return LineClearResult(cleared, rows_data)

    def _do_game_over(self) -> State:
        """Stop music, save, and transition to GameOverState."""
        self.audio.stop_music()
        _logger.debug(
            "Game over | score=%d, lines=%d, level=%d",
            self.stats.score,
            self.stats.total_lines,
            self.stats.level,
        )
        self.pieces.save()
        from tetris.states.game_over import GameOverState

        return GameOverState(self.screen, self.font, self.audio, self, self.menu)

    # --- Event / update / render ----------------------------------------

    def _return_to_menu(self) -> State:
        """Return the originating menu if available, else create a fresh one."""
        if self.menu is not None:
            return self.menu
        from tetris.states.menu import MenuState

        return MenuState(self.screen, self.font, self.audio)

    def _on_exit(self) -> None:
        """Hook called before returning to menu on ESC. Override in subclasses."""

    def handle_event(self, event: pygame.event.Event) -> State | None:
        """Shared event handler: mute key + ESC (back to menu).

        Subclasses override to add player-specific keys (movement, pause, etc.)
        and call ``super().handle_event`` first.

        Returns a new :class:`State` on ESC (back to menu), or ``None``.
        """
        if event.type == pygame.KEYDOWN:
            if event.key == self._mute_key:
                self.audio.toggle_mute()
            elif event.key == pygame.K_ESCAPE:
                self.audio.stop_music()
                self.pieces.save()
                self._on_exit()
                return self._return_to_menu()
        return None

    def update(self, dt: float, particles: ParticleSystem) -> State | None:
        """Advance gravity, lock delay, and level-up SFX.

        Returns a new :class:`State` on game-over, or ``None`` to stay.
        """
        if self.game_over:
            return self._do_game_over()
        if self.paused:
            return None

        # --- Gravity / soft drop ---
        self.drop_time += dt
        step = SPEED_MODES[self.speed_mode]
        speed = (
            _drop_interval(self.stats.level, step) * SOFT_DROP_FACTOR
            if self.down_pressed
            else _drop_interval(self.stats.level, step)
        )
        self.current_speed = speed

        # Check grounded state
        can_drop = self.board.is_valid_move(self.current_piece, dy=1)
        self._grounded = not can_drop

        if can_drop:
            if self.drop_time / 1000 >= speed:
                self.current_piece.move(0, 1)
                if self.down_pressed:
                    self.stats.add_soft_drop(1)
                self.drop_time = 0
        else:
            # Piece is grounded: run lock delay (non-locking soft drop)
            self._lock_timer += dt
            if self._lock_timer >= LOCK_DELAY_MS:
                cleared, rows_data = self._lock_and_spawn()
                if cleared > 0:
                    self._emit_line_particles(particles, rows_data)
                self._lock_timer = 0.0
                self._lock_resets = 0
                self.drop_time = 0

        if self.stats.level > self._last_level:
            self._pending_level_up = True
            self.audio.set_music_speed(_music_speed_for_level(self.stats.level))
        self._last_level = self.stats.level
        if self._pending_level_up and self.audio.play("level_up"):
            self._pending_level_up = False
        if self.game_over:
            return self._do_game_over()  # type: ignore[unreachable]
        return None

    def _emit_line_particles(self, particles: ParticleSystem, rows_data: list[ClearedRow]) -> None:
        hidden = HIDDEN_ROWS
        for r_idx, colors in rows_data:
            for c_idx, col in enumerate(colors):
                particles.emit(
                    c_idx * BLOCK_SIZE + BOARD_OFFSET_X + BLOCK_SIZE // 2,
                    (r_idx - hidden) * BLOCK_SIZE + BOARD_OFFSET_Y + BLOCK_SIZE // 2,
                    col,
                    80,
                )

    def draw(self, screen: pygame.Surface, *, particles: ParticleSystem | None = None) -> None:
        """Delegate rendering to :meth:`Renderer.render_frame`."""
        if particles is not None:
            self.renderer.render_frame(self, particles)
