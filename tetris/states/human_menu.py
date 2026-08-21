"""Human sub-menu: mode, keybindings, statistics, back."""

from __future__ import annotations

from tetris.states.base import State
from tetris.states.menu_base import MenuBase


class HumanMenuState(MenuBase):
    """Human player sub-menu: mode, keybindings, stats, back.

    Mode is a human-player setting stored on the parent ``MenuState``.
    Keybindings and statistics are future features.
    """

    _OPTIONS = ("Mode", "Touches", "Statistiques", "Retour")
    _toggle_indices = frozenset({0})
    _title = "Humain"

    def __init__(self, screen, font, audio, menu) -> None:
        super().__init__(screen, font, audio)
        self.menu = menu

    # --- Hooks ----------------------------------------------------------

    def _value_label(self, i: int) -> str:
        match i:
            case 0:
                return self.menu.mode
            case _:
                return ""

    def _toggle(self, direction: int) -> None:
        match self.selection:
            case 0:  # Mode
                self.menu.mode = "Replay" if self.menu.mode == "Normal" else "Normal"

    def _save(self) -> None:
        self.menu.save_settings()

    def _on_back(self) -> State | None:
        return self.menu

    def _on_select(self) -> State | None:
        match self.selection:
            case 1:  # Touches
                from tetris.states.keybind import KeybindState

                return KeybindState(self.screen, self.font, self.audio, self)
            case 2:  # Statistiques
                from tetris.states.human_stats import HumanStatsState

                return HumanStatsState(self.screen, self.font, self.audio, self)
            case 3:  # Retour
                return self.menu
        return None
