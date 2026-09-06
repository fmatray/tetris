"""Bot sub-menu: El-Tetris skill level and lookahead settings."""

from __future__ import annotations

from tetris.i18n import tr
from tetris.settings import PLAYER_LEVEL_LABELS, PLAYER_LEVELS
from tetris.states.base import State
from tetris.states.menu_base import MenuBase


class BotMenuState(MenuBase):
    """El-Tetris bot sub-menu: skill level and lookahead settings.

    ``Level`` (Noob → God) is stored on the parent ``MenuState`` as
    ``bot_level``; it degrades playing skill (placement missteps, slower
    decisions, less anticipation). ``Look-ahead`` ("None" / "Same as
    preview") is stored as ``bot_lookahead`` ("none" / "preview").
    """

    _OPTIONS = ("Level", "Look-ahead", "Back")
    _toggle_indices = frozenset({0, 1})  # Level, Look-ahead
    _title = "El-Tetris Bot"

    def __init__(self, screen, font, audio, menu) -> None:
        super().__init__(screen, font, audio)
        self.menu = menu

    # --- Hooks ----------------------------------------------------------

    def _value_label(self, i: int) -> str:
        match i:
            case 0:  # Level
                return tr(PLAYER_LEVEL_LABELS[self.menu.bot_level])
            case 1:  # Look-ahead
                return tr("None") if self.menu.bot_lookahead == "none" else tr("Same as preview")
            case _:
                return ""

    def _toggle(self, direction: int) -> None:
        match self.selection:
            case 0:  # Level
                levels = PLAYER_LEVELS
                idx = levels.index(self.menu.bot_level)
                self.menu.bot_level = levels[(idx + direction) % len(levels)]
            case 1:  # Look-ahead
                self.menu.bot_lookahead = "preview" if self.menu.bot_lookahead == "none" else "none"

    def _save(self) -> None:
        self.menu.save_settings()

    def _on_back(self) -> State | None:
        return self.menu

    def _on_select(self) -> State | None:
        match self.selection:
            case 2:  # Back
                return self.menu
        return None
