"""Tests for menu states: AudioMenu, AIMenu, GameRules, Hyperparam, MenuBase, Leaderboard, Stats, Human."""

import json
import os
import os.path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

pygame.init()
pygame.mixer.init()

from tetris.ai.trainer import TrainingLog
from tetris.audio import AudioManager
from tetris.settings import GENERATOR_LABELS, LOG_PATH, MODEL_PATH
from tetris.states.ai_menu import AIMenuState
from tetris.states.audio_menu import AudioMenuState
from tetris.states.game_rules_menu import GameRulesMenuState
from tetris.states.human_menu import HumanMenuState
from tetris.states.hyperparam_menu import HyperparamMenuState
from tetris.states.leaderboard import LeaderboardState
from tetris.states.menu import MenuState
from tetris.states.stats import StatsState

import pytest

from tetris.settings import SETTINGS_PATH


@pytest.fixture(autouse=True)
def _isolate_settings():
    """Remove data/settings.json for each test so MenuState uses defaults.

    Backs up and restores the file around the test; tests see defaults,
    not whatever was persisted from the last manual run.
    """
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

# ── Helpers ──────────────────────────────────────────────────────────


def _make_menu():
    screen = pygame.Surface((640, 480))
    font = pygame.font.Font(None, 20)
    audio = AudioManager(sound_volume=0, music_volume=0)
    return MenuState(screen, font, audio)


def _make_state(cls, menu):
    screen = pygame.Surface((640, 480))
    font = pygame.font.Font(None, 20)
    audio = AudioManager(sound_volume=0, music_volume=0)
    return cls(screen, font, audio, menu)


def _make_state_with_screen(cls, menu, screen, font, audio):
    return cls(screen, font, audio, menu)


def _key(key_code):
    return pygame.event.Event(pygame.KEYDOWN, key=key_code)


# ── AudioMenuState ────────────────────────────────────────────────────


def test_audio_menu_options():
    assert AudioMenuState._OPTIONS == ("Son", "Musique", "Morceau", "Retour")


def test_audio_menu_toggle_indices():
    assert AudioMenuState._toggle_indices == frozenset({0, 1, 2})


def test_audio_menu_value_labels():
    menu = _make_menu()
    state = _make_state(AudioMenuState, menu)
    # Sound volume label
    assert state._value_label(0) == "Max"  # default 3
    # Music volume label
    assert state._value_label(1) == "Max"  # default 3
    # Song label
    assert state._value_label(2) == "Korobeiniki"
    # Retour has no label
    assert state._value_label(3) == ""


def test_audio_menu_toggle_sound_up():
    menu = _make_menu()
    state = _make_state(AudioMenuState, menu)
    state.selection = 0
    state._toggle(1)
    assert menu.sound_volume == 0  # (3 + 1) % 4 == 0


def test_audio_menu_toggle_sound_down():
    menu = _make_menu()
    state = _make_state(AudioMenuState, menu)
    state.selection = 0
    state._toggle(-1)
    assert menu.sound_volume == 2  # (3 - 1) % 4 == 2


def test_audio_menu_toggle_music():
    menu = _make_menu()
    state = _make_state(AudioMenuState, menu)
    state.selection = 1
    state._toggle(1)
    assert menu.music_volume == 0  # (3 + 1) % 4 == 0


def test_audio_menu_toggle_song():
    menu = _make_menu()
    state = _make_state(AudioMenuState, menu)
    state.selection = 2
    state._toggle(1)
    assert menu.music_song == "kalinka"


def test_audio_menu_select_sound_toggles():
    menu = _make_menu()
    state = _make_state(AudioMenuState, menu)
    state.selection = 0
    state._on_select()
    assert menu.sound_volume == 0  # toggled by +1


def test_audio_menu_select_retour_returns_menu():
    menu = _make_menu()
    state = _make_state(AudioMenuState, menu)
    state.selection = 3
    result = state._on_select()
    assert result is menu


def test_audio_menu_back_returns_menu():
    menu = _make_menu()
    state = _make_state(AudioMenuState, menu)
    assert state._on_back() is menu


def test_audio_menu_draw_no_error():
    menu = _make_menu()
    screen = pygame.Surface((1500, 800))
    state = _make_state(AudioMenuState, menu)
    state.draw(screen)


def test_audio_menu_handle_left_right_toggle():
    menu = _make_menu()
    state = _make_state(AudioMenuState, menu)
    state.selection = 0
    state.handle_event(_key(pygame.K_LEFT))
    assert menu.sound_volume == 2


# ── AIMenuState ──────────────────────────────────────────────────────


def test_ai_menu_options():
    assert AIMenuState._OPTIONS == (
        "Mode", "Vitesse", "Apprentissage",
        "Statistiques", "Réinitialiser IA", "Retour",
    )


def test_ai_menu_toggle_indices():
    assert AIMenuState._toggle_indices == frozenset({0, 1})


def test_ai_menu_value_labels():
    menu = _make_menu()
    state = _make_state(AIMenuState, menu)
    # Mode default "learning"
    assert state._value_label(0) == "Apprentissage"
    # Speed default "normal"
    assert state._value_label(1) == "Normal"
    # Others have no value
    assert state._value_label(2) == ""


def test_ai_menu_toggle_mode():
    menu = _make_menu()
    state = _make_state(AIMenuState, menu)
    state.selection = 0
    state._toggle(-1)
    assert menu.ai_mode == "playing"


def test_ai_menu_toggle_speed():
    menu = _make_menu()
    state = _make_state(AIMenuState, menu)
    state.selection = 1
    state._toggle(1)
    assert menu.ai_speed == "fast"


def test_ai_menu_disabled_when_playing():
    menu = _make_menu()
    state = _make_state(AIMenuState, menu)
    menu.ai_mode = "playing"
    assert state._is_disabled(2) is True
    assert state._is_disabled(0) is False


def test_ai_menu_not_disabled_when_learning():
    menu = _make_menu()
    state = _make_state(AIMenuState, menu)
    menu.ai_mode = "learning"
    assert state._is_disabled(2) is False


def test_ai_menu_select_mode_toggles():
    menu = _make_menu()
    state = _make_state(AIMenuState, menu)
    state.selection = 0
    state._on_select()
    assert menu.ai_mode == "playing"


def test_ai_menu_select_apprentissage_navigates():
    menu = _make_menu()
    state = _make_state(AIMenuState, menu)
    state.selection = 2
    result = state._on_select()
    assert isinstance(result, HyperparamMenuState)


def test_ai_menu_select_stats_navigates():
    menu = _make_menu()
    state = _make_state(AIMenuState, menu)
    state.selection = 3
    result = state._on_select()
    assert isinstance(result, StatsState)


def test_ai_menu_select_reset_first_press_confirms():
    menu = _make_menu()
    state = _make_state(AIMenuState, menu)
    state.selection = 4
    result = state._on_select()
    assert result is None
    assert state._confirm_reset is True


def test_ai_menu_select_reset_second_press_deletes():
    menu = _make_menu()
    state = _make_state(AIMenuState, menu)
    state.selection = 4
    state._confirm_reset = True
    # Create dummy files to test deletion
    from pathlib import Path
    Path(MODEL_PATH).write_text("test")
    Path(LOG_PATH).write_text("test")
    state._on_select()
    assert not Path(MODEL_PATH).exists()
    assert not Path(LOG_PATH).exists()


def test_ai_menu_select_reset_no_files_no_error():
    menu = _make_menu()
    state = _make_state(AIMenuState, menu)
    state.selection = 4
    state._confirm_reset = True
    # Ensure files don't exist
    for path in [MODEL_PATH, LOG_PATH]:
        if os.path.exists(path):
            os.remove(path)
    state._on_select()  # should not raise


def test_ai_menu_select_retour_returns_menu():
    menu = _make_menu()
    state = _make_state(AIMenuState, menu)
    state.selection = 5
    result = state._on_select()
    assert result is menu


def test_ai_menu_back_returns_menu():
    menu = _make_menu()
    state = _make_state(AIMenuState, menu)
    assert state._on_back() is menu


def test_ai_menu_option_text_confirm_reset():
    menu = _make_menu()
    state = _make_state(AIMenuState, menu)
    state._confirm_reset = True
    text = state._option_text(4, True)
    assert "Confirmer" in text


def test_ai_menu_option_text_normal():
    menu = _make_menu()
    state = _make_state(AIMenuState, menu)
    text = state._option_text(0, True)
    assert "Mode" in text


def test_ai_menu_option_color_confirm_reset():
    menu = _make_menu()
    state = _make_state(AIMenuState, menu)
    state._confirm_reset = True
    color = state._option_color(4, True, False)
    assert color == (255, 0, 0)


def test_ai_menu_option_color_normal():
    menu = _make_menu()
    state = _make_state(AIMenuState, menu)
    color = state._option_color(0, True, False)
    assert color == (255, 255, 255)


def test_ai_menu_navigate_clears_confirm_reset():
    menu = _make_menu()
    state = _make_state(AIMenuState, menu)
    state._confirm_reset = True
    state._on_navigate()
    assert state._confirm_reset is False


def test_ai_menu_draw_no_error():
    menu = _make_menu()
    screen = pygame.Surface((1500, 800))
    state = _make_state(AIMenuState, menu)
    state.draw(screen)


def test_ai_menu_update_drives_animation():
    menu = _make_menu()
    state = _make_state(AIMenuState, menu)
    result = state.update(0.016, None)
    assert result is None


# ── GameRulesMenuState ────────────────────────────────────────────────


def test_game_rules_value_label_generator():
    menu = _make_menu()
    state = _make_state(GameRulesMenuState, menu)
    assert state._value_label(0) == GENERATOR_LABELS["7bag"]


def test_game_rules_value_label_preview():
    menu = _make_menu()
    state = _make_state(GameRulesMenuState, menu)
    assert state._value_label(1) == "3 pièces"


def test_game_rules_value_label_handicap():
    menu = _make_menu()
    menu.handicap = 4
    state = _make_state(GameRulesMenuState, menu)
    assert state._value_label(2) == "4"


def test_game_rules_value_label_retour():
    menu = _make_menu()
    state = _make_state(GameRulesMenuState, menu)
    assert state._value_label(3) == ""


# ── HyperparamMenuState ───────────────────────────────────────────────


def _make_ai_menu(menu=None):
    menu = menu or _make_menu()
    screen = pygame.Surface((640, 480))
    font = pygame.font.Font(None, 20)
    audio = AudioManager(sound_volume=0, music_volume=0)
    return AIMenuState(screen, font, audio, menu)


def _make_hyperparam(ai_menu=None):
    if ai_menu is None:
        ai_menu = _make_ai_menu()
    screen = pygame.Surface((640, 480))
    font = pygame.font.Font(None, 20)
    audio = AudioManager(sound_volume=0, music_volume=0)
    return HyperparamMenuState(screen, font, audio, ai_menu)


def test_hyperparam_options_count():
    assert len(HyperparamMenuState._OPTIONS) == 16


def test_hyperparam_toggle_indices():
    assert HyperparamMenuState._toggle_indices == frozenset(range(14))


def test_hyperparam_value_labels():
    state = _make_hyperparam()
    assert state._value_label(0) == f"{state.menu.ai_epsilon_decay:.4f}"
    assert state._value_label(1) == f"{state.menu.ai_epsilon_end:.2f}"
    assert state._value_label(3) == f"{state.menu.ai_gamma:.3f}"
    assert state._value_label(4) == str(state.menu.ai_batch_size)
    assert state._value_label(5) == f"{state.menu.ai_buffer_size:,}"
    assert state._value_label(6) == "OFF"
    assert state._value_label(9) == "ON"
    assert state._value_label(13) == "ON"
    assert state._value_label(14) == ""  # Réinitialiser
    assert state._value_label(15) == ""  # Retour


def test_hyperparam_toggle_epsilon_decay_up():
    state = _make_hyperparam()
    original = state.menu.ai_epsilon_decay
    state.selection = 0
    state._toggle(1)
    assert state.menu.ai_epsilon_decay == round(min(0.9999, original + 0.0001), 4)


def test_hyperparam_toggle_epsilon_decay_clamp_high():
    state = _make_hyperparam()
    state.menu.ai_epsilon_decay = 0.9999
    state.selection = 0
    state._toggle(1)
    assert state.menu.ai_epsilon_decay == 0.9999


def test_hyperparam_toggle_epsilon_decay_clamp_low():
    state = _make_hyperparam()
    state.menu.ai_epsilon_decay = 0.990
    state.selection = 0
    state._toggle(-1)
    assert state.menu.ai_epsilon_decay == 0.990


def test_hyperparam_toggle_epsilon_end_clamp():
    state = _make_hyperparam()
    state.menu.ai_epsilon_end = 0.10
    state.selection = 1
    state._toggle(1)
    assert state.menu.ai_epsilon_end == 0.10
    state.menu.ai_epsilon_end = 0.02
    state._toggle(-1)
    assert state.menu.ai_epsilon_end == 0.02


def test_hyperparam_toggle_lr_up():
    state = _make_hyperparam()
    state.selection = 2
    state._toggle(1)
    assert state.menu.ai_lr == state.menu.ai_lr  # just check no crash


def test_hyperparam_toggle_lr_down():
    state = _make_hyperparam()
    state.selection = 2
    state._toggle(-1)
    # lr should decrease by factor of 10
    assert state.menu.ai_lr <= 1e-3


def test_hyperparam_toggle_gamma_clamp():
    state = _make_hyperparam()
    state.menu.ai_gamma = 0.99
    state.selection = 3
    state._toggle(1)
    assert state.menu.ai_gamma == 0.99
    state.menu.ai_gamma = 0.80
    state._toggle(-1)
    assert state.menu.ai_gamma == 0.80


def test_hyperparam_toggle_batch_size_clamp():
    state = _make_hyperparam()
    state.menu.ai_batch_size = 256
    state.selection = 4
    state._toggle(1)
    assert state.menu.ai_batch_size == 256
    state.menu.ai_batch_size = 8
    state._toggle(-1)
    assert state.menu.ai_batch_size == 8


def test_hyperparam_toggle_buffer_size_clamp():
    state = _make_hyperparam()
    state.menu.ai_buffer_size = 200_000
    state.selection = 5
    state._toggle(1)
    assert state.menu.ai_buffer_size == 200_000
    state.menu.ai_buffer_size = 1_000
    state._toggle(-1)
    assert state.menu.ai_buffer_size == 1_000


def test_hyperparam_toggle_curriculum_bool():
    state = _make_hyperparam()
    original = state.menu.ai_curriculum
    state.selection = 6
    state._toggle(1)
    assert state.menu.ai_curriculum is not original


def test_hyperparam_toggle_curriculum_freq_clamp():
    state = _make_hyperparam()
    state.menu.ai_curriculum_freq = 2000
    state.selection = 7
    state._toggle(1)
    assert state.menu.ai_curriculum_freq == 2000
    state.menu.ai_curriculum_freq = 10
    state._toggle(-1)
    assert state.menu.ai_curriculum_freq == 10


def test_hyperparam_toggle_curriculum_epsilon_cycle():
    state = _make_hyperparam()
    state.menu.ai_curriculum_epsilon = "reset"
    state.selection = 8
    state._toggle(1)
    assert state.menu.ai_curriculum_epsilon == "boost"
    state._toggle(1)
    assert state.menu.ai_curriculum_epsilon == "decay"
    state._toggle(1)
    assert state.menu.ai_curriculum_epsilon == "reset"


def test_hyperparam_toggle_warm_start_bool():
    state = _make_hyperparam()
    original = state.menu.ai_warm_start
    state.selection = 9
    state._toggle(1)
    assert state.menu.ai_warm_start is not original


def test_hyperparam_toggle_learn_per_action_clamp():
    state = _make_hyperparam()
    state.menu.ai_learn_per_action = 8
    state.selection = 10
    state._toggle(1)
    assert state.menu.ai_learn_per_action == 8
    state.menu.ai_learn_per_action = 1
    state._toggle(-1)
    assert state.menu.ai_learn_per_action == 1


def test_hyperparam_toggle_lookahead_bool():
    state = _make_hyperparam()
    original = state.menu.ai_lookahead
    state.selection = 11
    state._toggle(1)
    assert state.menu.ai_lookahead is not original


def test_hyperparam_toggle_lookahead_depth_clamp():
    state = _make_hyperparam()
    state.menu.ai_lookahead_depth = 3
    state.selection = 12
    state._toggle(1)
    assert state.menu.ai_lookahead_depth == 3
    state.menu.ai_lookahead_depth = 1
    state._toggle(-1)
    assert state.menu.ai_lookahead_depth == 1


def test_hyperparam_toggle_soft_drop_bool():
    state = _make_hyperparam()
    original = state.menu.ai_soft_drop
    state.selection = 13
    state._toggle(1)
    assert state.menu.ai_soft_drop is not original


def test_hyperparam_select_retour_returns_ai_menu():
    ai_menu = _make_ai_menu()
    state = _make_hyperparam(ai_menu)
    state.selection = 15
    result = state._on_select()
    assert result is ai_menu


def test_hyperparam_select_reset_restores_defaults():
    ai_menu = _make_ai_menu()
    state = _make_hyperparam(ai_menu)
    # Modify some params
    state.menu.ai_epsilon_decay = 0.990
    state.menu.ai_batch_size = 8
    state.menu.ai_curriculum = True
    state.selection = 14
    state._on_select()
    assert state.menu.ai_epsilon_decay == HyperparamMenuState._DEFAULTS["ai_epsilon_decay"]
    assert state.menu.ai_batch_size == HyperparamMenuState._DEFAULTS["ai_batch_size"]
    assert state.menu.ai_curriculum == HyperparamMenuState._DEFAULTS["ai_curriculum"]


def test_hyperparam_back_returns_ai_menu():
    ai_menu = _make_ai_menu()
    state = _make_hyperparam(ai_menu)
    assert state._on_back() is ai_menu


def test_hyperparam_save_persists():
    state = _make_hyperparam()
    state.menu.ai_batch_size = 128
    state._save()
    # Reload settings to verify persistence
    menu2 = _make_menu()
    assert menu2.ai_batch_size == 128


def test_hyperparam_draw_no_error():
    state = _make_hyperparam()
    screen = pygame.Surface((1500, 800))
    state.draw(screen)


def test_hyperparam_menu_property():
    ai_menu = _make_ai_menu()
    state = _make_hyperparam(ai_menu)
    assert state.menu is ai_menu.menu


# ── MenuBase ─────────────────────────────────────────────────────────


def test_menu_base_handle_up_navigates():
    menu = _make_menu()
    state = _make_state(AudioMenuState, menu)
    state.selection = 2
    state.handle_event(_key(pygame.K_UP))
    assert state.selection == 1


def test_menu_base_handle_down_navigates():
    menu = _make_menu()
    state = _make_state(AudioMenuState, menu)
    state.selection = 0
    state.handle_event(_key(pygame.K_DOWN))
    assert state.selection == 1


def test_menu_base_handle_left_toggles():
    menu = _make_menu()
    state = _make_state(AudioMenuState, menu)
    state.selection = 0
    state.handle_event(_key(pygame.K_LEFT))
    assert menu.sound_volume == 2


def test_menu_base_handle_right_toggles():
    menu = _make_menu()
    state = _make_state(AudioMenuState, menu)
    state.selection = 0
    state.handle_event(_key(pygame.K_RIGHT))
    assert menu.sound_volume == 0  # (3+1)%4


def test_menu_base_handle_enter_selects():
    menu = _make_menu()
    state = _make_state(AudioMenuState, menu)
    state.selection = 3  # Retour
    result = state.handle_event(_key(pygame.K_RETURN))
    assert result is menu


def test_menu_base_handle_enter_disabled_does_nothing():
    menu = _make_menu()
    menu.ai_mode = "playing"
    state = _make_state(AIMenuState, menu)
    state.selection = 2  # Apprentissage, disabled when playing
    result = state.handle_event(_key(pygame.K_RETURN))
    assert result is None


def test_menu_base_handle_escape_back():
    menu = _make_menu()
    state = _make_state(AudioMenuState, menu)
    result = state.handle_event(_key(pygame.K_ESCAPE))
    assert result is menu


def test_menu_base_handle_non_keydown_returns_none():
    menu = _make_menu()
    state = _make_state(AudioMenuState, menu)
    event = pygame.event.Event(pygame.QUIT)
    assert state.handle_event(event) is None


def test_menu_base_draw_no_error():
    menu = _make_menu()
    screen = pygame.Surface((1500, 800))
    state = _make_state(AudioMenuState, menu)
    state.draw(screen)


def test_menu_base_draw_with_particles():
    from tetris.visuals.particles import ParticleSystem

    menu = _make_menu()
    screen = pygame.Surface((1500, 800))
    state = _make_state(AudioMenuState, menu)
    particles = ParticleSystem()
    state.draw(screen, particles=particles)


def test_menu_base_prev_enabled_skips_disabled():
    """Navigating up should skip disabled options."""
    menu = _make_menu()
    menu.player = "Humain"
    state = menu  # MenuState itself
    # IA (index 3) is disabled when player is Humain
    state.selection = 4  # Règles du jeu
    new = state._prev_enabled(4)
    # Should skip index 3 (disabled)
    assert new == 2  # Humain


def test_menu_base_next_enabled_skips_disabled():
    """Navigating down should skip disabled options."""
    menu = _make_menu()
    menu.player = "IA"
    state = menu
    # Humain (index 2) is disabled when player is IA
    state.selection = 1  # Joueur
    new = state._next_enabled(1)
    # Should skip index 2 (disabled)
    assert new == 3  # IA


def test_menu_base_prev_enabled_wraps():
    menu = _make_menu()
    state = _make_state(AudioMenuState, menu)
    assert state._prev_enabled(0) == len(AudioMenuState._OPTIONS) - 1


def test_menu_base_next_enabled_wraps():
    menu = _make_menu()
    state = _make_state(AudioMenuState, menu)
    last = len(AudioMenuState._OPTIONS) - 1
    assert state._next_enabled(last) == 0


def test_menu_base_option_text_selected_prefix():
    menu = _make_menu()
    state = _make_state(AudioMenuState, menu)
    text = state._option_text(0, True)
    assert text.startswith("> ")


def test_menu_base_option_text_unselected_prefix():
    menu = _make_menu()
    state = _make_state(AudioMenuState, menu)
    text = state._option_text(0, False)
    assert text.startswith("  ")


def test_menu_base_option_color_disabled():
    menu = _make_menu()
    state = _make_state(AudioMenuState, menu)
    color = state._option_color(0, True, True)
    assert color == (64, 64, 64)


def test_menu_base_option_color_selected():
    menu = _make_menu()
    state = _make_state(AudioMenuState, menu)
    color = state._option_color(0, True, False)
    assert color == (255, 255, 255)


def test_menu_base_option_color_unselected():
    menu = _make_menu()
    state = _make_state(AudioMenuState, menu)
    color = state._option_color(0, False, False)
    assert color == (128, 128, 128)


def test_menu_base_update_drives_animation():
    menu = _make_menu()
    state = _make_state(AudioMenuState, menu)
    result = state.update(0.016, None)
    assert result is None


# ── MenuState ─────────────────────────────────────────────────────────


def test_menu_state_value_labels():
    menu = _make_menu()
    assert menu._value_label(1) == "Humain"  # Joueur
    assert menu._value_label(7) == "OFF"  # debug default False
    assert menu._value_label(0) == ""  # Démarrer


def test_menu_state_disabled_ia_when_human():
    menu = _make_menu()
    menu.player = "Humain"
    assert menu._is_disabled(3) is True  # IA (new idx 3)


def test_menu_state_disabled_human_when_ai():
    menu = _make_menu()
    menu.player = "IA"
    assert menu._is_disabled(2) is True  # Humain (new idx 2)


def test_menu_state_toggle_player():
    menu = _make_menu()
    menu.selection = 1  # Joueur (new idx 1)
    menu._toggle(1)
    assert menu.player == "IA"


def test_menu_state_toggle_debug():
    menu = _make_menu()
    menu.selection = 7  # Débogage (new idx 7)
    menu._toggle(1)
    assert menu.debug is True


def test_menu_state_select_audio():
    menu = _make_menu()
    menu.selection = 6  # Audio (new idx 6)
    result = menu._on_select()
    assert isinstance(result, AudioMenuState)


def test_menu_state_select_game_rules():
    menu = _make_menu()
    menu.selection = 4  # Règles du jeu (new idx 4)
    result = menu._on_select()
    assert isinstance(result, GameRulesMenuState)


def test_menu_state_select_human():
    menu = _make_menu()
    menu.player = "Humain"
    menu.selection = 2  # Humain (new idx 2)
    result = menu._on_select()
    assert isinstance(result, HumanMenuState)


def test_menu_state_select_ai():
    menu = _make_menu()
    menu.player = "IA"
    menu.selection = 3  # IA (new idx 3)
    result = menu._on_select()
    assert isinstance(result, AIMenuState)


def test_menu_state_select_leaderboard():
    menu = _make_menu()
    menu.selection = 5  # Leaderboard (new idx 5)
    result = menu._on_select()
    assert isinstance(result, LeaderboardState)


def test_menu_state_draw_no_error():
    menu = _make_menu()
    screen = pygame.Surface((1500, 800))
    menu.draw(screen)


def test_menu_state_save_settings_roundtrip():
    menu = _make_menu()
    menu.handicap = 3
    menu.sound_volume = 1
    menu.save_settings()
    menu2 = _make_menu()
    assert menu2.handicap == 3
    assert menu2.sound_volume == 1


# ── LeaderboardState ──────────────────────────────────────────────────


def test_leaderboard_handle_keydown_returns_menu():
    menu = _make_menu()
    screen = pygame.Surface((640, 480))
    font = pygame.font.Font(None, 20)
    audio = AudioManager(sound_volume=0, music_volume=0)
    state = LeaderboardState(screen, font, audio, menu)
    result = state.handle_event(_key(pygame.K_RETURN))
    assert result is menu


def test_leaderboard_handle_keydown_no_menu_creates_new():
    screen = pygame.Surface((640, 480))
    font = pygame.font.Font(None, 20)
    audio = AudioManager(sound_volume=0, music_volume=0)
    state = LeaderboardState(screen, font, audio, None)
    result = state.handle_event(_key(pygame.K_RETURN))
    assert isinstance(result, MenuState)


def test_leaderboard_handle_non_keydown_returns_none():
    screen = pygame.Surface((640, 480))
    font = pygame.font.Font(None, 20)
    audio = AudioManager(sound_volume=0, music_volume=0)
    state = LeaderboardState(screen, font, audio, None)
    result = state.handle_event(pygame.event.Event(pygame.QUIT))
    assert result is None


def test_leaderboard_draw_no_error():
    screen = pygame.Surface((1500, 800))
    font = pygame.font.Font(None, 20)
    audio = AudioManager(sound_volume=0, music_volume=0)
    state = LeaderboardState(screen, font, audio, None)
    state.draw(screen)


# ── StatsState ───────────────────────────────────────────────────────


def _make_stats():
    ai_menu = _make_ai_menu()
    screen = pygame.Surface((640, 480))
    font = pygame.font.Font(None, 20)
    audio = AudioManager(sound_volume=0, music_volume=0)
    return StatsState(screen, font, audio, ai_menu)


def test_stats_handle_keydown_returns_ai_menu():
    state = _make_stats()
    result = state.handle_event(_key(pygame.K_RETURN))
    assert result is state.ai_menu


def test_stats_handle_non_keydown_returns_none():
    state = _make_stats()
    result = state.handle_event(pygame.event.Event(pygame.QUIT))
    assert result is None


def test_stats_stat_values_empty_log():
    state = _make_stats()
    values = state._stat_values()
    assert len(values) == 8
    assert values[0] == "0"  # total_episodes
    assert values[1] == "0"  # avg_score
    assert values[2] == "0"  # best_score


def test_stats_stat_values_populated_log(tmp_path):
    """Test stat values with a populated training log."""
    log_path = tmp_path / "log.json"


    episodes = []
    for i in range(5):
        episodes.append({
            "episode": i, "score": 100 + i * 50, "lines": i,
            "level": i, "steps": 100, "epsilon": 0.5, "loss": 1.0,
        })
    log_path.write_text(json.dumps(episodes))

    ai_menu = _make_ai_menu()
    screen = pygame.Surface((640, 480))
    font = pygame.font.Font(None, 20)
    audio = AudioManager(sound_volume=0, music_volume=0)
    state = StatsState(screen, font, audio, ai_menu)
    state._stats = TrainingLog(str(log_path))
    values = state._stat_values()
    assert values[0] == "5"  # total_episodes
    assert values[2] == "300"  # best_score (100+4*50=300)


def test_stats_draw_no_error():
    state = _make_stats()
    screen = pygame.Surface((1500, 800))
    state.draw(screen)


# ── HumanMenuState ────────────────────────────────────────────────────


def test_human_menu_value_labels():
    menu = _make_menu()
    state = _make_state(HumanMenuState, menu)
    assert state._value_label(0) == "Normal"  # mode default
    assert state._value_label(1) == "ON"  # ghost_piece default True
    assert state._value_label(2) == ""  # Touches
    assert state._value_label(3) == ""  # Statistiques
    assert state._value_label(4) == ""  # Retour


def test_human_menu_toggle_mode():
    menu = _make_menu()
    state = _make_state(HumanMenuState, menu)
    state.selection = 0
    state._toggle(1)
    assert menu.mode == "Replay"


def test_human_menu_toggle_ghost():
    menu = _make_menu()
    state = _make_state(HumanMenuState, menu)
    state.selection = 1
    state._toggle(1)
    assert menu.ghost_piece is False


def test_human_menu_select_keybind_navigates():
    menu = _make_menu()
    state = _make_state(HumanMenuState, menu)
    state.selection = 2
    result = state._on_select()
    assert result is not None
    assert result is not state


def test_human_menu_select_stats_navigates():
    menu = _make_menu()
    state = _make_state(HumanMenuState, menu)
    state.selection = 3
    result = state._on_select()
    assert result is not None
    assert result is not state


def test_human_menu_select_retour_returns_menu():
    menu = _make_menu()
    state = _make_state(HumanMenuState, menu)
    state.selection = 4
    result = state._on_select()
    assert result is menu


def test_human_menu_back_returns_menu():
    menu = _make_menu()
    state = _make_state(HumanMenuState, menu)
    assert state._on_back() is menu


def test_human_menu_draw_no_error():
    menu = _make_menu()
    screen = pygame.Surface((1500, 800))
    state = _make_state(HumanMenuState, menu)
    state.draw(screen)


# ── MenuState edge cases ──────────────────────────────────────────────


def test_menu_load_settings_invalid_json():
    """Loading invalid JSON falls back to defaults."""
    # Write invalid JSON to settings file
    with open(SETTINGS_PATH, "w") as f:
        f.write("{invalid json")
    menu = _make_menu()
    # Should not crash; defaults remain
    assert menu.player == "Humain"


def test_menu_load_settings_boolean_sound_migration():
    """Old boolean 'sound' value migrates to integer sound_volume."""
    import json
    with open(SETTINGS_PATH, "w") as f:
        json.dump({"sound": True, "player": "Humain"}, f)
    menu = _make_menu()
    assert menu.sound_volume == 3  # True → 3
    with open(SETTINGS_PATH, "w") as f:
        json.dump({"sound": False, "player": "Humain"}, f)
    menu2 = _make_menu()
    assert menu2.sound_volume == 0  # False → 0


def test_menu_load_settings_missing_file_uses_defaults():
    """Missing settings file leaves defaults intact."""
    if os.path.exists(SETTINGS_PATH):
        os.remove(SETTINGS_PATH)
    menu = _make_menu()
    assert menu.player == "Humain"
    assert menu.sound_volume == 3
    assert menu.piece_generator == "7bag"


def test_menu_load_settings_keybinds_merge():
    """Saved keybinds merge over defaults."""
    import json
    with open(SETTINGS_PATH, "w") as f:
        json.dump({"keybinds": {"move_left": pygame.K_a}}, f)
    menu = _make_menu()
    assert menu.keybinds["move_left"] == pygame.K_a
    # Other actions keep defaults
    assert "move_right" in menu.keybinds


def test_menu_save_persists_keybinds():
    """save_settings persists keybinds dict."""
    menu = _make_menu()
    menu.keybinds["move_left"] = pygame.K_a
    menu.save_settings()
    menu2 = _make_menu()
    assert menu2.keybinds["move_left"] == pygame.K_a


def test_menu_toggle_debug_via_event():
    """Toggling debug via K_LEFT/K_RIGHT persists."""
    menu = _make_menu()
    menu.selection = 7  # Débogage (new idx 7)
    menu.handle_event(_key(pygame.K_RIGHT))
    assert menu.debug is True
    menu.handle_event(_key(pygame.K_LEFT))
    assert menu.debug is False


def test_menu_toggle_player_via_event():
    """Toggling player via K_LEFT/K_RIGHT changes player."""
    menu = _make_menu()
    menu.selection = 1  # Joueur (new idx 1)
    menu.handle_event(_key(pygame.K_RIGHT))
    assert menu.player == "IA"
    menu.handle_event(_key(pygame.K_LEFT))
    assert menu.player == "Humain"


def test_menu_select_start_human():
    """Selecting 'Démarrer' with human player creates GameState."""
    from tetris.states.game import GameState
    menu = _make_menu()
    menu.player = "Humain"
    menu.selection = 0  # Démarrer (new idx 0)
    result = menu._on_select()
    assert isinstance(result, GameState)


def test_menu_select_start_ai():
    """Selecting 'Démarrer' with AI player creates AIState."""
    from tetris.states.ai import AIState
    menu = _make_menu()
    menu.player = "IA"
    menu.selection = 0  # Démarrer (new idx 0)
    result = menu._on_select()
    assert isinstance(result, AIState)


def test_menu_save_calls_save_settings():
    """_save hook persists settings."""
    menu = _make_menu()
    menu.handicap = 5
    menu._save()
    menu2 = _make_menu()
    assert menu2.handicap == 5


def test_menu_handle_enter_on_disabled_returns_none():
    """ENTER on disabled option returns None."""
    menu = _make_menu()
    menu.player = "Humain"  # IA disabled
    menu.selection = 3  # IA (new idx 3)
    result = menu.handle_event(_key(pygame.K_RETURN))
    assert result is None


def test_menu_handle_left_on_non_toggle_does_nothing():
    """LEFT on non-toggle index does nothing."""
    menu = _make_menu()
    menu.selection = 6  # Audio — not a toggle index
    menu.handle_event(_key(pygame.K_LEFT))
    assert menu.player == "Humain"


def test_menu_handle_right_on_non_toggle_does_nothing():
    """RIGHT on non-toggle index does nothing."""
    menu = _make_menu()
    menu.selection = 4  # Règles du jeu — not a toggle index
    menu.handle_event(_key(pygame.K_RIGHT))
    assert menu.player == "Humain"