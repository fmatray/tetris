"""Menu state: player, sound, human/AI submenus, start, leaderboard, quit."""

from __future__ import annotations

import json
import sys
from typing import ClassVar

import pygame

from tetris.logger import configure_logging, get_logger
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
        "Joueur",          # 0
        "Audio",           # 1
        "Règles du jeu",  # 2
        "Débogage",        # 3
        "Humain",          # 4
        "IA",              # 5
        "Démarrer le jeu", # 6
        "Leaderboard",     # 7
        "Quitter",         # 8
    )
    _GENERATOR_CYCLE: ClassVar[tuple[str, ...]] = ("random", "7bag", "35bag")
    _toggle_indices = frozenset({0, 3})  # Joueur, Débogage
    _title = "TETRIS"

    _instructions = "Flèches: Navigation | Entrée: Valider | Échap: Quitter"

    def __init__(self, screen, font, audio) -> None:
        """Initialize the root menu and load persisted settings.

        Sets all defaults first, then overrides from ``data/settings.json``
        if it exists. Configures logging based on the loaded debug flag.
        """
        self.ai_speed = "normal"
        super().__init__(screen, font, audio)
        # Defaults — overridden by _load_settings() if a file exists
        self.handicap = 0
        self.sound_volume = 3      # 0=Off, 1=Low, 2=Half, 3=Full
        self.music_volume = 3
        self.music_song = "korobeiniki"
        self.player = "Humain"
        self.mode = "Normal"
        self.piece_generator = "7bag"
        self.ghost_piece = True
        self.preview_count = 3
        self.debug = False
        self.ai_epsilon_decay = 0.999
        self.ai_epsilon_end = 0.1
        self.ai_lr = 1e-4
        self.ai_gamma = 0.97
        self.ai_batch_size = 64
        self.ai_buffer_size = 50_000
        self.ai_mode = "learning"  # "learning" or "playing"
        self.ai_curriculum = False
        self.ai_curriculum_freq = 50
        self.ai_curriculum_epsilon = "reset"
        self.ai_warm_start = True
        self.ai_learn_per_action = 2
        self.ai_lookahead = True
        self.ai_lookahead_depth = 3
        self.ai_soft_drop = True

        # DEFAULT_KEYBINDS imported locally to avoid circular import at module load.
        from tetris.settings import DEFAULT_KEYBINDS

        self.keybinds: dict[str, int] = dict(DEFAULT_KEYBINDS)
        self._load_settings()
        configure_logging(self.debug)

    # --- Settings persistence -------------------------------------------

    # Maps internal attribute names to human-readable JSON keys.
    _SETTINGS_MAP: ClassVar[dict[str, str]] = {
        "player": "player",
        "sound_volume": "sound",
        "music_volume": "music",
        "music_song": "song",
        "handicap": "handicap",
        "ai_speed": "ai_speed",
        "ai_epsilon_decay": "ai_epsilon_decay",
        "ai_epsilon_end": "ai_epsilon_end",
        "ai_lr": "ai_lr",
        "ai_gamma": "ai_gamma",
        "ai_batch_size": "ai_batch_size",
        "ai_buffer_size": "ai_buffer_size",
        "ai_mode": "ai_mode",
        "ai_curriculum": "ai_curriculum",
        "ai_curriculum_freq": "ai_curriculum_freq",
        "ai_curriculum_epsilon": "ai_curriculum_epsilon",
        "ai_warm_start": "ai_warm_start",
        "ai_learn_per_action": "ai_learn_per_action",
        "ai_lookahead": "ai_lookahead",
        "ai_lookahead_depth": "ai_lookahead_depth",
        "ai_soft_drop": "ai_soft_drop",
        "ghost_piece": "ghost_piece",
        "preview_count": "preview_count",
        "debug": "debug",
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
        # Migrate old boolean "sound" to integer "sound_volume"
        if isinstance(self.sound_volume, bool):
            self.sound_volume = 3 if self.sound_volume else 0

    def save_settings(self) -> None:
        """Persist current menu options to the settings JSON file."""
        data = {key: getattr(self, attr) for attr, key in self._SETTINGS_MAP.items()}
        data["keybinds"] = self.keybinds
        try:
            with open(SETTINGS_PATH, "w") as f:
                json.dump(data, f, indent=2)
        except OSError as e:
            logger = get_logger("menu")
            logger.error("Settings save error: %s", e)

    # --- Hooks ----------------------------------------------------------

    def _value_label(self, i: int) -> str:
        if i == 0:
            return self.player
        if i == 3:
            return "ON" if self.debug else "OFF"
        return ""

    def _is_disabled(self, i: int) -> bool:
        return bool(i == 5 and self.player == "Humain" or i == 4 and self.player == "IA")

    def _toggle(self, direction: int) -> None:
        if self.selection == 0:  # Joueur
            self.player = "IA" if self.player == "Humain" else "Humain"
        elif self.selection == 3:  # Débogage
            self.debug = not self.debug
            configure_logging(self.debug)

    def _save(self) -> None:
        self.save_settings()

    def _on_back(self) -> State | None:
        pygame.quit()
        sys.exit()

    def _on_select(self) -> State | None:
        sel = self.selection
        if sel == 1:  # Audio submenu
            from tetris.states.audio_menu import AudioMenuState

            return AudioMenuState(self.screen, self.font, self.audio, self)
        if sel == 2:  # Règles du jeu submenu
            from tetris.states.game_rules_menu import GameRulesMenuState

            return GameRulesMenuState(self.screen, self.font, self.audio, self)
        if sel == 4:  # Humain sub-menu
            from tetris.states.human_menu import HumanMenuState

            return HumanMenuState(self.screen, self.font, self.audio, self)
        if sel == 5:  # IA sub-menu
            from tetris.states.ai_menu import AIMenuState

            return AIMenuState(self.screen, self.font, self.audio, self)
        if sel == 6:  # Start
            from tetris.game.piece_provider import PieceProvider
            from tetris.states.game import GameState

            provider = PieceProvider(
                mode="replay" if self.mode == "Replay" else "normal",
                generator=self.piece_generator,
            )
            if self.player == "IA":
                return self._build_ai_state()
            return GameState(
                self.screen, self.font, self.audio, self.handicap,
                self.sound_volume, self.music_volume, self.music_song, provider, self,
                ghost_piece=self.ghost_piece,
                preview_count=self.preview_count,
                debug=self.debug,
            )
        if sel == 7:  # Leaderboard
            from tetris.states.leaderboard import LeaderboardState

            return LeaderboardState(self.screen, self.font, self.audio, self)
        if sel == 8:  # Quit
            pygame.quit()
            sys.exit()
        return None

    def _build_ai_state(self) -> State:
        from tetris.game.piece_provider import PieceProvider
        from tetris.states.ai import AIState

        ai_provider = PieceProvider(mode="normal", generator=self.piece_generator)
        return AIState(
            self.screen, self.font, self.audio, self.handicap,
            self.sound_volume, self.music_volume, self.music_song,
            ai_provider, self.ai_speed, self,
            epsilon_decay=self.ai_epsilon_decay,
            epsilon_end=self.ai_epsilon_end,
            lr=self.ai_lr,
            gamma=self.ai_gamma,
            batch_size=self.ai_batch_size,
            buffer_size=self.ai_buffer_size,
            ai_mode=self.ai_mode,
            curriculum=self.ai_curriculum,
            curriculum_freq=self.ai_curriculum_freq,
            curriculum_epsilon=self.ai_curriculum_epsilon,
            warm_start=self.ai_warm_start,
            lookahead=self.ai_lookahead,
            lookahead_depth=self.ai_lookahead_depth,
            soft_drop=self.ai_soft_drop,
            preview_count=self.preview_count,
            debug=self.debug,
        )