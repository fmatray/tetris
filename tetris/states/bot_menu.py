"""Bot sub-menu: Dellacherie lookahead setting."""

from __future__ import annotations

from tetris.states.base import State
from tetris.states.menu_base import MenuBase


class BotMenuState(MenuBase):
    """Dellacherie bot sub-menu: single lookahead setting.

    ``Anticipation`` ("Non" / "Comme aperçu") is stored on the parent
    ``MenuState`` as ``bot_lookahead`` ("none" / "preview").
    """

    _OPTIONS = ("Anticipation", "Retour")
    _toggle_indices = frozenset({0})  # Anticipation
    _title = "Bot Dellacherie"

    def __init__(self, screen, font, audio, menu) -> None:
        super().__init__(screen, font, audio)
        self.menu = menu

    # --- Hooks ----------------------------------------------------------

    def _value_label(self, i: int) -> str:
        match i:
            case 0:  # Anticipation
                return "Non" if self.menu.bot_lookahead == "none" else "Comme aperçu"
            case _:
                return ""

    def _toggle(self, direction: int) -> None:
        match self.selection:
            case 0:  # Anticipation
                self.menu.bot_lookahead = "preview" if self.menu.bot_lookahead == "none" else "none"

    def _save(self) -> None:
        self.menu.save_settings()

    def _on_back(self) -> State | None:
        return self.menu

    def _on_select(self) -> State | None:
        match self.selection:
            case 1:  # Retour
                return self.menu
        return None
