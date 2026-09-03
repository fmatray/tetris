"""AI sub-menu: mode, speed, learning submenu, stats, reset, back."""

from __future__ import annotations

import os

from tetris.settings import (
    LOG_PATH,
    MODEL_PATH,
    RED,
)
from tetris.states.base import State
from tetris.i18n import tr
from tetris.states.menu_base import MenuBase

# Files deleted on "Reset AI"
AI_FILES = [MODEL_PATH, LOG_PATH]


class AIMenuState(MenuBase):
    """AI sub-menu: mode, speed, learning submenu, stats, reset, back.

    Mode and speed are AI settings stored on the parent ``MenuState``.
    Learning submenu is disabled when Mode = Game (playing).
    """

    _OPTIONS = ("Mode", "Speed", "Training", "Tournament", "Statistics", "Reset AI", "Back")
    _toggle_indices = frozenset({0, 1})  # Mode, Speed
    _title = "AI"

    def __init__(self, screen, font, audio, menu) -> None:
        super().__init__(screen, font, audio)
        self.menu = menu
        self._confirm_reset = False

    # --- Hooks ----------------------------------------------------------

    def _value_label(self, i: int) -> str:
        match i:
            case 0:  # Mode
                return tr("Training") if self.menu.ai_mode == "learning" else tr("Game")
            case 1:  # Speed
                return tr("Fast") if self.menu.ai_speed == "fast" else tr("Normal")
            case _:
                return ""

    def _is_disabled(self, i: int) -> bool:
        if i == 2:  # Training — locked while a checkpoint exists or in playing mode
            return self.menu.ai_mode == "playing" or self.menu.training_in_progress()
        if i == 3:  # Tournament — needs a trained checkpoint to evolve
            return not os.path.exists(MODEL_PATH)
        return False

    def _toggle(self, direction: int) -> None:
        match self.selection:
            case 0:  # Mode
                self.menu.ai_mode = "playing" if self.menu.ai_mode == "learning" else "learning"
            case 1:  # Speed
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
            case 2:  # Training submenu
                from tetris.states.hyperparam_menu import HyperparamMenuState

                return HyperparamMenuState(self.screen, self.font, self.audio, self)
            case 3:  # Tournament submenu
                from tetris.states.tournament_menu import TournamentMenuState

                return TournamentMenuState(self.screen, self.font, self.audio, self)
            case 4:  # Statistics
                from tetris.states.ai_stats import AIStatsState

                return AIStatsState(self.screen, self.font, self.audio, self)
            case 5:  # Reset AI
                if not self._confirm_reset:
                    self._confirm_reset = True
                else:
                    self._reset_ai()
                    self._confirm_reset = False
            case 6:  # Back
                return self.menu
        return None

    def _option_text(self, i: int, is_sel: bool) -> str:
        if i == 5 and self._confirm_reset:
            prefix = "> " if is_sel else "  "
            return f"{prefix}{tr('Confirm reset?')} (Enter)"
        return super()._option_text(i, is_sel)

    def _option_color(self, i: int, is_sel: bool, disabled: bool) -> tuple[int, int, int]:
        if i == 5 and self._confirm_reset:
            return RED
        return super()._option_color(i, is_sel, disabled)

    def _reset_ai(self) -> None:
        """Delete model and training log files."""
        for f in AI_FILES:
            try:
                os.remove(f)
            except OSError:
                pass
