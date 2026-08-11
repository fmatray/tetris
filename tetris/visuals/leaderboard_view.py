"""Shared, stateless leaderboard rendering (DRY).

Both ``LeaderboardState`` and the ``GameOverState`` leaderboard step
rendered identical tables. This module centralizes that logic.
"""

import pygame

from tetris.settings import BLACK, GRAY, SCREEN_WIDTH, WHITE
from tetris.storage import load_leaderboard
from tetris.visuals.fonts import (
    CONTENT_Y,
    INSTRUCTIONS_Y,
    LINE_HEIGHT_SMALL,
    TITLE_Y,
    get_large_font,
)


def draw_leaderboard(screen: pygame.Surface, font: pygame.font.Font) -> None:
    """Render the top-10 leaderboard table onto *screen*."""
    screen.fill(BLACK)
    scores = load_leaderboard()
    title = get_large_font().render("TOP 10 LEADERBOARD", True, WHITE)
    screen.blit(title, (SCREEN_WIDTH // 2 - title.get_width() // 2, TITLE_Y))
    # Explicit pixel columns — proportional Arial breaks f-string padding.
    columns = [
        ("#", 40, "right"),
        ("Name", 180, "left"),
        ("Score", 100, "right"),
        ("Lvl", 50, "right"),
        ("Lines", 60, "right"),
        ("Générateur", 110, "left"),
        ("Mode", 90, "left"),
        ("Date", 190, "left"),
    ]
    total_width = sum(w for _, w, _ in columns)
    x0 = SCREEN_WIDTH // 2 - total_width // 2
    # Compute absolute x for each column (start of cell).
    xs = []
    x = x0
    for _, w, _ in columns:
        xs.append(x)
        x += w
    # Header row.
    for (label, w, align), cx in zip(columns, xs):
        surf = font.render(label, True, GRAY)
        px = cx if align == "left" else cx + w - surf.get_width()
        screen.blit(surf, (px, CONTENT_Y))
    # Data rows.
    for i, entry in enumerate(scores[:10], 1):
        y = CONTENT_Y + LINE_HEIGHT_SMALL + i * LINE_HEIGHT_SMALL
        gen = {"7bag": "7-bag", "35bag": "35-bag"}.get(entry.get("generator", ""), "Aléatoire")
        mode = entry.get("mode", "-") or "-"
        values = [
            str(i),
            entry["name"],
            str(entry["score"]),
            str(entry["level"]),
            str(entry["lines"]),
            gen,
            mode,
            entry.get("date", "Unknown"),
        ]
        for val, (label, w, align), cx in zip(values, columns, xs):
            surf = font.render(val, True, WHITE)
            px = cx if align == "left" else cx + w - surf.get_width()
            screen.blit(surf, (px, y))
    instr = font.render("Press any key to continue", True, GRAY)
    screen.blit(instr, (SCREEN_WIDTH // 2 - instr.get_width() // 2, INSTRUCTIONS_Y))