"""Menu state: player mode, handicap, sound, AI settings, start/leaderboard/quit."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Optional

import pygame

from tetris.settings import BLACK, GRAY, SCREEN_HEIGHT, SCREEN_WIDTH, SETTINGS_PATH, WHITE
from tetris.states.base import State

# Options that have a left/right-toggable value displayed inline.
_TOGGLE_INDICES = {0, 1, 2, 3}


class MenuState(State):
    """Start menu with player, mode, handicap, sound, and navigation.

    All settings (player, mode, handicap, sound, AI speed, selection)
    persist across game/leaderboard round-trips because child states
    receive and return *this same* ``MenuState`` instance.
    """

    _OPTIONS = [
        "Joueur",
        "Mode",
        "Handicap",
        "Son",
        "IA",
        "Démarrer le jeu",
        "Leaderboard",
        "Quitter",
    ]

    def __init__(self, screen, font, audio) -> None:
        self.screen, self.font, self.audio = screen, font, audio
        # Defaults — overridden by _load_settings() if a file exists
        self.h = 0
        self.s = True
        self.player = "Humain"
        self.mode = "Normal"
        self.ai_speed = "normal"
        self.ai_epsilon_decay = 0.999
        self.ai_epsilon_end = 0.1
        self.selection = 0
        self._load_settings()

    # --- Settings persistence -------------------------------------------

    # Maps internal attribute names to human-readable JSON keys.
    _SETTINGS_MAP = {
        "player": "player",
        "mode": "mode",
        "h": "handicap",
        "s": "sound",
        "ai_speed": "ai_speed",
        "ai_epsilon_decay": "ai_epsilon_decay",
        "ai_epsilon_end": "ai_epsilon_end",
    }

    def _load_settings(self) -> None:
        """Load menu options from the settings JSON file."""
        path = Path(SETTINGS_PATH)
        if not path.exists():
            return
        try:
            data = json.loads(path.read_text())
        except (json.JSONDecodeError, OSError):
            return
        for attr, key in self._SETTINGS_MAP.items():
            if key in data:
                setattr(self, attr, data[key])
            # Backward compat: old files used abbreviated keys
            elif attr in ("h", "s") and attr in data:
                setattr(self, attr, data[attr])

    def save_settings(self) -> None:
        """Persist current menu options to the settings JSON file."""
        data = {key: getattr(self, attr) for attr, key in self._SETTINGS_MAP.items()}
        try:
            Path(SETTINGS_PATH).write_text(json.dumps(data, indent=2))
        except OSError as e:
            print(f"Settings save error: {e}")

    # --- Value helpers --------------------------------------------------

    def _value_label(self, i: int) -> str:
        """Inline value shown after the option label, if any."""
        if i == 0:
            return self.player
        if i == 1:
            return self.mode
        if i == 2:
            return str(self.h)
        if i == 3:
            return "ON" if self.s else "OFF"
        return ""

    # --- Input ----------------------------------------------------------

    def _toggle_left(self) -> None:
        if self.selection == 0:
            self.player = "IA" if self.player == "Humain" else "Humain"
        elif self.selection == 1:
            self.mode = "Replay" if self.mode == "Normal" else "Normal"
        elif self.selection == 2:
            self.h = max(0, self.h - 1)
        elif self.selection == 3:
            self.s = not self.s

    def _toggle_right(self) -> None:
        if self.selection == 0:
            self.player = "IA" if self.player == "Humain" else "Humain"
        elif self.selection == 1:
            self.mode = "Replay" if self.mode == "Normal" else "Normal"
        elif self.selection == 2:
            self.h = min(5, self.h + 1)
        elif self.selection == 3:
            self.s = not self.s

    def handle_event(self, event: pygame.event.Event) -> Optional[State]:
        if event.type != pygame.KEYDOWN:
            return None
        if event.key == pygame.K_UP:
            self.selection = (self.selection - 1) % len(self._OPTIONS)
        elif event.key == pygame.K_DOWN:
            self.selection = (self.selection + 1) % len(self._OPTIONS)
        elif event.key == pygame.K_LEFT:
            self._toggle_left()
            self.save_settings()
        elif event.key == pygame.K_RIGHT:
            self._toggle_right()
            self.save_settings()
        elif event.key == pygame.K_RETURN:
            return self._on_select()
        elif event.key == pygame.K_ESCAPE:
            pygame.quit()
            sys.exit()
        return None

    def _on_select(self) -> Optional[State]:
        sel = self.selection
        if sel == 4:  # IA sub-menu
            from tetris.states.ai_menu import AIMenuState

            return AIMenuState(self.screen, self.font, self.audio, self)
        if sel == 5:  # Start
            from tetris.states.game import GameState
            from tetris.game.piece_provider import PieceProvider

            provider = PieceProvider(
                mode="replay" if self.mode == "Replay" else "normal"
            )
            if self.player == "IA":
                from tetris.states.ai import AIState

                return AIState(
                    self.screen, self.font, self.audio, self.h, self.s,
                    provider, self.ai_speed, self,
                    epsilon_decay=self.ai_epsilon_decay,
                    epsilon_end=self.ai_epsilon_end,
                )
            return GameState(
                self.screen, self.font, self.audio, self.h, self.s, provider, self
            )
        if sel == 6:  # Leaderboard
            from tetris.states.leaderboard import LeaderboardState

            return LeaderboardState(self.screen, self.font, self.audio, self)
        if sel == 7:  # Quit
            pygame.quit()
            sys.exit()
        return None

    # --- Rendering ------------------------------------------------------

    def draw(self, screen: pygame.Surface) -> None:
        screen.fill(BLACK)

        title = self.font.render("TETRIS", True, WHITE)
        screen.blit(title, (SCREEN_WIDTH // 2 - title.get_width() // 2, 80))

        for i, option in enumerate(self._OPTIONS):
            is_sel = i == self.selection
            color = WHITE if is_sel else GRAY
            prefix = "> " if is_sel else "  "
            value = self._value_label(i)
            text = f"{prefix}{option}" + (f" : {value}" if value else "")
            surf = self.font.render(text, True, color)
            screen.blit(surf, (SCREEN_WIDTH // 2 - surf.get_width() // 2, 160 + i * 48))

        # Navigation instructions
        instr = self.font.render(
            "Flèches: Navigation | Entrée: Valider | Échap: Quitter", True, GRAY
        )
        screen.blit(
            instr,
            (SCREEN_WIDTH // 2 - instr.get_width() // 2, SCREEN_HEIGHT - 50),
        )