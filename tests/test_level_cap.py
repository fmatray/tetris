"""Tests for the level-cap rule: Human / Bot / AI playing end the game at the cap.

Headless: conftest.py sets SDL_VIDEODRIVER=dummy + SDL_AUDIODRIVER=dummy.
"""

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

pygame.init()
pygame.mixer.init()

from tetris.game.piece_provider import PieceProvider
from tetris.settings import DEFAULT_LEVEL_CAP, LEVEL_CAP_VALUES
from tetris.states.ai import AIState, AIConfig
from tetris.states.eltetris import BotConfig, ElTetrisState
from tetris.states.game_over import GameOverState
from tetris.states.game_rules_menu import GameRulesMenuState
from tetris.states.menu import MenuState
from tetris.visuals.particles import ParticleSystem
from tests.helpers import make_audio, make_font, make_game_config, make_screen


def _make_bot(cap):
    """Build an ElTetrisState with a level cap (config override)."""
    screen = make_screen()
    return ElTetrisState(
        screen,
        make_font(),
        make_audio(),
        config=make_game_config(level_cap=cap),
        bot_config=BotConfig(lookahead=False, lookahead_depth=0),
        piece_provider=PieceProvider(generator="7bag"),
    )


def _make_ai(cap, mode):
    """Build an AIState with a level cap in the given mode."""
    return AIState(
        make_screen(),
        make_font(),
        make_audio(),
        config=make_game_config(level_cap=cap),
        ai_config=AIConfig(
            epsilon_decay=0.999,
            epsilon_end=0.1,
            lr=1e-3,
            gamma=0.97,
            batch_size=64,
            buffer_size=50_000,
            ai_mode=mode,
            curriculum=False,
            curriculum_freq=50,
            curriculum_epsilon="reset",
            warm_start=True,
            learn_per_action=2,
            lookahead=True,
            lookahead_depth=1,
        ),
        piece_provider=PieceProvider(generator="7bag"),
        speed="fast",
    )


def _make_game_over(cap) -> GameOverState:
    """Build a GameOverState from a cap-triggered bot game."""
    state = _make_bot(cap)
    state.stats.level = cap
    state.game_over = False
    result = state.update(1 / 60, ParticleSystem())
    assert isinstance(result, GameOverState)
    return result


# --- Settings -------------------------------------------------------------


def test_level_cap_default_is_1000():
    assert DEFAULT_LEVEL_CAP == 1000


def test_level_cap_values():
    assert LEVEL_CAP_VALUES[0] == 500
    assert LEVEL_CAP_VALUES[-1] == 20_000
    assert LEVEL_CAP_VALUES == tuple(range(500, 20_001, 500))


# --- Game rules menu -------------------------------------------------------


def test_game_rules_options_include_level_cap():
    assert "Level cap" in GameRulesMenuState._OPTIONS


def test_game_rules_level_cap_is_last_toggle():
    """Level cap is index 7, toggleable, Back stays last."""
    assert GameRulesMenuState._OPTIONS[7] == "Level cap"
    assert GameRulesMenuState._OPTIONS[8] == "Back"
    assert 7 in GameRulesMenuState._toggle_indices


def test_game_rules_level_cap_value_label():
    menu = MenuState(make_screen(), make_font(), make_audio())
    state = GameRulesMenuState(make_screen(), make_font(), make_audio(), menu)
    menu.level_cap = DEFAULT_LEVEL_CAP
    assert state._value_label(7) == "1000"
    menu.level_cap = None
    assert state._value_label(7) == "OFF"


def test_game_rules_level_cap_toggle_wraps():
    menu = MenuState(make_screen(), make_font(), make_audio())
    state = GameRulesMenuState(make_screen(), make_font(), make_audio(), menu)
    menu.level_cap = DEFAULT_LEVEL_CAP
    state.selection = 7
    state._toggle(1)
    assert menu.level_cap == 1500
    state._toggle(-1)
    assert menu.level_cap == 1000
    state._toggle(-1)
    assert menu.level_cap == 500
    state._toggle(-1)
    cap = menu.level_cap
    assert cap is None  # OFF below 500


def test_game_rules_level_cap_off_to_on():
    """Below-500 wraps OFF; the next cycle turns it on at 500."""
    menu = MenuState(make_screen(), make_font(), make_audio())
    state = GameRulesMenuState(make_screen(), make_font(), make_audio(), menu)
    menu.level_cap = None
    state.selection = 7
    state._toggle(1)
    assert menu.level_cap == 500  # ON above OFF


def test_game_rules_level_cap_reaches_game_config():
    menu = MenuState(make_screen(), make_font(), make_audio())
    menu.level_cap = 2000
    assert menu._game_config().level_cap == 2000
    menu.level_cap = None
    assert menu._game_config().level_cap is None


# --- Game end -------------------------------------------------------------


def test_bot_game_over_at_cap():
    state = _make_game_over(500)
    assert state is not None
    assert state.game.stats.level >= 500
    assert state.game.player_type == "Bot"


def test_bot_not_game_over_below_cap():
    state = _make_bot(500)
    state.stats.level = 499
    state.game_over = False
    assert state.update(1 / 60, ParticleSystem()) is None


def test_bot_no_cap_no_game_over():
    state = _make_bot(None)
    state.stats.level = 1000
    state.game_over = False
    assert state.update(1 / 60, ParticleSystem()) is None


def test_human_game_over_at_cap():
    from tetris.states.human import HumanState

    state = HumanState(
        make_screen(),
        make_font(),
        make_audio(),
        make_game_config(level_cap=10),
        menu=MenuState(make_screen(), make_font(), make_audio()),
    )
    state.stats.level = 10
    state.game_over = False
    result = state.update(1 / 60, ParticleSystem())
    assert isinstance(result, GameOverState)
    assert result.game.player_type == "Humain"


def test_ai_playing_ignores_cap_restart():
    """AI playing mode ends the episode and restarts, never a GameOverState."""
    ai = _make_ai(500, "playing")
    ai.stats.level = 500
    ai.game_over = False
    result = ai.update(1 / 60, ParticleSystem())
    assert result is None  # episode restarts in place


def test_ai_learning_ignores_cap():
    ai = _make_ai(2, "learning")
    assert ai.level_cap is None  # training never stopped by the cap
    ai.stats.level = 2
    ai.game_over = False
    assert ai.update(1 / 60, ParticleSystem()) is None


def test_cap_rule_skips_mcp():
    """MCP (external agent) has no recording path — the cap rule is inert."""
    from tetris.states.mcp import MCPConfig, MCPState

    state = MCPState(
        make_screen(),
        make_font(),
        make_audio(),
        make_game_config(level_cap=1),
        MCPConfig(port=8765),
        start_server=False,
    )
    assert state.level_cap == 1
    state.stats.level = 1
    state.game_over = False
    assert state.update(1 / 60, ParticleSystem()) is None
