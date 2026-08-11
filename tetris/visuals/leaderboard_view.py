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
    # pad gives breathing room between adjacent columns.
    margin = 150
    pad = 15
    columns = [
        ("#", 60, "right"),
        ("Name", 240, "left"),
        ("Score", 130, "right"),
        ("Lvl", 60, "right"),
        ("Lines", 80, "right"),
        ("Générateur", 170, "left"),
        ("Mode", 130, "left"),
        ("Date", 330, "left"),
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
            px = cx + pad if align == "left" else cx + w - pad - surf.get_width()
            screen.blit(surf, (px, y))
    instr = font.render("Press any key to continue", True, GRAY)
    screen.blit(instr, (SCREEN_WIDTH // 2 - instr.get_width() // 2, INSTRUCTIONS_Y))