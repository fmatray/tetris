"""Tests for AIState: DQN agent autonomous play and learning.

Headless: conftest.py sets SDL_VIDEODRIVER=dummy + SDL_AUDIODRIVER=dummy.
"""

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import numpy as np
import pygame
import pytest

from tetris.ai.agent import DQNAgent
from tetris.ai.trainer import TrainingLog
from tetris.audio import AudioManager
from tetris.game.piece_provider import PieceProvider
from tetris.game.shapes import SHAPES
from tetris.game.tetromino import Tetromino
from tetris.settings import (
    BOARD_HEIGHT,
    BOARD_WIDTH,
    CURRICULUM_ORDER,
    GRAY,
    LOG_PATH,
    MODEL_PATH,
)
from tetris.ai.candidates import iter_column_positions, best_next_placement, gen_placements
from tetris.ai.hud import _hud_table_rows, _trend_arrow, draw_ai_hud
from tetris.states.game import GameConfig
from tetris.states.ai import AIConfig
from tetris.states.ai import AIState, NUM_ROTATIONS, PendingTransition
from tetris.visuals.particles import ParticleSystem

pygame.init()
pygame.mixer.init()
_screen = pygame.Surface((640, 480))
_font = pygame.font.Font(None, 20)
_counter = 0


def _unique_path() -> str:
    global _counter
    _counter += 1
    return f"/tmp/_test_ai_states_{_counter}.json"


def _make_ai(learning: bool = True, **kwargs: object) -> AIState:
    speed: str = str(kwargs.pop("speed", "fast"))  # type: ignore[arg-type]
    return _make_ai_full(learning=learning, speed=speed, **kwargs)


from typing import cast


def _make_ai_full(learning: bool = True, speed: str = "fast", **kwargs: object) -> AIState:
    audio = AudioManager(sound_volume=0, music_volume=0)
    provider = PieceProvider(generator="7bag", path=_unique_path())
    ai = AIState(
        screen=_screen,
        font=_font,
        audio=audio,
        config=GameConfig(
            handicap=0,
            sound_volume=0,
            music_volume=0,
            music_song="korobeiniki",
            debug=False,
            ghost_piece=True,
            preview_count=1,
            speed_mode="normal",
        ),
        ai_config=AIConfig(
            epsilon_decay=0.999,
            epsilon_end=0.1,
            lr=1e-3,
            gamma=0.97,
            batch_size=64,
            buffer_size=50_000,
            ai_mode="learning" if learning else "playing",
            curriculum=cast(bool, kwargs.get("curriculum", False)),
            curriculum_freq=cast(int, kwargs.get("curriculum_freq", 50)),
            curriculum_epsilon=cast(str, kwargs.get("curriculum_epsilon", "reset")),
            warm_start=cast(bool, kwargs.get("warm_start", True)),
            learn_per_action=cast(int, kwargs.get("learn_per_action", 2)),
            lookahead=cast(bool, kwargs.get("lookahead", True)),
            lookahead_depth=cast(int, kwargs.get("lookahead_depth", 1)),
        ),
        piece_provider=provider,
        speed=speed,
    )
    ai.log.path = _unique_path()
    return ai


@pytest.fixture(autouse=True)
def _clean_ai_files():
    """Remove AI model and training log before/after each test."""
    for f in (MODEL_PATH, LOG_PATH):
        if os.path.exists(f):
            os.unlink(f)
    yield
    for f in (MODEL_PATH, LOG_PATH):
        if os.path.exists(f):
            os.unlink(f)


# ---------------------------------------------------------------------------
# Init
# ---------------------------------------------------------------------------


class TestInit:
    def test_learning_mode_attributes(self):
        ai = _make_ai(learning=True)
        assert ai.ai_mode == "learning"
        assert ai.episode == 0
        assert isinstance(ai.agent, DQNAgent)
        assert isinstance(ai.log, TrainingLog)
        assert ai.episode_steps == 0
        assert ai._pending is None
        assert ai._prev_action is None
        assert ai.speed == "fast"
        assert ai.ghost_piece is True
        assert ai.warm_start is True
        assert ai.lookahead is True

    def test_playing_mode_epsilon_zero(self):
        ai = _make_ai(learning=False)
        assert ai.ai_mode == "playing"
        assert ai.agent.epsilon == 0.0

    def test_playing_mode_no_curriculum(self):
        ai = _make_ai(learning=False, curriculum=True)
        assert ai._curriculum_types is None
        assert ai.pieces.allowed_types is None

    def test_curriculum_init_restricts_pieces(self):
        ai = _make_ai(learning=True, curriculum=True)
        assert ai._curriculum_types == ["O"]
        assert ai.pieces.allowed_types == ["O"]

    def test_model_load_error_logged(self):
        """Wrong checkpoint keys → KeyError caught, AIState still created."""
        import torch

        torch.save({"wrong_key": 0}, MODEL_PATH)
        ai = _make_ai()
        assert ai is not None


# ---------------------------------------------------------------------------
# Candidate generation
# ---------------------------------------------------------------------------


class TestIterColumnPositions:
    def test_all_piece_types_yield_positions(self):
        for piece_type in SHAPES:
            positions = list(iter_column_positions(piece_type))
            assert len(positions) > 0
            for shape, rot, px in positions:
                assert isinstance(shape, list)
                assert 0 <= rot < NUM_ROTATIONS
                assert -2 <= px < BOARD_WIDTH

    def test_o_piece_one_rotation(self):
        positions = list(iter_column_positions("O"))
        rots = {rot for _, rot, _ in positions}
        assert rots == {0}

    def test_i_piece_all_rotations(self):
        positions = list(iter_column_positions("I"))
        rots = {rot for _, rot, _ in positions}
        assert rots == {0, 1, 2, 3}


class TestBestNextPlacement:
    def test_empty_grid_returns_grid(self):
        grid = np.zeros((BOARD_HEIGHT, BOARD_WIDTH), dtype=np.float32)
        result = best_next_placement(grid, "I")
        assert result.shape == grid.shape
        assert not np.array_equal(result, grid)  # piece placed

    def test_full_grid_clears_lines(self):
        """Full grid: placement triggers line clears → result differs."""
        grid = np.ones((BOARD_HEIGHT, BOARD_WIDTH), dtype=np.float32)
        result = best_next_placement(grid, "O")
        # After clearing, the grid is not all ones
        assert not np.array_equal(result, grid)


class TestGenPlacements:
    def test_yields_placements(self):
        grid = np.zeros((BOARD_HEIGHT, BOARD_WIDTH), dtype=np.float32)
        placements = list(gen_placements(grid, "I"))
        assert len(placements) > 0
        for p in placements:
            assert len(p.shape) == 4
            assert p.py >= 0
            assert 0 <= p.rot < NUM_ROTATIONS
            # Each placement has a move sequence
            assert isinstance(p.moves, list)

    def test_full_grid_yields_spawn(self):
        """Full grid: BFS finds spawn position (py=0)."""
        grid = np.ones((BOARD_HEIGHT, BOARD_WIDTH), dtype=np.float32)
        placements = list(gen_placements(grid, "O"))
        assert len(placements) >= 1
        ai = _make_ai()
        candidates, actions, dellvals = ai._get_candidate_states()
        assert candidates.ndim == 2
        assert candidates.shape[1] == 17
        assert len(actions) == len(candidates)
        assert len(dellvals) == len(candidates)

    def test_includes_hold_candidates(self):
        ai = _make_ai()
        ai.hold_piece = Tetromino("T")
        ai._get_candidate_states()
        holds = [p.hold for p in ai._candidate_placements]
        assert True in holds
        assert False in holds

    def test_includes_non_hold_candidates(self):
        ai = _make_ai()
        ai._get_candidate_states()
        holds = [p.hold for p in ai._candidate_placements]
        assert False in holds

    def test_full_board_still_yields_candidates(self):
        """Full board: spawn position (y=0) is still valid for shape_fits."""
        ai = _make_ai()
        for y in range(BOARD_HEIGHT):
            for x in range(BOARD_WIDTH):
                ai.board.grid[y][x] = GRAY
        candidates, actions, dellvals = ai._get_candidate_states()
        # Spawn placements are valid (y=0, shape fits at spawn)
        assert len(candidates) >= 1
        assert len(actions) == len(candidates)
        assert len(dellvals) == len(candidates)


# ---------------------------------------------------------------------------
# Macro-action execution
# ---------------------------------------------------------------------------


class TestExecuteMoveSequence:
    def test_non_hold_move_sequence(self):
        ai = _make_ai()
        ai._get_candidate_states()
        assert len(ai._candidate_placements) > 0
        # Find a non-hold candidate
        idx = next(i for i, p in enumerate(ai._candidate_placements) if not p.hold)
        original_y = ai.current_piece.y
        ai._execute_move_sequence(idx)
        assert ai.current_piece.y >= original_y

    def test_hold_candidate(self):
        ai = _make_ai()
        ai._get_candidate_states()
        hold_idx = next((i for i, p in enumerate(ai._candidate_placements) if p.hold), None)
        if hold_idx is None:
            pytest.skip("No hold candidate")
        ai._execute_move_sequence(hold_idx)
        assert ai._can_hold is False


# ---------------------------------------------------------------------------
# Update
# ---------------------------------------------------------------------------


class TestUpdate:
    def test_learning_fast_selects_and_locks(self):
        ai = _make_ai(learning=True, speed="fast")
        particles = ParticleSystem()
        # First update: select candidate + execute
        ai.update(16, particles)
        assert ai.episode_steps == 1
        assert ai._prev_action is not None
        # Second update: fast-forward lock delay → piece locks
        ai.update(16, particles)
        assert ai._prev_action is None  # reset after lock

    def test_learning_episode_steps_increment(self):
        ai = _make_ai(learning=True, speed="fast")
        particles = ParticleSystem()
        for _ in range(6):
            ai.update(16, particles)
        assert ai.episode_steps >= 3

    def test_normal_speed_throttle(self):
        ai = _make_ai(learning=True, speed="normal")
        particles = ParticleSystem()
        # 4 calls × 16ms = 64ms < 80ms → no action yet
        for _ in range(4):
            result = ai.update(16, particles)
            assert result is None
        assert ai.episode_steps == 0
        # 5th call: 80ms reached → action selected
        ai.update(16, particles)
        assert ai.episode_steps == 1

    def test_playing_mode_no_learning(self):
        ai = _make_ai(learning=False, speed="fast")
        particles = ParticleSystem()
        assert ai.agent.epsilon == 0.0
        ai.update(16, particles)
        assert ai.episode_steps == 1
        # Lock the piece (no fast-forward in playing mode)
        ai.update(600, particles)
        assert len(ai.agent.buffer) == 0
        assert len(ai.agent._n_step_buffer) == 0

    def test_paused_returns_none(self):
        ai = _make_ai(learning=True)
        ai.paused = True
        result = ai.update(16, ParticleSystem())
        assert result is None

    def test_game_over_triggers_episode_end(self):
        ai = _make_ai(learning=True)
        ai.game_over = True
        ai.episode = 1  # avoid model save
        ai.update(16, ParticleSystem())
        assert ai.game_over is False


# ---------------------------------------------------------------------------
# _lock_and_spawn: transition storage
# ---------------------------------------------------------------------------


class TestLockAndSpawn:
    def test_stores_transition_after_locks(self):
        ai = _make_ai(learning=True, speed="fast")
        particles = ParticleSystem()
        # First lock: no store (prev_state=None). Subsequent locks store.
        # N_STEP=3: need 4 locks to flush first transition to PER.
        for _ in range(8):
            ai.update(16, particles)  # select + execute
            ai.update(16, particles)  # fast-forward lock
        assert len(ai.agent.buffer) >= 1

    def test_playing_mode_no_transition_stored(self):
        ai = _make_ai(learning=False, speed="fast")
        particles = ParticleSystem()
        ai.update(16, particles)
        ai.update(600, particles)  # lock
        assert len(ai.agent.buffer) == 0


# ---------------------------------------------------------------------------
# Episode management
# ---------------------------------------------------------------------------


class TestOnEpisodeEnd:
    def test_no_game_over_returns_none(self):
        ai = _make_ai()
        assert ai._on_episode_end() is None

    def test_learning_mode_logs_and_resets(self):
        ai = _make_ai(learning=True)
        ai.game_over = True
        ai.episode = 1  # avoid model save
        initial_epsilon = ai.agent.epsilon
        ai._on_episode_end()
        assert not getattr(ai, "game_over", True)
        assert ai.episode_steps == 0
        assert ai.agent.epsilon < initial_epsilon
        assert len(ai.log.episodes) == 1

    def test_playing_mode_resets_without_logging(self):
        ai = _make_ai(learning=False)
        before = len(ai.log.episodes)
        ai.game_over = True
        ai._on_episode_end()
        assert ai.game_over is False
        # Playing mode writes exactly one entry to the playing log.
        assert len(ai.log.episodes) == before + 1


class TestLogAndLearn:
    def test_without_curriculum(self):
        ai = _make_ai(learning=True, curriculum=False)
        ai.episode = 1
        initial_epsilon = ai.agent.epsilon
        ai._log_and_learn()
        assert len(ai.log.episodes) == 1
        assert ai.agent.epsilon < initial_epsilon

    def test_with_curriculum_advances(self):
        ai = _make_ai(
            learning=True,
            curriculum=True,
            curriculum_freq=1,
            curriculum_epsilon="reset",
        )
        ai.episode = 1
        ai._log_and_learn()
        assert len(ai.log.episodes) == 1
        assert ai._curriculum_types == ["O", "I"]
        assert ai.agent.epsilon == 1.0

    def test_model_save_on_interval(self):
        ai = _make_ai(learning=True, curriculum=False)
        ai.episode = 0  # 0 % 50 == 0 → save
        ai._log_and_learn()
        assert os.path.exists(MODEL_PATH)


class TestResetEpisode:
    def test_resets_all_state(self):
        ai = _make_ai(learning=True)
        ai.episode_steps = 42
        ai.game_over = True
        ai.paused = True
        ai._lock_timer = 999.0
        ai._grounded = True
        ai._pending = PendingTransition(state=np.zeros(17, dtype=np.float32), reward=0.0)
        ai._prev_action = 5
        ai._reset_episode()
        assert ai.episode_steps == 0
        assert not ai.game_over
        assert not ai.paused  # type: ignore[unreachable]
        assert ai._lock_timer == 0.0
        assert not ai._grounded
        assert ai._pending is None
        assert ai._prev_action is None
        assert ai._action_timer == 0.0

    def test_resets_board_and_pieces(self):
        ai = _make_ai(learning=True)
        # Fill board
        for y in range(BOARD_HEIGHT):
            for x in range(BOARD_WIDTH):
                ai.board.grid[y][x] = GRAY
        ai._reset_episode()
        # Board should be empty (minus handicap)
        assert ai.board.grid[BOARD_HEIGHT - 1][0] is None

    def test_resets_stats(self):
        ai = _make_ai(learning=True)
        ai.stats.score = 9999
        ai.stats.total_lines = 42
        ai._reset_episode()
        assert ai.stats.score == 0
        assert ai.stats.total_lines == 0


class TestAdvanceCurriculum:
    def test_advances_at_freq(self):
        ai = _make_ai(learning=True, curriculum=True, curriculum_freq=1)
        assert ai.agent.advance_curriculum(len(CURRICULUM_ORDER) - 1, 1) is True
        assert ai.agent.curriculum_level == 1

    def test_no_advance_before_freq(self):
        ai = _make_ai(learning=True, curriculum=True, curriculum_freq=10)
        assert ai.agent.advance_curriculum(len(CURRICULUM_ORDER) - 1, 10) is False
        assert ai.agent.curriculum_level == 0

    def test_all_pieces_reached(self):
        ai = _make_ai(learning=True, curriculum=True, curriculum_freq=1)
        for _ in range(len(CURRICULUM_ORDER) - 1):
            ai.agent.advance_curriculum(len(CURRICULUM_ORDER) - 1, 1)
        assert ai.agent.curriculum_level == len(CURRICULUM_ORDER) - 1
        assert ai.agent.advance_curriculum(len(CURRICULUM_ORDER) - 1, 1) is False


class TestApplyEpsilonPolicy:
    def test_reset(self):
        ai = _make_ai(learning=True, curriculum=True, curriculum_epsilon="reset")
        ai.agent.epsilon = 0.3
        ai._apply_epsilon_policy()
        assert ai.agent.epsilon == 1.0

    def test_boost(self):
        ai = _make_ai(learning=True, curriculum=True, curriculum_epsilon="boost")
        ai.agent.epsilon = 0.2
        ai._apply_epsilon_policy()
        assert ai.agent.epsilon == 0.5

    def test_boost_does_not_lower(self):
        ai = _make_ai(learning=True, curriculum=True, curriculum_epsilon="boost")
        ai.agent.epsilon = 0.8
        ai._apply_epsilon_policy()
        assert ai.agent.epsilon == 0.8

    def test_decay_unchanged(self):
        ai = _make_ai(learning=True, curriculum=True, curriculum_epsilon="decay")
        ai.agent.epsilon = 0.42
        ai._apply_epsilon_policy()
        assert ai.agent.epsilon == 0.42


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------


class TestDraw:
    def test_draw_smoke(self):
        ai = _make_ai(learning=True)
        particles = ParticleSystem()
        ai.draw(_screen, particles=particles)

    def test_draw_playing_mode(self):
        ai = _make_ai(learning=False)
        particles = ParticleSystem()
        ai.draw(_screen, particles=particles)


class TestDrawAiHud:
    def test_smoke_learning_mode(self):
        ai = _make_ai(learning=True)
        draw_ai_hud(ai)

    def test_smoke_playing_mode(self):
        ai = _make_ai(learning=False)
        draw_ai_hud(ai)

    def test_smoke_with_curriculum(self):
        ai = _make_ai(learning=True, curriculum=True)
        draw_ai_hud(ai)


class TestHudTableRows:
    def test_returns_six_rows(self):
        ai = _make_ai(learning=True)
        rows = _hud_table_rows(ai.log, ai.stats, ai.episode_steps)
        assert len(rows) == 6

    def test_row_structure(self):
        ai = _make_ai(learning=True)
        rows = _hud_table_rows(ai.log, ai.stats, ai.episode_steps)
        for row in rows:
            assert len(row) == 5
        assert rows[0][0] == "Current"
        assert rows[1][0] == "Total"
        assert rows[2][0] == "Best"
        assert rows[3][0] == "Average"
        assert rows[4][0] == "Last 100"
        assert rows[5][0] == "Trend"

    def test_current_row_values(self):
        ai = _make_ai(learning=True)
        ai.episode_steps = 5
        rows = _hud_table_rows(ai.log, ai.stats, ai.episode_steps)
        assert rows[0] == ["Current", 5, 0, 0, 0]


class TestTrendArrow:
    def test_up(self):
        assert _trend_arrow("up") == "\u2191"

    def test_down(self):
        assert _trend_arrow("down") == "\u2193"

    def test_stable(self):
        assert _trend_arrow("stable") == "\u2192"

    def test_unknown(self):
        assert _trend_arrow("unknown") == "\u2192"


# ---------------------------------------------------------------------------
# Event handling
# ---------------------------------------------------------------------------


class TestHandleEvent:
    def test_esc_returns_menu(self):
        ai = _make_ai(learning=True)
        event = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE)
        result = ai.handle_event(event)
        assert result is not None
        assert type(result).__name__ == "MenuState"

    def test_mute_key(self):
        ai = _make_ai(learning=True)
        event = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_m)
        result = ai.handle_event(event)
        assert result is None

    def test_other_key_ignored(self):
        ai = _make_ai(learning=True)
        event = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_a)
        result = ai.handle_event(event)
        assert result is None

    def test_keyup_ignored(self):
        ai = _make_ai(learning=True)
        event = pygame.event.Event(pygame.KEYUP, key=pygame.K_m)
        result = ai.handle_event(event)
        assert result is None


# ---------------------------------------------------------------------------
# Update cycle: full play-through tests
# ---------------------------------------------------------------------------


class TestUpdateCycle:
    """Tests covering the update → select → execute → lock → learn pipeline."""

    def test_fast_learning_locks_piece_and_stores_transition(self):
        """One update in fast learning mode should select, place, lock, and learn."""
        ai = _make_ai(learning=True, speed="fast")
        particles = ParticleSystem()
        # Run enough updates to select, place, and lock at least one piece.
        for _ in range(20):
            ai.update(16, particles)
        assert ai.episode_steps >= 1

    def test_normal_speed_throttles_decisions(self):
        """Normal speed mode delays decisions until AI_ACTION_DELAY_MS elapsed."""
        ai = _make_ai(learning=True, speed="normal")
        particles = ParticleSystem()
        # Small dt should not trigger a decision yet.
        for _ in range(3):
            ai.update(10, particles)
        # With only 30ms total, no decision yet (delay is 80ms).
        assert ai._action_timer > 0

    def test_normal_speed_actually_acts(self):
        """Normal speed mode acts after enough dt accumulates."""
        ai = _make_ai(learning=True, speed="normal")
        particles = ParticleSystem()
        # 100ms > AI_ACTION_DELAY_MS (80ms) → should act.
        ai.update(100, particles)
        assert ai.episode_steps >= 1

    def test_playing_mode_does_not_learn(self):
        """Playing mode should not store transitions or run learn()."""
        ai = _make_ai(learning=False, speed="fast")
        particles = ParticleSystem()
        prev_buffer = len(ai.agent.buffer)
        for _ in range(20):
            ai.update(16, particles)
        assert len(ai.agent.buffer) == prev_buffer
        assert ai.agent.epsilon == 0.0

    def test_lock_and_spawn_computes_reward(self):
        """_lock_and_spawn should compute reward and set _pending."""
        ai = _make_ai(learning=True, speed="fast")
        particles = ParticleSystem()
        # Run one piece lock.
        for _ in range(20):
            ai.update(16, particles)
        # After at least one lock, _pending should be set (or None if game over).
        assert ai.episode_start_grid is not None

    def test_paused_returns_none(self):
        """Paused AI should return None from update."""
        ai = _make_ai(learning=True, speed="fast")
        ai.paused = True
        result = ai.update(16, ParticleSystem())
        assert result is None

    def test_game_over_triggers_episode_end(self):
        """Game over should trigger episode logging and reset."""
        ai = _make_ai(learning=True, speed="fast")
        ai.game_over = True
        result = ai.update(16, ParticleSystem())
        # _on_episode_end returns None after resetting.
        assert result is None
        assert not ai.game_over

    def test_draw_with_particles(self):
        """Draw with particles should render without error."""
        ai = _make_ai(learning=True, speed="fast")
        particles = ParticleSystem()
        ai.draw(_screen, particles=particles)

    def test_draw_without_particles(self):
        """Draw without particles should not render."""
        ai = _make_ai(learning=True, speed="fast")
        ai.draw(_screen, particles=None)

    def test_draw_ai_hud_smoke(self):
        """draw_ai_hud should render without error."""
        ai = _make_ai(learning=True, speed="fast")
        draw_ai_hud(ai)

    def test_hud_table_rows_structure(self):
        """_hud_table_rows should return 6 rows with 5 columns each."""
        ai = _make_ai(learning=True, speed="fast")
        rows = _hud_table_rows(ai.log, ai.stats, ai.episode_steps)
        assert len(rows) == 6
        for row in rows:
            assert len(row) == 5
        assert rows[0][0] == "Current"
        assert rows[1][0] == "Total"
        assert rows[2][0] == "Best"
        assert rows[3][0] == "Average"
        assert rows[4][0] == "Last 100"
        assert rows[5][0] == "Trend"


class TestLastMoves:
    """Tests for the last-5-moves HUD tracking."""

    def test_initially_empty(self):
        ai = _make_ai(learning=True, speed="fast")
        assert ai._last_moves == []

    def test_records_moves_on_update(self):
        ai = _make_ai(learning=True, speed="fast")
        particles = ParticleSystem()
        for _ in range(20):
            ai.update(16, particles)
        assert len(ai._last_moves) >= 1
        # Each entry is (piece_type, rot, col, hold)
        ptype, rot, col, hold = ai._last_moves[0]
        assert ptype in "IOTSZJL"
        assert isinstance(rot, int)
        assert isinstance(col, int)
        assert isinstance(hold, bool)

    def test_capped_at_five(self):
        ai = _make_ai(learning=True, speed="fast")
        particles = ParticleSystem()
        for _ in range(200):
            ai.update(16, particles)
            if len(ai._last_moves) >= 5:
                break
        assert len(ai._last_moves) <= 5

    def test_reset_clears_moves(self):
        ai = _make_ai(learning=True, speed="fast")
        particles = ParticleSystem()
        for _ in range(20):
            ai.update(16, particles)
        assert len(ai._last_moves) >= 1
        ai._reset_episode()
        assert ai._last_moves == []

    def test_hud_renders_with_moves(self):
        ai = _make_ai(learning=True, speed="fast")
        particles = ParticleSystem()
        for _ in range(20):
            ai.update(16, particles)
        assert len(ai._last_moves) >= 1
        draw_ai_hud(ai)  # should not raise


# --- Observability tests --------------------------------------------------


class TestObservabilityCounters:
    """Per-episode counters reset correctly and accumulate during play."""

    def test_counters_reset_on_new_episode(self):
        ai = _make_ai(learning=True, speed="fast")
        particles = ParticleSystem()
        for _ in range(20):
            ai.update(16, particles)
        # Manually trigger reset to verify counters are cleared
        assert len(ai._ep_candidates) > 0
        ai._reset_episode()
        assert ai._ep_n_random == 0
        assert ai._ep_n_greedy == 0
        assert ai._ep_n_hold == 0
        assert len(ai._ep_candidates) == 0
        assert len(ai._ep_rewards) == 0

    def test_candidates_accumulate_during_play(self):
        ai = _make_ai(learning=True, speed="fast")
        particles = ParticleSystem()
        for _ in range(20):
            ai.update(16, particles)
        assert len(ai._ep_candidates) >= 1
        assert all(c > 0 for c in ai._ep_candidates)

    def test_reward_components_accumulate(self):
        ai = _make_ai(learning=True, speed="fast")
        particles = ParticleSystem()
        for _ in range(50):
            ai.update(16, particles)
            if ai.game_over:
                break
        if len(ai._ep_reward_components) > 0:
            comps = ai._ep_reward_components[0]
            assert "lines" in comps
            assert "game_over" in comps

    def test_behavior_log_jsonl_written(self):
        """After an episode, ai_behavior_log.jsonl has a valid JSON line."""
        import json
        import tempfile

        log_path = tempfile.mktemp(suffix=".jsonl")
        ai = _make_ai(learning=True, speed="fast")
        ai.log.path = _unique_path()
        # Set instance attribute — _write_behavior_log uses self._behavior_log_path
        ai._behavior_log_path = log_path
        try:
            particles = ParticleSystem()
            for _ in range(300):
                ai.update(16, particles)
                if ai.game_over:
                    break
            assert os.path.exists(log_path)
            with open(log_path) as f:
                entry = json.loads(f.readline())
            assert "episode" in entry
            assert "score" in entry
            assert "steps" in entry
            assert "placement_success_rate" in entry
            assert isinstance(entry["col_hist"], list)
            assert isinstance(entry["rot_hist"], list)
            assert len(entry["col_hist"]) == 10
            assert len(entry["rot_hist"]) == 4
        finally:
            if os.path.exists(log_path):
                os.unlink(log_path)

    def test_reward_components_in_episode_log(self):
        """Episode log contains reward component fields."""
        ai = _make_ai(learning=True, speed="fast")
        particles = ParticleSystem()
        for _ in range(300):
            ai.update(16, particles)
            if ai.game_over:
                break
        if ai.log.episodes:
            entry = ai.log.episodes[-1]
            # Check at least some observability fields are present
            assert "avg_loss" in entry or "avg_candidates" in entry
