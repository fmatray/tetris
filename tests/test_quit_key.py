"""`q` key — quit to menu after natural game over (AI, Bot, MCP).

Semantics under test (plan: quit-key-after-game-over-plan):
- `q` sets ``quit_pending``; play continues until natural game over.
- AI: the final episode is logged before quitting (unlike Esc, which
  discards the in-flight episode); the state returns to the parent menu
  instead of starting a new episode.
- Bot: returns to the parent menu instead of GameOverState.
- MCP: stays live until game over, then returns to the menu.
- Human: `q` is ignored.
- HUD hint renders translated in all 4 languages, in bounds, no overlap.

Headless: conftest.py sets SDL_VIDEODRIVER=dummy + SDL_AUDIODRIVER=dummy.
"""

from __future__ import annotations

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import json

import pygame
import pytest

from tests.helpers import make_audio, make_game_config, make_screen
from tests.layout_harness import (
    RecordingFont,
    RecordingScreen,
    assert_layout_in_bounds,
    assert_no_text_overlap,
)
from tetris.game.piece_provider import PieceProvider
from tetris.i18n import set_language
from tetris.states.ai import AIConfig, AIState
from tetris.states.eltetris import BotConfig, ElTetrisState
from tetris.states.human import HumanState
from tetris.states.mcp import MCPConfig, MCPState
from tetris.states.menu import MenuState
from tetris.visuals.particles import ParticleSystem

LANGUAGES = ("en", "fr", "es", "sl")
HINT_TEXTS = {
    "en": "Quit after game over",
    "fr": "Quitter après la fin de partie",
    "es": "Salir al terminar la partida",
    "sl": "Zapri po koncu igre",
}

_counter = 0


def _unique_path() -> str:
    global _counter
    _counter += 1
    return f"/tmp/_test_quit_key_{_counter}.json"


def _make_menu(screen=None, font=None) -> MenuState:
    return MenuState(screen or make_screen(), font or make_font(), make_audio())


def make_font() -> pygame.font.Font:
    return pygame.font.Font(None, 24)


def _q() -> pygame.event.Event:
    return pygame.event.Event(pygame.KEYDOWN, key=pygame.K_q)


def test_bot_q_sets_flag_then_quits_at_game_over():
    menu = _make_menu()
    state = ElTetrisState(
        make_screen(),
        make_font(),
        make_audio(),
        make_game_config(preview_count=1),
        PieceProvider(generator="7bag", path=_unique_path()),
        menu=menu,
        bot_config=BotConfig(lookahead=False, lookahead_depth=1),
    )
    assert state.handle_event(_q()) is None
    assert state.quit_pending is True
    state.game_over = True
    result = state.update(1.0 / 60.0, ParticleSystem())
    assert result is menu


def test_bot_without_q_goes_to_game_over_state():
    state = ElTetrisState(
        make_screen(),
        make_font(),
        make_audio(),
        make_game_config(preview_count=1),
        PieceProvider(generator="7bag", path=_unique_path()),
        menu=_make_menu(),
        bot_config=BotConfig(lookahead=False, lookahead_depth=1),
    )
    state.game_over = True
    result = state.update(1.0 / 60.0, ParticleSystem())
    from tetris.states.game_over import GameOverState

    assert isinstance(result, GameOverState)


def test_ai_q_quits_to_menu_after_logging_episode(tmp_path, monkeypatch):
    monkeypatch.setattr("tetris.states.ai.PLAYING_LOG_PATH", str(tmp_path / "plog.json"))
    monkeypatch.setattr("tetris.states.ai.PLAYING_BEHAVIOR_LOG_PATH", str(tmp_path / "pblog.jsonl"))
    menu = _make_menu()
    state = AIState(
        make_screen(),
        make_font(),
        make_audio(),
        make_game_config(preview_count=1),
        AIConfig(
            epsilon_decay=0.999,
            epsilon_end=0.1,
            lr=1e-3,
            gamma=0.97,
            batch_size=64,
            buffer_size=50_000,
            ai_mode="playing",
            curriculum=False,
            curriculum_freq=50,
            curriculum_epsilon="reset",
            warm_start=True,
            learn_per_action=2,
            lookahead=False,
            lookahead_depth=1,
        ),
        PieceProvider(generator="7bag", path=_unique_path()),
        speed="fast",
        menu=menu,
    )
    state.handle_event(_q())
    assert state.quit_pending is True
    state.game_over = True
    result = state.update(1.0 / 60.0, ParticleSystem())
    assert result is menu
    # The final episode WAS logged before quitting — the q-vs-Esc distinction.
    episodes = json.loads((tmp_path / "plog.json").read_text())
    assert len(episodes) == 1
    assert episodes[0]["score"] == state.stats.score


def test_ai_without_q_starts_next_episode():
    state = AIState(
        make_screen(),
        make_font(),
        make_audio(),
        make_game_config(preview_count=1),
        AIConfig(
            epsilon_decay=0.999,
            epsilon_end=0.1,
            lr=1e-3,
            gamma=0.97,
            batch_size=64,
            buffer_size=50_000,
            ai_mode="playing",
            curriculum=False,
            curriculum_freq=50,
            curriculum_epsilon="reset",
            warm_start=True,
            learn_per_action=2,
            lookahead=False,
            lookahead_depth=1,
        ),
        PieceProvider(generator="7bag", path=_unique_path()),
        speed="fast",
        menu=_make_menu(),
    )
    state.log.path = _unique_path()
    state.game_over = True
    result = state.update(1.0 / 60.0, ParticleSystem())
    assert result is None
    assert state.game_over is False  # episode was reset, play continues


def test_mcp_q_stays_live_until_game_over():
    state = MCPState(
        make_screen(),
        make_font(),
        make_audio(),
        make_game_config(preview_count=1),
        MCPConfig(port=8765),
        start_server=False,
    )
    state.handle_event(_q())
    assert state.quit_pending is True
    assert state.update(1.0 / 60.0, ParticleSystem()) is None  # game stays live
    state.game_over = True
    result = state.update(1.0 / 60.0, ParticleSystem())
    assert isinstance(result, MenuState)


def test_mcp_q_with_parent_menu_returns_it():
    menu = _make_menu()
    state = MCPState(
        make_screen(),
        make_font(),
        make_audio(),
        make_game_config(preview_count=1),
        MCPConfig(port=8765),
        start_server=False,
        menu=menu,
    )
    state.handle_event(_q())
    state.game_over = True
    assert state.update(1.0 / 60.0, ParticleSystem()) is menu


def test_mcp_client_start_game_cancels_pending_quit():
    """Client start_game restarts play; a pending q must not fire on it."""
    import queue as q_mod

    from tetris.states.mcp import MCPRequest

    state = MCPState(
        make_screen(),
        make_font(),
        make_audio(),
        make_game_config(preview_count=1),
        MCPConfig(port=8765),
        start_server=False,
    )
    state.handle_event(_q())
    state.game_over = True
    result_q: q_mod.Queue = q_mod.Queue()
    state._action_queue.put(MCPRequest(["start_game"], 0, result_q, False))
    assert state.update(1.0 / 60.0, ParticleSystem()) is None
    assert state.game_over is False


def test_human_q_ignored():
    state = HumanState(
        make_screen(),
        make_font(),
        make_audio(),
        make_game_config(preview_count=3),
        PieceProvider(generator="7bag", path=_unique_path()),
    )
    assert state.handle_event(_q()) is None
    assert state.quit_pending is False


@pytest.mark.parametrize("lang", LANGUAGES)
def test_quit_hint_rendered_translated(lang, monkeypatch):
    set_language(lang)
    monkeypatch.setattr("tetris.visuals.renderer.get_large_font", lambda: RecordingFont(None, 32))
    screen = RecordingScreen()
    font = RecordingFont(None, 24)
    state = ElTetrisState(
        screen,
        font,
        make_audio(),
        make_game_config(preview_count=1),
        PieceProvider(generator="7bag", path=_unique_path()),
        bot_config=BotConfig(lookahead=False, lookahead_depth=1),
    )
    state.quit_pending = True
    state.draw(screen, particles=ParticleSystem())
    texts = [t[0] for t in screen.text_blits]
    assert HINT_TEXTS[lang] in texts
    assert_layout_in_bounds(screen)
    assert_no_text_overlap(screen)


@pytest.fixture(autouse=True)
def _restore_language():
    yield
    set_language("en")
