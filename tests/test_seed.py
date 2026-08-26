"""Tests for seed feature: reproducible piece sequences, handicap, MCP, AI."""

import random

import pygame

from tetris.game.board import Board
from tetris.game.piece_provider import PieceProvider


# ── PieceProvider seed tests ──


def test_seed_reproducible_sequence():
    """Two providers with the same seed produce identical piece sequences."""
    p1 = PieceProvider(generator="7bag", seed=42)
    p2 = PieceProvider(generator="7bag", seed=42)
    seq1 = [p1.next_type() for _ in range(20)]
    seq2 = [p2.next_type() for _ in range(20)]
    assert seq1 == seq2


def test_seed_different_from_different_seed():
    """Different seeds produce different sequences (with overwhelming probability)."""
    p1 = PieceProvider(generator="7bag", seed=42)
    p2 = PieceProvider(generator="7bag", seed=99)
    seq1 = [p1.next_type() for _ in range(20)]
    seq2 = [p2.next_type() for _ in range(20)]
    assert seq1 != seq2


def test_seed_reset_reproduces_sequence():
    """After reset(), a seeded provider reproduces the same sequence."""
    p = PieceProvider(generator="7bag", seed=42)
    seq1 = [p.next_type() for _ in range(14)]
    p.reset()
    seq2 = [p.next_type() for _ in range(14)]
    assert seq1 == seq2


def test_seed_with_random_generator():
    """RandomGenerator with seed produces reproducible sequences."""
    p1 = PieceProvider(generator="random", seed=42)
    p2 = PieceProvider(generator="random", seed=42)
    seq1 = [p1.next_type() for _ in range(20)]
    seq2 = [p2.next_type() for _ in range(20)]
    assert seq1 == seq2


def test_seed_with_weighted_generator():
    """WeightedGenerator with seed produces reproducible sequences."""
    p1 = PieceProvider(generator="weighted", seed=42)
    p2 = PieceProvider(generator="weighted", seed=42)
    seq1 = [p1.next_type() for _ in range(20)]
    seq2 = [p2.next_type() for _ in range(20)]
    assert seq1 == seq2


def test_seed_with_35bag_generator():
    """ThirtyFiveBagGenerator with seed produces reproducible sequences."""
    p1 = PieceProvider(generator="35bag", seed=42)
    p2 = PieceProvider(generator="35bag", seed=42)
    seq1 = [p1.next_type() for _ in range(35)]
    seq2 = [p2.next_type() for _ in range(35)]
    assert seq1 == seq2


def test_seed_property_returns_seed():
    """PieceProvider.seed returns the configured seed."""
    p = PieceProvider(generator="7bag", seed=42)
    assert p.seed == 42


def test_seed_none_property():
    """PieceProvider.seed returns None when no seed configured."""
    p = PieceProvider(generator="7bag")
    assert p.seed is None


def test_seed_first_piece_safety():
    """Seeded provider still respects first-piece safety filter."""
    p = PieceProvider(generator="7bag", seed=42)
    first = p.next_type()
    assert first in ("I", "J", "L", "T")


# ── Board.apply_handicap seed tests ──


def test_apply_handicap_with_seed_reproducible():
    """Same seed + handicap level produces same board layout."""
    b1 = Board()
    b2 = Board()
    b1.apply_handicap(3, random.Random(42))
    b2.apply_handicap(3, random.Random(42))
    assert b1.grid == b2.grid


def test_apply_handicap_different_seed_different_layout():
    """Different seeds produce different handicap layouts."""
    b1 = Board()
    b2 = Board()
    b1.apply_handicap(3, random.Random(42))
    b2.apply_handicap(3, random.Random(99))
    assert b1.grid != b2.grid


def test_apply_handicap_no_rng_backward_compatible():
    """apply_handicap without rng uses module random (backward compatible)."""
    b = Board()
    b.apply_handicap(2)  # should not raise
    assert any(1 for row in b.grid for cell in row if cell)


# ── MCP seed tests ──


def _make_mcp_state(seed=42):
    from tetris.audio import AudioManager
    from tetris.states.game import GameConfig
    from tetris.states.mcp import MCPConfig, MCPState

    screen = pygame.Surface((800, 600))
    font = pygame.font.Font(None, 20)
    audio = AudioManager(sound_volume=0, music_volume=0)
    config = GameConfig(
        handicap=0,
        sound_volume=0,
        music_volume=0,
        music_song="korobeiniki",
        debug=False,
        ghost_piece=True,
        preview_count=3,
        speed_mode="normal",
        seed=seed,
    )
    mcp_config = MCPConfig(port=12345)
    return MCPState(
        screen=screen,
        font=font,
        audio=audio,
        config=config,
        mcp_config=mcp_config,
        piece_provider=PieceProvider(generator="7bag", seed=seed),
        start_server=False,
    )


def test_mcp_snapshot_includes_seed():
    """_board_snapshot includes the seed field."""
    state = _make_mcp_state(seed=42)
    snap = state._board_snapshot()
    assert "seed" in snap
    assert snap["seed"] == 42


def test_mcp_reset_game_with_seed():
    """_reset_game with a seed updates the stored seed."""
    state = _make_mcp_state(seed=42)
    state._reset_game(seed=99)
    assert state.seed == 99
    snap = state._board_snapshot()
    assert snap["seed"] == 99


def test_mcp_reset_game_auto_generates_seed():
    """_reset_game without a seed when seed is None auto-generates one."""
    state = _make_mcp_state(seed=None)
    state._reset_game()
    assert state.seed is not None
    assert isinstance(state.seed, int)


def test_mcp_seed_reproducible_pieces():
    """Two MCP games with the same seed produce identical first pieces."""
    s1 = _make_mcp_state(seed=42)
    s2 = _make_mcp_state(seed=42)
    assert s1.current_piece.type == s2.current_piece.type
    assert s1.next_piece.type == s2.next_piece.type


# ── SeedEntryState tests ──


def _make_menu_with_seed(seed=None):
    from tetris.states.menu import MenuState

    screen = pygame.Surface((800, 600))
    font = pygame.font.Font(None, 20)
    from tetris.audio import AudioManager

    audio = AudioManager(sound_volume=0, music_volume=0)
    menu = MenuState(screen=screen, font=font, audio=audio)
    menu.seed = seed
    return menu


def test_seed_entry_digit_input():
    """Typing digits builds the seed text."""
    from tetris.states.seed_entry import SeedEntryState

    menu = _make_menu_with_seed(None)
    state = SeedEntryState(screen=menu.screen, font=menu.font, audio=menu.audio, menu=menu)
    for ch in "12345":
        state.handle_event(pygame.event.Event(pygame.KEYDOWN, key=ord(ch), unicode=ch))
    assert state.text == "12345"


def test_seed_entry_backspace():
    """Backspace removes the last digit."""
    from tetris.states.seed_entry import SeedEntryState

    menu = _make_menu_with_seed(None)
    state = SeedEntryState(screen=menu.screen, font=menu.font, audio=menu.audio, menu=menu)
    for ch in "123":
        state.handle_event(pygame.event.Event(pygame.KEYDOWN, key=ord(ch), unicode=ch))
    state.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_BACKSPACE, unicode=""))
    assert state.text == "12"


def test_seed_entry_enter_confirms():
    """ENTER stores the seed on the menu and returns to menu."""
    from tetris.states.seed_entry import SeedEntryState

    menu = _make_menu_with_seed(None)
    state = SeedEntryState(screen=menu.screen, font=menu.font, audio=menu.audio, menu=menu)
    for ch in "42":
        state.handle_event(pygame.event.Event(pygame.KEYDOWN, key=ord(ch), unicode=ch))
    result = state.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN, unicode="\r"))
    assert menu.seed == 42
    assert result is menu


def test_seed_entry_empty_enter_sets_none():
    """ENTER with empty text sets seed to None (random)."""
    from tetris.states.seed_entry import SeedEntryState

    menu = _make_menu_with_seed(123)
    state = SeedEntryState(screen=menu.screen, font=menu.font, audio=menu.audio, menu=menu)
    # Clear the pre-filled text
    state.text = ""
    result = state.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN, unicode="\r"))
    assert menu.seed is None
    assert result is menu


def test_seed_entry_escape_cancels():
    """ESC cancels without modifying the seed."""
    from tetris.states.seed_entry import SeedEntryState

    menu = _make_menu_with_seed(99)
    state = SeedEntryState(screen=menu.screen, font=menu.font, audio=menu.audio, menu=menu)
    for ch in "1":
        state.handle_event(pygame.event.Event(pygame.KEYDOWN, key=ord(ch), unicode=ch))
    result = state.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE, unicode=""))
    assert menu.seed == 99  # unchanged
    assert result is menu


def test_seed_entry_rejects_non_digits():
    """Non-digit characters are rejected."""
    from tetris.states.seed_entry import SeedEntryState

    menu = _make_menu_with_seed(None)
    state = SeedEntryState(screen=menu.screen, font=menu.font, audio=menu.audio, menu=menu)
    state.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_a, unicode="a"))
    assert state.text == ""


def test_seed_entry_max_length():
    """Seed input is capped at 10 digits."""
    from tetris.states.seed_entry import SeedEntryState

    menu = _make_menu_with_seed(None)
    state = SeedEntryState(screen=menu.screen, font=menu.font, audio=menu.audio, menu=menu)
    for ch in "12345678901":
        state.handle_event(pygame.event.Event(pygame.KEYDOWN, key=ord(ch), unicode=ch))
    assert len(state.text) == 10


# ── Storage seed tests ──


def test_save_score_with_seed(tmp_path):
    """save_score stores the seed in the leaderboard entry."""
    from unittest.mock import patch

    from tetris.storage import save_score

    with patch("tetris.storage.LEADERBOARD_PATH", str(tmp_path / "lb.json")):
        save_score("Alice", 1000, 5, 20, seed=42)
        from tetris.storage import load_leaderboard

        scores = load_leaderboard()
        assert scores[0]["seed"] == 42


def test_save_human_game_with_seed(tmp_path):
    from unittest.mock import patch

    from tetris.storage import load_human_games, save_human_game

    with patch("tetris.storage.HUMAN_STATS_PATH", str(tmp_path / "hs.json")):
        save_human_game("Bob", 500, 3, 10, 50, seed=99)
        games = load_human_games()
        assert games[0]["seed"] == 99


# ── GameState seed tests ──


def test_game_state_auto_generates_seed():
    """GameState auto-generates a seed when config.seed is None."""
    from tetris.audio import AudioManager
    from tetris.states.game import GameConfig

    screen = pygame.Surface((800, 600))
    font = pygame.font.Font(None, 20)
    audio = AudioManager(sound_volume=0, music_volume=0)
    config = GameConfig(
        handicap=0,
        sound_volume=0,
        music_volume=0,
        music_song="korobeiniki",
        debug=False,
        ghost_piece=True,
        preview_count=3,
        speed_mode="normal",
        seed=None,
    )
    provider = PieceProvider(generator="7bag")
    # GameState is abstract — use HumanState
    from tetris.states.human import HumanState

    state = HumanState(screen=screen, font=font, audio=audio, config=config, piece_provider=provider)
    assert state.seed is not None
    assert isinstance(state.seed, int)


def test_game_state_uses_configured_seed():
    """GameState uses the seed from GameConfig when provided."""
    from tetris.audio import AudioManager
    from tetris.states.game import GameConfig
    from tetris.states.human import HumanState
    from tetris.game.piece_provider import PieceProvider

    screen = pygame.Surface((800, 600))
    font = pygame.font.Font(None, 20)
    audio = AudioManager(sound_volume=0, music_volume=0)
    config = GameConfig(
        handicap=0,
        sound_volume=0,
        music_volume=0,
        music_song="korobeiniki",
        debug=False,
        ghost_piece=True,
        preview_count=3,
        speed_mode="normal",
        seed=12345,
    )
    provider = PieceProvider(generator="7bag", seed=12345)
    state = HumanState(screen=screen, font=font, audio=audio, config=config, piece_provider=provider)
    assert state.seed == 12345


# ── TrainingLog seed tests ──


def test_training_log_records_seed(tmp_path):
    from tetris.ai.trainer import TrainingLog

    log = TrainingLog(str(tmp_path / "log.json"))
    log.record(0, 100, 5, 3, 200, 0.1, 0.01, seed=42)
    entries = log.episodes
    assert entries[0]["seed"] == 42
