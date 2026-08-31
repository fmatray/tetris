"""Tests for KeybindState: navigation, listening mode, conflicts, reset, draw."""

import json
import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

pygame.init()
pygame.mixer.init()

import pytest

from tetris.audio import AudioManager
from tetris.settings import DEFAULT_KEYBINDS, KEYBIND_LABELS, SETTINGS_PATH
from tetris.states.human_menu import HumanMenuState
from tetris.states.keybind import (
    _ACTIONS,
    _NUM_ENTRIES,
    _RESET_INDEX,
    KeybindState,
    key_name,
)
from tetris.states.menu import MenuState


# ── Helpers ─────────────────────────────────────────────────────────


def _reset_keybinds_file():
    """Write DEFAULT_KEYBINDS into settings.json (no-op if file absent)."""
    try:
        with open(SETTINGS_PATH) as f:
            data = json.load(f)
        data["keybinds"] = dict(DEFAULT_KEYBINDS)
        with open(SETTINGS_PATH, "w") as f:
            json.dump(data, f, indent=2)
    except (OSError, KeyError, json.JSONDecodeError):
        pass


@pytest.fixture(autouse=True)
def _restore_keybinds():
    """Reset keybinds in settings.json to defaults before and after each test."""
    _reset_keybinds_file()
    yield
    _reset_keybinds_file()


def _make_state():
    screen = pygame.Surface((640, 480))
    font = pygame.font.Font(None, 20)
    audio = AudioManager(sound_volume=0, music_volume=0)
    menu = MenuState(screen, font, audio)
    human_menu = HumanMenuState(screen, font, audio, menu)
    return KeybindState(screen, font, audio, human_menu)


def _key(key):
    """Build a KEYDOWN event for the given pygame key constant."""
    return pygame.event.Event(pygame.KEYDOWN, key=key)


# ── key_name ───────────────────────────────────────────────────────


def test_key_name_special_keys():
    """Special keys map to their English/arrow labels."""
    assert key_name(pygame.K_LEFT) == "←"
    assert key_name(pygame.K_RIGHT) == "→"
    assert key_name(pygame.K_UP) == "↑"
    assert key_name(pygame.K_DOWN) == "↓"
    assert key_name(pygame.K_SPACE) == "Space"
    assert key_name(pygame.K_RETURN) == "Enter"
    assert key_name(pygame.K_ESCAPE) == "Esc"
    assert key_name(pygame.K_TAB) == "Tab"
    assert key_name(pygame.K_BACKSPACE) == "Backspace"
    assert key_name(pygame.K_LSHIFT) == "L Shift"
    assert key_name(pygame.K_RSHIFT) == "R Shift"
    assert key_name(pygame.K_LCTRL) == "L Ctrl"
    assert key_name(pygame.K_RCTRL) == "R Ctrl"
    assert key_name(pygame.K_LALT) == "L Alt"
    assert key_name(pygame.K_RALT) == "R Alt"


def test_key_name_single_char_uppercased():
    """Single-char keys return their uppercase letter."""
    assert key_name(pygame.K_a) == "A"
    assert key_name(pygame.K_c) == "C"
    assert key_name(pygame.K_p) == "P"
    assert key_name(pygame.K_m) == "M"
    assert key_name(pygame.K_s) == "S"


def test_key_name_multi_char_passthrough():
    """Multi-char non-special keys pass through pygame.key.name unchanged."""
    assert key_name(pygame.K_F1) == "f1"
    assert key_name(pygame.K_F5) == "f5"


# ── Navigation ──────────────────────────────────────────────────────


def test_navigation_down_increments():
    """K_DOWN moves selection forward by one."""
    st = _make_state()
    assert st.selection == 0
    st.handle_event(_key(pygame.K_DOWN))
    assert st.selection == 1


def test_navigation_up_decrements():
    """K_UP moves selection backward by one."""
    st = _make_state()
    st.selection = 2
    st.handle_event(_key(pygame.K_UP))
    assert st.selection == 1


def test_navigation_wraps_down():
    """K_DOWN at last entry wraps to index 0."""
    st = _make_state()
    st.selection = _NUM_ENTRIES - 1
    st.handle_event(_key(pygame.K_DOWN))
    assert st.selection == 0


def test_navigation_wraps_up():
    """K_UP at index 0 wraps to the last entry."""
    st = _make_state()
    st.handle_event(_key(pygame.K_UP))
    assert st.selection == _NUM_ENTRIES - 1


def test_navigation_clears_conflict_msg():
    """Moving the selection clears any lingering conflict message."""
    st = _make_state()
    st._conflict_msg = "stale"
    st.handle_event(_key(pygame.K_DOWN))
    assert st._conflict_msg == ""


# ── Listening mode ──────────────────────────────────────────────────


def test_enter_listening_on_enter():
    """ENTER on an action enters listening mode."""
    st = _make_state()
    assert not st._listening
    st.handle_event(_key(pygame.K_RETURN))
    assert st._listening


def test_listening_rebinds_action():
    """After ENTER, the next non-reserved key rebinds the selected action."""
    st = _make_state()
    action = _ACTIONS[st.selection]  # move_left
    st.handle_event(_key(pygame.K_RETURN))
    assert st._listening
    st.handle_event(_key(pygame.K_q))
    assert not st._listening
    assert st._keybinds()[action] == pygame.K_q  # type: ignore[unreachable]


def test_listening_clears_conflict_msg():
    """Entering listening mode clears a stale conflict message."""
    st = _make_state()
    st._conflict_msg = "stale"
    st.handle_event(_key(pygame.K_RETURN))
    assert st._conflict_msg == ""


# ── Reserved key rejection ──────────────────────────────────────────


def test_reserved_key_rejected():
    """Pressing a reserved key while listening shows 'Reserved key'."""
    st = _make_state()
    st.handle_event(_key(pygame.K_RETURN))
    assert st._listening
    st.handle_event(_key(pygame.K_UP))
    assert not st._listening
    assert st._conflict_msg == "Reserved key"  # type: ignore[unreachable]


def test_reserved_key_left_rejected():
    """K_LEFT is also reserved and rejected during listening."""
    st = _make_state()
    st.handle_event(_key(pygame.K_RETURN))
    st.handle_event(_key(pygame.K_LEFT))
    assert not st._listening
    assert st._conflict_msg == "Reserved key"


def test_reserved_key_does_not_rebind():
    """A rejected reserved key must not change the keybind."""
    st = _make_state()
    action = _ACTIONS[st.selection]
    original = st._keybinds()[action]
    st.handle_event(_key(pygame.K_RETURN))
    st.handle_event(_key(pygame.K_DOWN))
    assert st._keybinds()[action] == original


# ── Conflict detection ──────────────────────────────────────────────


def test_conflict_detected():
    """Rebinding to a key already used by another action is rejected."""
    st = _make_state()
    # move_left is at index 0; 'hold' uses K_c (non-reserved) → conflict
    st.handle_event(_key(pygame.K_RETURN))  # listening for move_left
    st.handle_event(_key(pygame.K_c))  # already used by hold
    assert not st._listening
    assert "Used by" in st._conflict_msg
    assert st._keybinds()["move_left"] == pygame.K_LEFT


def test_conflict_message_names_the_action():
    """Conflict message includes the label of the conflicting action."""
    st = _make_state()
    st.handle_event(_key(pygame.K_RETURN))
    st.handle_event(_key(pygame.K_c))
    assert st._conflict_msg == f"Used by: {KEYBIND_LABELS['hold']}"


def test_conflict_does_not_rebind():
    """A conflicting key must not overwrite the original or the other action."""
    st = _make_state()
    st.handle_event(_key(pygame.K_RETURN))
    st.handle_event(_key(pygame.K_c))
    assert st._keybinds()["move_left"] == pygame.K_LEFT
    assert st._keybinds()["hold"] == pygame.K_c


# ── ESC ─────────────────────────────────────────────────────────────


def test_esc_returns_to_human_menu():
    """ESC while not listening returns the HumanMenuState."""
    st = _make_state()
    result = st.handle_event(_key(pygame.K_ESCAPE))
    assert result is st.human_menu


def test_esc_cancels_listening():
    """ESC while listening cancels rebinding and stays in KeybindState."""
    st = _make_state()
    st.handle_event(_key(pygame.K_RETURN))
    assert st._listening
    result = st.handle_event(_key(pygame.K_ESCAPE))
    assert not st._listening
    assert result is None  # type: ignore[unreachable]


def test_esc_cancel_does_not_rebind():
    """Canceling listening with ESC must not change the keybind."""
    st = _make_state()
    action = _ACTIONS[st.selection]
    original = st._keybinds()[action]
    st.handle_event(_key(pygame.K_RETURN))
    st.handle_event(_key(pygame.K_ESCAPE))
    assert st._keybinds()[action] == original


# ── Reset ───────────────────────────────────────────────────────────


def test_reset_index_is_last_entry():
    """The reset option sits at the last menu index."""
    assert _RESET_INDEX == _NUM_ENTRIES - 1


def test_enter_on_reset_restores_defaults():
    """Selecting 'Reset' restores DEFAULT_KEYBINDS."""
    st = _make_state()
    st._keybinds()["move_left"] = pygame.K_z
    st._keybinds()["move_right"] = pygame.K_x
    st.selection = _RESET_INDEX
    st.handle_event(_key(pygame.K_RETURN))
    assert st._keybinds() == dict(DEFAULT_KEYBINDS)


def test_reset_does_not_enter_listening():
    """Resetting does not put the state into listening mode."""
    st = _make_state()
    st.selection = _RESET_INDEX
    st.handle_event(_key(pygame.K_RETURN))
    assert not st._listening


def test_reset_clears_conflict_msg():
    """Resetting clears any conflict message."""
    st = _make_state()
    st._conflict_msg = "stale"
    st.selection = _RESET_INDEX
    st.handle_event(_key(pygame.K_RETURN))
    assert st._conflict_msg == ""


# ── Non-KEYDOWN events ──────────────────────────────────────────────


def test_non_keydown_event_ignored():
    """Non-KEYDOWN events return None and change nothing."""
    st = _make_state()
    result = st.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1))
    assert result is None
    assert st.selection == 0
    assert not st._listening


# ── Draw ────────────────────────────────────────────────────────────


def test_draw_normal_renders_without_error():
    """draw() renders the menu without raising."""
    st = _make_state()
    screen = pygame.Surface((640, 480))
    st.draw(screen)


def test_draw_listening_renders_without_error():
    """draw() renders listening mode (red '...' text) without raising."""
    st = _make_state()
    st.handle_event(_key(pygame.K_RETURN))
    screen = pygame.Surface((640, 480))
    st.draw(screen)


def test_draw_with_conflict_msg_renders():
    """draw() renders the conflict message line without raising."""
    st = _make_state()
    st._conflict_msg = "Reserved key"
    screen = pygame.Surface((640, 480))
    st.draw(screen)


def test_draw_reset_selected_renders():
    """draw() renders the reset option highlighted when selected."""
    st = _make_state()
    st.selection = _RESET_INDEX
    screen = pygame.Surface((640, 480))
    st.draw(screen)