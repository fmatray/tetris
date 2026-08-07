"""Game renderer: draws the board, pieces, HUD, and game-over animation.

Separation of rendering from game logic (Single Responsibility). The
renderer is a pure presentation object — it reads from game state but
never mutates it.
"""

from __future__ import annotations

import random
import sys
from typing import TYPE_CHECKING

import numpy as np
import pygame

from tetris.settings import (
    BLACK,
    BLOCK_SIZE,
    BOARD_HEIGHT,
    BOARD_OFFSET_X,
    BOARD_OFFSET_Y,
    BOARD_WIDTH,
    GAME_OVER_DURATION_MS,
    GAME_OVER_PARTICLE_COUNT,
    GRAY,
    HUD_POSITIONS,
    NEXT_PANEL_X,
    NEXT_PANEL_Y,
    SCREEN_HEIGHT,
    SCREEN_WIDTH,
    WHITE,
)
from tetris.game.board import Board
from tetris.game.tetromino import Tetromino
from tetris.visuals.particles import Particle, ParticleSystem

if TYPE_CHECKING:
    from tetris.states.game import GameState



class Renderer:
    """Draws game frames and the game-over animation."""

    _GLITCH_COLORS = [WHITE, GRAY, (255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 0), (255, 0, 255)]

    def __init__(self, screen: pygame.Surface, font: pygame.font.Font) -> None:
        self.screen = screen
        self.font = font

    # --- In-game frame --------------------------------------------------

    def render_frame(self, game: "GameState", particles: ParticleSystem) -> None:
        self.screen.fill(BLACK)
        self.draw_grid(game.board)
        self.draw_tetromino(game.current_piece)
        self._draw_text(f"SCORE: {game.stats.score}", HUD_POSITIONS["score"])
        self._draw_text(f"LINES: {game.stats.total_lines}", HUD_POSITIONS["lines"])
        self._draw_text(f"LEVEL: {game.stats.level}", HUD_POSITIONS["level"])
        self._draw_text("NEXT:", HUD_POSITIONS["next"])
        self.draw_next_piece(game.next_piece)
        if game.paused:
            pause_text = self.font.render("PAUSE", True, WHITE)
            self.screen.blit(
                pause_text,
                (SCREEN_WIDTH // 2 - pause_text.get_width() // 2, SCREEN_HEIGHT // 2),
            )
        particles.draw(self.screen)
        pygame.display.flip()

    def _draw_text(self, text: str, pos: tuple[int, int]) -> None:
        surf = self.font.render(text, True, WHITE)
        self.screen.blit(surf, pos)

    def draw_grid(self, board: Board) -> None:
        for y in range(BOARD_HEIGHT):
            for x in range(BOARD_WIDTH):
                rect = pygame.Rect(
                    x * BLOCK_SIZE + BOARD_OFFSET_X,
                    y * BLOCK_SIZE + BOARD_OFFSET_Y,
                    BLOCK_SIZE,
                    BLOCK_SIZE,
                )
                pygame.draw.rect(self.screen, GRAY, rect, 1)
                color = board.grid[y][x]
                if color:
                    pygame.draw.rect(self.screen, color, rect)

    def draw_tetromino(self, tetromino: Tetromino) -> None:
        for x, y in tetromino.get_blocks():
            if y >= 0:
                rect = pygame.Rect(
                    x * BLOCK_SIZE + BOARD_OFFSET_X,
                    y * BLOCK_SIZE + BOARD_OFFSET_Y,
                    BLOCK_SIZE,
                    BLOCK_SIZE,
                )
                pygame.draw.rect(self.screen, tetromino.color, rect)

    def draw_next_piece(self, tetromino: Tetromino) -> None:
        for x, y in tetromino.get_blocks():
            rect = pygame.Rect(
                x * BLOCK_SIZE + NEXT_PANEL_X,
                y * BLOCK_SIZE + NEXT_PANEL_Y,
                BLOCK_SIZE,
                BLOCK_SIZE,
            )
            pygame.draw.rect(self.screen, tetromino.color, rect)

    # --- Game-over animation --------------------------------------------

    def play_game_over_animation(self, game: "GameState", audio) -> None:
        """Run the chaotic 4-second game-over sequence (blocking)."""
        start_time = pygame.time.get_ticks()
        particles: list[Particle] = []
        for _ in range(GAME_OVER_PARTICLE_COUNT):
            particles.append(
                Particle(
                    random.randint(BOARD_OFFSET_X, BOARD_OFFSET_X + BOARD_WIDTH * BLOCK_SIZE),
                    random.randint(BOARD_OFFSET_Y, BOARD_OFFSET_Y + BOARD_HEIGHT * BLOCK_SIZE),
                    random.choice(self._GLITCH_COLORS),
                )
            )
        audio.play("game_over")
        while pygame.time.get_ticks() - start_time < GAME_OVER_DURATION_MS:
            elapsed = pygame.time.get_ticks() - start_time
            if random.random() < 0.1:
                self.screen.fill((random.randint(50, 150), 0, 0))
                audio.play("glitch")
            else:
                self.screen.fill(BLACK)
            shake_x = (
                random.randint(-15, 15) if elapsed < 1500 else random.randint(-3, 3)
            )
            shake_y = (
                random.randint(-15, 15) if elapsed < 1500 else random.randint(-3, 3)
            )
            board_surf = pygame.Surface(
                (BOARD_WIDTH * BLOCK_SIZE, BOARD_HEIGHT * BLOCK_SIZE)
            )
            board_surf.set_colorkey(BLACK)
            glitch = random.random()
            for y in range(BOARD_HEIGHT):
                for x in range(BOARD_WIDTH):
                    rect = pygame.Rect(
                        x * BLOCK_SIZE, y * BLOCK_SIZE, BLOCK_SIZE, BLOCK_SIZE
                    )
                    pygame.draw.rect(board_surf, GRAY, rect, 1)
                    if game.board.grid[y][x]:
                        color = (
                            game.board.grid[y][x]
                            if glitch <= 0.95
                            else (
                                random.randint(0, 255),
                                random.randint(0, 255),
                                random.randint(0, 255),
                            )
                        )
                        if color:
                            pygame.draw.rect(board_surf, color, rect)
            for x, y in game.current_piece.get_blocks():
                if y >= 0:
                    pygame.draw.rect(
                        board_surf,
                        game.current_piece.color,
                        (x * BLOCK_SIZE, y * BLOCK_SIZE, BLOCK_SIZE, BLOCK_SIZE),
                    )
            self.screen.blit(board_surf, (BOARD_OFFSET_X + shake_x, BOARD_OFFSET_Y + shake_y))
            if random.random() < 0.3:
                particles.append(
                    Particle(
                        random.randint(0, SCREEN_WIDTH),
                        random.randint(0, SCREEN_HEIGHT),
                        random.choice([WHITE, (255, 0, 0), (0, 255, 0)]),
                    )
                )
            for p in particles[:]:
                p.update()
                p.draw(self.screen)
                if p.life <= 0:
                    particles.remove(p)
            try:
                r = int(127 + 127 * np.sin(elapsed * 0.01))
                g = int(127 + 127 * np.sin(elapsed * 0.01 + 2 * np.pi / 3))
                b = int(127 + 127 * np.sin(elapsed * 0.01 + 4 * np.pi / 3))
            except Exception:
                r, g, b = 255, 0, 0
            txt = self.font.render("!!! GAME OVER !!!", True, (r, g, b))
            dx, dy = (
                (random.randint(-10, 10), random.randint(-10, 10))
                if elapsed < 2000
                else (0, 0)
            )
            self.screen.blit(
                txt,
                (
                    SCREEN_WIDTH // 2 - txt.get_width() // 2 + dx,
                    SCREEN_HEIGHT // 2 - txt.get_height() // 2 + dy,
                ),
            )
            pygame.display.flip()
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit()
            pygame.time.delay(16)