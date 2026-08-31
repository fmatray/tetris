"""Bot sub-menu: El-Tetris lookahead setting."""

from __future__ import annotations

from tetris.i18n import tr
from tetris.states.base import State
from tetris.states.menu_base import MenuBase


class BotMenuState(MenuBase):
    """El-Tetris bot sub-menu: single lookahead setting.

    ``Look-ahead`` ("None" / "Same as preview") is stored on the parent
    ``MenuState`` as ``bot_lookahead`` ("none" / "preview").
    """

    _OPTIONS = ("Look-ahead", "Back")
    _toggle_indices = frozenset({0})  # Look-ahead
    _title = "El-Tetris Bot"

    def __init__(self, screen, font, audio, menu) -> None:
        super().__init__(screen, font, audio)
        self.menu = menu

    # --- Hooks ----------------------------------------------------------

    def _value_label(self, i: int) -> str:
        match i:
            case 0:  # Look-ahead
                return tr("None") if self.menu.bot_lookahead == "none" else tr("Same as preview")
            case _:
                return ""

    def _toggle(self, direction: int) -> None:
        match self.selection:
            case 0:  # Look-ahead
                self.menu.bot_lookahead = "preview" if self.menu.bot_lookahead == "none" else "none"

    def _save(self) -> None:
        self.menu.save_settings()

    def _on_back(self) -> State | None:
        return self.menu

    def _on_select(self) -> State | None:
        match self.selection:
            case 1:  # Back
                return self.menu
        return None
