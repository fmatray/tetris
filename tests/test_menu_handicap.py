"""Tests that handicap lives in GameRulesMenuState, not HumanMenuState."""

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

pygame.init()
pygame.mixer.init()

from tetris.audio import AudioManager
from tetris.states.game_rules_menu import GameRulesMenuState
from tetris.states.human_menu import HumanMenuState
from tetris.states.menu import MenuState


def _make_menu():
    screen = pygame.Surface((640, 480))
    font = pygame.font.Font(None, 24)
    audio = AudioManager(sound_volume=0, music_volume=0)
    return MenuState(screen, font, audio)


def _make_state(cls, menu):
    screen = pygame.Surface((640, 480))
    font = pygame.font.Font(None, 24)
    audio = AudioManager(sound_volume=0, music_volume=0)
    return cls(screen, font, audio, menu)


# ── GameRulesMenuState ───────────────────────────────────────────────


def test_game_rules_options_include_handicap():
    assert "Handicap" in GameRulesMenuState._OPTIONS


def test_game_rules_handicap_toggle_index():
    """Handicap is at index 2 and is a toggle."""
    assert 2 in GameRulesMenuState._toggle_indices


def test_game_rules_handicap_value_label():
    menu = _make_menu()
    menu.handicap = 3
    state = _make_state(GameRulesMenuState, menu)
    idx = GameRulesMenuState._OPTIONS.index("Handicap")
    assert state._value_label(idx) == "3"


def test_game_rules_handicap_toggle_up():
    menu = _make_menu()
    menu.handicap = 2
    state = _make_state(GameRulesMenuState, menu)
    state.selection = GameRulesMenuState._OPTIONS.index("Handicap")
    state._toggle(1)
    assert menu.handicap == 3


def test_game_rules_handicap_toggle_down():
    menu = _make_menu()
    menu.handicap = 2
    state = _make_state(GameRulesMenuState, menu)
    state.selection = GameRulesMenuState._OPTIONS.index("Handicap")
    state._toggle(-1)
    assert menu.handicap == 1


def test_game_rules_handicap_clamp_zero():
    menu = _make_menu()
    menu.handicap = 0
    state = _make_state(GameRulesMenuState, menu)
    state.selection = GameRulesMenuState._OPTIONS.index("Handicap")
    state._toggle(-1)
    assert menu.handicap == 0


def test_game_rules_handicap_clamp_five():
    menu = _make_menu()
    menu.handicap = 5
    state = _make_state(GameRulesMenuState, menu)
    state.selection = GameRulesMenuState._OPTIONS.index("Handicap")
    state._toggle(1)
    assert menu.handicap == 5


def test_game_rules_handicap_select_does_not_navigate():
    """Selecting Handicap toggles it, doesn't leave the menu."""
    menu = _make_menu()
    menu.handicap = 1
    state = _make_state(GameRulesMenuState, menu)
    state.selection = GameRulesMenuState._OPTIONS.index("Handicap")
    result = state._on_select()
    assert result is None
    assert menu.handicap == 2


def test_game_rules_retour_is_last_option():
    assert GameRulesMenuState._OPTIONS[-1] == "Retour"


def test_game_rules_retour_navigates_back():
    menu = _make_menu()
    state = _make_state(GameRulesMenuState, menu)
    state.selection = GameRulesMenuState._OPTIONS.index("Retour")
    result = state._on_select()
    assert result is menu


def test_game_rules_options_include_ghost():
    assert "Fantôme" in GameRulesMenuState._OPTIONS


def test_game_rules_ghost_toggle_index():
    """Ghost piece is a toggle."""
    idx = GameRulesMenuState._OPTIONS.index("Fantôme")
    assert idx in GameRulesMenuState._toggle_indices


def test_game_rules_ghost_value_label():
    menu = _make_menu()
    menu.ghost_piece = True
    state = _make_state(GameRulesMenuState, menu)
    idx = GameRulesMenuState._OPTIONS.index("Fantôme")
    assert state._value_label(idx) == "ON"
    menu.ghost_piece = False
    assert state._value_label(idx) == "OFF"


def test_game_rules_ghost_toggle_on():
    menu = _make_menu()
    menu.ghost_piece = False
    state = _make_state(GameRulesMenuState, menu)
    state.selection = GameRulesMenuState._OPTIONS.index("Fantôme")
    state._toggle(1)
    assert menu.ghost_piece is True


def test_game_rules_ghost_toggle_off():
    menu = _make_menu()
    menu.ghost_piece = True
    state = _make_state(GameRulesMenuState, menu)
    state.selection = GameRulesMenuState._OPTIONS.index("Fantôme")
    state._toggle(-1)
    assert menu.ghost_piece is False


def test_human_menu_no_ghost_option():
    assert "Fantôme" not in HumanMenuState._OPTIONS


# ── HumanMenuState ──────────────────────────────────────────────────


def test_human_menu_no_handicap_option():
    assert "Handicap" not in HumanMenuState._OPTIONS


def test_human_menu_options():
    assert HumanMenuState._OPTIONS == (
        "Mode",
        "Touches",
        "Statistiques",
        "Retour",
    )


def test_human_menu_toggle_indices():
    """Only Mode (0) is toggleable."""
    assert HumanMenuState._toggle_indices == frozenset({0})


def test_human_menu_keybind_index():
    """Keybinds is at index 1."""
    assert HumanMenuState._OPTIONS.index("Touches") == 1


def test_human_menu_stats_index():
    """Stats is at index 2."""
    assert HumanMenuState._OPTIONS.index("Statistiques") == 2


def test_human_menu_retour_index():
    """Retour is at index 3."""
    assert HumanMenuState._OPTIONS.index("Retour") == 3


def test_human_menu_keybind_navigates():
    menu = _make_menu()
    state = _make_state(HumanMenuState, menu)
    state.selection = HumanMenuState._OPTIONS.index("Touches")
    result = state._on_select()
    assert result is not None
    assert result is not state


def test_human_menu_stats_navigates():
    menu = _make_menu()
    state = _make_state(HumanMenuState, menu)
    state.selection = HumanMenuState._OPTIONS.index("Statistiques")
    result = state._on_select()
    assert result is not None
    assert result is not state


def test_human_menu_retour_navigates_back():
    menu = _make_menu()
    state = _make_state(HumanMenuState, menu)
    state.selection = HumanMenuState._OPTIONS.index("Retour")
    result = state._on_select()
    assert result is menu
