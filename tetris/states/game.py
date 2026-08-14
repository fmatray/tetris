"""Game state: the active playfield, piece movement, scoring, locking."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tetris.states.menu import MenuState

import pygame

from tetris.audio import AudioManager
from tetris.game.board import Board
from tetris.game.piece_provider import PieceProvider
from tetris.game.stats import GameStats
from tetris.game.tetromino import Tetromino
from tetris.logger import get_logger
from tetris.settings import (
    BLOCK_SIZE,
    BOARD_HEIGHT,
    BOARD_OFFSET_X,
    BOARD_OFFSET_Y,
    DAS_DELAY_MS,
    DAS_REPEAT_MS,
    DROP_BASE,
    DROP_MIN_INTERVAL,
    DROP_STEP,
    LOCK_DELAY_MS,
    LOCK_DELAY_RESETS,
    MUSIC_BASE_SPEED,
    MUSIC_MAX_SPEED,
    MUSIC_SPEED_PER_LEVEL,
    SOFT_DROP_FACTOR,
    VISIBLE_ROWS,
)
from tetris.states.base import State
from tetris.visuals.particles import ParticleSystem
from tetris.visuals.renderer import Renderer

_logger = get_logger("game")


def _drop_interval(level: int) -> float:
    """Seconds per row at the given level (Tetris Guideline gravity)."""
    base = max(DROP_MIN_INTERVAL, DROP_BASE - level * DROP_STEP)
    return max(DROP_MIN_INTERVAL, base ** level)


def _music_speed_for_level(level: int) -> float:
    """Music playback speed factor for the given level."""
    return min(MUSIC_BASE_SPEED + level * MUSIC_SPEED_PER_LEVEL, MUSIC_MAX_SPEED)

class GameState(State):
    """Active gameplay: spawns pieces, processes input, advances the board."""

    def __init__(
        self,
        screen: pygame.Surface,
        font: pygame.font.Font,
        audio: AudioManager,
        handicap: int,
        sound_volume: int = 3,
        music_volume: int = 3,
        music_song: str = "korobeiniki",
        piece_provider: PieceProvider | None = None,
        menu: MenuState | None = None,
        debug: bool = False,
        ghost_piece: bool = True,
    ) -> None:
        self.screen, self.font, self.audio = screen, font, audio
        self.audio.apply_settings(sound_volume, music_volume, music_song)
        self._last_level = 0
        self._pending_level_up = False
        self.menu = menu
        self.debug = debug
        self.ghost_piece = ghost_piece
        self.renderer = Renderer(screen, font)
        self.board = Board()
        self.board.apply_handicap(handicap)
        self.pieces = piece_provider or PieceProvider()
        self.current_piece = Tetromino(self.pieces.next_type())
        self.next_piece = Tetromino(self.pieces.next_type())
        self.preview_pieces = [Tetromino(self.pieces.next_type()) for _ in range(2)]
        self.drop_time = 0
        self.stats = GameStats()
        self.current_speed = _drop_interval(0)
        self.game_over = False
        self.paused = False
        self.down_pressed = False
        # Hold piece state
        self.hold_piece: Tetromino | None = None
        self._can_hold = True
        # Lock delay state
        self._lock_timer: float = 0.0
        self._lock_resets: int = 0
        self._grounded: bool = False
        # DAS state: {key: held_ms}
        self._das_held: dict[int, float] = {}
        self._setup_keybinds(menu)

    def _setup_keybinds(self, menu: MenuState | None) -> None:
        """Build key → action map from the menu's keybindings (or defaults)."""
        from tetris.settings import DEFAULT_KEYBINDS

        kb = menu.keybinds if menu is not None else dict(DEFAULT_KEYBINDS)
        self.input_map: dict[int, Callable[[], None]] = {
            kb["move_left"]: self._move_left,
            kb["move_right"]: self._move_right,
            kb["rotate_cw"]: self._rotate_cw,
            kb["rotate_ccw"]: self._rotate_ccw,
            kb["soft_drop"]: self._toggle_down_true,
            kb["hard_drop"]: self._hard_drop,
            kb["hold"]: self._hold,
        }
        self._mute_key: int = kb["mute"]
        self._pause_key: int = kb["pause"]
        self._soft_drop_key: int = kb["soft_drop"]
        self._left_key: int = kb["move_left"]
        self._right_key: int = kb["move_right"]
        self._hold_key: int = kb["hold"]

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

    def _toggle_down_true(self) -> None:
        self.down_pressed = True
        self.audio.play("soft_drop")

    def _hard_drop(self) -> None:
        """Drop piece to bottom instantly, lock, and spawn next piece."""
        if self.paused:
            return
        distance = self.board.hard_drop(self.current_piece)
        self.stats.add_hard_drop(distance)
        self._lock_and_spawn(hard_drop=True)

    def _hold(self) -> None:
        """Swap current piece with held piece. Can't hold twice per lock."""
        if self.paused or not self._can_hold:
            return
        if self.hold_piece is None:
            self.hold_piece = Tetromino(self.current_piece.type)
            self.current_piece = self.next_piece
            self.next_piece = self.preview_pieces.pop(0)
            self.preview_pieces.append(Tetromino(self.pieces.next_type()))
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

    def _lock_and_spawn(self, hard_drop: bool = False) -> tuple[int, list]:
        """Lock current piece, update stats, spawn next. Returns (cleared, rows_data)."""
        locked_blocks = self.current_piece.get_blocks()
        hidden = BOARD_HEIGHT - VISIBLE_ROWS
        # Top-out: piece locked entirely above the visible field
        if all(y < hidden for _, y in locked_blocks):
            self.game_over = True
            self.audio.play("hard_drop")
            _logger.debug("Top out: %s locked above visible field", self.current_piece.type)
            return 0, []
        tspin = self.board.is_tspin(self.current_piece)
        cleared, rows_data = self.board.lock_tetromino(self.current_piece)
        locked_type = self.current_piece.type
        self.stats.on_piece_locked(cleared, tspin=tspin)
        if cleared > 0:
            self.audio.play(f"clear_{cleared}")
        elif hard_drop:
            self.audio.play("hard_drop")
        else:
            self.audio.play("spawn")
        self.current_piece = self.next_piece
        self.next_piece = self.preview_pieces.pop(0)
        self.preview_pieces.append(Tetromino(self.pieces.next_type()))
        self.down_pressed = False
        self._can_hold = True
        self._lock_timer = 0.0
        self._lock_resets = 0
        self._grounded = False
        if not self.board.is_valid_move(self.current_piece):
            self.game_over = True
        _logger.debug("Locked %s, cleared %d", locked_type, cleared)
        return cleared, rows_data

    def _do_game_over(self) -> State:
        """Stop music, save, and transition to GameOverState."""
        self.audio.stop_music()
        _logger.debug(
            "Game over | score=%d, lines=%d, level=%d",
            self.stats.score, self.stats.total_lines, self.stats.level,
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

    def handle_event(self, event: pygame.event.Event) -> State | None:
        if event.type == pygame.KEYDOWN:
            if event.key == self._pause_key:
                self.paused = not self.paused
            elif event.key == self._mute_key:
                self.audio.toggle_mute()
            elif event.key == pygame.K_ESCAPE:
                self.audio.stop_music()
                self.pieces.save()
                return self._return_to_menu()
            elif event.key in self.input_map:
                self.input_map[event.key]()
                # Start DAS tracking for left/right
                if event.key in (self._left_key, self._right_key):
                    self._das_held[event.key] = 0.0
        elif event.type == pygame.KEYUP:
            if event.key == self._soft_drop_key:
                self.down_pressed = False
            if event.key in self._das_held:
                del self._das_held[event.key]
        return None

    def update(self, dt: float, particles: ParticleSystem) -> State | None:
        if self.game_over:
            return self._do_game_over()
        if self.paused:
            return None

        # --- DAS auto-shift ---
        for key in list(self._das_held):
            self._das_held[key] += dt
            held = self._das_held[key]
            if held >= DAS_DELAY_MS:
                # In repeat phase: fire every DAS_REPEAT_MS
                since_last = held - DAS_DELAY_MS
                if since_last >= DAS_REPEAT_MS:
                    self._das_held[key] = DAS_DELAY_MS
                    self.input_map[key]()

        # --- Gravity / soft drop ---
        self.drop_time += dt
        speed = (
            _drop_interval(self.stats.level) * SOFT_DROP_FACTOR
            if self.down_pressed
            else _drop_interval(self.stats.level)
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
            return self._do_game_over()
        return None

    def _tick(self, particles: ParticleSystem) -> None:
        """Legacy gravity tick — kept for AIState compatibility.

        AIState calls super().update() which no longer uses _tick, but
        _execute_macro_action calls _lock_and_spawn directly.
        """
        if self.board.is_valid_move(self.current_piece, dy=1):
            self.current_piece.move(0, 1)
            if self.down_pressed:
                self.stats.add_soft_drop(1)
            return

        cleared, rows_data = self._lock_and_spawn()
        if cleared > 0:
            self._emit_line_particles(particles, rows_data)

    def _emit_line_particles(self, particles: ParticleSystem, rows_data) -> None:
        hidden = BOARD_HEIGHT - VISIBLE_ROWS
        for r_idx, colors in rows_data:
            for c_idx, col in enumerate(colors):
                particles.emit(
                    c_idx * BLOCK_SIZE + BOARD_OFFSET_X + BLOCK_SIZE // 2,
                    (r_idx - hidden) * BLOCK_SIZE + BOARD_OFFSET_Y + BLOCK_SIZE // 2,
                    col,
                    80,
                )

    def draw(self, screen: pygame.Surface, *, particles: ParticleSystem | None = None) -> None:
        if particles is not None:
            self.renderer.render_frame(self, particles)