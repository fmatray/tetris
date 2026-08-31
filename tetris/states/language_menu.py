"""Language sub-menu: pick UI language (English, French, Spanish, Slovenian)."""

from __future__ import annotations

from tetris import i18n
from tetris.states.base import State
from tetris.states.menu_base import MenuBase


class LanguageMenuState(MenuBase):
    """Language sub-menu; language names always show in their own language."""

    _OPTIONS = ("English", "Français", "Español", "Slovenščina", "Back")
    _toggle_indices = frozenset({0, 1, 2, 3})
    _title = "Language"
    _LANG_CODES = ("en", "fr", "es", "sl")  # parallel to _OPTIONS[0:4]

    def __init__(self, screen, font, audio, menu) -> None:
        super().__init__(screen, font, audio)
        self.menu = menu

    # --- Hooks ----------------------------------------------------------

    def _value_label(self, i: int) -> str:
        if i < 4 and self._LANG_CODES[i] == i18n.get_language():
            return "✓"
        return ""

    def _toggle(self, direction: int) -> None:
        code = self._LANG_CODES[(self.selection + direction) % 4]
        self.menu.language = code
        i18n.set_language(code)

    def _save(self) -> None:
        self.menu.save_settings()

    def _on_back(self) -> State | None:
        return self.menu

    def _on_select(self) -> State | None:
        if self.selection == 4:  # Back
            return self.menu
        self._toggle(1)
        self._save()
        return None
