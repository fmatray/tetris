"""El-Tetris bot state and shared bot library tests.

Run: SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy python -m pytest tests/test_eltetris_state.py -q
"""

from __future__ import annotations

import os
import re

import numpy as np
import pygame
import pytest

from pathlib import Path

from tetris.audio import AudioManager

from tetris.bots.moves import BotMovesMixin
from tetris.game.piece_provider import PieceProvider
from tetris.states.bot_menu import BotMenuState
from tetris.states.eltetris import BotConfig, ElTetrisState
from tetris.states.game import GameConfig
from tetris.states.menu import MenuState
from tetris.visuals.particles import ParticleSystem

ROOT = Path(__file__).resolve().parent.parent

_counter = 0


def _unique_path() -> str:
    global _counter
    _counter += 1
    return f"/tmp/_test_eltetris_{_counter}.json"


@pytest.fixture(scope="session", autouse=True)
def _init_pygame():
    pygame.init()
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    os.environ.setdefault("SDL_AUDIODRIVER", "dummy")


def _make_bot(
    lookahead: bool = False,
    lookahead_depth: int = 1,
    preview_count: int = 1,
) -> ElTetrisState:
    screen = pygame.Surface((800, 600))
    font = pygame.font.Font(None, 20)
    audio = AudioManager(sound_volume=0, music_volume=0)
    provider = PieceProvider(generator="7bag", path=_unique_path())
    return ElTetrisState(
        screen=screen,
        font=font,
        audio=audio,
        config=GameConfig(
            handicap=0,
            sound_volume=0,
            music_volume=0,
            music_song="korobeiniki",
            debug=False,
            ghost_piece=True,
            preview_count=preview_count,
            speed_mode="normal",
        ),
        piece_provider=provider,
        bot_config=BotConfig(lookahead=lookahead, lookahead_depth=lookahead_depth),
    )


class TestElTetrisPick:
    def test_picks_max(self):
        assert int(np.argmax(np.array([1.0, 3.0, 2.0]))) == 1

    def test_tie_lowest_index(self):
        # np.argmax resolves ties to the lowest index — the pick rule
        assert int(np.argmax(np.array([2.0, 3.0, 3.0]))) == 1

    def test_single(self):
        assert int(np.argmax(np.array([5.0]))) == 0


class TestElTetrisStateInit:
    def test_defaults_no_lookahead(self):
        bot = _make_bot()
        assert bot.lookahead is False
        assert bot.lookahead_depth == 1
        assert bot.episode_steps == 0
        assert bot.player_type == "Bot"

    def test_none_config_falls_back(self):
        bot = ElTetrisState(
            pygame.Surface((800, 600)),
            pygame.font.Font(None, 20),
            AudioManager(sound_volume=0, music_volume=0),
            GameConfig(
                handicap=0,
                sound_volume=0,
                music_volume=0,
                music_song="korobeiniki",
                debug=False,
                ghost_piece=True,
                preview_count=1,
                speed_mode="normal",
            ),
            PieceProvider(generator="7bag", path=_unique_path()),
        )
        assert bot.lookahead is False

    def test_lookahead_config(self):
        bot = _make_bot(lookahead=True, lookahead_depth=2, preview_count=3)
        assert bot.lookahead is True
        assert bot.lookahead_depth == 2


class TestElTetrisIndependence:
    def test_no_ai_state_dependency(self):
        source = (ROOT / "tetris" / "states" / "eltetris.py").read_text()
        assert not re.search(r"from tetris\.states\.ai\b", source)
        assert "tetris.ai.agent" not in source


class TestElTetrisGameplay:
    def test_bot_places_pieces(self):
        bot = _make_bot()
        parts = ParticleSystem()
        for _ in range(30):
            bot.update(16, parts)
        assert bot.episode_steps > 0
        assert len(bot._candidate_placements) > 0

    def test_bot_survives_long_run(self):
        bot = _make_bot()
        parts = ParticleSystem()
        # ~200 frames of gameplay: bot should place several pieces
        # without invalid-move crashes.
        for _ in range(200):
            bot.update(16, parts)
        assert bot.episode_steps >= 3

    def test_replay_lands_exactly_on_evaluated_placement(self):
        """BFS paths start from spawn; replay must land on the exact (px, py, rot)
        the evaluation saw, even when gravity pre-falls the piece during the
        80ms decision delay (the replay snaps the piece back to spawn)."""
        bot = _make_bot()
        parts = ParticleSystem()
        placements: list = []
        orig = ElTetrisState._execute_move_sequence

        def spy(self: BotMovesMixin, action: int) -> None:
            # Simulate one frame of gravity pre-fall before replay.
            if self.board.is_valid_move(self.current_piece, dy=1):
                self.current_piece.move(0, 1)
            p = self._candidate_placements[action]
            orig(self, action)
            placements.append((p, (self.current_piece.x, self.current_piece.y, self.current_piece.rotation % 4)))

        ElTetrisState._execute_move_sequence = spy  # type: ignore[method-assign]
        try:
            for _ in range(120):
                bot.update(16, parts)
        finally:
            ElTetrisState._execute_move_sequence = orig  # type: ignore[method-assign]
        assert placements, "bot never executed a move"
        for p, (x, y, rot) in placements:
            assert (x, y, rot) == (p.px, p.py, p.rot % 4)

    def test_pick_values_match_candidates(self):
        """_pick_values is the El-Tetris array matching the candidate list."""
        bot = _make_bot()
        candidates, _actions, returned = bot._get_candidate_states()
        assert len(bot._pick_values) == len(candidates)
        assert returned is bot._pick_values


class TestBotMenu:
    def _make_menu(self) -> MenuState:
        screen = pygame.Surface((800, 600))
        font = pygame.font.Font(None, 20)
        audio = AudioManager(sound_volume=0, music_volume=0)
        return MenuState(screen, font, audio)

    def test_menu_builds_eltetris_state(self):
        menu = self._make_menu()
        menu.player = "Bot"
        menu.selection = 0
        state = menu._on_select()
        assert isinstance(state, ElTetrisState)
        # Default bot_lookahead="preview", preview_count=3 → depth 3
        assert state.lookahead_depth == 3
        assert state.lookahead is True

    def test_player_cycle_includes_bot(self):
        menu = self._make_menu()
        menu.selection = 1
        menu._toggle(1)
        assert menu.player == "IA"
        menu._toggle(1)
        assert menu.player == "Bot"
        menu._toggle(1)
        assert menu.player == "MCP"
        menu._toggle(1)
        assert menu.player == "Humain"

    def test_bot_sub_menu_disabled_for_others(self):
        menu = self._make_menu()
        menu.player = "Humain"
        assert menu._is_disabled(4) is True
        assert menu._is_disabled(3) is True  # IA greyed
        menu.player = "Bot"
        assert menu._is_disabled(4) is False

    def test_bot_menu_toggle(self):
        menu = self._make_menu()
        menu.bot_lookahead = "preview"
        bm = BotMenuState(menu.screen, menu.font, menu.audio, menu)
        bm.selection = 0
        bm._toggle(1)
        assert menu.bot_lookahead == "none"
        bm._toggle(1)
        assert menu.bot_lookahead == "preview"
