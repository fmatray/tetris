"""Tests for TournamentStatsState: table values, graph, missing-file safety."""

import json
import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

pygame.init()
pygame.mixer.init()

import pytest

import tetris.states.tournament_stats as mod
from tetris.states.tournament_stats import TournamentStatsState


@pytest.fixture(autouse=True)
def _isolated_loops_path(tmp_path, monkeypatch):
    """Point the stats state at a temp loops.json."""
    loops = tmp_path / "loops.json"
    monkeypatch.setattr(mod, "TOURNAMENT_LOOPS_PATH", str(loops))
    return loops


def _make_state():
    screen = pygame.Surface((1500, 800))
    font = pygame.font.Font(None, 20)
    from tetris.audio import AudioManager

    audio = AudioManager(sound_volume=0, music_volume=0)
    return TournamentStatsState(screen, font, audio, tournament_menu=None)


def _entry(loop: int, best: float, mean: float, seed: int) -> dict:
    return {
        "loop": loop,
        "seed": seed,
        "best": best,
        "mean": mean,
        "elapsed_s": 1.0,
        "timestamp": "2026-01-01T00:00:00",
    }

_THREE_ENTRIES = [
    _entry(0, 100.0, 50.0, 1),
    _entry(1, 300.0, 200.0, 2),
    _entry(2, 200.0, 150.0, 3),
]


def test_missing_file_placeholders_no_crash():
    state = _make_state()
    screen = pygame.Surface((1500, 800))
    state.draw(screen)  # builds entries; missing file must not raise
    assert state._stat_values() == ["—"] * 6
    assert state._surface is None


def test_invalid_json_placeholders_no_crash(_isolated_loops_path):
    _isolated_loops_path.write_text("{not json")
    state = _make_state()
    screen = pygame.Surface((1500, 800))
    state.draw(screen)
    assert state._stat_values() == ["—"] * 6


def test_three_entries_stat_values(_isolated_loops_path):
    entries = [
        _entry(0, 100.0, 50.0, 1),
        _entry(1, 300.0, 200.0, 2),
        _entry(2, 200.0, 150.0, 3),
    ]
    _isolated_loops_path.write_text(json.dumps(entries))
    state = _make_state()
    state._load_entries()
    values = state._stat_values()
    assert values == ["3", "300", "200", "150", "3", "4"]


def test_graph_surface_built_with_entries(_isolated_loops_path):
    entries = _THREE_ENTRIES
    _isolated_loops_path.write_text(json.dumps(entries))
    state = _make_state()
    screen = pygame.Surface((1500, 800))
    state.draw(screen)
    assert state._surface is not None


def test_any_key_returns_parent():
    state = _make_state()
    parent = object()
    state.tournament_menu = parent
    event = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN)
    assert state.handle_event(event) is parent

def test_graph_is_narrow_enough_for_text(_isolated_loops_path):
    """800px graph at gx=670 must clear the widest stat line (FR ~480px at x=60)."""
    entries = _THREE_ENTRIES
    _isolated_loops_path.write_text(json.dumps(entries))
    state = _make_state()
    state._load_entries()
    state._build_surface()
    assert state._surface is not None
    gx = 1500 - state._surface.get_width() - 30
    assert gx >= 670  # leaves >=130px margin past the widest text


def test_stats_layout_all_languages(_isolated_loops_path):
    """Text blits stay in bounds and never overlap in EN/FR/ES/SL."""
    from tetris.i18n import set_language
    from tests.layout_harness import (
        RecordingFont,
        RecordingScreen,
        assert_layout_in_bounds,
        assert_no_text_overlap,
    )

    entries = _THREE_ENTRIES
    _isolated_loops_path.write_text(json.dumps(entries))
    try:
        for lang in ("en", "fr", "es", "sl"):
            set_language(lang)
            font = RecordingFont(None, 20)
            screen = RecordingScreen()
            state = TournamentStatsState(screen, font, None, tournament_menu=None)
            state.draw(screen)
            assert_layout_in_bounds(screen)
            assert_no_text_overlap(screen)
    finally:
        set_language("en")
