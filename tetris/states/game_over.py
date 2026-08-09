"""Game-over state: animation -> name entry -> leaderboard -> menu."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tetris.states.menu import MenuState
    from tetris.visuals.particles import ParticleSystem

import pygame

from tetris.audio import AudioManager
from tetris.settings import BLACK, GRAY, MAX_NAME_LENGTH, SCREEN_WIDTH, WHITE
from tetris.states.base import State
from tetris.states.game import GameState
from tetris.storage import save_human_game, save_score
from tetris.visuals.fonts import (
    CONTENT_Y,
    LINE_HEIGHT_SMALL,
    TITLE_Y,
    get_large_font,
)
from tetris.visuals.leaderboard_view import draw_leaderboard
from tetris.visuals.renderer import Renderer


class GameOverState(State):
    """Three-step flow after a game ends.

    Steps: ``ANIMATION`` → ``NAME`` → ``LEADERBOARD``.
    Each step handles its own events and drawing. After the leaderboard,
    any key returns to the main menu.
    """

    def __init__(
        self,
        screen: pygame.Surface,
        font: pygame.font.Font,
        audio: AudioManager,
        game: GameState,
        menu: MenuState | None = None,
    ) -> None:
        self.screen, self.font, self.audio, self.game = screen, font, audio, game
        self.menu = menu
        self.renderer = Renderer(screen, font)
        self.name = ""
        self.step = "ANIMATION"

    def update(self, dt: float, particles) -> State | None:
        if self.step == "ANIMATION":
            self.renderer.play_game_over_animation(self.game, self.audio)
            self.step = "NAME"
        return None

    def handle_event(self, event: pygame.event.Event) -> State | None:
        if event.type != pygame.KEYDOWN:
            return None
        if self.step == "NAME":
            return self._handle_name_event(event)
        elif self.step == "LEADERBOARD":
            if self.menu is not None:
                return self.menu
            from tetris.states.menu import MenuState

            return MenuState(self.screen, self.font, self.audio)
        return None

    def _handle_name_event(self, event: pygame.event.Event) -> State | None:
        if event.key == pygame.K_RETURN and self.name.strip():
            save_score(
                self.name,
                self.game.stats.score,
                self.game.stats.level,
                self.game.stats.total_lines,
            )
            save_human_game(
                self.name,
                self.game.stats.score,
                self.game.stats.level,
                self.game.stats.total_lines,
                self.game.stats.piece_count,
            )
            self.step = "LEADERBOARD"
        elif event.key == pygame.K_BACKSPACE:
            self.name = self.name[:-1]
        elif len(self.name) < MAX_NAME_LENGTH:
            self.name += event.unicode
        return None

    def draw(self, screen: pygame.Surface, *, particles: ParticleSystem | None = None) -> None:
        if self.step == "NAME":
            self._draw_name_entry(screen)
        elif self.step == "LEADERBOARD":
            draw_leaderboard(screen, self.font)

    def _draw_name_entry(self, screen: pygame.Surface) -> None:
        screen.fill(BLACK)
        prompt = get_large_font().render("GAME OVER!", True, WHITE)
        screen.blit(prompt, (SCREEN_WIDTH // 2 - prompt.get_width() // 2, TITLE_Y))
        instr = self.font.render("Enter your name and press ENTER:", True, GRAY)
        screen.blit(instr, (SCREEN_WIDTH // 2 - instr.get_width() // 2,
                            TITLE_Y + LINE_HEIGHT_SMALL + 10))
        rect = pygame.Rect(SCREEN_WIDTH // 2 - 150, CONTENT_Y + LINE_HEIGHT_SMALL * 2 + 10, 300, 50)
        pygame.draw.rect(screen, GRAY, rect, 2)
        txt = self.font.render(self.name, True, WHITE)
        screen.blit(txt, (rect.x + 10, rect.y + 10))