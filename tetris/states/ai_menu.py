"""AI sub-menu: mode, speed, learning submenu, stats, reset, back."""

from __future__ import annotations

import os

from tetris.settings import (
    LOG_PATH,
    MODEL_PATH,
    RED,
)
from tetris.states.base import State
from tetris.states.menu_base import MenuBase

# Files deleted on "Reset AI"
AI_FILES = [MODEL_PATH, LOG_PATH]


class AIMenuState(MenuBase):
    """AI sub-menu: mode, speed, learning submenu, stats, reset, back.

    Mode and speed are AI settings stored on the parent ``MenuState``.
    Learning submenu is disabled when Mode = Jeu (playing).
    """

    _OPTIONS = ("Mode", "Vitesse", "Apprentissage", "Statistiques", "Réinitialiser IA", "Retour")
    _toggle_indices = frozenset({0, 1})  # Mode, Vitesse
    _title = "IA"

    def __init__(self, screen, font, audio, menu) -> None:
        super().__init__(screen, font, audio)
        self.menu = menu
        self._confirm_reset = False

    # --- Hooks ----------------------------------------------------------

    def _value_label(self, i: int) -> str:
        match i:
            case 0:  # Mode
                return "Apprentissage" if self.menu.ai_mode == "learning" else "Jeu"
            case 1:  # Vitesse
                return "Rapide" if self.menu.ai_speed == "fast" else "Normal"
            case _:
                return ""

    def _is_disabled(self, i: int) -> bool:
        return bool(i == 2 and self.menu.ai_mode == "playing")

    def _toggle(self, direction: int) -> None:
        match self.selection:
            case 0:  # Mode
                self.menu.ai_mode = "playing" if self.menu.ai_mode == "learning" else "learning"
            case 1:  # Vitesse
                self.menu.ai_speed = "fast" if self.menu.ai_speed == "normal" else "normal"

    def _save(self) -> None:
        self.menu.save_settings()

    def _on_navigate(self) -> None:
        self._confirm_reset = False

    def _on_back(self) -> State | None:
        return self.menu

    def _on_select(self) -> State | None:
        match self.selection:
            case 0:  # Mode — toggle
                self._toggle(-1)
                self._save()
            case 2:  # Apprentissage submenu
                from tetris.states.hyperparam_menu import HyperparamMenuState

                return HyperparamMenuState(self.screen, self.font, self.audio, self)
            case 3:  # Statistiques
                from tetris.states.ai_stats import AIStatsState

                return AIStatsState(self.screen, self.font, self.audio, self)
            case 4:  # Réinitialiser IA
                if not self._confirm_reset:
                    self._confirm_reset = True
                else:
                    self._reset_ai()
                    self._confirm_reset = False
            case 5:  # Retour
                return self.menu
        return None

    def _option_text(self, i: int, is_sel: bool) -> str:
        if i == 4 and self._confirm_reset:
            prefix = "> " if is_sel else "  "
            return f"{prefix}Confirmer ? (Entrée)"
        return super()._option_text(i, is_sel)

    def _option_color(self, i: int, is_sel: bool, disabled: bool) -> tuple[int, int, int]:
        if i == 4 and self._confirm_reset:
            return RED
        return super()._option_color(i, is_sel, disabled)

    def _reset_ai(self) -> None:
        """Delete model and training log files."""
        for f in AI_FILES:
            try:
                os.remove(f)
            except OSError:
                pass
