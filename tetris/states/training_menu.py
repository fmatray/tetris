"""Training sub-menu: strategies, hyperparameters, back.

Nested under the AI menu. Only reachable when AI Mode = Apprentissage.
Strategies is a future feature (placeholder). Hyperparameters exposes
epsilon decay and epsilon end (configurable via left/right toggles).
"""

from __future__ import annotations

from tetris.states.base import State
from tetris.states.menu_base import MenuBase


class TrainingMenuState(MenuBase):
    """AI training sub-menu: strategies, hyperparameters, back."""

    _OPTIONS = ("Stratégies", "Hyperparamètres", "Retour")
    _toggle_indices = frozenset()
    _title = "Apprentissage"

    def __init__(self, screen, font, audio, ai_menu) -> None:
        super().__init__(screen, font, audio)
        self.ai_menu = ai_menu

    @property
    def menu(self):
        """Access the root MenuState through the AI menu."""
        return self.ai_menu.menu

    # --- Hooks ----------------------------------------------------------

    def _on_back(self) -> State | None:
        return self.ai_menu

    def _on_select(self) -> State | None:
        sel = self.selection
        if sel == 0:  # Stratégies
            from tetris.states.placeholder import PlaceholderState

            return PlaceholderState(
                self.screen, self.font, self.audio, self, "Stratégies"
            )
        if sel == 1:  # Hyperparamètres
            from tetris.states.hyperparam_menu import HyperparamMenuState

            return HyperparamMenuState(self.screen, self.font, self.audio, self)
        if sel == 2:  # Retour
            return self.ai_menu
        return None