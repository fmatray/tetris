"""Menu state: player, sound, human/AI submenus, start, leaderboard, quit."""

from __future__ import annotations

import json
import sys
from typing import ClassVar

import pygame

from tetris.settings import (
    SETTINGS_PATH,
)
from tetris.states.base import State
from tetris.states.menu_base import MenuBase


class MenuState(MenuBase):
    """Start menu with player, sound, human/AI submenus, and navigation.

    All settings persist across game/leaderboard round-trips because child
    states receive and return *this same* ``MenuState`` instance.
    """

    _OPTIONS = (
        "Joueur",
        "Son",
        "Humain",
        "IA",
        "Démarrer le jeu",
        "Leaderboard",
        "Quitter",
    )
    _toggle_indices = frozenset({0, 1})  # Joueur, Son
    _title = "TETRIS"

    _instructions = "Flèches: Navigation | Entrée: Valider | Échap: Quitter"

    def __init__(self, screen, font, audio) -> None:
        super().__init__(screen, font, audio)
        # Defaults — overridden by _load_settings() if a file exists
        self.handicap = 0
        self.sound_enabled = True
        self.player = "Humain"
        self.mode = "Normal"
        self.ai_speed = "normal"
        self.ai_epsilon_decay = 0.999
        self.ai_epsilon_end = 0.1
        self.ai_lr = 1e-4
        self.ai_gamma = 0.97
        self.ai_batch_size = 64
        self.ai_buffer_size = 50_000
        self.ai_target_sync_steps = 500
        self.ai_mode = "learning"  # "learning" or "playing"
        from tetris.settings import DEFAULT_KEYBINDS

        self.keybinds: dict[str, int] = dict(DEFAULT_KEYBINDS)
        self._load_settings()

    # --- Settings persistence -------------------------------------------

    # Maps internal attribute names to human-readable JSON keys.
    _SETTINGS_MAP: ClassVar[dict[str, str]] = {
        "player": "player",
        "mode": "mode",
        "handicap": "handicap",
        "sound_enabled": "sound",
        "ai_speed": "ai_speed",
        "ai_epsilon_decay": "ai_epsilon_decay",
        "ai_epsilon_end": "ai_epsilon_end",
        "ai_lr": "ai_lr",
        "ai_gamma": "ai_gamma",
        "ai_batch_size": "ai_batch_size",
        "ai_buffer_size": "ai_buffer_size",
        "ai_target_sync_steps": "ai_target_sync_steps",
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

    # --- Hooks ----------------------------------------------------------

    def _value_label(self, i: int) -> str:
        if i == 0:
            return self.player
        if i == 1:
            return "ON" if self.sound_enabled else "OFF"
        return ""

    def _is_disabled(self, i: int) -> bool:
        return bool(i == 3 and self.player == "Humain" or i == 2 and self.player == "IA")

    def _toggle(self, direction: int) -> None:
        if self.selection == 0:  # Joueur
            self.player = "IA" if self.player == "Humain" else "Humain"
        elif self.selection == 1:  # Son
            self.sound_enabled = not self.sound_enabled

    def _save(self) -> None:
        self.save_settings()

    def _on_back(self) -> State | None:
        pygame.quit()
        sys.exit()

    def _on_select(self) -> State | None:
        sel = self.selection
        if sel == 2:  # Humain sub-menu
            from tetris.states.human_menu import HumanMenuState

            return HumanMenuState(self.screen, self.font, self.audio, self)
        if sel == 3:  # IA sub-menu
            from tetris.states.ai_menu import AIMenuState

            return AIMenuState(self.screen, self.font, self.audio, self)
        if sel == 4:  # Start
            from tetris.game.piece_provider import PieceProvider
            from tetris.states.game import GameState

            provider = PieceProvider(
                mode="replay" if self.mode == "Replay" else "normal"
            )
            if self.player == "IA":
                from tetris.states.ai import AIState

                return AIState(
                    self.screen, self.font, self.audio, self.handicap, self.sound_enabled,
                    provider, self.ai_speed, self,
                    epsilon_decay=self.ai_epsilon_decay,
                    epsilon_end=self.ai_epsilon_end,
                    lr=self.ai_lr,
                    gamma=self.ai_gamma,
                    batch_size=self.ai_batch_size,
                    buffer_size=self.ai_buffer_size,
                    target_sync_steps=self.ai_target_sync_steps,
                    ai_mode=self.ai_mode,
                )
            return GameState(
                self.screen, self.font, self.audio, self.handicap, self.sound_enabled, provider, self
            )
        if sel == 5:  # Leaderboard
            from tetris.states.leaderboard import LeaderboardState

            return LeaderboardState(self.screen, self.font, self.audio, self)
        if sel == 6:  # Quit
            pygame.quit()
            sys.exit()
        return None