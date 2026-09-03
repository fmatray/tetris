"""Tournament sub-menu: post-training evolution loop configuration.

Nested under the AI menu (Tournament entry). Configures and runs the
evolutionary self-play loop (``run_tournament_loops``) with per-param
explanations, a restore-checkpoint action, and a stats view. Rendered
as a multi-column table copied from :class:`HyperparamMenuState`.
"""

from __future__ import annotations

import os
import shutil
from typing import ClassVar

import pygame

from tetris.i18n import tr
from tetris.settings import (
    BLACK,
    GRAY,
    MODEL_PATH,
    PRE_TOURNAMENT_PATH,
    RED,
    SCREEN_WIDTH,
    TOURNAMENT_LOOPS_PATH,
    WHITE,
)
from tetris.states.base import State
from tetris.states.menu_base import MenuBase
from tetris.visuals.fonts import (
    CONTENT_Y,
    INSTRUCTIONS_Y,
    LINE_HEIGHT_SMALL,
    TITLE_Y,
    get_large_font,
)


class TournamentMenuState(MenuBase):
    """Tournament sub-menu: loop params, stats, restore checkpoint, start."""

    _title = "Tournament"

    _OPTIONS = (
        "TOURNAMENT",  # 0  header
        "Loops",  # 1  toggle
        "Generations",  # 2  toggle
        "Episodes",  # 3  toggle
        "Population",  # 4  toggle
        "Sigma",  # 5  toggle
        "Statistics",  # 6  select (disabled without loops.json entries)
        "Restore checkpoint",  # 7  select (two-press confirm)
        "Start",  # 8  select (disabled without a model)
        "Back",  # 9  select
    )
    _header_indices: ClassVar[frozenset[int]] = frozenset({0})
    _toggle_indices = frozenset({1, 2, 3, 4, 5})
    _instructions = "Left/Right: Adjust | Enter: Select | Esc: Back"

    # Per-param metadata: (min, max, step, explanation). Headers and
    # action rows use empty strings.
    _PARAM_META: ClassVar[tuple[tuple[str, str, str, str], ...]] = (
        ("", "", "", ""),  # TOURNAMENT header
        ("1", "20", "1", "Post-training evolution rounds; each round re-seeds the model with its winner."),
        ("1", "20", "1", "Evolution steps per round: mutate → evaluate → keep the best half."),
        ("1", "5", "1", "Seeded games per agent; fitness = average score (more = less noise, slower)."),
        ("2", "12", "2", "Agents per generation (even: half survive). Bigger = more exploration, slower."),
        (
            "0.005",
            "0.10",
            "0.005",
            "Mutation strength: Gaussian noise scale on weights. Small = fine-tune, big = explore.",
        ),
        ("", "", "", ""),  # Statistics
        ("", "", "", ""),  # Restore checkpoint
        ("", "", "", ""),  # Start
        ("", "", "", ""),  # Back
    )

    def __init__(self, screen, font, audio, ai_menu) -> None:
        super().__init__(screen, font, audio)
        self.ai_menu = ai_menu
        self._confirm_restore = False

    @property
    def menu(self):
        """Access the root MenuState through the AI menu."""
        return self.ai_menu.menu

    # --- Hooks ----------------------------------------------------------

    def _value_label(self, i: int) -> str:
        m = self.menu
        match i:
            case 1:  # Loops
                return str(m.tournament_loops)
            case 2:  # Generations
                return str(m.tournament_generations)
            case 3:  # Episodes
                return str(m.tournament_episodes)
            case 4:  # Population
                return str(m.tournament_population)
            case 5:  # Sigma
                return f"{m.tournament_sigma:.3f}"
            case _:
                return ""

    def _is_disabled(self, i: int) -> bool:
        match i:
            case 0:  # Header
                return True
            case 6:  # Statistics — needs at least one recorded loop
                try:
                    with open(TOURNAMENT_LOOPS_PATH) as f:
                        import json

                        entries = json.load(f)
                except (OSError, ValueError):
                    return True
                return not isinstance(entries, list) or not entries
            case 7:  # Restore checkpoint — needs the pre-tournament file
                return not os.path.exists(PRE_TOURNAMENT_PATH)
            case 8:  # Start — needs a trained checkpoint
                return not os.path.exists(MODEL_PATH)
            case _:
                return False

    def _toggle(self, direction: int) -> None:
        m = self.menu
        match self.selection:
            case 1:  # Loops
                m.tournament_loops = max(1, min(20, m.tournament_loops + direction))
            case 2:  # Generations
                m.tournament_generations = max(1, min(20, m.tournament_generations + direction))
            case 3:  # Episodes
                m.tournament_episodes = max(1, min(5, m.tournament_episodes + direction))
            case 4:  # Population (even counts: half survive)
                m.tournament_population = max(2, min(12, m.tournament_population + direction * 2))
            case 5:  # Sigma (float — round to kill FP drift)
                m.tournament_sigma = round(
                    max(0.005, min(0.10, m.tournament_sigma + direction * 0.005)),
                    3,
                )

    def _save(self) -> None:
        self.menu.save_settings()

    def _on_navigate(self) -> None:
        self._confirm_restore = False

    def _on_back(self) -> State | None:
        return self.ai_menu

    def _on_select(self) -> State | None:
        match self.selection:
            case 6:  # Statistics
                from tetris.states.tournament_stats import TournamentStatsState

                return TournamentStatsState(self.screen, self.font, self.audio, self)
            case 7:  # Restore checkpoint (two-press confirm)
                if not self._confirm_restore:
                    self._confirm_restore = True
                else:
                    shutil.copyfile(PRE_TOURNAMENT_PATH, MODEL_PATH)
                    self._confirm_restore = False
            case 8:  # Start
                from tetris.states.tournament import TournamentState

                return TournamentState(self.screen, self.font, self.audio, self)
            case 9:  # Back
                return self.ai_menu
        return None

    def _option_text(self, i: int, is_sel: bool) -> str:
        if i == 7 and self._confirm_restore:
            prefix = "> " if is_sel else "  "
            return f"{prefix}{tr('Press again to restore')} (Enter)"
        return super()._option_text(i, is_sel)

    def _option_color(self, i: int, is_sel: bool, disabled: bool) -> tuple[int, int, int]:
        if i == 7 and self._confirm_restore:
            return RED
        return super()._option_color(i, is_sel, disabled)

    # --- Custom table draw ------------------------------------------------

    def draw(self, screen: pygame.Surface, *, particles=None) -> None:
        """Render tournament params as a multi-column explanation table.

        Draw order: black fill → background animation → particles →
        title → table → instructions. Overrides :meth:`MenuBase.draw`
        to use the multi-column pixel layout (same shape as
        :class:`HyperparamMenuState`).

        Columns: Param | Current | Min | Max | Step | Explanation
        """
        screen.fill(BLACK)
        self.bg_anim.draw(screen)
        if particles is not None:
            particles.draw(screen)
        title = get_large_font().render(tr(self._title), True, WHITE)
        screen.blit(title, (SCREEN_WIDTH // 2 - title.get_width() // 2, TITLE_Y))

        # --- Column layout ---
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

        # --- Header row ---
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
            disabled = self._is_disabled(i)

            if i in self._header_indices:
                # Category header: white, no table columns
                surf = self.font.render(tr(option), True, WHITE)
                screen.blit(surf, (x_left, y))
                y += lh
                continue

            color = self._option_color(i, is_sel, disabled)

            # Param name (left-aligned, prefixed with cursor)
            prefix = "> " if is_sel else "  "
            surf = self.font.render(f"{prefix}{tr(option)}", True, color)
            screen.blit(surf, (x_left, y))

            # Numeric columns: Current, Min, Max, Step
            meta = self._PARAM_META[i]
            current = self._value_label(i)
            values = [current, meta[0], meta[1], meta[2]]
            for c, val in enumerate(values):
                if val:
                    surf = self.font.render(val, True, color)
                    screen.blit(surf, (x_num[c] + num_w - surf.get_width(), y))

            # Explanation (left-aligned, truncated to fit)
            if meta[3]:
                text = tr(meta[3])
                surf = self.font.render(text, True, color)
                if surf.get_width() > expl_w:
                    while surf.get_width() > expl_w - 10 and len(text) > 5:
                        text = text[:-1]
                        surf = self.font.render(text + "…", True, color)
                screen.blit(surf, (x_expl, y))

            y += lh

        # --- Instructions ---
        instr = self.font.render(tr(self._instructions), True, GRAY)
        screen.blit(instr, (SCREEN_WIDTH // 2 - instr.get_width() // 2, INSTRUCTIONS_Y))
