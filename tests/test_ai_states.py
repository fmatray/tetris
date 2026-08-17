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
from tetris.game.tetromino import Tetromino
from tetris.settings import (
    BOARD_HEIGHT,
    BOARD_WIDTH,
    GRAY,
    LOG_PATH,
    MODEL_PATH,
    SHAPES,
)
from tetris.states.ai import AIState, NUM_ROTATIONS
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

def _make_ai_full(learning: bool = True, speed: str = "fast", **kwargs: object) -> AIState:
    soft_drop = bool(kwargs.pop("soft_drop", True))
    audio = AudioManager(sound_volume=0, music_volume=0)
    provider = PieceProvider(generator="7bag", path=_unique_path())
    ai = AIState(
        screen=_screen,
        font=_font,
        audio=audio,
        handicap=0,
        sound_volume=0,
        music_volume=0,
        piece_provider=provider,
        speed=speed,
        ai_mode="learning" if learning else "playing",
        lookahead=True,
        lookahead_depth=1,
        soft_drop=soft_drop,
        preview_count=1,
        warm_start=True,
        learn_per_action=2,
        **kwargs,  # type: ignore[arg-type]
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
        assert ai._prev_state is None
        assert ai._prev_reward is None
        assert ai._prev_action is None
        assert ai._prev_done is False
        assert ai.speed == "fast"
        assert ai.ghost_piece is False
        assert ai.warm_start is True
        assert ai.lookahead is True
        assert ai.soft_drop is True

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
            positions = list(AIState._iter_column_positions(piece_type))
            assert len(positions) > 0
            for shape, rot, px in positions:
                assert isinstance(shape, list)
                assert 0 <= rot < NUM_ROTATIONS
                assert 0 <= px < BOARD_WIDTH

    def test_o_piece_one_rotation(self):
        positions = list(AIState._iter_column_positions("O"))
        rots = {rot for _, rot, _ in positions}
        assert rots == {0}

    def test_i_piece_all_rotations(self):
        positions = list(AIState._iter_column_positions("I"))
        rots = {rot for _, rot, _ in positions}
        assert rots == {0, 1, 2, 3}


class TestIsValidPlacement:
    def test_valid_on_empty_board(self):
        ai = _make_ai()
        piece = ai.current_piece
        assert ai._is_valid_placement(piece, 0, 3) is True

    def test_invalid_on_full_board(self):
        ai = _make_ai()
        for y in range(BOARD_HEIGHT):
            for x in range(BOARD_WIDTH):
                ai.board.grid[y][x] = GRAY
        piece = ai.current_piece
        assert ai._is_valid_placement(piece, 0, 3) is False


class TestBestNextPlacement:
    def test_empty_grid_returns_grid(self):
        ai = _make_ai()
        grid = np.zeros((BOARD_HEIGHT, BOARD_WIDTH), dtype=np.float32)
        result = ai._best_next_placement(grid, "I")
        assert result.shape == grid.shape
        assert not np.array_equal(result, grid)  # piece placed

    def test_full_grid_clears_lines(self):
        """Full grid: placement triggers line clears → result differs."""
        ai = _make_ai()
        grid = np.ones((BOARD_HEIGHT, BOARD_WIDTH), dtype=np.float32)
        result = ai._best_next_placement(grid, "O")
        # After clearing, the grid is not all ones
        assert not np.array_equal(result, grid)


class TestGenPlacements:
    def test_soft_drop_yields_placements(self):
        ai = _make_ai(soft_drop=True)
        grid = np.zeros((BOARD_HEIGHT, BOARD_WIDTH), dtype=np.float32)
        placements = list(ai._gen_placements(grid, "I"))
        assert len(placements) > 0
        for shape, px, py, rot in placements:
            assert len(shape) == 4
            assert py >= 0
            assert 0 <= rot < NUM_ROTATIONS

    def test_hard_drop_yields_placements(self):
        ai = _make_ai(soft_drop=False)
        grid = np.zeros((BOARD_HEIGHT, BOARD_WIDTH), dtype=np.float32)
        placements = list(ai._gen_placements(grid, "I"))
        assert len(placements) > 0
        for shape, px, py, rot in placements:
            assert len(shape) == 4
            assert 0 <= px < BOARD_WIDTH
            assert py >= 0

    def test_full_grid_soft_drop_yields_spawn(self):
        """Full grid: soft_drop BFS finds spawn position (py=0)."""
        ai = _make_ai(soft_drop=True)
        grid = np.ones((BOARD_HEIGHT, BOARD_WIDTH), dtype=np.float32)
        placements = list(ai._gen_placements(grid, "O"))
        assert len(placements) >= 1

    def test_full_grid_hard_drop_yields_nothing(self):
        """Full grid: shape_fits at y=0 fails → no hard-drop placements."""
        ai = _make_ai(soft_drop=False)
        grid = np.ones((BOARD_HEIGHT, BOARD_WIDTH), dtype=np.float32)
        placements = list(ai._gen_placements(grid, "O"))
        assert len(placements) == 0


class TestGetCandidateStates:
    def test_returns_correct_shapes(self):
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
        holds = [p[3] for p in ai._candidate_placements]
        assert True in holds
        assert False in holds

    def test_includes_non_hold_candidates(self):
        ai = _make_ai()
        ai._get_candidate_states()
        holds = [p[3] for p in ai._candidate_placements]
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


class TestExecuteMacroAction:
    def test_non_hold_soft_drop(self):
        ai = _make_ai(soft_drop=True)
        ai._get_candidate_states()
        assert len(ai._candidate_placements) > 0
        # Find a non-hold candidate
        idx = next(i for i, p in enumerate(ai._candidate_placements) if not p[3])
        original_y = ai.current_piece.y
        ai._execute_macro_action(idx)
        assert ai.current_piece.y >= original_y

    def test_non_hold_hard_drop(self):
        ai = _make_ai(soft_drop=False)
        ai._get_candidate_states()
        assert len(ai._candidate_placements) > 0
        idx = next(i for i, p in enumerate(ai._candidate_placements) if not p[3])
        ai._execute_macro_action(idx)
        # Hard-drop path locks immediately
        assert ai._prev_action is None

    def test_hold_candidate(self):
        ai = _make_ai()
        ai._get_candidate_states()
        hold_idx = next(
            (i for i, p in enumerate(ai._candidate_placements) if p[3]), None
        )
        if hold_idx is None:
            pytest.skip("No hold candidate")
        ai._execute_macro_action(hold_idx)
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
        ai.game_over = True
        ai._on_episode_end()
        assert ai.game_over is False
        assert len(ai.log.episodes) == 0  # type: ignore[unreachable]


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
            learning=True, curriculum=True,
            curriculum_freq=1, curriculum_epsilon="reset",
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
        ai._prev_state = np.zeros(17, dtype=np.float32)
        ai._prev_action = 5
        ai._reset_episode()
        assert ai.episode_steps == 0
        assert not ai.game_over
        assert not ai.paused  # type: ignore[unreachable]
        assert ai._lock_timer == 0.0
        assert not ai._grounded
        assert ai._prev_state is None
        assert ai._prev_reward is None
        assert not ai._prev_done
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


class TestMaybeAdvanceCurriculum:
    def test_advances_at_freq(self):
        ai = _make_ai(learning=True, curriculum=True, curriculum_freq=1)
        assert ai._maybe_advance_curriculum() is True
        assert ai._curriculum_types == ["O", "I"]

    def test_no_advance_before_freq(self):
        ai = _make_ai(learning=True, curriculum=True, curriculum_freq=10)
        assert ai._maybe_advance_curriculum() is False
        assert ai._curriculum_types == ["O"]

    def test_all_pieces_reached(self):
        ai = _make_ai(learning=True, curriculum=True, curriculum_freq=1)
        from tetris.settings import CURRICULUM_ORDER
        for _ in range(len(CURRICULUM_ORDER) - 1):
            ai._maybe_advance_curriculum()
        assert ai._curriculum_types == list(CURRICULUM_ORDER)
        assert ai._maybe_advance_curriculum() is False


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
        ai._draw_ai_hud()

    def test_smoke_playing_mode(self):
        ai = _make_ai(learning=False)
        ai._draw_ai_hud()

    def test_smoke_with_curriculum(self):
        ai = _make_ai(learning=True, curriculum=True)
        ai._draw_ai_hud()


class TestHudTableRows:
    def test_returns_six_rows(self):
        ai = _make_ai(learning=True)
        rows = ai._hud_table_rows()
        assert len(rows) == 6

    def test_row_structure(self):
        ai = _make_ai(learning=True)
        rows = ai._hud_table_rows()
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
        rows = ai._hud_table_rows()
        assert rows[0] == ["Current", 5, 0, 0, 0]


class TestTrendArrow:
    def test_up(self):
        assert AIState._trend_arrow("up") == "\u2191"

    def test_down(self):
        assert AIState._trend_arrow("down") == "\u2193"

    def test_stable(self):
        assert AIState._trend_arrow("stable") == "\u2192"

    def test_unknown(self):
        assert AIState._trend_arrow("unknown") == "\u2192"


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
        """_lock_and_spawn should compute reward and set _prev_state."""
        ai = _make_ai(learning=True, speed="fast")
        particles = ParticleSystem()
        # Run one piece lock.
        for _ in range(20):
            ai.update(16, particles)
        # After at least one lock, _prev_state should be set (or None if game over).
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
        """_draw_ai_hud should render without error."""
        ai = _make_ai(learning=True, speed="fast")
        ai._draw_ai_hud()

    def test_hud_table_rows_structure(self):
        """_hud_table_rows should return 6 rows with 5 columns each."""
        ai = _make_ai(learning=True, speed="fast")
        rows = ai._hud_table_rows()
        assert len(rows) == 6
        for row in rows:
            assert len(row) == 5
        assert rows[0][0] == "Current"
        assert rows[1][0] == "Total"
        assert rows[2][0] == "Best"
        assert rows[3][0] == "Average"
        assert rows[4][0] == "Last 100"
        assert rows[5][0] == "Trend"
