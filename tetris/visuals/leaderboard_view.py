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
    header = font.render(
        "#  Name       Score   Lvl  Lines  Générateur  Mode     Date", True, GRAY
    )
    screen.blit(header, (SCREEN_WIDTH // 2 - header.get_width() // 2, CONTENT_Y))
    for i, entry in enumerate(scores[:10], 1):
        gen = {"7bag": "7-bag", "35bag": "35-bag"}.get(entry.get("generator", ""), "Aléatoire")
        mode = entry.get("mode", "-") or "-"
        row_str = (
            f"{i:<2} {entry['name']:<10} {entry['score']:<7} "
            f"{entry['level']:<4} {entry['lines']:<6} {gen:<11} {mode:<8} {entry['date']}"
        )
        row = font.render(row_str, True, WHITE)
        screen.blit(row, (SCREEN_WIDTH // 2 - row.get_width() // 2,
                          CONTENT_Y + LINE_HEIGHT_SMALL + i * LINE_HEIGHT_SMALL))
    instr = font.render("Press any key to continue", True, GRAY)
    screen.blit(instr, (SCREEN_WIDTH // 2 - instr.get_width() // 2, INSTRUCTIONS_Y))