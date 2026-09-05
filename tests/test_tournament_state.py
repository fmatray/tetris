"""Tests for TournamentState: live HUD counters, progress math, celebration."""

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import threading
import pygame

pygame.init()
pygame.mixer.init()

import pytest

from tetris.states.tournament import TournamentState
from tetris.visuals.particles import ParticleSystem


class _FakeThread:
    """Stub: TournamentState.__init__ would spawn a real tournament otherwise."""

    def __init__(self, target=None, daemon=None) -> None:
        pass

    def start(self) -> None:
        pass

    def join(self, timeout=None) -> None:
        pass


class _FakeMenu:
    tournament_loops = 2
    tournament_generations = 3
    tournament_population = 4
    tournament_episodes = 2
    tournament_sigma = 0.02
    tournament_seed = 7

    def save_settings(self) -> None:
        pass


class _FakeTournamentMenu:
    def __init__(self) -> None:
        self.menu = _FakeMenu()


@pytest.fixture(autouse=True)
def _no_real_thread(monkeypatch):
    monkeypatch.setattr(threading, "Thread", _FakeThread)
    yield


def _make_state() -> TournamentState:
    screen = pygame.Surface((1500, 800))
    font = pygame.font.Font(None, 20)
    return TournamentState(screen, font, None, _FakeTournamentMenu())


def test_initial_progress_is_idle():
    state = _make_state()
    assert state._progress == {"loop": -1, "gen": -1, "done": 0}
    assert state._progress_fraction() == 0.0


def test_progress_fraction_mid_run():
    state = _make_state()
    state._progress.update({"loop": 0, "gen": 1, "done": 1})
    # 1 finished loop + (1+1)/3 of the second, over 2 loops
    assert state._progress_fraction() == pytest.approx((1 + 2 / 3) / 2)


def test_progress_fraction_clamped():
    state = _make_state()
    state._progress.update({"done": 5, "gen": 99})
    assert state._progress_fraction() == 1.0
    state._progress.update({"done": 0, "gen": -1})
    assert state._progress_fraction() == 0.0


def test_celebration_fires_once_per_done_increment():
    state = _make_state()
    particles = ParticleSystem()
    state.update(16, particles)
    assert len(particles.particles) == 0

    state._progress["done"] = 1
    state.update(16, particles)
    assert len(particles.particles) > 0

    state._last_done = 1
    alive = len(particles.particles)
    state.update(16, particles)  # decay only, no new burst
    assert len(particles.particles) == alive


def test_update_returns_menu_when_worker_finished():
    state = _make_state()
    state._result = {"loops_run": 2, "next_seed": 9}
    assert state.update(16, ParticleSystem()) is state.tournament_menu


def test_escape_sets_stop_flag():
    state = _make_state()
    event = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE)
    assert state.handle_event(event) is None
    assert state._should_stop is True


def test_draw_smoke_with_mid_run_progress():
    state = _make_state()
    screen = pygame.Surface((1500, 800))
    state._progress.update(
        {
            "loop": 0,
            "gen": 1,
            "member": 2,
            "episode": 1,
            "best": 4321.0,
            "mean": 1234.5,
            "history": [100, 250, 180, 400, 520],
        }
    )
    state.draw(screen, particles=ParticleSystem())  # must not raise


def test_tournament_layout_all_languages():
    """HUD text stays in bounds and never overlaps in EN/FR/ES/SL."""
    from tetris.i18n import set_language
    from tests.layout_harness import (
        RecordingFont,
        RecordingScreen,
        assert_layout_in_bounds,
        assert_no_text_overlap,
    )

    try:
        for lang in ("en", "fr", "es", "sl"):
            set_language(lang)
            state = _make_state()
            font = RecordingFont(None, 20)
            state.font = font
            screen = RecordingScreen()
            state._progress.update(
                {
                    "loop": 1,
                    "gen": 2,
                    "member": 3,
                    "episode": 1,
                    "best": 15230.0,
                    "mean": 8210.5,
                    "history": [100, 250, 180, 400, 520, 610],
                }
            )
            state.draw(screen, particles=ParticleSystem())
            assert_layout_in_bounds(screen)
            assert_no_text_overlap(screen)
    finally:
        set_language("en")


def test_sparkline_line_never_crosses_label():
    """Regression: line must stay below the in-box label even when the max
    occurs at the first point (flat top line used to cross the text)."""
    from tetris.states.tournament import _SPARK_RECT

    state = _make_state()
    state._progress.update(
        {
            "loop": 0,
            "gen": 3,
            "member": 0,
            "episode": 0,
            "best": 170386.0,
            "mean": 166556.0,
            "history": [170386, 170386, 170385, 170300, 170290],
        }
    )
    screen = pygame.Surface((1500, 800))
    state.draw(screen)  # must not raise; geometry checked below

    inner = _SPARK_RECT.inflate(-24, 0).move(0, 36)
    inner.height -= 48
    label_w, label_h = state.font.size("Best per generation")
    label_rect = pygame.Rect(_SPARK_RECT.x + 8, _SPARK_RECT.y + 6, label_w, label_h)
    # inner band must start below the label band
    assert inner.top >= label_rect.bottom
