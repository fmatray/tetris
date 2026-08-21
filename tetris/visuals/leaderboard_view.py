"""Shared, stateless leaderboard rendering (DRY).

Both ``LeaderboardState`` and the ``GameOverState`` leaderboard step
rendered identical tables. This module centralizes that logic.
"""

import pygame
from typing import NamedTuple
from tetris.settings import BLACK, GENERATOR_LABELS, GRAY, RED, SCREEN_WIDTH, SPEED_MODE_LABELS, WHITE
from tetris.storage import load_leaderboard
from tetris.visuals.fonts import (
    CONTENT_Y,
    INSTRUCTIONS_Y,
    LINE_HEIGHT_SMALL,
    TITLE_Y,
    get_large_font,
)


class ColumnDef(NamedTuple):
    """A leaderboard table column: header label, pixel width, text alignment."""

    label: str
    width: int
    align: str


def draw_leaderboard(
    screen: pygame.Surface, font: pygame.font.Font, scores: list[dict] | None = None, highlight_index: int | None = None
) -> None:
    """Render the top-10 leaderboard table onto *screen*.

    When *highlight_index* is set, that row (0-based) is rendered in red.
    """
    screen.fill(BLACK)
    if scores is None:
        scores = load_leaderboard()
    title = get_large_font().render("TOP 10 LEADERBOARD", True, WHITE)
    screen.blit(title, (SCREEN_WIDTH // 2 - title.get_width() // 2, TITLE_Y))
    # Explicit pixel columns — proportional Arial breaks f-string padding.
    # pad gives breathing room between adjacent columns.
    margin = 150
    pad = 15
    columns = [
        ColumnDef("#", 60, "right"),
        ColumnDef("Name", 240, "left"),
        ColumnDef("Score", 130, "right"),
        ColumnDef("Lvl", 60, "right"),
        ColumnDef("Lines", 80, "right"),
        ColumnDef("Générateur", 170, "left"),
        ColumnDef("Mode", 130, "left"),
        ColumnDef("Vitesse", 130, "left"),
        ColumnDef("Date", 200, "left"),
    ]
    x0 = margin
    # Compute absolute x for each column (start of cell).
    xs = []
    x = x0
    for _, w, _ in columns:
        xs.append(x)
        x += w
    # Header row.
    for (label, w, align), cx in zip(columns, xs):
        surf = font.render(label, True, GRAY)
        px = cx + pad if align == "left" else cx + w - pad - surf.get_width()
        screen.blit(surf, (px, CONTENT_Y))
    # Data rows.
    for i, entry in enumerate(scores[:10], 1):
        y = CONTENT_Y + LINE_HEIGHT_SMALL + i * LINE_HEIGHT_SMALL
        gen = GENERATOR_LABELS.get(entry.get("generator", ""), "Aléatoire")
        mode = entry.get("mode", "-") or "-"
        values = [
            str(i),
            entry["name"],
            str(entry["score"]),
            str(entry["level"]),
            str(entry["lines"]),
            gen,
            mode,
            SPEED_MODE_LABELS.get(entry.get("speed_mode", ""), "-"),
            entry.get("date", "Unknown"),
        ]
        for val, (label, w, align), cx in zip(values, columns, xs):
            color = RED if highlight_index == i - 1 else WHITE
            surf = font.render(val, True, color)
            px = cx + pad if align == "left" else cx + w - pad - surf.get_width()
            screen.blit(surf, (px, y))
    instr = font.render("Press any key to continue", True, GRAY)
    screen.blit(instr, (SCREEN_WIDTH // 2 - instr.get_width() // 2, INSTRUCTIONS_Y))
