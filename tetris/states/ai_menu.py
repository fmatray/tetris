"""AI sub-menu: speed toggle, reset AI data, back to main menu."""

from __future__ import annotations

import os
from typing import Optional

import pygame

from tetris.ai.trainer import TrainingLog
from tetris.settings import BLACK, GRAY, RED, SCREEN_HEIGHT, SCREEN_WIDTH, WHITE
from tetris.states.base import State

# Files deleted on "Reset AI"
AI_FILES = ["ai_model.pt", "ai_training_log.json"]

_STAT_LABELS = [
    "Épisodes",
    "Score moyen",
    "Meilleur score",
    "Moyenne (100 derniers)",
    "Lignes totales",
    "Pièces totales",
]


class AIMenuState(State):
    """AI sub-menu: speed toggle, reset, back to main menu.

    Receives the parent ``MenuState`` so speed changes propagate back when
    the player returns. Stats are loaded from the training log and shown
    inline. Reset requires a double-press confirmation.
    """

    _OPTIONS = ["Vitesse", "Epsilon decay", "Epsilon fin", "Réinitialiser IA", "Retour"]

    def __init__(self, screen, font, audio, menu) -> None:
        self.screen, self.font, self.audio = screen, font, audio
        self.menu = menu
        self.selection = 0
        self._confirm_reset = False
        self._stats = TrainingLog()

    # --- Input ----------------------------------------------------------

    def handle_event(self, event: pygame.event.Event) -> Optional[State]:
        if event.type != pygame.KEYDOWN:
            return None
        if event.key == pygame.K_UP:
            self.selection = (self.selection - 1) % len(self._OPTIONS)
            self._confirm_reset = False
        elif event.key == pygame.K_DOWN:
            self.selection = (self.selection + 1) % len(self._OPTIONS)
            self._confirm_reset = False
        elif event.key in (pygame.K_LEFT, pygame.K_RIGHT):
            direction = 1 if event.key == pygame.K_RIGHT else -1
            if self.selection == 0:  # Vitesse
                self.menu.ai_speed = (
                    "fast" if self.menu.ai_speed == "normal" else "normal"
                )
            elif self.selection == 1:  # Epsilon decay
                self.menu.ai_epsilon_decay = round(
                    max(0.990, min(0.999, self.menu.ai_epsilon_decay + direction * 0.0001)),
                    4,
                )
            elif self.selection == 2:  # Epsilon fin
                self.menu.ai_epsilon_end = round(
                    max(0.02, min(0.10, self.menu.ai_epsilon_end + direction * 0.01)),
                    2,
                )
        elif event.key == pygame.K_RETURN:
            return self._on_select()
        elif event.key == pygame.K_ESCAPE:
            return self.menu
        return None

    def _on_select(self) -> Optional[State]:
        sel = self.selection
        if sel == 0:  # Vitesse — toggle
            self.menu.ai_speed = "fast" if self.menu.ai_speed == "normal" else "normal"
        elif sel == 3:  # Réinitialiser IA
            if not self._confirm_reset:
                self._confirm_reset = True
            else:
                self._reset_ai()
                self._confirm_reset = False
                self._stats = TrainingLog()
        elif sel == 4:  # Retour
            return self.menu
        return None

    def _reset_ai(self) -> None:
        """Delete model and training log files."""
        for path in AI_FILES:
            try:
                os.remove(path)
            except FileNotFoundError:
                pass

    # --- Rendering ------------------------------------------------------

    def _stat_values(self) -> list[str]:
        s = self._stats
        return [
            str(s.total_episodes),
            f"{s.avg_score:.0f}",
            str(s.best_score),
            f"{s.last_100_avg:.0f}",
            str(s.total_lines),
            str(s.total_steps),
        ]

    def draw(self, screen: pygame.Surface) -> None:
        screen.fill(BLACK)

        title = self.font.render("IA", True, WHITE)
        screen.blit(title, (SCREEN_WIDTH // 2 - title.get_width() // 2, 60))

        # Menu options
        for i, option in enumerate(self._OPTIONS):
            is_sel = i == self.selection
            color = WHITE if is_sel else GRAY
            prefix = "> " if is_sel else "  "
            text = option
            if i == 0:  # Vitesse
                label = "Rapide" if self.menu.ai_speed == "fast" else "Normal"
                text = f"{option} : {label}"
            elif i == 1:  # Epsilon decay
                text = f"{option} : {self.menu.ai_epsilon_decay:.4f}"
            elif i == 2:  # Epsilon fin
                text = f"{option} : {self.menu.ai_epsilon_end:.2f}"
            if i == 3 and self._confirm_reset:
                text = "Confirmer ? (Entrée)"
                color = RED
            surf = self.font.render(f"{prefix}{text}", True, color)
            screen.blit(surf, (SCREEN_WIDTH // 2 - surf.get_width() // 2, 140 + i * 48))

        # Stats section
        y = 410
        header = self.font.render("Statistiques", True, WHITE)
        screen.blit(header, (SCREEN_WIDTH // 2 - header.get_width() // 2, y))
        y += 45

        values = self._stat_values()
        for label, value in zip(_STAT_LABELS, values):
            line = f"{label} : {value}"
            surf = self.font.render(line, True, GRAY)
            screen.blit(surf, (SCREEN_WIDTH // 2 - surf.get_width() // 2, y))
            y += 35

        # Navigation instructions
        instr = self.font.render(
            "Flèches: Navigation | Entrée: Valider | Échap: Retour", True, GRAY
        )
        screen.blit(
            instr,
            (SCREEN_WIDTH // 2 - instr.get_width() // 2, SCREEN_HEIGHT - 50),
        )