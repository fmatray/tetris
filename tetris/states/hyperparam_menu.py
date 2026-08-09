"""Hyperparameters sub-menu: epsilon decay, epsilon end, back.

Nested under the Training menu. Exposes the DQN hyperparameters that
are configurable at runtime via left/right toggles.
"""

from __future__ import annotations

from typing import Optional

import pygame

from tetris.settings import BLACK, GRAY, SCREEN_HEIGHT, SCREEN_WIDTH, WHITE
from tetris.states.base import State


class HyperparamMenuState(State):
    """AI hyperparameters sub-menu: epsilon decay, epsilon end, back."""

    _OPTIONS = ["Epsilon decay", "Epsilon fin", "Retour"]
    _TOGGLE_INDICES = {0, 1}

    def __init__(self, screen, font, audio, training_menu) -> None:
        self.screen, self.font, self.audio = screen, font, audio
        self.training_menu = training_menu
        self.selection = 0

    @property
    def menu(self):
        """Access the root MenuState through the training menu."""
        return self.training_menu.menu

    def _value_label(self, i: int) -> str:
        if i == 0:
            return f"{self.menu.ai_epsilon_decay:.4f}"
        if i == 1:
            return f"{self.menu.ai_epsilon_end:.2f}"
        return ""

    # --- Input ----------------------------------------------------------

    def _toggle(self, direction: int) -> None:
        if self.selection == 0:  # Epsilon decay
            self.menu.ai_epsilon_decay = round(
                max(0.990, min(0.9999, self.menu.ai_epsilon_decay + direction * 0.0001)),
                4,
            )
        elif self.selection == 1:  # Epsilon fin
            self.menu.ai_epsilon_end = round(
                max(0.02, min(0.10, self.menu.ai_epsilon_end + direction * 0.01)),
                2,
            )

    def handle_event(self, event: pygame.event.Event) -> Optional[State]:
        if event.type != pygame.KEYDOWN:
            return None
        if event.key == pygame.K_UP:
            self.selection = (self.selection - 1) % len(self._OPTIONS)
        elif event.key == pygame.K_DOWN:
            self.selection = (self.selection + 1) % len(self._OPTIONS)
        elif event.key == pygame.K_LEFT:
            if self.selection in self._TOGGLE_INDICES:
                self._toggle(-1)
                self.menu.save_settings()
        elif event.key == pygame.K_RIGHT:
            if self.selection in self._TOGGLE_INDICES:
                self._toggle(1)
                self.menu.save_settings()
        elif event.key == pygame.K_RETURN:
            return self._on_select()
        elif event.key == pygame.K_ESCAPE:
            return self.training_menu
        return None

    def _on_select(self) -> Optional[State]:
        if self.selection == 2:  # Retour
            return self.training_menu
        return None

    # --- Rendering ------------------------------------------------------

    def draw(self, screen: pygame.Surface) -> None:
        screen.fill(BLACK)

        title = self.font.render("Hyperparamètres", True, WHITE)
        screen.blit(title, (SCREEN_WIDTH // 2 - title.get_width() // 2, 60))

        for i, option in enumerate(self._OPTIONS):
            is_sel = i == self.selection
            color = WHITE if is_sel else GRAY
            prefix = "> " if is_sel else "  "
            value = self._value_label(i)
            text = f"{prefix}{option}" + (f" : {value}" if value else "")
            surf = self.font.render(text, True, color)
            screen.blit(surf, (SCREEN_WIDTH // 2 - surf.get_width() // 2, 140 + i * 48))

        instr = self.font.render(
            "Flèches: Navigation | Entrée: Valider | Échap: Retour", True, GRAY
        )
        screen.blit(
            instr,
            (SCREEN_WIDTH // 2 - instr.get_width() // 2, SCREEN_HEIGHT - 50),
        )