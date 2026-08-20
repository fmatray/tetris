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
from tetris.game.shapes import SHAPES_TYPES
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
    GENERATOR_LABELS,
    GHOST_OUTLINE_WIDTH,
    GRAY,
    HIDDEN_ROWS,
    HUD_POSITIONS,
    SCREEN_HEIGHT,
    SCREEN_WIDTH,
    SHAPES_COLORS,
    SPEED_MODE_LABELS,
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
        """Store the target surface and font for all rendering methods."""
        self.screen = screen
        self.font = font

    # --- In-game frame --------------------------------------------------

    def render_frame(self, game: GameState, particles: ParticleSystem) -> None:
        """Draw a complete game frame: board, ghost, current piece, HUD, panels."""
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
            self.draw_panel_pieces(
                [game.hold_piece],
                HUD_POSITIONS["hold_panel"][0],
                HUD_POSITIONS["hold_panel"][1],
                dim=not game._can_hold,
            )
        if getattr(game, "preview_count", 3) > 0:
            self._draw_text("NEXT:", HUD_POSITIONS["next"])
            next_queue = [game.next_piece] + getattr(game, "preview_pieces", [])
            self.draw_panel_pieces(next_queue, HUD_POSITIONS["next_panel"][0], HUD_POSITIONS["next_panel"][1])
        if game.debug:
            match game.pieces.generator:
                case "7bag" | "35bag":
                    self._draw_debug_bag(game)
                case "weighted":
                    self._draw_debug_weights(game)
        mode = game.menu.mode if game.menu else "Normal"
        gen = GENERATOR_LABELS.get(game.pieces.generator, "Aléatoire")
        self._draw_text(f"MODE: {mode}", HUD_POSITIONS["mode"])
        self._draw_text(f"GÉNÉRATEUR: {gen}", HUD_POSITIONS["generator"])
        speed_label = SPEED_MODE_LABELS.get(game.speed_mode, "Normal")
        self._draw_text(f"VITESSE: {speed_label}", HUD_POSITIONS["speed_mode"])
        if game.paused:
            pause_text = get_large_font().render("PAUSE", True, WHITE)
            self.screen.blit(
                pause_text,
                (HUD_POSITIONS["pause"][0] - pause_text.get_width() // 2, HUD_POSITIONS["pause"][1]),
            )
        particles.draw(self.screen)

    def _draw_text(self, text: str, pos: tuple[int, int]) -> None:
        surf = self.font.render(text, True, WHITE)
        self.screen.blit(surf, pos)

    def _draw_debug_bag(self, game: GameState) -> None:
        """Draw remaining bag pieces as colored blocks right of the next-piece panel."""
        bag = game.pieces.bag_remaining
        x = HUD_POSITIONS["debug_bag"][0]
        y = HUD_POSITIONS["debug_bag"][1]
        self._draw_text(f"SAC ({len(bag)}):", (x, y))
        y += self.font.get_height() + 4
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
            lx = x + (BLOCK_SIZE - letter.get_width()) // 2
            ly = y + (BLOCK_SIZE - letter.get_height()) // 2
            self.screen.blit(letter, (lx, ly))
            x += BLOCK_SIZE + 2

    def _draw_debug_weights(self, game: GameState) -> None:
        """Draw each tetromino type and its current weight (weighted generator)."""
        weights = game.pieces.weights
        x = HUD_POSITIONS["debug_bag"][0]
        y = HUD_POSITIONS["debug_bag"][1]
        self._draw_text("POIDS:", (x, y))
        y += self.font.get_height() + 4
        for piece_type in SHAPES_TYPES:
            color = SHAPES_COLORS[piece_type]
            rect = pygame.Rect(x, y, BLOCK_SIZE, BLOCK_SIZE)
            pygame.draw.rect(self.screen, color, rect)
            letter = self.font.render(piece_type, True, WHITE)
            lx = x + (BLOCK_SIZE - letter.get_width()) // 2
            ly = y + (BLOCK_SIZE - letter.get_height()) // 2
            self.screen.blit(letter, (lx, ly))
            w = weights.get(piece_type, 1.0)
            self._draw_text(f"{w:.2f}", (x + BLOCK_SIZE + 6, y + (BLOCK_SIZE - self.font.get_height()) // 2))
            y += BLOCK_SIZE + 2

    @staticmethod
    def _cell_rect(x: int, y: int, ox: int, oy: int) -> pygame.Rect:
        # y is a grid row; offset by hidden rows so only visible rows are drawn
        screen_y = y - HIDDEN_ROWS
        return pygame.Rect(x * BLOCK_SIZE + ox, screen_y * BLOCK_SIZE + oy, BLOCK_SIZE, BLOCK_SIZE)

    def draw_grid(self, board: Board) -> None:
        """Draw the visible portion of the board grid with locked blocks."""
        hidden = HIDDEN_ROWS
        for y in range(hidden, BOARD_HEIGHT):
            for x in range(BOARD_WIDTH):
                rect = self._cell_rect(x, y, BOARD_OFFSET_X, BOARD_OFFSET_Y)
                pygame.draw.rect(self.screen, GRAY, rect, 1)
                color = board.grid[y][x]
                if color:
                    pygame.draw.rect(self.screen, color, rect)

    def draw_ghost(self, tetromino: Tetromino, board: Board) -> None:
        """Draw the ghost piece at the piece's hard-drop landing position."""
        hidden = HIDDEN_ROWS
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
        """Draw the active piece on the board (visible rows only)."""
        hidden = HIDDEN_ROWS
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

    def draw_panel_pieces(
        self,
        pieces: list[Tetromino],
        ox: int,
        oy: int,
        spacing: int = 3,
        dim: bool | list[bool] = False,
    ) -> None:
        """Draw a vertical list of tetrominos in a side panel.

        Args:
            pieces: tetrominos to draw (top to bottom).
            ox, oy: top-left pixel of the first piece slot.
            spacing: vertical gap between slots, in BLOCK_SIZE units.
            dim: True to dim all, or a per-piece list of dim flags.
        """
        dim_flags = [dim] * len(pieces) if isinstance(dim, bool) else dim
        for i, piece in enumerate(pieces):
            y = oy + i * spacing * BLOCK_SIZE
            color = GRAY if (i < len(dim_flags) and dim_flags[i]) else piece.color
            for bx, by in self._normalized_blocks(piece):
                rect = self._panel_rect(bx, by, ox, y)
                pygame.draw.rect(self.screen, color, rect)

    # --- Game-over animation --------------------------------------------

    def _render_glitch_board(self, game: GameState, shake_x: int, shake_y: int, glitch: float) -> pygame.Surface:
        hidden = HIDDEN_ROWS
        board_surf = pygame.Surface((BOARD_WIDTH * BLOCK_SIZE, VISIBLE_ROWS * BLOCK_SIZE))
        board_surf.set_colorkey(BLACK)
        for y in range(hidden, BOARD_HEIGHT):
            for x in range(BOARD_WIDTH):
                sy = y - hidden
                rect = pygame.Rect(x * BLOCK_SIZE, sy * BLOCK_SIZE, BLOCK_SIZE, BLOCK_SIZE)
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
        dx, dy = (random.randint(-10, 10), random.randint(-10, 10)) if elapsed < 2000 else (0, 0)
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
            shake_x = random.randint(-15, 15) if elapsed < 1500 else random.randint(-3, 3)
            shake_y = random.randint(-15, 15) if elapsed < 1500 else random.randint(-3, 3)
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
