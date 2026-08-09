"""Human statistics state: aggregate stats from recorded human games.

Reads ``human_stats.json`` (every human game, unbounded) and aggregates
total / best / average for tetrominos, lines, scores, and levels.
Any key returns to the human menu.
"""

from __future__ import annotations

from typing import Optional

import pygame

from tetris.settings import BLACK, GRAY, SCREEN_HEIGHT, SCREEN_WIDTH, WHITE
from tetris.states.base import State
from tetris.storage import load_human_games

# Metrics: (label, key_in_record) — each shown as Total / Best / Average.
_METRICS = [
    ("Tetrominos", "tetrominos"),
    ("Lignes", "lines"),
    ("Score", "score"),
    ("Niveau", "level"),
]


class HumanStatsState(State):
    """Human player statistics page, aggregated from human_stats.json.

    Layout: summary table (total / best / average per metric) on the left,
    recent games on the right. Any keypress returns to the human menu.
    """

    def __init__(self, screen, font, audio, human_menu) -> None:
        self.screen, self.font, self.audio = screen, font, audio
        self.human_menu = human_menu
        self._games: list[dict] = []

    def _load(self) -> None:
        self._games = load_human_games()

    def _aggregate(self) -> list[tuple[str, int, int, float]]:
        """Return (label, total, best, average) per metric."""
        if not self._games:
            return [(label, 0, 0, 0.0) for label, _ in _METRICS]
        result = []
        for label, key in _METRICS:
            values = [g.get(key, 0) for g in self._games]
            total = sum(values)
            best = max(values)
            avg = total / len(values)
            result.append((label, total, best, avg))
        return result

    # --- Rendering ------------------------------------------------------

    def draw(self, screen: pygame.Surface) -> None:
        self._load()
        screen.fill(BLACK)

        # --- Title ---
        title = self.font.render("Statistiques Humain", True, WHITE)
        screen.blit(title, (SCREEN_WIDTH // 2 - title.get_width() // 2, 40))

        if not self._games:
            empty = self.font.render(
                "Aucune partie enregistrée", True, GRAY
            )
            screen.blit(empty, (SCREEN_WIDTH // 2 - empty.get_width() // 2, 300))
            self._draw_instructions(screen)
            return

        # --- Summary table (left) ---
        # Column x-positions (pixels)
        col_label = 60
        col_total = 260
        col_best = 370
        col_avg = 500
        y = 110

        # Header
        for text, cx in [("Total", col_total), ("Meilleur", col_best),
                         ("Moyenne", col_avg)]:
            h = self.font.render(text, True, GRAY)
            screen.blit(h, (cx, y))
        y += 35

        for label, total, best, avg in self._aggregate():
            lbl = self.font.render(label, True, WHITE)
            screen.blit(lbl, (col_label, y))
            t = self.font.render(str(total), True, GRAY)
            screen.blit(t, (col_total, y))
            b = self.font.render(str(best), True, GRAY)
            screen.blit(b, (col_best, y))
            a = self.font.render(f"{avg:.1f}", True, GRAY)
            screen.blit(a, (col_avg, y))
            y += 32

        y += 10
        games_played = self.font.render(
            f"Parties jouées : {len(self._games)}", True, WHITE
        )
        screen.blit(games_played, (col_label, y))

        # --- Recent games (right) ---
        # Fixed pixel columns — no format-string alignment, no overflow.
        rx = SCREEN_WIDTH - 600
        ry = 110
        recent_header = self.font.render("Dernières parties", True, WHITE)
        screen.blit(recent_header, (rx, ry))
        ry += 35

        # Column positions relative to rx
        cols = [
            ("#", 0),
            ("Score", 30),
            ("Niv", 130),
            ("Lign", 180),
            ("Tetr", 240),
            ("Date", 310),
        ]
        for text, dx in cols:
            h = self.font.render(text, True, GRAY)
            screen.blit(h, (rx + dx, ry))
        ry += 28

        for i, g in enumerate(self._games[-5:], 1):
            vals = [
                (str(i), 0),
                (str(g.get("score", 0)), 30),
                (str(g.get("level", 0)), 130),
                (str(g.get("lines", 0)), 180),
                (str(g.get("tetrominos", 0)), 240),
                (g.get("date", ""), 310),
            ]
            for text, dx in vals:
                surf = self.font.render(text, True, WHITE)
                screen.blit(surf, (rx + dx, ry))
            ry += 26

    def _draw_instructions(self, screen: pygame.Surface) -> None:
        instr = self.font.render(
            "Appuyez sur une touche pour revenir", True, GRAY
        )
        screen.blit(
            instr,
            (SCREEN_WIDTH // 2 - instr.get_width() // 2, SCREEN_HEIGHT - 50),
        )

    # --- Input ----------------------------------------------------------

    def handle_event(self, event: pygame.event.Event) -> Optional[State]:
        if event.type == pygame.KEYDOWN:
            return self.human_menu
        return None
