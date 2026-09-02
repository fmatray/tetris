"""ARE (entry delay) + IRS/IHS buffering tests.

All tests opt in with ``are=True``; the default config keeps ARE off so
existing behavior is unchanged.
"""

from __future__ import annotations

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

pygame.init()

from tetris.game.tetromino import Tetromino
from tetris.settings import ARE_MS
from tetris.states.game import GameConfig
from tetris.visuals.particles import ParticleSystem
from tests.helpers import make_audio, make_font, make_game_config, make_screen


def _make_state(**config_kwargs):
    """HumanState with ARE-capable config (are=True by default here)."""
    from tetris.states.human import HumanState

    config_kwargs.setdefault("are", True)
    return HumanState(
        screen=make_screen(),
        font=make_font(),
        audio=make_audio(),
        config=make_game_config(**config_kwargs),
    )


def _drop_and_lock(state) -> None:
    """Slam the piece to the floor, then lock (avoids the spawn top-out path)."""
    state.board.hard_drop(state.current_piece)
    state._lock_and_spawn()


def test_are_off_by_default() -> None:
    """Default GameConfig has are=False — no behavior change."""
    assert (
        GameConfig(
            handicap=0,
            sound_volume=0,
            music_volume=0,
            music_song="korobeiniki",
            debug=False,
            ghost_piece=True,
            preview_count=1,
            speed_mode="normal",
        ).are
        is False
    )
    assert make_game_config().are is False


def test_are_gates_activity() -> None:
    """With are=True, locking starts a timer; movement/gravity wait it out."""
    state = _make_state()
    particles = ParticleSystem()
    assert state._are_timer == 0.0
    assert not state.are_active

    _drop_and_lock(state)
    assert state._are_timer == ARE_MS
    assert state.are_active

    assert state.current_piece is not None  # type: ignore[unreachable]
    x_before = state.current_piece.x
    state._move_left()
    state._move_right()
    assert state.current_piece.x == x_before

    # Gravity is gated: piece does not fall during ARE
    y_before = state.current_piece.y
    state.update(200, particles)
    assert state.current_piece.y == y_before

    # ARE expires, piece becomes active
    state.update(ARE_MS, particles)
    assert state._are_timer == 0.0
    assert not state.are_active


def test_irs_buffer_applied_at_spawn() -> None:
    """Rotation input during ARE is buffered and applied when ARE ends."""
    state = _make_state()
    particles = ParticleSystem()
    _drop_and_lock(state)
    state.current_piece = Tetromino("T")  # rotatable at spawn, deterministic
    state._are_timer = ARE_MS  # restore the ARE window the swap consumed
    rot_before = state.current_piece.rotation

    state._rotate_cw()  # during ARE: buffered
    assert state._irs_pending == 1
    assert state.current_piece.rotation == rot_before  # not applied yet

    state.update(ARE_MS, particles)  # expire ARE -> apply IRS
    assert state._irs_pending == 0
    assert (state.current_piece.rotation - rot_before) % 4 == 1


def test_irs_last_input_wins() -> None:
    """During ARE, the most recent rotation input wins (ccw overrides cw)."""
    state = _make_state()
    particles = ParticleSystem()
    _drop_and_lock(state)
    state.current_piece = Tetromino("T")
    state._are_timer = ARE_MS
    state._rotate_cw()
    state._rotate_ccw()
    assert state._irs_pending == -1

    rot_before = state.current_piece.rotation
    state.update(ARE_MS, particles)
    assert (state.current_piece.rotation - rot_before) % 4 == 3


def test_ihs_buffer_swaps_piece_at_spawn() -> None:
    """Hold input during ARE is buffered; spawn performs the swap."""
    state = _make_state()
    particles = ParticleSystem()
    _drop_and_lock(state)
    state.current_piece = Tetromino("T")
    state._are_timer = ARE_MS
    spawned_type = state.current_piece.type

    state._hold()  # during ARE: buffered
    assert state._ihs_pending is True
    assert state.current_piece.type == spawned_type  # no swap yet

    state.update(ARE_MS, particles)
    assert state._ihs_pending is False
    assert state.hold_piece is not None  # type: ignore[unreachable]
    assert state.hold_piece.type == spawned_type
    assert state.current_piece.type != spawned_type  # swapped with next


def test_soft_drop_buffers_during_are() -> None:
    """Held soft-drop key sets down_pressed during ARE; drop resumes after."""
    state = _make_state()
    _drop_and_lock(state)
    assert not state.down_pressed

    state._soft_drop()
    assert state.down_pressed is True


def test_are_off_no_timer() -> None:
    """With are=False (default), locking does not start an ARE timer."""
    state = _make_state(are=False)
    _drop_and_lock(state)
    assert state._are_timer == 0.0
    assert not state.are_active


def test_ai_learning_fast_forwards_are() -> None:
    """AIState learning mode zeroes the ARE timer on lock (training speed)."""
    from tetris.game.piece_provider import PieceProvider
    from tetris.states.ai import AIConfig, AIState

    state = AIState(
        screen=make_screen(),
        font=make_font(),
        audio=make_audio(),
        config=make_game_config(are=True, preview_count=1),
        ai_config=AIConfig(
            epsilon_decay=0.999,
            epsilon_end=0.1,
            lr=1e-3,
            gamma=0.97,
            batch_size=64,
            buffer_size=1000,
            ai_mode="learning",
            curriculum=False,
            curriculum_freq=50,
            curriculum_epsilon="reset",
            warm_start=True,
            learn_per_action=2,
            lookahead=True,
            lookahead_depth=1,
        ),
        piece_provider=PieceProvider(generator="7bag"),
        speed="fast",
    )
    state.board.hard_drop(state.current_piece)
    state._lock_and_spawn()
    assert state._are_timer == 0.0  # learning mode fast-forwards ARE


def test_eltetris_are_gating() -> None:
    """ElTetrisState update defers to GameState while ARE is active."""
    from tetris.game.piece_provider import PieceProvider
    from tetris.states.eltetris import BotConfig, ElTetrisState

    state = ElTetrisState(
        screen=make_screen(),
        font=make_font(),
        audio=make_audio(),
        config=make_game_config(are=True),
        bot_config=BotConfig(lookahead=True, lookahead_depth=1),
        piece_provider=PieceProvider(generator="7bag"),
    )
    state._are_timer = 50.0
    # Update during ARE must not attempt selection (no exception) and just ticks the timer
    state.update(30, ParticleSystem())
    assert state._are_timer == 20.0


def test_mcp_snapshot_are_ms_and_reset() -> None:
    """MCP snapshot exposes are_ms; _reset_game clears ARE state."""
    from tetris.states.mcp import MCPConfig, MCPState

    state = MCPState(
        make_screen(),
        make_font(),
        make_audio(),
        make_game_config(are=True),
        MCPConfig(port=8081),
        start_server=False,
    )
    snap = state._board_snapshot()
    assert snap["are_ms"] == 0.0

    state._are_timer = 42.5
    state._irs_pending = 1
    state._ihs_pending = True
    state._reset_game(seed=123)
    assert state._are_timer == 0.0
    assert state._irs_pending == 0
    assert state._ihs_pending is False


def test_simulator_sim_fields_round_trip() -> None:
    """ARE fields survive simulator SIM_FIELDS save/restore."""
    from tetris.states.simulator import SIM_FIELDS

    for field in ("_are_timer", "_irs_pending", "_ihs_pending"):
        assert field in SIM_FIELDS


def test_renderer_skips_piece_during_are() -> None:
    """Renderer omits ghost and current piece while ARE is active."""
    from tetris.visuals.renderer import Renderer

    renderer = Renderer(make_screen(), make_font())
    state = _make_state()
    state._are_timer = 1.0
    # Smoke: no exception, board still drawn
    renderer.render_frame(state, ParticleSystem())
