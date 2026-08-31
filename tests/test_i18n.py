"""Tests for tetris.i18n: translation, fallback, catalogs, on-the-fly switching, language menu."""

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

pygame.init()
pygame.mixer.init()

import pytest

from tetris import i18n
from tetris.i18n import get_language, set_language, tr


@pytest.fixture(autouse=True)
def _english():
    set_language("en")
    yield
    set_language("en")


# ── tr / set_language ────────────────────────────────────────────────


def test_tr_english_is_passthrough():
    assert tr("Back") == "Back"


def test_tr_french():
    set_language("fr")
    assert tr("Back") == "Retour"


def test_tr_missing_key_falls_back_to_key():
    set_language("fr")
    assert tr("No such key") == "No such key"


def test_set_language_unknown_falls_back_to_english():
    set_language("xx")
    assert get_language() == "en"


def test_tr_format_placeholder():
    set_language("fr")
    assert tr("Games played: {}").format(5) == "Parties jouées : 5"


# ── Catalog consistency ─────────────────────────────────────────────


def test_catalogs_have_identical_keys():
    assert set(i18n._FR) == set(i18n._ES) == set(i18n._SL)


def test_catalogs_values_non_empty():
    for lang in (i18n._FR, i18n._ES, i18n._SL):
        for key, value in lang.items():
            assert isinstance(value, str) and value, (key, value)


def test_language_codes_match_names():
    assert i18n.LANGUAGES == {
        "en": "English",
        "fr": "Français",
        "es": "Español",
        "sl": "Slovenščina",
    }


# ── On-the-fly switching via menus ──────────────────────────────────


def _make_menu():
    from tetris.states.menu import MenuState
    from tetris.audio import AudioManager

    screen = pygame.Surface((640, 480))
    font = pygame.font.Font(None, 20)
    audio = AudioManager(sound_volume=0, music_volume=0)
    return MenuState(screen, font, audio)


def _make_state(cls, menu):
    from tetris.audio import AudioManager

    screen = pygame.Surface((640, 480))
    font = pygame.font.Font(None, 20)
    audio = AudioManager(sound_volume=0, music_volume=0)
    return cls(screen, font, audio, menu)


def test_menu_option_text_translates_on_the_fly():
    from tetris.states.ai_menu import AIMenuState

    menu = _make_menu()
    state = _make_state(AIMenuState, menu)
    text_en = state._option_text(2, False)
    assert "Training" in text_en
    set_language("fr")
    text_fr = state._option_text(2, False)
    assert "Apprentissage" in text_fr
    assert "Training" not in text_fr


def test_main_menu_player_value_display():
    menu = _make_menu()
    assert menu.player == "Humain"  # internal value untouched
    assert "Human" in menu._option_text(1, False)  # display translated
    set_language("fr")
    assert "Humain" in menu._option_text(1, False)


# ── LanguageMenuState ────────────────────────────────────────────────


def test_language_menu_options_and_codes():
    from tetris.states.language_menu import LanguageMenuState

    assert LanguageMenuState._OPTIONS == ("English", "Français", "Español", "Slovenščina", "Back")
    assert LanguageMenuState._LANG_CODES == ("en", "fr", "es", "sl")


def test_language_menu_toggle_sets_language_and_menu():
    from tetris.states.language_menu import LanguageMenuState

    menu = _make_menu()
    state = _make_state(LanguageMenuState, menu)
    state.selection = 1  # Français
    state._toggle(1)
    assert get_language() == "fr"
    assert menu.language == "fr"
    assert state._value_label(1) == "✓"
    assert state._value_label(0) == ""


def test_language_menu_select_persists_and_back_returns_menu(tmp_path, monkeypatch):
    from tetris.states.language_menu import LanguageMenuState

    monkeypatch.setattr("tetris.states.menu.SETTINGS_PATH", str(tmp_path / "s.json"))
    menu = _make_menu()
    state = _make_state(LanguageMenuState, menu)
    state.selection = 2  # Español
    state._on_select()
    assert get_language() == "es"
    state.selection = 4  # Back
    assert state._on_select() is menu
    # Fresh menu restores the persisted language
    menu2 = _make_menu()
    assert menu2.language == "es"
    assert get_language() == "es"


def test_menu_state_options_include_language():
    from tetris.states.menu import MenuState

    assert MenuState._OPTIONS[10] == "Language"
    assert MenuState._OPTIONS[11] == "Quit"


def test_menu_state_select_language_navigates():
    from tetris.states.language_menu import LanguageMenuState

    menu = _make_menu()
    menu.selection = 10
    result = menu._on_select()
    assert isinstance(result, LanguageMenuState)
