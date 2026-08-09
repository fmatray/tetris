"""Training sub-menu: strategies, hyperparameters, back.

Nested under the AI menu. Only reachable when AI Mode = Apprentissage.
Strategies is a future feature (placeholder). Hyperparameters exposes
epsilon decay and epsilon end (configurable via left/right toggles).
"""

from __future__ import annotations

from typing import Optional

import pygame

from tetris.settings import BLACK, GRAY, SCREEN_HEIGHT, SCREEN_WIDTH, WHITE
from tetris.states.base import State


class TrainingMenuState(State):
    """AI training sub-menu: strategies, hyperparameters, back."""

    _OPTIONS = ["Stratégies", "Hyperparamètres", "Retour"]

    def __init__(self, screen, font, audio, ai_menu) -> None:
        self.screen, self.font, self.audio = screen, font, audio
        self.ai_menu = ai_menu
        self.selection = 0

    @property
    def menu(self):
        """Access the root MenuState through the AI menu."""
        return self.ai_menu.menu

    # --- Input ----------------------------------------------------------

    def handle_event(self, event: pygame.event.Event) -> Optional[State]:
        if event.type != pygame.KEYDOWN:
            return None
        if event.key == pygame.K_UP:
            self.selection = (self.selection - 1) % len(self._OPTIONS)
        elif event.key == pygame.K_DOWN:
            self.selection = (self.selection + 1) % len(self._OPTIONS)
        elif event.key == pygame.K_RETURN:
            return self._on_select()
        elif event.key == pygame.K_ESCAPE:
            return self.ai_menu
        return None

    def _on_select(self) -> Optional[State]:
        sel = self.selection
        if sel == 0:  # Stratégies
            from tetris.states.placeholder import PlaceholderState

            return PlaceholderState(
                self.screen, self.font, self.audio, self, "Stratégies"
            )
        if sel == 1:  # Hyperparamètres
            from tetris.states.hyperparam_menu import HyperparamMenuState

            return HyperparamMenuState(self.screen, self.font, self.audio, self)
        if sel == 2:  # Retour
            return self.ai_menu
        return None

    # --- Rendering ------------------------------------------------------

    def draw(self, screen: pygame.Surface) -> None:
        screen.fill(BLACK)

        title = self.font.render("Apprentissage", True, WHITE)
        screen.blit(title, (SCREEN_WIDTH // 2 - title.get_width() // 2, 60))

        for i, option in enumerate(self._OPTIONS):
            is_sel = i == self.selection
            color = WHITE if is_sel else GRAY
            prefix = "> " if is_sel else "  "
            text = f"{prefix}{option}"
            surf = self.font.render(text, True, color)
            screen.blit(surf, (SCREEN_WIDTH // 2 - surf.get_width() // 2, 140 + i * 48))

        instr = self.font.render(
            "Flèches: Navigation | Entrée: Valider | Échap: Retour", True, GRAY
        )
        screen.blit(
            instr,
            (SCREEN_WIDTH // 2 - instr.get_width() // 2, SCREEN_HEIGHT - 50),
        )