"""Game rules sub-menu: random generator, preview count, handicap, speed mode, ghost piece, back."""

from __future__ import annotations

from tetris.i18n import tr
from tetris.settings import GENERATOR_LABELS, SPEED_MODE_LABELS, SPEED_MODE_ORDER
from tetris.states.base import State
from tetris.states.menu_base import MenuBase

_GENERATORS = ("random", "7bag", "35bag", "weighted")
_PREVIEW_LABELS = ("Disabled", "1 piece", "3 pieces")
_PREVIEW_VALUES = (0, 1, 3)

_HOLES_OVERHANGS_LABELS = ("None", "Holes", "Overhangs", "Both")
_HOLES_OVERHANGS_VALUES = ("none", "holes", "overhangs", "both")


class GameRulesMenuState(MenuBase):
    """Game rules sub-menu: random generator, preview count, handicap, speed mode, ghost piece, back."""

    _OPTIONS = ("Generator", "Preview", "Handicap", "Speed", "Ghost piece", "Holes and overhangs", "Back")
    _toggle_indices = frozenset({0, 1, 2, 3, 4, 5})
    _title = "Game rules"

    def __init__(self, screen, font, audio, menu) -> None:
        super().__init__(screen, font, audio)
        self.menu = menu

    def _value_label(self, i: int) -> str:
        match i:
            case 0:
                return tr(GENERATOR_LABELS.get(self.menu.piece_generator, "Random"))
            case 1:
                idx = _PREVIEW_VALUES.index(self.menu.preview_count)
                return tr(_PREVIEW_LABELS[idx])
            case 2:
                return str(self.menu.handicap)
            case 3:
                return tr(SPEED_MODE_LABELS.get(self.menu.speed_mode, "Normal"))
            case 4:
                return "ON" if self.menu.ghost_piece else "OFF"
            case 5:
                return tr(_HOLES_OVERHANGS_LABELS[_HOLES_OVERHANGS_VALUES.index(self.menu.holes_overhangs_help)])
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
        if self.selection == 6:  # Back
            return self.menu
        self._toggle(1)
        self._save()
        return None
