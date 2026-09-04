"""Leaderboard state: top-10 per game mode, LEFT/RIGHT switch tabs."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tetris.visuals.particles import ParticleSystem

import pygame

from tetris.states.base import State
from tetris.storage import load_leaderboard
from tetris.visuals.leaderboard_view import draw_leaderboard


class LeaderboardState(State):
    """Shows the per-game-mode top-10. LEFT/RIGHT switch tabs, any other key exits."""

    def __init__(self, screen, font, audio, menu=None) -> None:
        self.screen, self.font, self.audio, self.menu = screen, font, audio, menu
        self.leaderboard_mode: str = "marathon"
        self._scores: list[dict] = []
        self._load()

    def _load(self) -> None:
        self._scores = load_leaderboard(self.leaderboard_mode)

    def handle_event(self, event: pygame.event.Event) -> State | None:
        if event.type == pygame.KEYDOWN:
            from tetris.settings import LEADERBOARD_MODES

            modes = LEADERBOARD_MODES
            if event.key in (pygame.K_LEFT, pygame.K_RIGHT):
                direction = 1 if event.key == pygame.K_RIGHT else -1
                self.leaderboard_mode = modes[(modes.index(self.leaderboard_mode) + direction) % len(modes)]
                self._load()
                return None
            if self.menu is not None:
                return self.menu
            from tetris.states.menu import MenuState

            return MenuState(self.screen, self.font, self.audio)
        return None

    def draw(self, screen: pygame.Surface, *, particles: ParticleSystem | None = None) -> None:
        draw_leaderboard(screen, self.font, self._scores, game_mode=self.leaderboard_mode)
