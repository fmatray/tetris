"""Hyperparameters sub-menu: epsilon decay, epsilon end, back.

Nested under the Training menu. Exposes the DQN hyperparameters that
are configurable at runtime via left/right toggles.
"""

from __future__ import annotations

from tetris.states.base import State
from tetris.states.menu_base import MenuBase


class HyperparamMenuState(MenuBase):
    """AI hyperparameters sub-menu: DQN learning params, back."""

    _OPTIONS = (
        "Epsilon decay",
        "Epsilon fin",
        "Learning rate",
        "Gamma",
        "Batch size",
        "Buffer size",
        "Target sync",
        "Retour",
    )
    _toggle_indices = frozenset({0, 1, 2, 3, 4, 5, 6})
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
        m = self.menu
        if i == 0:
            return f"{m.ai_epsilon_decay:.4f}"
        if i == 1:
            return f"{m.ai_epsilon_end:.2f}"
        if i == 2:
            return f"{m.ai_lr:.1e}"
        if i == 3:
            return f"{m.ai_gamma:.3f}"
        if i == 4:
            return str(m.ai_batch_size)
        if i == 5:
            return f"{m.ai_buffer_size:,}"
        if i == 6:
            return str(m.ai_target_sync_steps)
        return ""

    def _toggle(self, direction: int) -> None:
        m = self.menu
        s = self.selection
        if s == 0:  # Epsilon decay
            m.ai_epsilon_decay = round(
                max(0.990, min(0.9999, m.ai_epsilon_decay + direction * 0.0001)),
                4,
            )
        elif s == 1:  # Epsilon fin
            m.ai_epsilon_end = round(
                max(0.02, min(0.10, m.ai_epsilon_end + direction * 0.01)),
                2,
            )
        elif s == 2:  # Learning rate
            m.ai_lr = round(max(1e-6, min(1e-2, m.ai_lr * (10 ** direction))), 6)
        elif s == 3:  # Gamma
            m.ai_gamma = round(max(0.80, min(0.99, m.ai_gamma + direction * 0.01)), 2)
        elif s == 4:  # Batch size
            m.ai_batch_size = max(8, min(256, m.ai_batch_size + direction * 8))
        elif s == 5:  # Buffer size
            m.ai_buffer_size = max(
                1_000, min(200_000, m.ai_buffer_size + direction * 5_000)
            )
        elif s == 6:  # Target sync
            m.ai_target_sync_steps = max(
                100, min(2_000, m.ai_target_sync_steps + direction * 100)
            )

    def _save(self) -> None:
        self.menu.save_settings()

    def _on_back(self) -> State | None:
        return self.training_menu

    def _on_select(self) -> State | None:
        if self.selection == 7:  # Retour
            return self.training_menu
        return None