"""Layout regression tests — invariant assertions on text blits (roadmap #6).

Catches the d33393f bug class: FR/ES HUD text overflowing the screen or
overlapping other text. Drives real states through ``draw()`` with a
recording font + screen and asserts layout invariants in every supported
language (EN, FR, ES, SL).
"""

from __future__ import annotations

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

pygame.init()

import pytest

from tests.helpers import make_audio, make_game_config
from tests.layout_harness import (
    RecordingFont,
    RecordingScreen,
    assert_layout_in_bounds,
    assert_no_text_overlap,
)
from tetris.game.piece_provider import PieceProvider
from tetris.i18n import set_language
from tetris.states.ai import AIConfig, AIState
from tetris.states.human import HumanState
from tetris.states.menu import MenuState
from tetris.visuals.particles import ParticleSystem

LANGUAGES = ("en", "fr", "es", "sl")


@pytest.fixture(autouse=True)
def _restore_language():
    yield
    set_language("en")


def _make_ai_config(mode: str) -> AIConfig:
    return AIConfig(
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
        lookahead=False,
        lookahead_depth=1,
    )


def _draw_menu() -> RecordingScreen:
    screen = RecordingScreen()
    font = RecordingFont(None, 24)
    menu = MenuState(screen, font, make_audio())
    menu.draw(screen)
    return screen


def _draw_human() -> RecordingScreen:
    screen = RecordingScreen()
    font = RecordingFont(None, 24)
    state = HumanState(screen, font, make_audio(), make_game_config(preview_count=3))
    state.draw(screen, particles=ParticleSystem())
    state._on_exit()
    return screen


def _draw_ai(mode: str) -> RecordingScreen:
    screen = RecordingScreen()
    font = RecordingFont(None, 24)
    config = make_game_config(preview_count=3)
    state = AIState(
        screen,
        font,
        make_audio(),
        config,
        _make_ai_config(mode),
        PieceProvider(generator="7bag"),
        speed="normal",
        menu=None,
    )
    state.draw(screen, particles=ParticleSystem())
    state._on_exit()
    return screen


@pytest.mark.parametrize("lang", LANGUAGES)
def test_menu_layout(lang):
    set_language(lang)
    screen = _draw_menu()
    assert_layout_in_bounds(screen)
    assert_no_text_overlap(screen)


@pytest.mark.parametrize("lang", LANGUAGES)
def test_human_hud_layout(lang):
    set_language(lang)
    screen = _draw_human()
    assert_layout_in_bounds(screen)
    assert_no_text_overlap(screen)


@pytest.mark.parametrize("lang", LANGUAGES)
@pytest.mark.parametrize("selection", (0, 8, 14, 20, 22))
def test_hyperparam_menu_layout(lang, selection):
    set_language(lang)
    from tetris.states.ai_menu import AIMenuState
    from tetris.states.hyperparam_menu import HyperparamMenuState

    screen = RecordingScreen()
    font = RecordingFont(None, 24)
    menu = MenuState(screen, font, make_audio())
    ai = AIMenuState(screen, font, make_audio(), menu)
    state = HyperparamMenuState(screen, font, make_audio(), ai)
    state.selection = selection
    state.draw(screen)
    assert_layout_in_bounds(screen)
    assert_no_text_overlap(screen)


@pytest.mark.parametrize("lang", LANGUAGES)
@pytest.mark.parametrize("mode", ("learning", "playing"))
def test_ai_hud_layout(lang, mode):
    set_language(lang)
    screen = _draw_ai(mode)
    assert_layout_in_bounds(screen)
    assert_no_text_overlap(screen)


def test_harness_catches_overflow():
    """The harness itself must flag out-of-bounds text (meta-test)."""
    screen = RecordingScreen(size=(100, 50))
    screen.text_blits.append(("TOO LONG LABEL", 90, 0, 120, 20))
    with pytest.raises(AssertionError, match="exceeds screen"):
        assert_layout_in_bounds(screen)


def test_harness_catches_overlap():
    """The harness itself must flag overlapping text (meta-test)."""
    screen = RecordingScreen()
    screen.text_blits.append(("AAA", 10, 10, 50, 20))
    screen.text_blits.append(("BBB", 30, 10, 50, 20))
    with pytest.raises(AssertionError, match="overlaps"):
        assert_no_text_overlap(screen)


def test_harness_tolerates_rerender():
    """Same text at the same position (HUD refresh) must not be flagged."""
    screen = RecordingScreen()
    screen.text_blits.append(("Score", 100, 100, 50, 20))
    screen.text_blits.append(("Score", 100, 100, 50, 20))
    assert_no_text_overlap(screen)
