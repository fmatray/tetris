"""Menu state: player, sound, human/AI submenus, start, leaderboard, quit."""

from __future__ import annotations

import json
import sys
from typing import TYPE_CHECKING, Optional

import pygame

from tetris.settings import (
    BLACK,
    GRAY,
    SCREEN_HEIGHT,
    SCREEN_WIDTH,
    SETTINGS_PATH,
    WHITE,
)
from tetris.states.base import State

if TYPE_CHECKING:
    pass

# Options that have a left/right-toggable value displayed inline.
_TOGGLE_INDICES = {0, 1}  # Joueur, Son


class MenuState(State):
    """Start menu with player, sound, human/AI submenus, and navigation.

    All settings persist across game/leaderboard round-trips because child
    states receive and return *this same* ``MenuState`` instance.
    """

    _OPTIONS = [
        "Joueur",
        "Son",
        "Humain",
        "IA",
        "Démarrer le jeu",
        "Leaderboard",
        "Quitter",
    ]

    # Indices that lead to a submenu (ENTER navigates, not toggles).
    _SUBMENU_INDICES = {2, 3}

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
        self.ai_mode = "learning"  # "learning" or "playing"
        from tetris.settings import DEFAULT_KEYBINDS

        self.keybinds: dict[str, int] = dict(DEFAULT_KEYBINDS)
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
        "ai_mode": "ai_mode",
    }

    def _load_settings(self) -> None:
        """Load menu options from the settings JSON file."""
        try:
            with open(SETTINGS_PATH) as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError):
            return
        for attr, key in self._SETTINGS_MAP.items():
            if key in data:
                setattr(self, attr, data[key])
        # Keybindings are a dict — merge saved values over defaults
        # so new actions added in future versions get their default key.
        if "keybinds" in data and isinstance(data["keybinds"], dict):
            for action, key_code in data["keybinds"].items():
                if action in self.keybinds:
                    self.keybinds[action] = int(key_code)

    def save_settings(self) -> None:
        """Persist current menu options to the settings JSON file."""
        data = {key: getattr(self, attr) for attr, key in self._SETTINGS_MAP.items()}
        data["keybinds"] = self.keybinds
        try:
            with open(SETTINGS_PATH, "w") as f:
                json.dump(data, f, indent=2)
        except OSError as e:
            print(f"Settings save error: {e}")

    # --- Value helpers --------------------------------------------------

    def _value_label(self, i: int) -> str:
        """Inline value shown after the option label, if any."""
        if i == 0:
            return self.player
        if i == 1:
            return "ON" if self.s else "OFF"
        return ""

    def _is_disabled(self, i: int) -> bool:
        """Greyed-out options that can't be selected."""
        if i == 2 and self.player == "IA":
            return True
        if i == 3 and self.player == "Humain":
            return True
        return False

    # --- Input ----------------------------------------------------------

    def _toggle_left(self) -> None:
        if self.selection == 0:
            self.player = "IA" if self.player == "Humain" else "Humain"
        elif self.selection == 1:
            self.s = not self.s

    def _toggle_right(self) -> None:
        if self.selection == 0:
            self.player = "IA" if self.player == "Humain" else "Humain"
        elif self.selection == 1:
            self.s = not self.s

    def handle_event(self, event: pygame.event.Event) -> Optional[State]:
        if event.type != pygame.KEYDOWN:
            return None
        # Skip disabled options when navigating
        if event.key == pygame.K_UP:
            self.selection = self._prev_enabled(self.selection)
        elif event.key == pygame.K_DOWN:
            self.selection = self._next_enabled(self.selection)
        elif event.key == pygame.K_LEFT:
            if self.selection in _TOGGLE_INDICES:
                self._toggle_left()
                self.save_settings()
        elif event.key == pygame.K_RIGHT:
            if self.selection in _TOGGLE_INDICES:
                self._toggle_right()
                self.save_settings()
        elif event.key == pygame.K_RETURN:
            if not self._is_disabled(self.selection):
                return self._on_select()
        elif event.key == pygame.K_ESCAPE:
            pygame.quit()
            sys.exit()
        return None

    def _prev_enabled(self, current: int) -> int:
        n = len(self._OPTIONS)
        for step in range(1, n + 1):
            idx = (current - step) % n
            if not self._is_disabled(idx):
                return idx
        return current

    def _next_enabled(self, current: int) -> int:
        n = len(self._OPTIONS)
        for step in range(1, n + 1):
            idx = (current + step) % n
            if not self._is_disabled(idx):
                return idx
        return current

    def _on_select(self) -> Optional[State]:
        sel = self.selection
        if sel == 2:  # Humain sub-menu
            from tetris.states.human_menu import HumanMenuState

            return HumanMenuState(self.screen, self.font, self.audio, self)
        if sel == 3:  # IA sub-menu
            from tetris.states.ai_menu import AIMenuState

            return AIMenuState(self.screen, self.font, self.audio, self)
        if sel == 4:  # Start
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
                    ai_mode=self.ai_mode,
                )
            return GameState(
                self.screen, self.font, self.audio, self.h, self.s, provider, self
            )
        if sel == 5:  # Leaderboard
            from tetris.states.leaderboard import LeaderboardState

            return LeaderboardState(self.screen, self.font, self.audio, self)
        if sel == 6:  # Quit
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
            disabled = self._is_disabled(i)
            if disabled:
                color = (64, 64, 64)
            elif is_sel:
                color = WHITE
            else:
                color = GRAY
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