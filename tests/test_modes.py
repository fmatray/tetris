"""Tests for Sprint/Blitz modes, per-mode leaderboards, and efficiency stats."""

import json

import pygame
import pytest
from tests.helpers import make_audio, make_font, make_game_config, make_screen
from tetris.states.human import HumanState
from tetris.states.human_menu import HumanMenuState
from tetris.states.leaderboard import LeaderboardState
from tetris.states.menu import MenuState
from tetris.storage import load_leaderboard, load_human_games, save_human_game, save_score
from tetris.visuals.particles import ParticleSystem


def _make_human(mode="Normal", menu=None):
    screen = make_screen()
    font = make_font()
    audio = make_audio()
    if menu is None:
        menu = MenuState(screen, font, audio)
        menu.mode = mode
    return HumanState(screen, font, audio, make_game_config(), menu=menu)


# --- Mode mapping ---------------------------------------------------------


def test_mode_mapping():
    for ui_mode, expected in [("Normal", "marathon"), ("Replay", "marathon"), ("Sprint", "sprint"), ("Blitz", "blitz")]:
        state = _make_human(ui_mode)
        assert state.game_mode == expected


def test_no_menu_defaults_marathon():
    screen, font, audio = make_screen(), make_font(), make_audio()
    state = HumanState(screen, font, audio, make_game_config())
    assert state.game_mode == "marathon"


def test_mode_cycle_order():
    screen, font, audio = make_screen(), make_font(), make_audio()
    menu = MenuState(screen, font, audio)
    HumanMenuState(screen, font, audio, menu)
    assert HumanMenuState._MODE_CYCLE == ("Normal", "Replay", "Sprint", "Blitz")


# --- Timer accumulation ----------------------------------------------------


def test_timer_accumulates_and_pauses():
    state = _make_human()
    state.update(100.0, ParticleSystem())
    assert state.elapsed_ms == pytest.approx(100.0)
    state.paused = True
    state.update(100.0, ParticleSystem())
    assert state.elapsed_ms == pytest.approx(100.0)


def test_timer_not_accumulating_on_game_over():
    state = _make_human()
    state.game_over = True
    state.update(500.0, ParticleSystem())
    assert state.elapsed_ms == 0.0


# --- Sprint end condition --------------------------------------------------


def test_sprint_ends_at_40_lines():
    state = _make_human("Sprint")
    state.stats.total_lines = 40
    result = state.update(16.0, ParticleSystem())
    assert state.game_over
    assert result is not None  # transition to GameOverState


def test_sprint_not_ended_below_40_lines():
    state = _make_human("Sprint")
    state.stats.total_lines = 39
    result = state.update(16.0, ParticleSystem())
    assert not state.game_over
    assert result is None


def test_marathon_never_ends_on_lines():
    state = _make_human("Normal")
    state.stats.total_lines = 200
    state.update(16.0, ParticleSystem())
    assert not state.game_over


# --- Blitz end condition ---------------------------------------------------


def test_blitz_ends_at_duration():
    from tetris.settings import BLITZ_DURATION_MS

    state = _make_human("Blitz")
    # Just under the budget: still playing.
    state.update(BLITZ_DURATION_MS - 1.0, ParticleSystem())
    assert not state.game_over
    # Cross the budget: game over on this frame.
    result = state.update(10.0, ParticleSystem())
    assert state.game_over  # type: ignore[unreachable]  # zuban can't see the mutation
    assert result is not None  # type: ignore[unreachable]


# --- Finesse accounting -----------------------------------------------------


def test_finesse_zero_faults_when_inputs_minimal():
    state = _make_human()
    # A just-spawned piece with no inputs must not be a fault.
    state._piece_inputs = 0
    state._spawn_x = state.current_piece.x
    state._check_finesse()
    assert state.finesse_faults == 0


def test_finesse_fault_counted_on_excess_inputs():
    state = _make_human()
    piece = state.current_piece
    state._spawn_x = piece.x  # already in place: any rotation/lateral input is excess
    state._piece_inputs = 3
    state._check_finesse()
    assert state.finesse_faults == 1


def test_lock_resets_input_counter():
    state = _make_human()
    before = state._spawn_x
    assert before is not None
    # Directly simulate the post-lock bookkeeping without a real lock.
    state._note_spawn()
    assert state._piece_inputs == 0
    assert state._spawn_x == state.current_piece.x


# --- Per-mode leaderboard storage ------------------------------------------


@pytest.fixture()
def lb_path(tmp_path, monkeypatch):
    path = tmp_path / "leaderboard.json"
    monkeypatch.setattr("tetris.storage.LEADERBOARD_PATH", str(path))
    return path


def test_save_score_per_mode_cap(lb_path):
    # 12 marathon entries: only the top 10 survive.
    for i in range(12):
        save_score(f"P{i}", 1000 - i, 1, 5, game_mode="marathon")
    assert len(load_leaderboard("marathon")) == 10
    # A sprint entry lands in its own slice.
    save_score("S0", 40_000, 5, 40, game_mode="sprint", time_s=61.5)
    assert len(load_leaderboard("sprint")) == 1
    assert len(load_leaderboard("marathon")) == 10


def test_sprint_sorted_by_time(lb_path):
    save_score("Slow", 40_000, 5, 40, game_mode="sprint", time_s=90.0)
    save_score("Fast", 40_000, 5, 40, game_mode="sprint", time_s=55.0)
    scores = load_leaderboard("sprint")
    assert [s["name"] for s in scores] == ["Fast", "Slow"]


def test_load_without_mode_returns_everything(lb_path):
    save_score("M", 100, 1, 1, game_mode="marathon")
    save_score("S", 100, 1, 40, game_mode="sprint", time_s=60.0)
    assert len(load_leaderboard()) == 2


def test_legacy_entries_count_as_marathon(lb_path):
    lb_path.write_text(json.dumps([{"name": "Old", "score": 500, "level": 1, "lines": 3}]))
    scores = load_leaderboard("marathon")
    assert len(scores) == 1
    assert load_leaderboard("sprint") == []


def test_save_human_game_efficiency_fields(tmp_path, monkeypatch):
    hs_path = tmp_path / "human_stats.json"
    monkeypatch.setattr("tetris.storage.HUMAN_STATS_PATH", str(hs_path))
    save_human_game("Alice", 100, 1, 4, 20, time_s=50.0, pps=1.6, finesse_faults=3)
    games = load_human_games()
    assert games[0]["time_s"] == 50.0
    assert games[0]["pps"] == 1.6
    assert games[0]["finesse_faults"] == 3
    # Omitted fields stay absent (legacy-compatible records).
    save_human_game("Bob", 100, 1, 4, 20)
    games = load_human_games()
    assert "pps" not in games[1]


# --- Sprint qualification ---------------------------------------------------


def _make_game_over_sprint(lines, time_ms):
    state = _make_human("Sprint")
    state.stats.total_lines = lines
    state.elapsed_ms = time_ms
    from tetris.states.game_over import GameOverState

    return GameOverState(state.screen, state.font, state.audio, state)


def test_sprint_qualifies_only_on_win(lb_path):
    from tetris.states.game_over import GameOverState

    go = _make_game_over_sprint(lines=39, time_ms=60_000)
    assert isinstance(go, GameOverState)
    assert not go._score_qualifies()
    go = _make_game_over_sprint(lines=40, time_ms=60_000)
    assert go._score_qualifies()


def test_sprint_time_beats_worst(lb_path):
    save_score("Worst", 40_000, 5, 40, game_mode="sprint", time_s=90.0)
    for _ in range(9):
        save_score("Filler", 40_000, 5, 40, game_mode="sprint", time_s=50.0)
    go = _make_game_over_sprint(lines=40, time_ms=80_000)
    assert go._score_qualifies()
    go = _make_game_over_sprint(lines=40, time_ms=95_000)
    assert not go._score_qualifies()


# --- Leaderboard tabs --------------------------------------------------------


def test_leaderboard_tab_cycle(lb_path):
    screen, font, audio = make_screen(), make_font(), make_audio()
    menu = MenuState(screen, font, audio)
    state = LeaderboardState(screen, font, audio, menu=menu)
    assert state.leaderboard_mode == "marathon"
    state.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RIGHT))
    assert state.leaderboard_mode == "sprint"
    state.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RIGHT))
    assert state.leaderboard_mode == "blitz"
    state.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RIGHT))
    assert state.leaderboard_mode == "marathon"
    state.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_LEFT))
    assert state.leaderboard_mode == "blitz"


def test_leaderboard_tab_filters(lb_path):
    save_score("M", 100, 1, 1, game_mode="marathon")
    save_score("S", 100, 1, 40, game_mode="sprint", time_s=60.0)
    screen, font, audio = make_screen(), make_font(), make_audio()
    state = LeaderboardState(screen, font, audio)
    assert [e["name"] for e in state._scores] == ["M"]
    state.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RIGHT))
    assert [e["name"] for e in state._scores] == ["S"]


def test_leaderboard_other_key_returns_menu(lb_path):
    screen, font, audio = make_screen(), make_font(), make_audio()
    menu = MenuState(screen, font, audio)
    state = LeaderboardState(screen, font, audio, menu=menu)
    result = state.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN))
    assert result is menu


# --- Rendering ----------------------------------------------------------------


def test_draw_leaderboard_sprint_tab_renders(lb_path):
    save_score("S", 40_000, 5, 40, game_mode="sprint", time_s=61.25)
    screen, font, audio = make_screen(), make_font(), make_audio()
    state = LeaderboardState(screen, font, audio)
    state.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RIGHT))
    state.draw(screen)  # no crash; Time cell formatting exercised


def test_human_stats_efficiency_lines_render(tmp_path, monkeypatch):
    hs_path = tmp_path / "human_stats.json"
    monkeypatch.setattr("tetris.storage.HUMAN_STATS_PATH", str(hs_path))
    save_human_game("Alice", 100, 1, 4, 20, time_s=50.0, pps=1.6, finesse_faults=3)
    save_human_game("Bob", 200, 2, 8, 30)  # legacy record without fields
    from tetris.states.human_stats import HumanStatsState

    screen, font, audio = make_screen(), make_font(), make_audio()
    menu = MenuState(screen, font, audio)
    from tetris.states.human_menu import HumanMenuState

    human_menu = HumanMenuState(screen, font, audio, menu)
    stats = HumanStatsState(screen, font, audio, human_menu)
    stats.draw(screen)  # no crash with mixed legacy/new records
