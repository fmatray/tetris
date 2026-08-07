"""Shared, stateless leaderboard rendering (DRY).

Both ``LeaderboardState`` and the ``GameOverState`` leaderboard step
rendered identical tables. This module centralizes that logic.
"""

import pygame

from tetris.settings import BLACK, GRAY, SCREEN_WIDTH, WHITE
from tetris.storage import load_leaderboard


def draw_leaderboard(screen: pygame.Surface, font: pygame.font.Font) -> None:
    """Render the top-10 leaderboard table onto *screen*."""
    screen.fill(BLACK)
    scores = load_leaderboard()
    title = font.render("TOP 10 LEADERBOARD", True, WHITE)
    screen.blit(title, (SCREEN_WIDTH // 2 - title.get_width() // 2, 30))
    header = font.render("Name       Score    Lvl   Lines   Date", True, GRAY)
    screen.blit(header, (SCREEN_WIDTH // 2 - header.get_width() // 2, 80))
    for i, entry in enumerate(scores[:10], 1):
        row_str = (
            f"{i:<2} {entry['name']:<10} {entry['score']:<8} "
            f"{entry['level']:<5} {entry['lines']:<7} {entry['date']}"
        )
        row = font.render(row_str, True, WHITE)
        screen.blit(row, (SCREEN_WIDTH // 2 - row.get_width() // 2, 120 + i * 30))
    instr = font.render("Press any key to continue", True, GRAY)
    screen.blit(instr, (SCREEN_WIDTH // 2 - instr.get_width() // 2, 600))