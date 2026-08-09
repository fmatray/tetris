"""AI sub-menu: mode, speed, training submenu, stats, reset, back."""

from __future__ import annotations

import os
from typing import Optional

import pygame

from tetris.settings import BLACK, GRAY, RED, SCREEN_HEIGHT, SCREEN_WIDTH, WHITE
from tetris.states.base import State

# Files deleted on "Reset AI"
AI_FILES = ["ai_model.pt", "ai_training_log.json"]


class AIMenuState(State):
    """AI sub-menu: mode, speed, training submenu, stats, reset, back.

    Mode toggles between Apprentissage (learning) and Jeu (playing).
    Training submenu is disabled when Mode = Jeu.
    """

    _OPTIONS = ["Mode", "Vitesse", "Apprentissage", "Statistiques", "Réinitialiser IA", "Retour"]
    _TOGGLE_INDICES = {0, 1}  # Mode, Vitesse

    def __init__(self, screen, font, audio, menu) -> None:
        self.screen, self.font, self.audio = screen, font, audio
        self.menu = menu
        self.selection = 0
        self._confirm_reset = False

    # --- Value helpers --------------------------------------------------

    def _value_label(self, i: int) -> str:
        if i == 0:  # Mode
            label = "Apprentissage" if self.menu.ai_mode == "learning" else "Jeu"
            return label
        if i == 1:  # Vitesse
            return "Rapide" if self.menu.ai_speed == "fast" else "Normal"
        return ""

    def _is_disabled(self, i: int) -> bool:
        """Training submenu is disabled when Mode = Jeu."""
        if i == 2 and self.menu.ai_mode == "playing":
            return True
        return False

    # --- Input ----------------------------------------------------------

    def _toggle_left(self) -> None:
        if self.selection == 0:  # Mode
            self.menu.ai_mode = (
                "playing" if self.menu.ai_mode == "learning" else "learning"
            )
        elif self.selection == 1:  # Vitesse
            self.menu.ai_speed = (
                "fast" if self.menu.ai_speed == "normal" else "normal"
            )

    def _toggle_right(self) -> None:
        if self.selection == 0:
            self.menu.ai_mode = (
                "playing" if self.menu.ai_mode == "learning" else "learning"
            )
        elif self.selection == 1:
            self.menu.ai_speed = (
                "fast" if self.menu.ai_speed == "normal" else "normal"
            )

    def _prev_enabled(self, current: int) -> int:
        n = len(self._OPTIONS)
        for step in range(1, n + 1):
            idx = (current - step) % n
            if not self._is_disabled(idx):
                return idx
        return current

    def _next_enabled(self, current: int) -> int:
        n = len(self._OPTIONS)
        for step in range(1, n + 1):
            idx = (current + step) % n
            if not self._is_disabled(idx):
                return idx
        return current

    def handle_event(self, event: pygame.event.Event) -> Optional[State]:
        if event.type != pygame.KEYDOWN:
            return None
        if event.key == pygame.K_UP:
            self.selection = self._prev_enabled(self.selection)
            self._confirm_reset = False
        elif event.key == pygame.K_DOWN:
            self.selection = self._next_enabled(self.selection)
            self._confirm_reset = False
        elif event.key in (pygame.K_LEFT, pygame.K_RIGHT):
            if self.selection in self._TOGGLE_INDICES:
                self._toggle_left()
                self.menu.save_settings()
        elif event.key == pygame.K_RETURN:
            if not self._is_disabled(self.selection):
                return self._on_select()
        elif event.key == pygame.K_ESCAPE:
            return self.menu
        return None

    def _on_select(self) -> Optional[State]:
        sel = self.selection
        if sel == 0:  # Mode — toggle
            self._toggle_left()
            self.menu.save_settings()
        elif sel == 2:  # Apprentissage submenu
            from tetris.states.training_menu import TrainingMenuState

            return TrainingMenuState(self.screen, self.font, self.audio, self)
        elif sel == 3:  # Statistiques
            from tetris.states.stats import StatsState

            return StatsState(self.screen, self.font, self.audio, self)
        elif sel == 4:  # Réinitialiser IA
            if not self._confirm_reset:
                self._confirm_reset = True
            else:
                self._reset_ai()
                self._confirm_reset = False
        elif sel == 5:  # Retour
            return self.menu
        return None

    def _reset_ai(self) -> None:
        """Delete model and training log files."""
        for f in AI_FILES:
            try:
                os.remove(f)
            except OSError:
                pass

    # --- Rendering ------------------------------------------------------

    def draw(self, screen: pygame.Surface) -> None:
        screen.fill(BLACK)

        title = self.font.render("IA", True, WHITE)
        screen.blit(title, (SCREEN_WIDTH // 2 - title.get_width() // 2, 60))

        for i, option in enumerate(self._OPTIONS):
            is_sel = i == self.selection
            disabled = self._is_disabled(i)
            if disabled:
                color = (64, 64, 64)
            elif is_sel:
                color = WHITE
            else:
                color = GRAY
            prefix = "> " if is_sel else "  "
            text = option
            value = self._value_label(i)
            if value:
                text = f"{option} : {value}"
            if i == 4 and self._confirm_reset:
                text = "Confirmer ? (Entrée)"
                color = RED
            surf = self.font.render(f"{prefix}{text}", True, color)
            screen.blit(surf, (SCREEN_WIDTH // 2 - surf.get_width() // 2, 140 + i * 48))

        # Navigation instructions
        instr = self.font.render(
            "Flèches: Navigation | Entrée: Valider | Échap: Retour", True, GRAY
        )
        screen.blit(
            instr,
            (SCREEN_WIDTH // 2 - instr.get_width() // 2, SCREEN_HEIGHT - 50),
        )