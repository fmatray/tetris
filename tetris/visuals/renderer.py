"""Game renderer: draws the board, pieces, HUD, and game-over animation.

Separation of rendering from game logic (Single Responsibility). The
renderer is a pure presentation object — it reads from game state but
never mutates it.
"""

from __future__ import annotations

import math
import random
import sys
from typing import TYPE_CHECKING

import pygame

from tetris.game.board import Board
from tetris.game.tetromino import Tetromino
from tetris.settings import (
    BLACK,
    BLOCK_SIZE,
    BOARD_HEIGHT,
    BOARD_OFFSET_X,
    BOARD_OFFSET_Y,
    BOARD_WIDTH,
    GAME_OVER_DURATION_MS,
    GAME_OVER_PARTICLE_COUNT,
    GHOST_OUTLINE_WIDTH,
    GRAY,
    HOLD_PANEL_X,
    HOLD_PANEL_Y,
    HUD_POSITIONS,
    NEXT_PANEL_X,
    NEXT_PANEL_Y,
    PREVIEW_PANEL_X,
    PREVIEW_PANEL_Y,
    SCREEN_HEIGHT,
    SCREEN_WIDTH,
    SHAPES_COLORS,
    VISIBLE_ROWS,
    WHITE,
)
from tetris.visuals.fonts import get_large_font
from tetris.visuals.particles import Particle, ParticleSystem

if TYPE_CHECKING:
    from tetris.states.game import GameState



class Renderer:
    """Draws game frames and the game-over animation."""

    _GLITCH_COLORS = (WHITE, GRAY, (255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 0), (255, 0, 255))

    def __init__(self, screen: pygame.Surface, font: pygame.font.Font) -> None:
        self.screen = screen
        self.font = font

    # --- In-game frame --------------------------------------------------

    def render_frame(self, game: GameState, particles: ParticleSystem) -> None:
        self.screen.fill(BLACK)
        self.draw_grid(game.board)
        if game.ghost_piece:
            self.draw_ghost(game.current_piece, game.board)
        self.draw_tetromino(game.current_piece)
        self._draw_text(f"SCORE: {game.stats.score}", HUD_POSITIONS["score"])
        self._draw_text(f"TETROMINOS: {game.stats.piece_count}", HUD_POSITIONS["tetrominos"])
        self._draw_text(f"LIGNES: {game.stats.total_lines}", HUD_POSITIONS["lines"])
        self._draw_text(f"NIVEAU: {game.stats.level}", HUD_POSITIONS["level"])
        if game.stats.combo > 0:
            self._draw_text(f"COMBO: x{game.stats.combo}", HUD_POSITIONS["speed"])
        elif game.debug:
            self._draw_text(f"SPEED: {int(game.current_speed * 1000)}ms", HUD_POSITIONS["speed"])
        self._draw_text("HOLD:", HUD_POSITIONS["hold"])
        if game.hold_piece is not None:
            self.draw_hold_piece(game.hold_piece, game._can_hold)
        self._draw_text("NEXT:", HUD_POSITIONS["next"])
        self.draw_next_piece(game.next_piece)
        for i, piece in enumerate(getattr(game, "preview_pieces", [])):
            self.draw_preview_piece(piece, i)
        if game.debug:
            self._draw_text(f"SPEED: {int(game.current_speed * 1000)}ms", HUD_POSITIONS["speed"])
        if game.debug and game.pieces.generator in ("7bag", "35bag"):
            self._draw_debug_bag(game)
        # Bottom-left: mode and generator
        mode = game.menu.mode if game.menu else "Normal"
        gen = {"7bag": "7-bag", "35bag": "35-bag"}.get(game.pieces.generator, "Aléatoire")
        self._draw_text(f"MODE: {mode}", HUD_POSITIONS["mode"])
        self._draw_text(f"GÉNÉRATEUR: {gen}", HUD_POSITIONS["generator"])
        if game.paused:
            pause_text = get_large_font().render("PAUSE", True, WHITE)
            self.screen.blit(
                pause_text,
                (SCREEN_WIDTH // 2 - pause_text.get_width() // 2, SCREEN_HEIGHT // 2),
            )
        particles.draw(self.screen)

    def _draw_text(self, text: str, pos: tuple[int, int]) -> None:
        surf = self.font.render(text, True, WHITE)
        self.screen.blit(surf, pos)

    def _draw_debug_bag(self, game: GameState) -> None:
        """Draw remaining bag pieces as colored blocks right of the next-piece panel."""
        bag = game.pieces.bag_remaining
        x = NEXT_PANEL_X + 7 * BLOCK_SIZE + 20
        y = HUD_POSITIONS["next"][1]
        self._draw_text(f"SAC ({len(bag)}):", (x, y))
        y += 60
        start_x = x
        max_per_row = max(1, (SCREEN_WIDTH - x) // (BLOCK_SIZE + 2))
        for i, piece_type in enumerate(bag[::-1]):
            if i and i % max_per_row == 0:
                x = start_x
                y += BLOCK_SIZE + 2
            color = SHAPES_COLORS[piece_type]
            rect = pygame.Rect(x, y, BLOCK_SIZE, BLOCK_SIZE)
            pygame.draw.rect(self.screen, color, rect)
            letter = self.font.render(piece_type, True, WHITE)
            self.screen.blit(letter, (x + 2, y + 2))
            x += BLOCK_SIZE + 2
    @staticmethod
    def _cell_rect(x: int, y: int, ox: int, oy: int) -> pygame.Rect:
        # y is a grid row; offset by hidden rows so only visible rows are drawn
        screen_y = y - (BOARD_HEIGHT - VISIBLE_ROWS)
        return pygame.Rect(x * BLOCK_SIZE + ox, screen_y * BLOCK_SIZE + oy, BLOCK_SIZE, BLOCK_SIZE)

    def draw_grid(self, board: Board) -> None:
        hidden = BOARD_HEIGHT - VISIBLE_ROWS
        for y in range(hidden, BOARD_HEIGHT):
            for x in range(BOARD_WIDTH):
                rect = self._cell_rect(x, y, BOARD_OFFSET_X, BOARD_OFFSET_Y)
                pygame.draw.rect(self.screen, GRAY, rect, 1)
                color = board.grid[y][x]
                if color:
                    pygame.draw.rect(self.screen, color, rect)

    def draw_ghost(self, tetromino: Tetromino, board: Board) -> None:
        hidden = BOARD_HEIGHT - VISIBLE_ROWS
        drop = 0
        while board.is_valid_move(tetromino, dy=drop + 1):
            drop += 1
        if drop == 0:
            return
        for x, y in tetromino.get_blocks():
            gy = y + drop
            if gy >= hidden:
                rect = self._cell_rect(x, gy, BOARD_OFFSET_X, BOARD_OFFSET_Y)
                pygame.draw.rect(self.screen, tetromino.color, rect, GHOST_OUTLINE_WIDTH)

    def draw_tetromino(self, tetromino: Tetromino) -> None:
        hidden = BOARD_HEIGHT - VISIBLE_ROWS
        for x, y in tetromino.get_blocks():
            if y >= hidden:
                rect = self._cell_rect(x, y, BOARD_OFFSET_X, BOARD_OFFSET_Y)
                pygame.draw.rect(self.screen, tetromino.color, rect)

    @staticmethod
    def _panel_rect(x: int, y: int, ox: int, oy: int) -> pygame.Rect:
        """Rect for side-panel pieces (no hidden-row offset)."""
        return pygame.Rect(x * BLOCK_SIZE + ox, y * BLOCK_SIZE + oy, BLOCK_SIZE, BLOCK_SIZE)

    @staticmethod
    def _normalized_blocks(tetromino: Tetromino) -> list[tuple[int, int]]:
        """Block coords shifted so the piece's top-left cell is at (0, 0)."""
        blocks = tetromino.get_blocks()
        min_x = min(x for x, _ in blocks)
        min_y = min(y for _, y in blocks)
        return [(x - min_x, y - min_y) for x, y in blocks]

    def draw_next_piece(self, tetromino: Tetromino) -> None:
        for x, y in self._normalized_blocks(tetromino):
            rect = self._panel_rect(x, y, NEXT_PANEL_X, NEXT_PANEL_Y)
            pygame.draw.rect(self.screen, tetromino.color, rect)

    def draw_hold_piece(self, tetromino: Tetromino, can_hold: bool = True) -> None:
        """Draw the held piece. Dimmed if hold is unavailable."""
        color = tetromino.color if can_hold else GRAY
        for x, y in self._normalized_blocks(tetromino):
            rect = self._panel_rect(x, y, HOLD_PANEL_X, HOLD_PANEL_Y)
            pygame.draw.rect(self.screen, color, rect)

    def draw_preview_piece(self, tetromino: Tetromino, index: int) -> None:
        """Draw a preview piece below the next-piece panel."""
        y_offset = PREVIEW_PANEL_Y + index * 4 * BLOCK_SIZE
        for x, y in self._normalized_blocks(tetromino):
            rect = self._panel_rect(x, y, PREVIEW_PANEL_X, y_offset)
            pygame.draw.rect(self.screen, tetromino.color, rect)

    # --- Game-over animation --------------------------------------------

    def _render_glitch_board(self, game: GameState, shake_x: int, shake_y: int, glitch: float) -> pygame.Surface:
        hidden = BOARD_HEIGHT - VISIBLE_ROWS
        board_surf = pygame.Surface(
            (BOARD_WIDTH * BLOCK_SIZE, VISIBLE_ROWS * BLOCK_SIZE)
        )
        board_surf.set_colorkey(BLACK)
        for y in range(hidden, BOARD_HEIGHT):
            for x in range(BOARD_WIDTH):
                sy = y - hidden
                rect = pygame.Rect(
                    x * BLOCK_SIZE, sy * BLOCK_SIZE, BLOCK_SIZE, BLOCK_SIZE
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
            if y >= hidden:
                sy = y - hidden
                pygame.draw.rect(
                    board_surf,
                    game.current_piece.color,
                    (x * BLOCK_SIZE, sy * BLOCK_SIZE, BLOCK_SIZE, BLOCK_SIZE),
                )
        self.screen.blit(board_surf, (BOARD_OFFSET_X + shake_x, BOARD_OFFSET_Y + shake_y))
        return board_surf

    def _render_game_over_text(self, elapsed: int) -> None:
        r = int(127 + 127 * math.sin(elapsed * 0.01))
        g = int(127 + 127 * math.sin(elapsed * 0.01 + 2 * math.pi / 3))
        b = int(127 + 127 * math.sin(elapsed * 0.01 + 4 * math.pi / 3))
        txt = get_large_font().render("!!! GAME OVER !!!", True, (r, g, b))
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

    def play_game_over_animation(self, game: GameState, audio) -> None:
        """Run the chaotic 4-second game-over sequence (blocking)."""
        start_time = pygame.time.get_ticks()
        particles: list[Particle] = []
        for _ in range(GAME_OVER_PARTICLE_COUNT):
            particles.append(
                Particle(
                    random.randint(BOARD_OFFSET_X, BOARD_OFFSET_X + BOARD_WIDTH * BLOCK_SIZE),
                    random.randint(BOARD_OFFSET_Y, BOARD_OFFSET_Y + VISIBLE_ROWS * BLOCK_SIZE),
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
            glitch = random.random()
            self._render_glitch_board(game, shake_x, shake_y, glitch)
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
            self._render_game_over_text(elapsed)
            pygame.display.flip()
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit()
            pygame.time.delay(16)
