"""Game rules sub-menu: random generator, preview count, handicap, back."""

from __future__ import annotations

from tetris.states.base import State
from tetris.states.menu_base import MenuBase

_GENERATOR_LABELS = {"random": "Aléatoire", "7bag": "7-bag", "35bag": "35-bag", "weighted": "Pondéré"}
_GENERATORS = ("random", "7bag", "35bag", "weighted")
_PREVIEW_LABELS = ("Désactivé", "1 pièce", "3 pièces")
_PREVIEW_VALUES = (0, 1, 3)


class GameRulesMenuState(MenuBase):
    """Game rules sub-menu: random generator, preview count, handicap, back."""

    _OPTIONS = ("Générateur", "Prévisualisation", "Handicap", "Retour")
    _toggle_indices = frozenset({0, 1, 2})
    _title = "Règles du jeu"

    def __init__(self, screen, font, audio, menu) -> None:
        super().__init__(screen, font, audio)
        self.menu = menu

    def _value_label(self, i: int) -> str:
        match i:
            case 0:
                return _GENERATOR_LABELS.get(self.menu.piece_generator, "Aléatoire")
            case 1:
                idx = _PREVIEW_VALUES.index(self.menu.preview_count)
                return _PREVIEW_LABELS[idx]
            case 2:
                return str(self.menu.handicap)
            case _:
                return ""

    def _toggle(self, direction: int) -> None:
        match self.selection:
            case 0:
                idx = _GENERATORS.index(self.menu.piece_generator)
                self.menu.piece_generator = _GENERATORS[(idx + direction) % len(_GENERATORS)]
            case 1:
                idx = _PREVIEW_VALUES.index(self.menu.preview_count)
                self.menu.preview_count = _PREVIEW_VALUES[(idx + direction) % len(_PREVIEW_VALUES)]
            case 2:
                self.menu.handicap = max(0, min(5, self.menu.handicap + direction))

    def _save(self) -> None:
        self.menu.save_settings()

    def _on_back(self) -> State | None:
        return self.menu

    def _on_select(self) -> State | None:
        if self.selection == 2:  # Retour
            return self.menu
        self._toggle(1)
        self._save()
        return None