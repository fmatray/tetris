"""Menu state: player mode, handicap selection, sound toggle, start/leaderboard/quit."""

from __future__ import annotations

from typing import Optional

import pygame
import sys

from tetris.settings import BLACK, GRAY, SCREEN_WIDTH, WHITE
from tetris.states.base import State


class MenuState(State):
    """Start menu with player mode (Human/AI), handicap (0-5), sound toggle, and navigation."""

    _OPTIONS = [
        "Joueur",
        "Modifier Handicap",
        "Son",
        "Démarrer le jeu",
        "Leaderboard",
        "Quitter",
    ]

    def __init__(self, screen, font, audio) -> None:
        self.screen, self.font, self.audio = screen, font, audio
        self.h = 0
        self.s = True
        self.player = "Humain"
        self.selection = 0

    def handle_event(self, event: pygame.event.Event) -> Optional[State]:
        if event.type != pygame.KEYDOWN:
            return None
        if event.key == pygame.K_UP:
            self.selection = (self.selection - 1) % len(self._OPTIONS)
        elif event.key == pygame.K_DOWN:
            self.selection = (self.selection + 1) % len(self._OPTIONS)
        elif event.key == pygame.K_LEFT:
            if self.selection == 0:
                self.player = "IA" if self.player == "Humain" else "Humain"
            elif self.selection == 1:
                self.h = max(0, self.h - 1)
            elif self.selection == 2:
                self.s = not self.s
        elif event.key == pygame.K_RIGHT:
            if self.selection == 0:
                self.player = "IA" if self.player == "Humain" else "Humain"
            elif self.selection == 1:
                self.h = min(5, self.h + 1)
            elif self.selection == 2:
                self.s = not self.s
        elif event.key == pygame.K_RETURN:
            # Lazy imports to avoid circular dependency between states
            from tetris.states.game import GameState
            from tetris.states.leaderboard import LeaderboardState

            if self.selection == 3:  # Start
                if self.player == "IA":
                    return None  # AI mode not implemented yet
                return GameState(self.screen, self.font, self.audio, self.h, self.s)
            elif self.selection == 4:  # Leaderboard
                return LeaderboardState(self.screen, self.font, self.audio)
            elif self.selection == 5:  # Quit
                pygame.quit()
                sys.exit()
        return None

    def draw(self, screen: pygame.Surface) -> None:
        screen.fill(BLACK)
        title = self.font.render("TETRIS", True, WHITE)
        screen.blit(title, (SCREEN_WIDTH // 2 - title.get_width() // 2, 100))

        for i, option in enumerate(self._OPTIONS):
            color = WHITE if i == self.selection else GRAY
            prefix = "> " if i == self.selection else "  "
            text = option
            if i == 0:
                text = f"{option} : {self.player}"
            if i == 1:
                text = f"{option} : {self.h}"
            if i == 2:
                text = f"{option} : {'ON' if self.s else 'OFF'}"
            surf = self.font.render(f"{prefix}{text}", True, color)
            screen.blit(surf, (SCREEN_WIDTH // 2 - surf.get_width() // 2, 200 + i * 60))

        instr = self.font.render("Flèches: Navigation | Entrée: Valider", True, GRAY)
        screen.blit(instr, (SCREEN_WIDTH // 2 - instr.get_width() // 2, 550))