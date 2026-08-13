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
    BOARD_OFFSET_X,
    BOARD_OFFSET_Y,
    SOFT_DROP_FACTOR,
    drop_interval,
    music_speed_for_level,
)
from tetris.states.base import State
from tetris.visuals.particles import ParticleSystem
from tetris.visuals.renderer import Renderer

_logger = get_logger("game")

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
    ) -> None:
        self.screen, self.font, self.audio = screen, font, audio
        self.audio.apply_settings(sound_volume, music_volume, music_song)
        self._last_level = 0
        self._pending_level_up = False
        self.menu = menu
        self.debug = debug
        self.renderer = Renderer(screen, font)
        self.board = Board()
        self.board.apply_handicap(handicap)
        self.pieces = piece_provider or PieceProvider()
        self.current_piece = Tetromino(self.pieces.next_type())
        self.next_piece = Tetromino(self.pieces.next_type())
        self.drop_time = 0
        self.stats = GameStats()
        self.current_speed = drop_interval(0)
        self.game_over = False
        self.paused = False
        self.down_pressed = False

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
        }
        self._mute_key: int = kb["mute"]
        self._pause_key: int = kb["pause"]
        self._soft_drop_key: int = kb["soft_drop"]

    # --- Input handlers (SLAP: one operation each) ---------------------

    def _move_left(self) -> None:
        if not self.paused and self.board.is_valid_move(self.current_piece, dx=-1):
            self.current_piece.move(-1, 0)

    def _move_right(self) -> None:
        if not self.paused and self.board.is_valid_move(self.current_piece, dx=1):
            self.current_piece.move(1, 0)

    def _rotate_cw(self) -> None:
        if not self.paused and self.board.is_valid_move(
            self.current_piece, rotation=self.current_piece.rotation + 1
        ):
            self.current_piece.rotate(1)
            self.audio.play("rotate_cw")

    def _rotate_ccw(self) -> None:
        if not self.paused and self.board.is_valid_move(
            self.current_piece, rotation=self.current_piece.rotation - 1
        ):
            self.current_piece.rotate(-1)
            self.audio.play("rotate_ccw")

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

    def _lock_and_spawn(self, hard_drop: bool = False) -> tuple[int, list]:
        """Lock current piece, update stats, spawn next. Returns (cleared, rows_data)."""
        cleared, rows_data = self.board.lock_tetromino(self.current_piece)
        locked_type = self.current_piece.type
        self.stats.on_piece_locked(cleared)
        if cleared > 0:
            self.audio.play(f"clear_{cleared}")
        elif hard_drop:
            self.audio.play("hard_drop")
        else:
            self.audio.play("spawn")
        self.current_piece, self.next_piece = self.next_piece, Tetromino(
            self.pieces.next_type()
        )
        self.down_pressed = False
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
        elif event.type == pygame.KEYUP and event.key == self._soft_drop_key:
            self.down_pressed = False
        return None

    def update(self, dt: float, particles: ParticleSystem) -> State | None:
        if self.game_over:
            return self._do_game_over()
        if self.paused:
            return None
        self.drop_time += dt
        speed = (
            drop_interval(self.stats.level) * SOFT_DROP_FACTOR
            if self.down_pressed
            else drop_interval(self.stats.level)
        )
        self.current_speed = speed
        if self.drop_time / 1000 >= speed:
            self._tick(particles)
            self.drop_time = 0
        if self.stats.level > self._last_level:
            self._pending_level_up = True
            self.audio.set_music_speed(music_speed_for_level(self.stats.level))
        self._last_level = self.stats.level
        if self._pending_level_up and self.audio.play("level_up"):
            self._pending_level_up = False
        if self.game_over:
            return self._do_game_over()
        return None

    def _tick(self, particles: ParticleSystem) -> None:
        """Advance one drop step: move down or lock the current piece."""
        if self.board.is_valid_move(self.current_piece, dy=1):
            self.current_piece.move(0, 1)
            if self.down_pressed:
                self.stats.add_soft_drop(1)
            return

        cleared, rows_data = self._lock_and_spawn()
        if cleared > 0:
            self._emit_line_particles(particles, rows_data)

    def _emit_line_particles(self, particles: ParticleSystem, rows_data) -> None:
        for r_idx, colors in rows_data:
            for c_idx, col in enumerate(colors):
                particles.emit(
                    c_idx * BLOCK_SIZE + BOARD_OFFSET_X + BLOCK_SIZE // 2,
                    r_idx * BLOCK_SIZE + BOARD_OFFSET_Y + BLOCK_SIZE // 2,
                    col,
                    80,
                )

    def draw(self, screen: pygame.Surface, *, particles: ParticleSystem | None = None) -> None:
        if particles is not None:
            self.renderer.render_frame(self, particles)