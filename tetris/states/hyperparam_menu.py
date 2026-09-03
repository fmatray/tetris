"""Hyperparameters sub-menu: DQN learning params, reset, back.

Nested under the AI menu (Training entry). Exposes the DQN
hyperparameters that are configurable at runtime via left/right
toggles.  Rendered as a multi-column table (param, current, min,
max, step, explanation) grouped by category.
"""

from __future__ import annotations

from typing import Any, ClassVar

import pygame

from tetris.i18n import tr
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

# Option indices that are category headers (non-selectable, non-toggleable).
_HEADERS: frozenset[int] = frozenset()


class HyperparamMenuState(MenuBase):
    """AI learning sub-menu: DQN learning params, reset, back."""

    _title = "Training"

    # Category headers are uppercase, rendered as section separators.
    # Non-header options are toggleable or selectable.
    _OPTIONS = (
        "EXPLORATION",  # 0  header
        "Epsilon decay",  # 1  toggle
        "Epsilon end",  # 2  toggle
        "Warm-start",  # 3  toggle
        "LEARNING",  # 4  header
        "Learning rate",  # 5  toggle
        "Gamma",  # 6  toggle
        "Batch size",  # 7  toggle
        "Buffer size",  # 8  toggle
        "Updates per piece",  # 9  toggle
        "CURRICULUM",  # 10 header
        "Curriculum",  # 11 toggle
        "Curriculum freq.",  # 12 toggle
        "Curriculum epsilon",  # 13 toggle
        "GAMEPLAY",  # 14 header
        "Look-ahead",  # 15 toggle
        "Look-ahead depth",  # 16 toggle
        "Dueling",  # 17 toggle
        "Imitation",  # 18 toggle
        "Reset",  # 19 select
        "Back",  # 20 select
    )
    _header_indices: ClassVar[frozenset[int]] = frozenset({0, 4, 10, 14})
    _toggle_indices = frozenset({1, 2, 3, 5, 6, 7, 8, 9, 11, 12, 13, 15, 16, 17, 18})
    _instructions = "Left/Right: Adjust | Enter: Select | Esc: Back"

    # Per-param metadata: (min, max, step, explanation). Headers and
    # action rows use empty strings.
    _PARAM_META: ClassVar[tuple[tuple[str, str, str, str], ...]] = (
        ("", "", "", ""),  # EXPLORATION header
        ("0.990", "0.9999", "0.0001", "Exploration rate decay per episode."),
        ("0.02", "0.10", "0.01", "Epsilon floor — exploration never goes below this."),
        ("OFF", "ON", "ON/OFF", "Keep initial exploration when resuming a checkpoint."),
        ("", "", "", ""),  # LEARNING header
        ("1e-6", "1e-2", "x10", "Step size of gradient descent."),
        ("0.80", "0.99", "0.01", "Discount factor for future rewards."),
        ("8", "256", "8", "Samples per gradient update."),
        ("1000", "200000", "5000", "Replay buffer capacity."),
        ("1", "8", "1", "Gradient updates per locked piece."),
        ("", "", "", ""),  # CURRICULUM header
        ("OFF", "ON", "ON/OFF", "Progressive learning: O → +I → +L → +J → +T → +S → +Z"),
        ("10", "2000", "10", "Restart from easier pieces every N episodes."),
        ("reset", "decay", "", "Epsilon policy on curriculum restart."),
        ("", "", "", ""),  # GAMEPLAY header
        ("OFF", "ON", "ON/OFF", "Evaluate the next piece before locking."),
        ("1", "3", "1", "Number of next pieces evaluated."),
        ("OFF", "ON", "ON/OFF", "Split the V-network into value + advantage streams."),
        ("OFF", "ON", "ON/OFF", "Pre-train from recorded human placements before learning."),
        ("", "", "", ""),  # Reset
        ("", "", "", ""),  # Back
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
        "ai_dueling": False,
        "ai_imitation": False,
    }

    def __init__(self, screen, font, audio, ai_menu) -> None:
        super().__init__(screen, font, audio)
        self.ai_menu = ai_menu

    @property
    def menu(self):
        """Access the root MenuState through the AI menu."""
        return self.ai_menu.menu

    # --- Hooks ----------------------------------------------------------

    # (attr, fmt) per option index; None for headers and action rows.
    _VALUE_SPECS: ClassVar[list[tuple[str, Any] | None]] = [
        None,  # 0: EXPLORATION
        ("ai_epsilon_decay", lambda v: f"{v:.4f}"),
        ("ai_epsilon_end", lambda v: f"{v:.2f}"),
        ("ai_warm_start", lambda v: "ON" if v else "OFF"),
        None,  # 4: LEARNING
        ("ai_lr", lambda v: f"{v:.1e}"),
        ("ai_gamma", lambda v: f"{v:.3f}"),
        ("ai_batch_size", str),
        ("ai_buffer_size", lambda v: f"{v:,}"),
        ("ai_learn_per_action", str),
        None,  # 10: CURRICULUM
        ("ai_curriculum", lambda v: "ON" if v else "OFF"),
        ("ai_curriculum_freq", str),
        ("ai_curriculum_epsilon", str),
        None,  # 14: GAMEPLAY
        ("ai_lookahead", lambda v: "ON" if v else "OFF"),
        ("ai_lookahead_depth", str),
        ("ai_dueling", lambda v: "ON" if v else "OFF"),
        ("ai_imitation", lambda v: "ON" if v else "OFF"),
        None,  # 19: Reset
        None,  # 20: Back
    ]

    def _is_disabled(self, i: int) -> bool:
        """Category headers are non-selectable."""
        return i in self._header_indices

    def _value_label(self, i: int) -> str:
        if i >= len(self._VALUE_SPECS):
            return ""
        spec = self._VALUE_SPECS[i]
        if spec is None:
            return ""
        attr, fmt = spec
        return fmt(getattr(self.menu, attr))

    def _toggle(self, direction: int) -> None:
        m = self.menu
        match self.selection:
            case 1:  # Epsilon decay
                m.ai_epsilon_decay = round(
                    max(0.990, min(0.9999, m.ai_epsilon_decay + direction * 0.0001)),
                    4,
                )
            case 2:  # Epsilon end
                m.ai_epsilon_end = round(
                    max(0.02, min(0.10, m.ai_epsilon_end + direction * 0.01)),
                    2,
                )
            case 3:  # Warm-start
                m.ai_warm_start = not m.ai_warm_start
            case 5:  # Learning rate
                m.ai_lr = round(max(1e-6, min(1e-2, m.ai_lr * (10**direction))), 6)
            case 6:  # Gamma
                m.ai_gamma = round(max(0.80, min(0.99, m.ai_gamma + direction * 0.01)), 2)
            case 7:  # Batch size
                m.ai_batch_size = max(8, min(256, m.ai_batch_size + direction * 8))
            case 8:  # Buffer size
                m.ai_buffer_size = max(1_000, min(200_000, m.ai_buffer_size + direction * 5_000))
            case 9:  # Updates per piece
                m.ai_learn_per_action = max(1, min(8, m.ai_learn_per_action + direction))
            case 11:  # Curriculum
                m.ai_curriculum = not m.ai_curriculum
            case 12:  # Curriculum frequency
                m.ai_curriculum_freq = max(10, min(2000, m.ai_curriculum_freq + direction * 10))
            case 13:  # Curriculum epsilon policy
                policies = ["reset", "boost", "decay"]
                idx = policies.index(m.ai_curriculum_epsilon)
                m.ai_curriculum_epsilon = policies[(idx + direction) % len(policies)]
            case 15:  # Look-ahead
                m.ai_lookahead = not m.ai_lookahead
            case 16:  # Look-ahead depth
                m.ai_lookahead_depth = max(1, min(3, m.ai_lookahead_depth + direction))
            case 17:  # Dueling
                m.ai_dueling = not m.ai_dueling
            case 18:  # Imitation
                m.ai_imitation = not m.ai_imitation

    def _save(self) -> None:
        self.menu.save_settings()

    def _on_back(self) -> State | None:
        return self.ai_menu

    def _on_select(self) -> State | None:
        if self.selection == 19:  # Reset
            for attr, val in self._DEFAULTS.items():
                setattr(self.menu, attr, val)
            self.menu.save_settings()
            return None
        if self.selection == 20:  # Back
            return self.ai_menu
        return None

    # --- Custom table draw ------------------------------------------------

    def draw(self, screen: pygame.Surface, *, particles=None) -> None:
        """Render hyperparameters as a multi-column table grouped by category.

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
        title = get_large_font().render(tr(self._title), True, WHITE)
        screen.blit(title, (SCREEN_WIDTH // 2 - title.get_width() // 2, TITLE_Y))

        # --- Column layout ---
        # Left-aligned: Param, Explanation. Right-aligned: Current, Min, Max, Step.
        headers = ("Parameter", "Current", "Min", "Max", "Step", "Explanation")
        margin = 40
        left_w = 180  # Param
        num_w = 100  # Current, Min, Max, Step (right-aligned)
        gap = 15
        expl_w = SCREEN_WIDTH - margin * 2 - left_w - num_w * 4 - gap

        x_left = margin
        x_num = [margin + left_w + c * num_w for c in range(4)]
        x_expl = margin + left_w + num_w * 4 + gap

        y = CONTENT_Y
        lh = LINE_HEIGHT_SMALL

        # --- Header row (bold via large font? no — use small, white) ---
        for c in range(4):
            surf = self.font.render(tr(headers[c + 1]), True, GRAY)
            screen.blit(surf, (x_num[c] + num_w - surf.get_width(), y))
        surf = self.font.render(tr(headers[0]), True, GRAY)
        screen.blit(surf, (x_left, y))
        surf = self.font.render(tr(headers[5]), True, GRAY)
        screen.blit(surf, (x_expl, y))
        y += lh

        # --- Separator line ---
        pygame.draw.line(screen, GRAY, (margin, y - 6), (SCREEN_WIDTH - margin, y - 6))

        # --- Data rows ---
        for i, option in enumerate(self._OPTIONS):
            is_sel = i == self.selection
            is_header = i in self._header_indices
            meta = self._PARAM_META[i]

            if is_header:
                # Category header: render in white, slightly indented, no table columns
                surf = self.font.render(tr(option), True, WHITE)
                screen.blit(surf, (x_left, y))
                y += lh
                continue

            color = WHITE if is_sel else GRAY

            # Param name (left-aligned, prefixed with cursor)
            prefix = "> " if is_sel else "  "
            surf = self.font.render(f"{prefix}{tr(option)}", True, color)
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
                text = tr(meta[3])
                surf = self.font.render(text, True, color)
                # Truncate if too wide
                if surf.get_width() > expl_w:
                    while surf.get_width() > expl_w - 10 and len(text) > 5:
                        text = text[:-1]
                        surf = self.font.render(text + "…", True, color)
                screen.blit(surf, (x_expl, y))

            y += lh

        # --- Instructions ---
        instr = self.font.render(tr(self._instructions), True, GRAY)
        screen.blit(instr, (SCREEN_WIDTH // 2 - instr.get_width() // 2, INSTRUCTIONS_Y))
