"""Game state: the active playfield, piece movement, scoring, locking."""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional
if TYPE_CHECKING:
    from tetris.states.menu import MenuState

import pygame

from tetris.settings import (
    BLOCK_SIZE,
    BOARD_OFFSET_X,
    BOARD_OFFSET_Y,
    DROP_BASE,
    DROP_DECAY,
    SOFT_DROP_FACTOR,
)
from tetris.audio import AudioManager
from tetris.game.board import Board
from tetris.game.stats import GameStats
from tetris.game.tetromino import Tetromino
from tetris.game.piece_provider import PieceProvider
from tetris.states.base import State
from tetris.visuals.particles import ParticleSystem
from tetris.visuals.renderer import Renderer


class GameState(State):
    """Active gameplay: spawns pieces, processes input, advances the board."""

    def __init__(
        self,
        screen: pygame.Surface,
        font: pygame.font.Font,
        audio: AudioManager,
        handicap: int,
        sound_enabled: bool = True,
        piece_provider: "PieceProvider | None" = None,
        menu: "MenuState | None" = None,
    ) -> None:
        self.screen, self.font, self.audio = screen, font, audio
        self.audio.enabled = sound_enabled
        self.menu = menu
        self.renderer = Renderer(screen, font)
        self.board = Board()
        self.board.apply_handicap(handicap)
        self.pieces = piece_provider or PieceProvider()
        self.current_piece = Tetromino(self.pieces.next_type())
        self.next_piece = Tetromino(self.pieces.next_type())
        self.stats = GameStats()
        self.drop_time = 0
        self.game_over = False
        self.paused = False
        self.down_pressed = False

        self.input_map = {
            pygame.K_LEFT: self._move_left,
            pygame.K_RIGHT: self._move_right,
            pygame.K_UP: self._rotate_cw,
            pygame.K_s: self._rotate_ccw,
            pygame.K_DOWN: self._toggle_down_true,
        }

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

    def _hard_drop(self) -> None:
        """Drop piece to bottom instantly, lock, and spawn next piece."""
        if self.paused:
            return
        self.board.hard_drop(self.current_piece)
        self._lock_and_spawn()

    def _lock_and_spawn(self) -> tuple[int, list]:
        """Lock current piece, update stats, spawn next. Returns (cleared, rows_data)."""
        cleared, rows_data = self.board.lock_tetromino(self.current_piece)
        self.stats.add_lines(cleared)
        if cleared > 0:
            self.audio.play(f"clear_{cleared}")
        else:
            self.audio.play("lock")
        self.current_piece, self.next_piece = self.next_piece, Tetromino(
            self.pieces.next_type()
        )
        self.down_pressed = False
        if not self.board.is_valid_move(self.current_piece):
            self.game_over = True
        return cleared, rows_data

    # --- Event / update / render ----------------------------------------

    def _return_to_menu(self) -> State:
        """Return the originating menu if available, else create a fresh one."""
        if self.menu is not None:
            return self.menu
        from tetris.states.menu import MenuState

        return MenuState(self.screen, self.font, self.audio)

    def handle_event(self, event: pygame.event.Event) -> Optional[State]:
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_SPACE:
                self.paused = not self.paused
            elif event.key == pygame.K_ESCAPE:
                self.pieces.save()
                return self._return_to_menu()
            elif event.key in self.input_map:
                self.input_map[event.key]()
        elif event.type == pygame.KEYUP and event.key == pygame.K_DOWN:
            self.down_pressed = False
        return None

    def update(self, dt: float, particles: ParticleSystem) -> Optional[State]:
        if self.paused or self.game_over:
            return None
        self.drop_time += dt
        speed = (
            DROP_BASE * SOFT_DROP_FACTOR
            if self.down_pressed
            else DROP_BASE * (DROP_DECAY ** self.stats.level)
        )
        if self.drop_time / 1000 >= speed:
            self._tick(particles)
            self.drop_time = 0
        if self.game_over:
            self.pieces.save()
            from tetris.states.game_over import GameOverState

            return GameOverState(self.screen, self.font, self.audio, self, self.menu)
        return None

    def _tick(self, particles: ParticleSystem) -> None:
        """Advance one drop step: move down or lock the current piece."""
        if self.board.is_valid_move(self.current_piece, dy=1):
            self.current_piece.move(0, 1)
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

    def draw(self, screen: pygame.Surface) -> None:
        pass  # GameState uses render() instead, called by the app loop.

    def render(self, particles: ParticleSystem) -> None:
        self.renderer.render_frame(self, particles)