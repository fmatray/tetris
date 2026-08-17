"""Leaderboard state: display the top-10 scores, any key returns to menu."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tetris.visuals.particles import ParticleSystem

import pygame

from tetris.states.base import State
from tetris.storage import load_leaderboard
from tetris.visuals.leaderboard_view import draw_leaderboard


class LeaderboardState(State):
    """Shows the leaderboard. Any keypress returns to the menu."""

    def __init__(self, screen, font, audio, menu=None) -> None:
        self.screen, self.font, self.audio, self.menu = screen, font, audio, menu
        self._scores: list[dict] = []
        self._load()

    def _load(self) -> None:
        self._scores = load_leaderboard()

    def handle_event(self, event: pygame.event.Event) -> State | None:
        if event.type == pygame.KEYDOWN:
            if self.menu is not None:
                return self.menu
            from tetris.states.menu import MenuState

            return MenuState(self.screen, self.font, self.audio)
        return None

    def draw(self, screen: pygame.Surface, *, particles: ParticleSystem | None = None) -> None:
        draw_leaderboard(screen, self.font, self._scores)