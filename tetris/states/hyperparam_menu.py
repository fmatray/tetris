"""Hyperparameters sub-menu: epsilon decay, epsilon end, back.

Nested under the Training menu. Exposes the DQN hyperparameters that
are configurable at runtime via left/right toggles.
"""

from __future__ import annotations

from tetris.states.base import State
from tetris.states.menu_base import MenuBase


class HyperparamMenuState(MenuBase):
    """AI hyperparameters sub-menu: epsilon decay, epsilon end, back."""

    _OPTIONS = ("Epsilon decay", "Epsilon fin", "Retour")
    _toggle_indices = frozenset({0, 1})
    _title = "Hyperparamètres"

    def __init__(self, screen, font, audio, training_menu) -> None:
        super().__init__(screen, font, audio)
        self.training_menu = training_menu

    @property
    def menu(self):
        """Access the root MenuState through the training menu."""
        return self.training_menu.menu

    # --- Hooks ----------------------------------------------------------

    def _value_label(self, i: int) -> str:
        if i == 0:
            return f"{self.menu.ai_epsilon_decay:.4f}"
        if i == 1:
            return f"{self.menu.ai_epsilon_end:.2f}"
        return ""

    def _toggle(self, direction: int) -> None:
        if self.selection == 0:  # Epsilon decay
            self.menu.ai_epsilon_decay = round(
                max(0.990, min(0.9999, self.menu.ai_epsilon_decay + direction * 0.0001)),
                4,
            )
        elif self.selection == 1:  # Epsilon fin
            self.menu.ai_epsilon_end = round(
                max(0.02, min(0.10, self.menu.ai_epsilon_end + direction * 0.01)),
                2,
            )

    def _save(self) -> None:
        self.menu.save_settings()

    def _on_back(self) -> State | None:
        return self.training_menu

    def _on_select(self) -> State | None:
        if self.selection == 2:  # Retour
            return self.training_menu
        return None