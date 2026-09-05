"""Tournament runner state: background-thread evolutionary loop.

Launched from :class:`TournamentMenuState` "Start". Runs
``run_tournament_loops`` in a daemon thread (matching the
``mcp_server.py`` precedent) while the FSM polls a plain progress
dict at 60 FPS. Esc sets a stop flag checked between generations —
a coarse cancel: the running generation finishes first so the report
write is never corrupted.

The live HUD draws counters (loops, generations, population, episode),
the current best/mean fitness, a global progress bar, and a sparkline
of per-generation bests over an animated menu background; each finished
loop fires a particle burst.
"""

from __future__ import annotations

import threading

import pygame

from tetris.i18n import tr
from tetris.logger import get_logger
from tetris.settings import (
    BLACK,
    GRAY,
    GREEN,
    ORANGE,
    SCREEN_WIDTH,
    WHITE,
)
from tetris.states.base import State
from tetris.tournament import run_tournament_loops
from tetris.visuals.fonts import (
    CONTENT_Y,
    INSTRUCTIONS_Y,
    LINE_HEIGHT_SMALL,
    TITLE_Y,
    get_large_font,
)
from tetris.visuals.menu_animation import MenuBackgroundAnimation

logger = get_logger(__name__)

_LEFT_X = 60
_RIGHT_X = 560
_BAR_Y = 430
_BAR_H = 24
_SPARK_RECT = pygame.Rect(760, 140, 680, 220)


class TournamentState(State):
    """Run tournament loops in a background thread; draw live progress."""

    def __init__(self, screen, font, audio, tournament_menu) -> None:
        self.screen, self.font, self.audio = screen, font, audio
        self.tournament_menu = tournament_menu
        menu = tournament_menu.menu
        self._loops = menu.tournament_loops
        self._generations = menu.tournament_generations
        self._population = menu.tournament_population
        self._episodes = menu.tournament_episodes
        self._progress: dict = {"loop": -1, "gen": -1, "done": 0}
        self._should_stop = False
        self._result: dict | None = None
        self._error = False
        self._last_done = 0
        self._bg = MenuBackgroundAnimation()
        self._thread = threading.Thread(target=self._worker, daemon=True)
        self._thread.start()

    # --- Worker thread ----------------------------------------------------

    def _worker(self) -> None:
        menu = self.tournament_menu.menu
        try:
            self._result = run_tournament_loops(
                loops=self._loops,
                generations=self._generations,
                episodes=self._episodes,
                population=self._population,
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
        """Drive the background animation, celebrate finished loops, poll the worker."""
        self._bg.update(dt / 1000.0, particles)
        done = self._progress.get("done", 0)
        if done > self._last_done and particles is not None:
            self._celebrate(particles)
            self._last_done = done
        if self._result is not None or self._error:
            self._thread.join(timeout=5)
            return self.tournament_menu
        return None

    def _celebrate(self, particles) -> None:
        """Particle burst across the top of the screen when a loop finishes."""
        for x in (SCREEN_WIDTH // 4, SCREEN_WIDTH // 2, 3 * SCREEN_WIDTH // 4):
            particles.emit(x, 120, GREEN, count=30)
            particles.emit(x, 160, ORANGE, count=20)

    # --- HUD helpers --------------------------------------------------------

    def _progress_fraction(self) -> float:
        """Global completion in [0, 1]: finished loops plus in-loop generation share."""
        done = self._progress.get("done", 0)
        gen = self._progress.get("gen", -1)
        in_loop = min(max(gen + 1, 0), self._generations) / self._generations
        return min((done + in_loop) / self._loops, 1.0)

    def _draw_progress_bar(self, screen: pygame.Surface) -> None:
        """Horizontal completion bar with percentage label, thermometer pattern."""
        frac = self._progress_fraction()
        outline = pygame.Rect(_LEFT_X, _BAR_Y, SCREEN_WIDTH - 2 * _LEFT_X, _BAR_H)
        pygame.draw.rect(screen, WHITE, outline, 2)
        if frac > 0:
            fill = outline.inflate(-4, -4)
            fill.width = int(fill.width * frac)
            pygame.draw.rect(screen, GREEN, fill)
        pct = f"{tr('Global progress')} {frac:.0%}"
        surf = self.font.render(pct, True, WHITE)
        screen.blit(surf, (SCREEN_WIDTH // 2 - surf.get_width() // 2, _BAR_Y + _BAR_H + 6))

    def _draw_sparkline(self, screen: pygame.Surface) -> None:
        """Per-generation best scores as a line chart in a labelled box."""
        pygame.draw.rect(screen, GRAY, _SPARK_RECT, 1)
        label = self.font.render(tr("Best per generation"), True, GRAY)
        screen.blit(label, (_SPARK_RECT.x + 8, _SPARK_RECT.y + 6))

        history: list[float] = self._progress.get("history") or []
        if len(history) < 2:
            return
        lo, hi = min(history), max(history)
        span = (hi - lo) or 1.0
        # ponytail: label is 27px tall (small font) — reserve its band so the
        # line never crosses "Best per generation" when the max occurs early.
        inner = _SPARK_RECT.inflate(-24, 0).move(0, 36)
        inner.height -= 48
        pts = [
            (
                inner.x + int(inner.width * i / (len(history) - 1)),
                inner.y + inner.height - int(inner.height * (v - lo) / span),
            )
            for i, v in enumerate(history)
        ]
        pygame.draw.lines(screen, WHITE, False, pts, 2)
        pygame.draw.circle(screen, ORANGE, pts[-1], 4)  # latest best

    def draw(self, screen: pygame.Surface, *, particles=None) -> None:
        screen.fill(BLACK)
        self._bg.draw(screen)
        if particles is not None:
            particles.draw(screen)

        title = get_large_font().render(tr("Tournament"), True, WHITE)
        screen.blit(title, (SCREEN_WIDTH // 2 - title.get_width() // 2, TITLE_Y))

        p = self._progress
        lh = LINE_HEIGHT_SMALL

        # --- Left column: counters ---
        y = CONTENT_Y
        done = p.get("done", 0)
        if self._should_stop:
            line = tr("Cancelled")
        else:
            line = f"{tr('Loops')} {min(done + 1, self._loops)}/{self._loops}"
        screen.blit(self.font.render(line, True, WHITE), (_LEFT_X, y))
        y += lh

        gen = p.get("gen", -1)
        if gen >= 0:
            line = f"{tr('Generations')} {min(gen + 1, self._generations)}/{self._generations}"
            screen.blit(self.font.render(line, True, GRAY), (_LEFT_X, y))
        y += lh

        member = p.get("member", -1)
        if member >= 0:
            line = f"{tr('Population')} {member + 1}/{self._population}"
            screen.blit(self.font.render(line, True, GRAY), (_LEFT_X, y))
        y += lh

        episode = p.get("episode", -1)
        if episode >= 0:
            line = f"{tr('Episode')} {episode + 1}/{self._episodes}"
            screen.blit(self.font.render(line, True, GRAY), (_LEFT_X, y))
        y += lh

        if self._should_stop:
            screen.blit(self.font.render(tr("Finishing current generation…"), True, GRAY), (_LEFT_X, y))

        # --- Right column: fitness ---
        if p.get("best") is not None:
            screen.blit(
                self.font.render(f"{tr('Best')} {p['best']:.0f}", True, GREEN),
                (_RIGHT_X, CONTENT_Y),
            )
        if p.get("mean") is not None:
            screen.blit(
                self.font.render(f"{tr('Mean')} {p['mean']:.0f}", True, GRAY),
                (_RIGHT_X, CONTENT_Y + lh),
            )

        self._draw_sparkline(screen)
        self._draw_progress_bar(screen)

        instr = self.font.render(tr("Esc: Cancel"), True, GRAY)
        screen.blit(instr, (SCREEN_WIDTH // 2 - instr.get_width() // 2, INSTRUCTIONS_Y))
