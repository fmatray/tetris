"""AI statistics state: training stats table + score-over-episode graph.

Consolidates the old inline stats block and separate graph entry into a
single page. The graph surface is rendered once (matplotlib Agg backend,
slow) and cached. Any key returns to the AI menu.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tetris.visuals.particles import ParticleSystem

import pygame

from tetris.ai.trainer import TrainingLog
from tetris.settings import BLACK, GRAY, LOG_PATH, SCREEN_WIDTH, WHITE
from tetris.states.base import State
from tetris.visuals.fonts import (
    INSTRUCTIONS_Y,
    LINE_HEIGHT_SMALL,
    TITLE_Y,
    get_large_font,
)
from tetris.visuals.graph_view import render_score_graph

_STAT_LABELS = [
    "Épisodes",
    "Score moyen",
    "Meilleur score",
    "Moyenne (100 derniers)",
    "Niveau moyen",
    "Meilleur niveau",
    "Lignes totales",
    "Pièces totales",
]


class AIStatsState(State):
    """AI statistics page: stats table on the left, graph on the right.

    The graph surface is built lazily on first ``draw`` and cached for
    subsequent frames. Any keypress returns to the AI menu.
    """

    def __init__(self, screen, font, audio, ai_menu) -> None:
        self.screen, self.font, self.audio = screen, font, audio
        self.ai_menu = ai_menu
        self._surface: pygame.Surface | None = None
        self._episode_count = 0
        self._stats = TrainingLog(LOG_PATH)

    # --- Rendering ------------------------------------------------------

    def _stat_values(self) -> list[str]:
        s = self._stats
        return [
            str(s.total_episodes),
            f"{s.avg_score:.0f}",
            str(s.best_score),
            f"{s.last_100_avg:.0f}",
            f"{s.avg_level:.1f}",
            str(s.best_level),
            str(s.total_lines),
            str(s.total_steps),
        ]

    def _build_surface(self) -> None:
        """Render the graph once from the training log."""
        episodes = [e["episode"] for e in self._stats.episodes]
        scores = [e["score"] for e in self._stats.episodes]
        self._episode_count = len(episodes)
        self._surface = render_score_graph(episodes, scores)

    def draw(self, screen: pygame.Surface, *, particles: ParticleSystem | None = None) -> None:
        if self._surface is None:
            self._build_surface()

        screen.fill(BLACK)

        # --- Stats on the left ---
        x = 60
        y = TITLE_Y

        header = get_large_font().render("Statistiques", True, WHITE)
        screen.blit(header, (x, y))
        y += LINE_HEIGHT_SMALL + 10

        values = self._stat_values()
        for label, value in zip(_STAT_LABELS, values):
            line = f"{label} : {value}"
            surf = self.font.render(line, True, GRAY)
            screen.blit(surf, (x, y))
            y += LINE_HEIGHT_SMALL

        # --- Graph on the right ---
        if self._surface is not None:
            surf = self._surface
            gx = SCREEN_WIDTH - surf.get_width() - 30
            gy = TITLE_Y
            screen.blit(surf, (gx, gy))

        # --- Navigation instructions ---
        instr = self.font.render(
            f"{self._episode_count} épisode(s) — Appuyez sur une touche pour revenir",
            True,
            GRAY,
        )
        screen.blit(
            instr,
            (SCREEN_WIDTH // 2 - instr.get_width() // 2, INSTRUCTIONS_Y),
        )

    # --- Input ----------------------------------------------------------

    def handle_event(self, event: pygame.event.Event) -> State | None:
        if event.type == pygame.KEYDOWN:
            return self.ai_menu
        return None
