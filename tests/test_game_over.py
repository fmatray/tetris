"""Tests for GameOverState: animation -> name entry -> leaderboard -> menu."""

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

pygame.init()
pygame.mixer.init()

from tetris.audio import AudioManager
from tetris.states.game import GameConfig
from tetris.states.human import HumanState
from tetris.states.game_over import GameOverState
from tetris.settings import MAX_NAME_LENGTH
from tetris.visuals.particles import ParticleSystem


def _make_game_over(menu=None):
    """Build a GameOverState with dummy screen/font/audio and a real GameState."""
    screen = pygame.Surface((640, 480))
    font = pygame.font.Font(None, 20)
    audio = AudioManager(sound_volume=0, music_volume=0)
    game = HumanState(
        screen,
        font,
        audio,
        GameConfig(
            handicap=0,
            sound_volume=0,
            music_volume=0,
            music_song="korobeiniki",
            debug=False,
            ghost_piece=True,
            preview_count=3,
            speed_mode="normal",
        ),
    )
    return GameOverState(screen, font, audio, game, menu=menu)


def _keydown(key, unicode=""):
    return pygame.event.Event(pygame.KEYDOWN, key=key, unicode=unicode)


def test_init_defaults():
    """GameOverState starts in ANIMATION step with empty name and scores."""
    state = _make_game_over()
    assert state.step == "ANIMATION"
    assert state.name == ""
    assert state._scores == []


def test_update_transitions_animation_to_name(monkeypatch):
    """update() runs the game-over animation then advances step to NAME.

    The real animation is a blocking 4-second loop that calls
    pygame.display.flip() (incompatible with the dummy video driver), so
    stub it out — we only assert the step transition.
    """
    state = _make_game_over()
    assert state.step == "ANIMATION"
    monkeypatch.setattr(state.renderer, "play_game_over_animation", lambda *a, **k: None)
    result = state.update(16, ParticleSystem())
    assert result is None
    assert state.step == "NAME"


def test_handle_event_name_typing():
    """Typing printable chars appends to name during NAME step."""
    state = _make_game_over()
    state.step = "NAME"
    state.handle_event(_keydown(pygame.K_a, "A"))
    assert state.name == "A"
    state.handle_event(_keydown(pygame.K_b, "B"))
    assert state.name == "AB"


def test_handle_event_name_backspace():
    """K_BACKSPACE removes the last character of the name."""
    state = _make_game_over()
    state.step = "NAME"
    state.name = "ABC"
    state.handle_event(_keydown(pygame.K_BACKSPACE))
    assert state.name == "AB"


def test_handle_event_name_return_empty_no_transition(tmp_path, monkeypatch):
    """K_RETURN with empty name does NOT transition to LEADERBOARD."""
    monkeypatch.setattr("tetris.storage.LEADERBOARD_PATH", str(tmp_path / "lb.json"))
    monkeypatch.setattr("tetris.storage.HUMAN_STATS_PATH", str(tmp_path / "hs.json"))
    state = _make_game_over()
    state.step = "NAME"
    assert state.name == ""
    result = state.handle_event(_keydown(pygame.K_RETURN))
    assert result is None
    assert state.step == "NAME"


def test_handle_event_name_return_whitespace_no_transition(tmp_path, monkeypatch):
    """K_RETURN with only-whitespace name does NOT transition (strip check)."""
    monkeypatch.setattr("tetris.storage.LEADERBOARD_PATH", str(tmp_path / "lb.json"))
    monkeypatch.setattr("tetris.storage.HUMAN_STATS_PATH", str(tmp_path / "hs.json"))
    state = _make_game_over()
    state.step = "NAME"
    state.name = "   "
    result = state.handle_event(_keydown(pygame.K_RETURN))
    assert result is None
    assert state.step == "NAME"


def test_handle_event_name_return_saves_and_transitions(tmp_path, monkeypatch):
    """K_RETURN with a non-empty name saves the score and transitions to LEADERBOARD."""
    monkeypatch.setattr("tetris.storage.LEADERBOARD_PATH", str(tmp_path / "lb.json"))
    monkeypatch.setattr("tetris.storage.HUMAN_STATS_PATH", str(tmp_path / "hs.json"))
    state = _make_game_over()
    state.step = "NAME"
    state.name = "Alice"
    result = state.handle_event(_keydown(pygame.K_RETURN))
    assert result is None
    assert state.step == "LEADERBOARD"
    assert len(state._scores) == 1
    assert state._scores[0]["name"] == "Alice"
    assert state._scores[0]["speed_mode"] == "normal"


def test_handle_event_leaderboard_returns_menu(tmp_path, monkeypatch):
    """In LEADERBOARD step, any key returns the provided menu."""
    from tetris.states.menu import MenuState

    monkeypatch.setattr("tetris.storage.LEADERBOARD_PATH", str(tmp_path / "lb.json"))
    monkeypatch.setattr("tetris.storage.HUMAN_STATS_PATH", str(tmp_path / "hs.json"))
    screen = pygame.Surface((640, 480))
    font = pygame.font.Font(None, 20)
    audio = AudioManager(sound_volume=0, music_volume=0)
    menu = MenuState(screen, font, audio)
    state = _make_game_over(menu=menu)
    state.step = "LEADERBOARD"
    result = state.handle_event(_keydown(pygame.K_RETURN))
    assert result is menu


def test_handle_event_leaderboard_creates_menu_if_none(tmp_path, monkeypatch):
    """In LEADERBOARD step without a menu, a new MenuState is created and returned."""
    monkeypatch.setattr("tetris.storage.LEADERBOARD_PATH", str(tmp_path / "lb.json"))
    monkeypatch.setattr("tetris.storage.HUMAN_STATS_PATH", str(tmp_path / "hs.json"))
    state = _make_game_over(menu=None)
    state.step = "LEADERBOARD"
    result = state.handle_event(_keydown(pygame.K_RETURN))
    assert result is not None
    assert type(result).__name__ == "MenuState"


def test_handle_event_non_keydown_returns_none():
    """Non-KEYDOWN events return None regardless of step."""
    state = _make_game_over()
    state.step = "NAME"
    result = state.handle_event(pygame.event.Event(pygame.KEYUP, key=pygame.K_a))
    assert result is None
    state.step = "LEADERBOARD"
    result = state.handle_event(pygame.event.Event(pygame.KEYUP, key=pygame.K_a))
    assert result is None


def test_draw_name_entry():
    """draw() during NAME step renders the name entry screen without error."""
    state = _make_game_over()
    state.step = "NAME"
    state.name = "Bob"
    state.draw(state.screen)
    # No assertion needed — no exception means success.


def test_draw_leaderboard(tmp_path, monkeypatch):
    """draw() during LEADERBOARD step renders the leaderboard without error."""
    monkeypatch.setattr("tetris.storage.LEADERBOARD_PATH", str(tmp_path / "lb.json"))
    monkeypatch.setattr("tetris.storage.HUMAN_STATS_PATH", str(tmp_path / "hs.json"))
    state = _make_game_over()
    state.step = "NAME"
    state.name = "Alice"
    state.handle_event(_keydown(pygame.K_RETURN))
    assert state.step == "LEADERBOARD"
    state.draw(state.screen)


def test_name_max_length_not_exceeded(tmp_path, monkeypatch):
    """Typing beyond MAX_NAME_LENGTH does not add more characters."""
    monkeypatch.setattr("tetris.storage.LEADERBOARD_PATH", str(tmp_path / "lb.json"))
    monkeypatch.setattr("tetris.storage.HUMAN_STATS_PATH", str(tmp_path / "hs.json"))
    state = _make_game_over()
    state.step = "NAME"
    # Fill name to max length.
    for _ in range(MAX_NAME_LENGTH):
        state.handle_event(_keydown(pygame.K_a, "a"))
    assert len(state.name) == MAX_NAME_LENGTH
    # Extra typing must not grow the name.
    state.handle_event(_keydown(pygame.K_b, "b"))
    assert len(state.name) == MAX_NAME_LENGTH
    assert "b" not in state.name


def test_backspace_on_empty_name_stays_empty():
    """K_BACKSPACE on an empty name yields an empty string (no error)."""
    state = _make_game_over()
    state.step = "NAME"
    state.handle_event(_keydown(pygame.K_BACKSPACE))
    assert state.name == ""


def test_animation_step_draw_does_nothing():
    """draw() during ANIMATION step is a no-op (no branch matches)."""
    state = _make_game_over()
    assert state.step == "ANIMATION"
    state.draw(state.screen)


def test_handle_event_animation_step_returns_none():
    """KEYDOWN events during ANIMATION step (not NAME/LEADERBOARD) return None."""
    state = _make_game_over()
    assert state.step == "ANIMATION"
    result = state.handle_event(_keydown(pygame.K_RETURN))
    assert result is None


def test_mcp_player_does_not_save_human_stats(monkeypatch):
    """When player_type == 'MCP', save_human_game() is NOT called."""
    from tetris.settings import HUMAN_STATS_PATH

    # Ensure clean state
    if os.path.exists(HUMAN_STATS_PATH):
        os.remove(HUMAN_STATS_PATH)

    screen = pygame.Surface((640, 480))
    font = pygame.font.Font(None, 20)
    audio = AudioManager(sound_volume=0, music_volume=0)
    from tetris.states.mcp import MCPConfig, MCPState

    game = MCPState(
        screen,
        font,
        audio,
        GameConfig(
            handicap=0,
            sound_volume=0,
            music_volume=0,
            music_song="korobeiniki",
            debug=False,
            ghost_piece=True,
            preview_count=1,
            speed_mode="normal",
        ),
        MCPConfig(port=8765),
        start_server=False,
    )
    assert game.player_type == "MCP"

    state = GameOverState(screen, font, audio, game)
    state.step = "NAME"
    state.name = "TestBot"
    monkeypatch.setattr("tetris.states.game_over.save_score", lambda *a, **kw: None)
    state.handle_event(_keydown(pygame.K_RETURN))
    # human_stats.json should NOT exist for MCP player
    assert not os.path.exists(HUMAN_STATS_PATH)
