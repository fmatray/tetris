"""Tests for the TournamentMenuState: options, toggles, disables, selects."""

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

pygame.init()
pygame.mixer.init()

import pytest

from tetris.states.ai_menu import AIMenuState
from tetris.states.menu import MenuState
from tetris.states.tournament import TournamentState
from tetris.states.tournament_menu import TournamentMenuState
from tetris.states.tournament_stats import TournamentStatsState
from tetris.settings import SETTINGS_PATH


@pytest.fixture(autouse=True)
def _isolate_settings():
    """Remove data/settings.json for each test so MenuState uses defaults."""
    saved = ""
    if os.path.exists(SETTINGS_PATH):
        with open(SETTINGS_PATH) as f:
            saved = f.read()
        os.remove(SETTINGS_PATH)
    try:
        yield
    finally:
        if saved:
            with open(SETTINGS_PATH, "w") as f:
                f.write(saved)


def _make_menu():
    screen = pygame.Surface((640, 480))
    font = pygame.font.Font(None, 20)
    from tetris.audio import AudioManager

    audio = AudioManager(sound_volume=0, music_volume=0)
    return MenuState(screen, font, audio)


def _make_ai_menu(menu):
    screen = pygame.Surface((640, 480))
    font = pygame.font.Font(None, 20)
    from tetris.audio import AudioManager

    audio = AudioManager(sound_volume=0, music_volume=0)
    return AIMenuState(screen, font, audio, menu)


def _make_state(menu):
    screen = pygame.Surface((1500, 800))
    font = pygame.font.Font(None, 20)
    from tetris.audio import AudioManager

    audio = AudioManager(sound_volume=0, music_volume=0)
    return TournamentMenuState(screen, font, audio, _make_ai_menu(menu))


# ── Options ──────────────────────────────────────────────────────────


def test_options_count_and_layout():
    assert len(TournamentMenuState._OPTIONS) == 10
    assert TournamentMenuState._toggle_indices == frozenset({1, 2, 3, 4, 5})
    assert TournamentMenuState._header_indices == frozenset({0})
    assert len(TournamentMenuState._PARAM_META) == 10


def test_defaults_from_menu():
    menu = _make_menu()
    state = _make_state(menu)
    assert state.menu.tournament_loops == 2
    assert state.menu.tournament_generations == 5
    assert state.menu.tournament_episodes == 3
    assert state.menu.tournament_population == 6
    assert state.menu.tournament_sigma == 0.02
    assert state.menu.tournament_seed == 1
    assert state.menu is menu


# ── Value labels ─────────────────────────────────────────────────────


def test_value_labels():
    menu = _make_menu()
    state = _make_state(menu)
    assert state._value_label(0) == ""  # header
    assert state._value_label(1) == "2"
    assert state._value_label(2) == "5"
    assert state._value_label(3) == "3"
    assert state._value_label(4) == "6"
    assert state._value_label(5) == "0.020"
    assert state._value_label(9) == ""


# ── Toggles + clamps ────────────────────────────────────────────────


def test_toggle_loops_clamps():
    menu = _make_menu()
    state = _make_state(menu)
    state.selection = 1
    state._toggle(1)
    assert menu.tournament_loops == 3
    menu.tournament_loops = 20
    state._toggle(1)
    assert menu.tournament_loops == 20  # clamped at max
    menu.tournament_loops = 1
    state._toggle(-1)
    assert menu.tournament_loops == 1  # clamped at min


def test_toggle_generations_clamps():
    menu = _make_menu()
    state = _make_state(menu)
    state.selection = 2
    state._toggle(-1)
    assert menu.tournament_generations == 4
    menu.tournament_generations = 20
    state._toggle(1)
    assert menu.tournament_generations == 20
    menu.tournament_generations = 1
    state._toggle(-1)
    assert menu.tournament_generations == 1


def test_toggle_episodes_clamps():
    menu = _make_menu()
    state = _make_state(menu)
    state.selection = 3
    state._toggle(1)
    assert menu.tournament_episodes == 4
    menu.tournament_episodes = 5
    state._toggle(1)
    assert menu.tournament_episodes == 5
    menu.tournament_episodes = 1
    state._toggle(-1)
    assert menu.tournament_episodes == 1


def test_toggle_population_step2_clamps():
    menu = _make_menu()
    state = _make_state(menu)
    state.selection = 4
    state._toggle(1)
    assert menu.tournament_population == 8
    state._toggle(-1)
    assert menu.tournament_population == 6
    menu.tournament_population = 12
    state._toggle(1)
    assert menu.tournament_population == 12
    menu.tournament_population = 2
    state._toggle(-1)
    assert menu.tournament_population == 2


def test_toggle_sigma_float_rounding():
    menu = _make_menu()
    state = _make_state(menu)
    state.selection = 5
    state._toggle(1)
    assert menu.tournament_sigma == 0.025
    assert state._value_label(5) == "0.025"
    menu.tournament_sigma = 0.10
    state._toggle(1)
    assert menu.tournament_sigma == 0.1  # clamped, no FP drift
    menu.tournament_sigma = 0.005
    state._toggle(-1)
    assert menu.tournament_sigma == 0.005


def test_toggle_persists_settings(tmp_path, monkeypatch):
    settings = tmp_path / "settings.json"
    monkeypatch.setattr("tetris.states.menu.SETTINGS_PATH", str(settings))
    menu = _make_menu()
    state = _make_state(menu)
    state.selection = 1
    state._toggle(1)
    state._save()
    import json

    with open(settings) as f:
        data = json.load(f)
    assert data["tournament_loops"] == 3


# ── Disabled logic ──────────────────────────────────────────────────


def test_disabled_stats_without_loops(monkeypatch, tmp_path):
    import tetris.states.tournament_menu as mod

    monkeypatch.setattr(mod, "TOURNAMENT_LOOPS_PATH", str(tmp_path / "loops.json"))
    menu = _make_menu()
    state = _make_state(menu)
    assert state._is_disabled(6) is True
    with open(tmp_path / "loops.json", "w") as f:
        f.write('[{"loop": 0, "best": 1.0, "mean": 1.0}]')
    assert state._is_disabled(6) is False


def test_disabled_restore_without_checkpoint(monkeypatch, tmp_path):
    import tetris.states.tournament_menu as mod

    monkeypatch.setattr(mod, "PRE_TOURNAMENT_PATH", str(tmp_path / "pre.pt"))
    menu = _make_menu()
    state = _make_state(menu)
    assert state._is_disabled(7) is True
    (tmp_path / "pre.pt").write_bytes(b"checkpoint")
    assert state._is_disabled(7) is False


def test_disabled_start_without_model(monkeypatch, tmp_path):
    import tetris.states.tournament_menu as mod

    monkeypatch.setattr(mod, "MODEL_PATH", str(tmp_path / "model.pt"))
    menu = _make_menu()
    state = _make_state(menu)
    assert state._is_disabled(8) is True
    (tmp_path / "model.pt").write_bytes(b"checkpoint")
    assert state._is_disabled(8) is False


def test_header_disabled():
    menu = _make_menu()
    state = _make_state(menu)
    assert state._is_disabled(0) is True


# ── Selects ──────────────────────────────────────────────────────────


def test_select_stats_returns_stats_state():
    menu = _make_menu()
    state = _make_state(menu)
    state.selection = 6
    result = state._on_select()
    assert isinstance(result, TournamentStatsState)
    assert result.tournament_menu is state


def test_select_back_returns_ai_menu():
    menu = _make_menu()
    state = _make_state(menu)
    state.selection = 9
    result = state._on_select()
    assert isinstance(result, AIMenuState)


def test_select_start_returns_tournament_state():
    menu = _make_menu()
    state = _make_state(menu)
    state.selection = 8
    result = state._on_select()
    assert isinstance(result, TournamentState)


def test_on_back_returns_ai_menu():
    menu = _make_menu()
    state = _make_state(menu)
    result = state._on_back()
    assert isinstance(result, AIMenuState)


# ── Restore confirm flow ─────────────────────────────────────────────


def test_restore_first_press_arms_without_copy(monkeypatch, tmp_path):
    import tetris.states.tournament_menu as mod

    pre = tmp_path / "pre.pt"
    model = tmp_path / "model.pt"
    pre.write_bytes(b"original")
    model.write_bytes(b"evolved")
    monkeypatch.setattr(mod, "PRE_TOURNAMENT_PATH", str(pre))
    monkeypatch.setattr(mod, "MODEL_PATH", str(model))

    menu = _make_menu()
    state = _make_state(menu)
    state.selection = 7
    result = state._on_select()
    assert result is None
    assert state._confirm_restore is True
    assert model.read_bytes() == b"evolved"  # no copy on first press


def test_restore_second_press_copies(monkeypatch, tmp_path):
    import tetris.states.tournament_menu as mod

    pre = tmp_path / "pre.pt"
    model = tmp_path / "model.pt"
    pre.write_bytes(b"original")
    model.write_bytes(b"evolved")
    monkeypatch.setattr(mod, "PRE_TOURNAMENT_PATH", str(pre))
    monkeypatch.setattr(mod, "MODEL_PATH", str(model))

    menu = _make_menu()
    state = _make_state(menu)
    state.selection = 7
    state._on_select()  # arm
    state._on_select()  # copy
    assert model.read_bytes() == b"original"
    assert state._confirm_restore is False


def test_restore_navigation_clears_confirm(monkeypatch, tmp_path):
    import tetris.states.tournament_menu as mod

    pre = tmp_path / "pre.pt"
    model = tmp_path / "model.pt"
    pre.write_bytes(b"original")
    model.write_bytes(b"evolved")
    monkeypatch.setattr(mod, "PRE_TOURNAMENT_PATH", str(pre))
    monkeypatch.setattr(mod, "MODEL_PATH", str(model))

    menu = _make_menu()
    state = _make_state(menu)
    state.selection = 7
    state._on_select()  # arm
    state._on_navigate()
    assert state._confirm_restore is False
    # Pressing select after disarm re-arms instead of copying
    state._on_select()
    assert model.read_bytes() == b"evolved"
    assert state._confirm_restore is True


# ── Draw ─────────────────────────────────────────────────────────────


def test_draw_no_error():
    menu = _make_menu()
    state = _make_state(menu)
    screen = pygame.Surface((1500, 800))
    state.draw(screen)


# ── Layout / i18n ────────────────────────────────────────────────────


def test_menu_layout_all_languages():
    """Regression: tournament menu text stays in bounds in EN/FR/ES/SL.

    Uses RecordingFont to catch untranslated strings (wider than expected)
    and off-screen overflow of the explanation column."""
    from tests.layout_harness import (
        RecordingFont,
        RecordingScreen,
        assert_layout_in_bounds,
        assert_no_text_overlap,
    )
    from tetris.i18n import set_language
    from tetris.audio import AudioManager

    menu = _make_menu()
    try:
        for lang in ("en", "fr", "es", "sl"):
            set_language(lang)
            screen = RecordingScreen()
            font = RecordingFont(None, 20)
            audio = AudioManager(sound_volume=0, music_volume=0)
            state = TournamentMenuState(screen, font, audio, _make_ai_menu(menu))
            state.draw(screen)
            assert_layout_in_bounds(screen)
            assert_no_text_overlap(screen)
            # no string may render as its English key in a non-English catalog
            if lang != "en":
                texts = [b[0] if isinstance(b, tuple) else "" for b in screen.text_blits]
                assert "TOURNAMENT" not in texts
    finally:
        set_language("en")
