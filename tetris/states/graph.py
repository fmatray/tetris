"""Graph state: display the score-over-episode learning curve.

A new ``pygame.Surface`` is rendered once on entry (matplotlib Agg
backend), then blitted each frame. Any key returns to the AI sub-menu.
The parent ``AIMenuState`` is passed so the graph can be regenerated
after training. Holding the surface in the state avoids re-rendering
every frame (matplotlib draws are slow).
"""

from __future__ import annotations

from typing import Optional

import pygame

from tetris.ai.trainer import TrainingLog
from tetris.settings import BLACK, GRAY, SCREEN_HEIGHT, SCREEN_WIDTH
from tetris.states.base import State
from tetris.visuals.graph_view import render_score_graph

LOG_PATH = "ai_training_log.json"


class GraphState(State):
    """Shows the episode-vs-score graph. Any key returns to the AI menu."""

    def __init__(self, screen, font, audio, menu) -> None:
        self.screen, self.font, self.audio = screen, font, audio
        self.menu = menu
        self._surface: Optional[pygame.Surface] = None
        self._episode_count = 0

    # --- Input ----------------------------------------------------------

    def handle_event(self, event: pygame.event.Event) -> Optional[State]:
        if event.type == pygame.KEYDOWN:
            return self.menu
        return None

    # --- Rendering ------------------------------------------------------

    def _build_surface(self) -> None:
        """Render the graph once from the training log."""
        log = TrainingLog(LOG_PATH)
        episodes = [e["episode"] for e in log.episodes]
        scores = [e["score"] for e in log.episodes]
        self._episode_count = len(episodes)
        self._surface = render_score_graph(episodes, scores)

    def draw(self, screen: pygame.Surface) -> None:
        if self._surface is None:
            self._build_surface()
        screen.fill(BLACK)

        surf = self._surface
        x = (SCREEN_WIDTH - surf.get_width()) // 2
        y = 20
        screen.blit(surf, (x, y))

        msg = f"{self._episode_count} épisode(s) — Appuyez sur une touche pour revenir"
        instr = self.font.render(msg, True, GRAY)
        screen.blit(
            instr,
            (SCREEN_WIDTH // 2 - instr.get_width() // 2, SCREEN_HEIGHT - 50),
        )