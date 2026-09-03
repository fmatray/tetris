"""Tournament runner state: background-thread evolutionary loop.

Launched from :class:`TournamentMenuState` "Start". Runs
``run_tournament_loops`` in a daemon thread (matching the
``mcp_server.py`` precedent) while the FSM polls a plain progress
dict at 60 FPS. Esc sets a stop flag checked between generations —
a coarse cancel: the running generation finishes first so the report
write is never corrupted.
"""

from __future__ import annotations

import threading

import pygame

from tetris.i18n import tr
from tetris.logger import get_logger
from tetris.settings import BLACK, GRAY, SCREEN_WIDTH, WHITE
from tetris.states.base import State
from tetris.tournament import run_tournament_loops
from tetris.visuals.fonts import (
    CONTENT_Y,
    INSTRUCTIONS_Y,
    LINE_HEIGHT_SMALL,
    TITLE_Y,
    get_large_font,
)

logger = get_logger(__name__)


class TournamentState(State):
    """Run tournament loops in a background thread; draw live progress."""

    def __init__(self, screen, font, audio, tournament_menu) -> None:
        self.screen, self.font, self.audio = screen, font, audio
        self.tournament_menu = tournament_menu
        menu = tournament_menu.menu
        self._loops = menu.tournament_loops
        self._generations = menu.tournament_generations
        self._progress: dict = {"loop": -1, "gen": -1, "done": 0}
        self._should_stop = False
        self._result: dict | None = None
        self._error = False
        self._thread = threading.Thread(target=self._worker, daemon=True)
        self._thread.start()

    # --- Worker thread ----------------------------------------------------

    def _worker(self) -> None:
        menu = self.tournament_menu.menu
        try:
            self._result = run_tournament_loops(
                loops=self._loops,
                generations=self._generations,
                episodes=menu.tournament_episodes,
                population=menu.tournament_population,
                sigma=menu.tournament_sigma,
                seed=menu.tournament_seed,
                progress=self._progress,
                should_stop=lambda: self._should_stop,
            )
            menu.tournament_seed = self._result["next_seed"]
            menu.save_settings()
        except Exception:
            logger.exception("tournament run failed")
            self._error = True

    # --- FSM interface ----------------------------------------------------

    def handle_event(self, event: pygame.event.Event) -> State | None:
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self._should_stop = True  # coarse cancel: current generation finishes
        return None

    def update(self, dt: float, particles) -> State | None:
        """Poll the worker; transition back to the menu when it exits."""
        if self._result is not None or self._error:
            self._thread.join(timeout=5)
            return self.tournament_menu
        return None

    def draw(self, screen: pygame.Surface, *, particles=None) -> None:
        screen.fill(BLACK)

        title = get_large_font().render(tr("Tournament"), True, WHITE)
        screen.blit(title, (SCREEN_WIDTH // 2 - title.get_width() // 2, TITLE_Y))

        y = CONTENT_Y
        lh = LINE_HEIGHT_SMALL
        x = 60

        done = self._progress.get("done", 0)
        if self._should_stop:
            line = tr("Cancelled")
        else:
            line = f"{tr('Loops')} {min(done + 1, self._loops)}/{self._loops}"
        screen.blit(self.font.render(line, True, WHITE), (x, y))
        y += lh

        gen = self._progress.get("gen", -1)
        if gen >= 0:
            line = f"{tr('Generations')} {min(gen + 1, self._generations)}/{self._generations}"
            screen.blit(self.font.render(line, True, GRAY), (x, y))
        y += lh

        if self._should_stop:
            screen.blit(self.font.render(tr("Finishing current generation…"), True, GRAY), (x, y))

        instr = self.font.render(tr("Esc: Cancel"), True, GRAY)
        screen.blit(instr, (SCREEN_WIDTH // 2 - instr.get_width() // 2, INSTRUCTIONS_Y))
