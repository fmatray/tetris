"""Human sub-menu: mode, ghost piece, keybindings, statistics, back."""

from __future__ import annotations

from tetris.states.base import State
from tetris.states.menu_base import MenuBase


class HumanMenuState(MenuBase):
    """Human player sub-menu: mode, ghost piece, keybindings, stats, back.

    Mode and ghost piece are human-player settings stored on the parent
    ``MenuState``. Keybindings and statistics are future features.
    """

    _OPTIONS = ("Mode", "Fantôme", "Touches", "Statistiques", "Retour")
    _toggle_indices = frozenset({0, 1})
    _title = "Humain"

    def __init__(self, screen, font, audio, menu) -> None:
        super().__init__(screen, font, audio)
        self.menu = menu

    # --- Hooks ----------------------------------------------------------

    def _value_label(self, i: int) -> str:
        match i:
            case 0:
                return self.menu.mode
            case 1:
                return "ON" if self.menu.ghost_piece else "OFF"
            case _:
                return ""

    def _toggle(self, direction: int) -> None:
        match self.selection:
            case 0:  # Mode
                self.menu.mode = "Replay" if self.menu.mode == "Normal" else "Normal"
            case 1:  # Fantôme
                self.menu.ghost_piece = not self.menu.ghost_piece

    def _save(self) -> None:
        self.menu.save_settings()

    def _on_back(self) -> State | None:
        return self.menu

    def _on_select(self) -> State | None:
        match self.selection:
            case 2:  # Touches
                from tetris.states.keybind import KeybindState

                return KeybindState(self.screen, self.font, self.audio, self)
            case 3:  # Statistiques
                from tetris.states.human_stats import HumanStatsState

                return HumanStatsState(self.screen, self.font, self.audio, self)
            case 4:  # Retour
                return self.menu
        return None
