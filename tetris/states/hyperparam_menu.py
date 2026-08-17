"""Hyperparameters sub-menu: DQN learning params, reset, back.

Nested under the AI menu (Apprentissage entry). Exposes the DQN
hyperparameters that are configurable at runtime via left/right
toggles.  Rendered as a multi-column table (param, current, min,
max, step, explanation).
"""

from __future__ import annotations

from typing import Any, ClassVar

import pygame

from tetris.settings import BLACK, GRAY, SCREEN_WIDTH, WHITE
from tetris.states.base import State
from tetris.states.menu_base import MenuBase
from tetris.visuals.fonts import (
    CONTENT_Y,
    INSTRUCTIONS_Y,
    LINE_HEIGHT_SMALL,
    TITLE_Y,
    get_large_font,
)


class HyperparamMenuState(MenuBase):
    """AI learning sub-menu: DQN learning params, reset, back."""

    _title = "Apprentissage"

    _OPTIONS = (
        "Epsilon decay",
        "Epsilon fin",
        "Learning rate",
        "Gamma",
        "Batch size",
        "Buffer size",
        "Curriculum",
        "Fréq. curriculum",
        "Epsilon curr.",
        "Warm-start",
        "Maj. par pièce",
        "Look-ahead",
        "Prof. lookahead",
        "Soft-drop",
        "Réinitialiser",
        "Retour",
    )
    _toggle_indices = frozenset({0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13})

    # Per-param metadata: (min, max, step, explanation)
    _PARAM_META: ClassVar[tuple[tuple[str, str, str, str], ...]] = (
        ("0.990", "0.9999", "0.0001", "Décroissance d'epsilon. ↑ = exploration plus longue, apprentissage plus lent"),
        ("0.02", "0.10", "0.01", "Epsilon minimal. ↑ = plus d'exploration résiduelle, moins de convergence"),
        ("1e-6", "1e-2", "x10", "Taux d'apprentissage Adam. ↑ = apprentissage plus rapide mais instable"),
        ("0.80", "0.99", "0.01", "Actualisation récompenses futures. ↑ = long terme, ↓ = court terme"),
        ("8", "256", "8", "Taille du mini-batch. ↑ = gradients plus stables mais plus de mémoire"),
        ("1000", "200000", "5000", "Capacité du replay buffer. ↑ = plus de diversité, moins de corrélation"),
        ("OFF", "ON", "ON/OFF", "Apprentissage progressif: O → +I → +L → +J → +T → +S → +Z"),
        ("10", "2000", "10", "Épisodes entre ajout de pièce (curriculum)"),
        ("reset", "decay", "", "Epsilon à l'ajout: reset=1.0, boost=0.5, decay=normal"),
        ("OFF", "ON", "ON/OFF", "Exploration dirigée par heuristique Dellacherie (warm-start)"),
        ("1", "8", "1", "Mises à jour gradient par pièce verrouillée"),
        ("OFF", "ON", "ON/OFF", "Anticipation 2 pièces: simule le meilleur placement de la pièce suivante"),
        ("1", "3", "1", "Profondeur d'anticipation: 1=une pièce, 3=trois pièces"),
        ("OFF", "ON", "ON/OFF", "Recherche BFS: placements en glissé (surplombs, T-Spins)"),
        ("", "", "", ""),  # Réinitialiser
        ("", "", "", ""),  # Retour
    )

    _DEFAULTS: ClassVar[dict[str, float | int | bool | str]] = {
        "ai_epsilon_decay": 0.999,
        "ai_epsilon_end": 0.10,
        "ai_lr": 1e-3,
        "ai_gamma": 0.97,
        "ai_batch_size": 64,
        "ai_buffer_size": 50_000,
        "ai_curriculum": False,
        "ai_curriculum_freq": 50,
        "ai_curriculum_epsilon": "reset",
        "ai_warm_start": True,
        "ai_lookahead": True,
        "ai_lookahead_depth": 3,
        "ai_soft_drop": True,
    }

    def __init__(self, screen, font, audio, ai_menu) -> None:
        super().__init__(screen, font, audio)
        self.ai_menu = ai_menu

    @property
    def menu(self):
        """Access the root MenuState through the AI menu."""
        return self.ai_menu.menu

    # --- Hooks ----------------------------------------------------------

    _VALUE_SPECS: ClassVar[list[tuple[str, Any]]] = [
        ("ai_epsilon_decay", lambda v: f"{v:.4f}"),
        ("ai_epsilon_end", lambda v: f"{v:.2f}"),
        ("ai_lr", lambda v: f"{v:.1e}"),
        ("ai_gamma", lambda v: f"{v:.3f}"),
        ("ai_batch_size", str),
        ("ai_buffer_size", lambda v: f"{v:,}"),
        ("ai_curriculum", lambda v: "ON" if v else "OFF"),
        ("ai_curriculum_freq", str),
        ("ai_curriculum_epsilon", str),
        ("ai_warm_start", lambda v: "ON" if v else "OFF"),
        ("ai_learn_per_action", str),
        ("ai_lookahead", lambda v: "ON" if v else "OFF"),
        ("ai_lookahead_depth", str),
        ("ai_soft_drop", lambda v: "ON" if v else "OFF"),
    ]

    def _value_label(self, i: int) -> str:
        if i >= len(self._VALUE_SPECS):
            return ""
        attr, fmt = self._VALUE_SPECS[i]
        return fmt(getattr(self.menu, attr))

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
        elif s == 6:  # Curriculum
            m.ai_curriculum = not m.ai_curriculum
        elif s == 7:  # Curriculum frequency
            m.ai_curriculum_freq = max(10, min(2000, m.ai_curriculum_freq + direction * 10))
        elif s == 8:  # Curriculum epsilon policy
            policies = ["reset", "boost", "decay"]
            idx = policies.index(m.ai_curriculum_epsilon)
            m.ai_curriculum_epsilon = policies[(idx + direction) % len(policies)]
        elif s == 9:  # Warm-start
            m.ai_warm_start = not m.ai_warm_start
        elif s == 10:  # Maj. par pièce
            m.ai_learn_per_action = max(1, min(8, m.ai_learn_per_action + direction))
        elif s == 11:  # Look-ahead
            m.ai_lookahead = not m.ai_lookahead
        elif s == 12:  # Prof. lookahead
            m.ai_lookahead_depth = max(1, min(3, m.ai_lookahead_depth + direction))
        elif s == 13:  # Soft-drop
            m.ai_soft_drop = not m.ai_soft_drop

    def _save(self) -> None:
        self.menu.save_settings()

    def _on_back(self) -> State | None:
        return self.ai_menu

    def _on_select(self) -> State | None:
        if self.selection == 14:  # Réinitialiser
            for attr, val in self._DEFAULTS.items():
                setattr(self.menu, attr, val)
            self.menu.save_settings()
            return None
        if self.selection == 15:  # Retour
            return self.ai_menu
        return None
    # --- Custom table draw ------------------------------------------------

    def draw(self, screen: pygame.Surface, *, particles=None) -> None:
        """Render hyperparameters as a multi-column table.

        Draw order: black fill → background animation → explosion
        particles → title → table → instructions.  Overrides
        :meth:`MenuBase.draw` to use a multi-column pixel layout instead
        of centered single-column options.

        Columns: Param | Current | Min | Max | Step | Explanation
        """
        screen.fill(BLACK)
        self.bg_anim.draw(screen)
        if particles is not None:
            particles.draw(screen)
        title = get_large_font().render(self._title, True, WHITE)
        screen.blit(title, (SCREEN_WIDTH // 2 - title.get_width() // 2, TITLE_Y))

        # --- Column layout ---
        # Left-aligned: Param, Explanation. Right-aligned: Current, Min, Max, Step.
        headers = ("Paramètre", "Current", "Min", "Max", "Step", "Explication")
        margin = 40
        left_w = 180     # Param
        num_w = 100        # Current, Min, Max, Step (right-aligned)
        gap = 15
        expl_w = SCREEN_WIDTH - margin * 2 - left_w - num_w * 4 - gap

        x_left = margin
        x_num = [margin + left_w + c * num_w for c in range(4)]
        x_expl = margin + left_w + num_w * 4 + gap

        y = CONTENT_Y
        lh = LINE_HEIGHT_SMALL

        # --- Header row (bold via large font? no — use small, white) ---
        for c in range(4):
            surf = self.font.render(headers[c + 1], True, GRAY)
            screen.blit(surf, (x_num[c] + num_w - surf.get_width(), y))
        surf = self.font.render(headers[0], True, GRAY)
        screen.blit(surf, (x_left, y))
        surf = self.font.render(headers[5], True, GRAY)
        screen.blit(surf, (x_expl, y))
        y += lh

        # --- Separator line ---
        pygame.draw.line(screen, GRAY, (margin, y - 6), (SCREEN_WIDTH - margin, y - 6))

        # --- Data rows ---
        for i, option in enumerate(self._OPTIONS):
            is_sel = i == self.selection
            color = WHITE if is_sel else GRAY
            meta = self._PARAM_META[i]

            # Param name (left-aligned, prefixed with cursor)
            prefix = "> " if is_sel else "  "
            surf = self.font.render(f"{prefix}{option}", True, color)
            screen.blit(surf, (x_left, y))

            # Numeric columns: Current, Min, Max, Step
            current = self._value_label(i)
            values = [current, meta[0], meta[1], meta[2]]
            for c, val in enumerate(values):
                if val:
                    surf = self.font.render(val, True, color)
                    screen.blit(surf, (x_num[c] + num_w - surf.get_width(), y))

            # Explanation (left-aligned)
            if meta[3]:
                text = meta[3]
                surf = self.font.render(text, True, color)
                # Truncate if too wide
                if surf.get_width() > expl_w:
                    while surf.get_width() > expl_w - 10 and len(text) > 5:
                        text = text[:-1]
                        surf = self.font.render(text + "…", True, color)
                screen.blit(surf, (x_expl, y))

            y += lh

        # --- Instructions ---
        instr = self.font.render(self._instructions, True, GRAY)
        screen.blit(instr, (SCREEN_WIDTH // 2 - instr.get_width() // 2, INSTRUCTIONS_Y))
