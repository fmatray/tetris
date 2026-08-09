"""Placeholder state for menu entries not yet implemented.

Shows a title and "À venir" message. Any key returns to the parent state.
Used by: Touches (human), Statistiques (human), Stratégies (AI training).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

import pygame

from tetris.settings import BLACK, GRAY, SCREEN_HEIGHT, SCREEN_WIDTH, WHITE
from tetris.states.base import State

if TYPE_CHECKING:
    from tetris.states.base import State as StateType


class PlaceholderState(State):
    """Shows "À venir" for a future feature. Any key returns to parent."""

    def __init__(self, screen, font, audio, parent: StateType, title: str) -> None:
        self.screen, self.font, self.audio = screen, font, audio
        self.parent = parent
        self.title = title

    def handle_event(self, event: pygame.event.Event) -> Optional[State]:
        if event.type == pygame.KEYDOWN:
            return self.parent
        return None

    def draw(self, screen: pygame.Surface) -> None:
        screen.fill(BLACK)

        title = self.font.render(self.title, True, WHITE)
        screen.blit(title, (SCREEN_WIDTH // 2 - title.get_width() // 2, 200))

        msg = self.font.render("À venir", True, GRAY)
        screen.blit(msg, (SCREEN_WIDTH // 2 - msg.get_width() // 2, 300))

        instr = self.font.render("Appuyez sur une touche pour revenir", True, GRAY)
        screen.blit(
            instr,
            (SCREEN_WIDTH // 2 - instr.get_width() // 2, SCREEN_HEIGHT - 80),
        )