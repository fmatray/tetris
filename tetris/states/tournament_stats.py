"""Tournament statistics page: loop stats table + best-score graph.

Reads ``data/tournament/loops.json`` (list of per-loop entries) and
mirrors the :class:`AIStatsState` layout: stats table on the left,
best-score-per-loop graph on the right. Missing or empty file shows
placeholders — a brand-new install has no loops yet.
"""

from __future__ import annotations

import json

import pygame

from tetris.i18n import get_language, tr
from tetris.settings import BLACK, GRAY, SCREEN_WIDTH, TOURNAMENT_LOOPS_PATH, WHITE
from tetris.states.base import State
from tetris.visuals.fonts import (
    INSTRUCTIONS_Y,
    LINE_HEIGHT_SMALL,
    TITLE_Y,
    get_large_font,
)
from tetris.visuals.graph_view import render_score_graph

# (label, key) pairs in display order; keys index loops.json entries.
_STAT_KEYS: tuple[tuple[str, str], ...] = (
    ("Loops run", "loop"),
    ("All-time best score", "best"),
    ("Last round best", "best"),
    ("Last round mean", "mean"),
    ("Last round seed", "seed"),
    ("Next seed", "seed"),
)


class TournamentStatsState(State):
    """Tournament statistics: stats table on the left, graph on the right.

    The graph surface is built lazily on first ``draw`` and cached for
    subsequent frames. Any keypress returns to the tournament menu.
    """

    def __init__(self, screen, font, audio, tournament_menu) -> None:
        self.screen, self.font, self.audio = screen, font, audio
        self.tournament_menu = tournament_menu
        self._surface: pygame.Surface | None = None
        self._built_lang: str | None = None
        self._entries: list[dict] = []

    # --- Data -------------------------------------------------------------

    def _load_entries(self) -> list[dict]:
        """Read loops.json; missing/invalid file means no loops yet."""
        try:
            with open(TOURNAMENT_LOOPS_PATH) as f:
                entries = json.load(f)
        except (OSError, ValueError):
            entries = []
        if not isinstance(entries, list):
            entries = []
        self._entries = entries
        return entries

    def _stat_values(self) -> list[str]:
        entries = self._entries
        if not entries:
            return ["—"] * len(_STAT_KEYS)
        best_all = max(float(e["best"]) for e in entries)
        last = entries[-1]
        next_seed = int(last["seed"]) + 1
        return [
            str(len(entries)),
            f"{best_all:.0f}",
            f"{float(last['best']):.0f}",
            f"{float(last['mean']):.0f}",
            str(last["seed"]),
            str(next_seed),
        ]

    # --- Rendering ------------------------------------------------------

    def _build_surface(self) -> None:
        self._entries = self._load_entries()
        if self._entries:
            self._surface = render_score_graph(
                [e["loop"] for e in self._entries],
                [e["best"] for e in self._entries],
            )
        else:
            self._surface = None
        self._built_lang = get_language()

    def handle_event(self, event: pygame.event.Event) -> State | None:
        if event.type == pygame.KEYDOWN:
            return self.tournament_menu
        return None

    def update(self, dt: float, particles) -> State | None:
        return None

    def draw(self, screen: pygame.Surface, *, particles=None) -> None:
        if self._built_lang != get_language():
            self._build_surface()

        screen.fill(BLACK)

        # --- Stats on the left ---
        x = 60
        y = TITLE_Y

        header = get_large_font().render(tr("Statistics"), True, WHITE)
        screen.blit(header, (x, y))
        y += LINE_HEIGHT_SMALL + 10

        values = self._stat_values()
        for (label, _key), value in zip(_STAT_KEYS, values):
            line = f"{tr(label)}: {value}"
            surf = self.font.render(line, True, GRAY)
            screen.blit(surf, (x, y))
            y += LINE_HEIGHT_SMALL

        # --- Graph on the right ---
        if self._surface is not None:
            surf = self._surface
            gx = SCREEN_WIDTH - surf.get_width() - 30
            gy = TITLE_Y
            screen.blit(surf, (gx, gy))

        instr = self.font.render(tr("Press any key to go back"), True, GRAY)
        screen.blit(instr, (SCREEN_WIDTH // 2 - instr.get_width() // 2, INSTRUCTIONS_Y))
