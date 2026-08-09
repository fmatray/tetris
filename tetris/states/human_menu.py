"""Human sub-menu: mode, handicap, keybindings, statistics, back."""

from __future__ import annotations

from typing import Optional

import pygame

from tetris.settings import BLACK, GRAY, SCREEN_HEIGHT, SCREEN_WIDTH, WHITE
from tetris.states.base import State


class HumanMenuState(State):
    """Human player sub-menu: mode, handicap, keybindings, stats, back.

    Mode and handicap are human-player settings stored on the parent
    ``MenuState``. Keybindings and statistics are future features.
    """

    _OPTIONS = ["Mode", "Handicap", "Touches", "Statistiques", "Retour"]
    _TOGGLE_INDICES = {0, 1}

    def __init__(self, screen, font, audio, menu) -> None:
        self.screen, self.font, self.audio = screen, font, audio
        self.menu = menu
        self.selection = 0

    # --- Value helpers --------------------------------------------------

    def _value_label(self, i: int) -> str:
        if i == 0:
            return self.menu.mode
        if i == 1:
            return str(self.menu.h)
        return ""

    # --- Input ----------------------------------------------------------

    def _toggle_left(self) -> None:
        if self.selection == 0:
            self.menu.mode = "Replay" if self.menu.mode == "Normal" else "Normal"
        elif self.selection == 1:
            self.menu.h = max(0, self.menu.h - 1)

    def _toggle_right(self) -> None:
        if self.selection == 0:
            self.menu.mode = "Replay" if self.menu.mode == "Normal" else "Normal"
        elif self.selection == 1:
            self.menu.h = min(5, self.menu.h + 1)

    def handle_event(self, event: pygame.event.Event) -> Optional[State]:
        if event.type != pygame.KEYDOWN:
            return None
        if event.key == pygame.K_UP:
            self.selection = (self.selection - 1) % len(self._OPTIONS)
        elif event.key == pygame.K_DOWN:
            self.selection = (self.selection + 1) % len(self._OPTIONS)
        elif event.key == pygame.K_LEFT:
            if self.selection in self._TOGGLE_INDICES:
                self._toggle_left()
                self.menu.save_settings()
        elif event.key == pygame.K_RIGHT:
            if self.selection in self._TOGGLE_INDICES:
                self._toggle_right()
                self.menu.save_settings()
        elif event.key == pygame.K_RETURN:
            return self._on_select()
        elif event.key == pygame.K_ESCAPE:
            return self.menu
        return None

    def _on_select(self) -> Optional[State]:
        sel = self.selection
        if sel == 2:  # Touches
            from tetris.states.keybind import KeybindState

            return KeybindState(self.screen, self.font, self.audio, self)
        if sel == 3:  # Statistiques
            from tetris.states.human_stats import HumanStatsState

            return HumanStatsState(self.screen, self.font, self.audio, self)
        if sel == 4:  # Retour
            return self.menu
        return None

    # --- Rendering ------------------------------------------------------

    def draw(self, screen: pygame.Surface) -> None:
        screen.fill(BLACK)

        title = self.font.render("Humain", True, WHITE)
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