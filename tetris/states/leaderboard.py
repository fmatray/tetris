"""Leaderboard state: display the top-10 scores, any key returns to menu."""

from __future__ import annotations

from typing import Optional

import pygame

from tetris.states.base import State
from tetris.visuals.leaderboard_view import draw_leaderboard


class LeaderboardState(State):
    """Shows the leaderboard. Any keypress returns to the menu."""

    def __init__(self, screen, font, audio) -> None:
        self.screen, self.font, self.audio = screen, font, audio

    def handle_event(self, event: pygame.event.Event) -> Optional[State]:
        if event.type == pygame.KEYDOWN:
            from tetris.states.menu import MenuState

            return MenuState(self.screen, self.font, self.audio)
        return None

    def draw(self, screen: pygame.Surface) -> None:
        draw_leaderboard(screen, self.font)