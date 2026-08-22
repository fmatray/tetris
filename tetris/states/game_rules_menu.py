"""Game rules sub-menu: random generator, preview count, handicap, speed mode, ghost piece, back."""

from __future__ import annotations

from tetris.settings import GENERATOR_LABELS, SPEED_MODE_LABELS, SPEED_MODE_ORDER
from tetris.states.base import State
from tetris.states.menu_base import MenuBase

_GENERATORS = ("random", "7bag", "35bag", "weighted")
_PREVIEW_LABELS = ("Désactivé", "1 pièce", "3 pièces")
_PREVIEW_VALUES = (0, 1, 3)

_HOLES_OVERHANGS_LABELS = ("Aucun", "Trous", "Surplombs", "Les deux")
_HOLES_OVERHANGS_VALUES = ("none", "holes", "overhangs", "both")


class GameRulesMenuState(MenuBase):
    """Game rules sub-menu: random generator, preview count, handicap, speed mode, ghost piece, back."""

    _OPTIONS = ("Générateur", "Prévisualisation", "Handicap", "Vitesse", "Fantôme", "Trous et surplombs", "Retour")
    _toggle_indices = frozenset({0, 1, 2, 3, 4, 5})
    _title = "Règles du jeu"

    def __init__(self, screen, font, audio, menu) -> None:
        super().__init__(screen, font, audio)
        self.menu = menu

    def _value_label(self, i: int) -> str:
        match i:
            case 0:
                return GENERATOR_LABELS.get(self.menu.piece_generator, "Aléatoire")
            case 1:
                idx = _PREVIEW_VALUES.index(self.menu.preview_count)
                return _PREVIEW_LABELS[idx]
            case 2:
                return str(self.menu.handicap)
            case 3:
                return SPEED_MODE_LABELS.get(self.menu.speed_mode, "Normal")
            case 4:
                return "ON" if self.menu.ghost_piece else "OFF"
            case 5:
                return _HOLES_OVERHANGS_LABELS[_HOLES_OVERHANGS_VALUES.index(self.menu.holes_overhangs_help)]
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
            case 3:
                idx = SPEED_MODE_ORDER.index(self.menu.speed_mode)
                self.menu.speed_mode = SPEED_MODE_ORDER[(idx + direction) % len(SPEED_MODE_ORDER)]
            case 4:
                self.menu.ghost_piece = not self.menu.ghost_piece
            case 5:
                idx = _HOLES_OVERHANGS_VALUES.index(self.menu.holes_overhangs_help)
                self.menu.holes_overhangs_help = _HOLES_OVERHANGS_VALUES[
                    (idx + direction) % len(_HOLES_OVERHANGS_VALUES)
                ]

    def _save(self) -> None:
        self.menu.save_settings()

    def _on_back(self) -> State | None:
        return self.menu

    def _on_select(self) -> State | None:
        if self.selection == 6:  # Retour
            return self.menu
        self._toggle(1)
        self._save()
        return None
