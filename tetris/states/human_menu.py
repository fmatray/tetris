"""Human sub-menu: mode, handicap, keybindings, statistics, back."""

from __future__ import annotations

from tetris.states.base import State
from tetris.states.menu_base import MenuBase


class HumanMenuState(MenuBase):
    """Human player sub-menu: mode, handicap, keybindings, stats, back.

    Mode and handicap are human-player settings stored on the parent
    ``MenuState``. Keybindings and statistics are future features.
    """

    _OPTIONS = ("Mode", "Handicap", "Fantôme", "Touches", "Statistiques", "Retour")
    _toggle_indices = frozenset({0, 1, 2})
    _title = "Humain"

    def __init__(self, screen, font, audio, menu) -> None:
        super().__init__(screen, font, audio)
        self.menu = menu

    # --- Hooks ----------------------------------------------------------

    def _value_label(self, i: int) -> str:
        if i == 0:
            return self.menu.mode
        if i == 1:
            return str(self.menu.handicap)
        if i == 2:
            return "ON" if self.menu.ghost_piece else "OFF"
        return ""

    def _toggle(self, direction: int) -> None:
        if self.selection == 0:  # Mode
            self.menu.mode = "Replay" if self.menu.mode == "Normal" else "Normal"
        elif self.selection == 1:  # Handicap
            self.menu.handicap = max(0, min(5, self.menu.handicap + direction))
        elif self.selection == 2:  # Fantôme
            self.menu.ghost_piece = not self.menu.ghost_piece

    def _save(self) -> None:
        self.menu.save_settings()

    def _on_back(self) -> State | None:
        return self.menu

    def _on_select(self) -> State | None:
        sel = self.selection
        if sel == 3:  # Touches
            from tetris.states.keybind import KeybindState

            return KeybindState(self.screen, self.font, self.audio, self)
        if sel == 4:  # Statistiques
            from tetris.states.human_stats import HumanStatsState

            return HumanStatsState(self.screen, self.font, self.audio, self)
        if sel == 5:  # Retour
            return self.menu
        return None