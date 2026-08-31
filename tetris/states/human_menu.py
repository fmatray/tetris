"""Human sub-menu: mode, keybindings, statistics, back."""

from __future__ import annotations

from tetris.i18n import tr
from tetris.states.base import State
from tetris.states.menu_base import MenuBase


class HumanMenuState(MenuBase):
    """Human player sub-menu: mode, keybindings, stats, back.

    Mode is a human-player setting stored on the parent ``MenuState``.
    Keybindings and statistics are future features.
    """

    _OPTIONS = ("Mode", "Seed", "Keys", "Statistics", "Back")
    _toggle_indices = frozenset({0})
    _title = "Human"

    def __init__(self, screen, font, audio, menu) -> None:
        super().__init__(screen, font, audio)
        self.menu = menu

    # --- Hooks ----------------------------------------------------------

    def _value_label(self, i: int) -> str:
        match i:
            case 0:
                return tr(self.menu.mode)
            case 1:
                return str(self.menu.seed) if self.menu.seed is not None else tr("Random")
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
            case 1:  # Seed
                from tetris.states.seed_entry import SeedEntryState

                return SeedEntryState(self.screen, self.font, self.audio, self.menu)
            case 2:  # Keys
                from tetris.states.keybind import KeybindState

                return KeybindState(self.screen, self.font, self.audio, self)
            case 3:  # Statistics
                from tetris.states.human_stats import HumanStatsState

                return HumanStatsState(self.screen, self.font, self.audio, self)
            case 4:  # Back
                return self.menu
        return None
