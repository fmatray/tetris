"""Tests for MCPState: construction, action dispatch, frozen game, board snapshot, game over."""

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

pygame.init()
pygame.mixer.init()

from tetris.audio import AudioManager
from tetris.states.game import GameConfig
from tetris.states.mcp import MCPConfig, MCPState, draw_mcp_hud
from tetris.visuals.particles import ParticleSystem
from tetris.game.shapes import get_shape_rot
from tetris.game.tetromino import Tetromino
from tetris.settings import BOARD_HEIGHT, BOARD_WIDTH


def _make_mcp_state(start_server: bool = True) -> MCPState:
    screen = pygame.Surface((640, 480))
    font = pygame.font.Font(None, 24)
    audio = AudioManager(sound_volume=0, music_volume=0)
    return MCPState(
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
        start_server=start_server,
    )


# ── Construction ──────────────────────────────────────────────────────


def test_mcp_state_construction_no_server():
    """MCPState can be constructed without starting the server."""
    state = _make_mcp_state(start_server=False)
    assert state.player_type == "MCP"
    assert state.mcp_config.port == 8765
    assert state._server is None
    assert state.game_over is False


def test_mcp_state_action_queue_empty_on_init():
    """Action queue starts empty."""
    state = _make_mcp_state(start_server=False)
    assert state._action_queue.empty()


# ── Frozen game ───────────────────────────────────────────────────────


def test_mcp_state_frozen_when_queue_empty():
    """update() returns None and does not advance gravity when queue is empty."""
    state = _make_mcp_state(start_server=False)
    particles = ParticleSystem()
    dt = 1.0 / 60.0
    initial_y = state.current_piece.y
    for _ in range(120):  # 2 seconds of game time
        result = state.update(dt, particles)
        assert result is None
    # Piece should not have moved (frozen)
    assert state.current_piece.y == initial_y


# ── Action dispatch ───────────────────────────────────────────────────


def test_mcp_state_execute_actions():
    """_execute_actions dispatches valid actions and reports unknown ones."""
    state = _make_mcp_state(start_server=False)
    results = state._execute_actions(["left", "right", "bad_action"])
    assert results[0] == "ok"
    assert results[1] == "ok"
    assert results[2].startswith("unknown:")


def test_mcp_state_actions_dict_keys():
    """_ACTIONS dict has all expected action names."""
    expected = {"left", "right", "rotate_cw", "rotate_ccw", "soft_drop", "hard_drop", "hold", "start_game"}
    assert set(MCPState._ACTIONS.keys()) == expected


# ── Board snapshot ────────────────────────────────────────────────────


def test_mcp_state_board_snapshot_keys():
    """_board_snapshot returns dict with all expected keys."""
    state = _make_mcp_state(start_server=False)
    snap = state._board_snapshot(["ok"])
    expected_keys = {
        "board",
        "current_piece",
        "next_piece",
        "preview_pieces",
        "hold_piece",
        "can_hold",
        "score",
        "lines",
        "level",
        "game_over",
        "action_results",
    }
    assert set(snap.keys()) == expected_keys


def test_mcp_state_board_snapshot_no_action_results():
    """_board_snapshot without action_results omits that key."""
    state = _make_mcp_state(start_server=False)
    snap = state._board_snapshot()
    assert "action_results" not in snap


def test_mcp_state_board_snapshot_board_is_2d_list():
    """board field is a 2D list of 0/1 ints."""
    state = _make_mcp_state(start_server=False)
    snap = state._board_snapshot()
    assert isinstance(snap["board"], list)
    assert all(isinstance(row, list) for row in snap["board"])
    assert all(cell in (0, 1) for row in snap["board"] for cell in row)


def test_mcp_state_reset_game_via_queue():
    """start_game action resets the board and returns a fresh snapshot."""
    import queue as q_mod

    state = _make_mcp_state(start_server=False)
    # Simulate some progress: lock a piece to get non-zero score
    state._hard_drop()
    assert state.stats.score > 0
    # Queue a start_game reset
    result_q: q_mod.Queue = q_mod.Queue()
    state._action_queue.put((["start_game"], 0, result_q))
    state.update(1.0 / 60.0, ParticleSystem())
    snap = result_q.get()
    assert snap["score"] == 0
    assert snap["lines"] == 0
    assert snap["level"] == 0
    assert snap["game_over"] is False
    assert snap["action_results"] == ["ok"]


# ── Queue processing ─────────────────────────────────────────────────


def test_mcp_state_processes_queue_request():
    """update() processes a queued request and returns the snapshot via result_queue."""
    import queue as q_mod

    state = _make_mcp_state(start_server=False)
    particles = ParticleSystem()
    result_q: q_mod.Queue = q_mod.Queue()
    state._action_queue.put((["left"], 0, result_q))
    state.update(1.0 / 60.0, particles)
    assert not result_q.empty()
    snap = result_q.get()
    assert snap["action_results"] == ["ok"]
    assert state._last_tool_call is not None
    assert state._last_tool_call["actions"] == ["left"]


def test_mcp_state_advances_frames():
    """update() advances N frames when frames > 0."""
    import queue as q_mod

    state = _make_mcp_state(start_server=False)
    particles = ParticleSystem()
    result_q: q_mod.Queue = q_mod.Queue()
    # Request 60 frames = 1 second at 60 FPS
    state._action_queue.put(([], 60, result_q))
    state.update(1.0 / 60.0, particles)
    snap = result_q.get()
    assert "score" in snap


# ── Game over ────────────────────────────────────────────────────────


def test_mcp_state_game_over_stays_in_state():
    """Top-out no longer leaves MCP; update() stays and server survives."""
    from tetris.states.menu import MenuState

    screen = pygame.Surface((640, 480))
    font = pygame.font.Font(None, 24)
    audio = AudioManager(sound_volume=0, music_volume=0)
    menu = MenuState(screen, font, audio)
    state = MCPState(
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
        menu=menu,
    )
    state.game_over = True
    result = state.update(1.0 / 60.0, ParticleSystem())
    assert result is None
    assert state.game_over is True


def test_mcp_state_quit_returns_menu():
    """An explicit quit request returns to the menu and stops the server."""
    import queue as q_mod
    from tetris.states.menu import MenuState

    screen = pygame.Surface((640, 480))
    font = pygame.font.Font(None, 24)
    audio = AudioManager(sound_volume=0, music_volume=0)
    menu = MenuState(screen, font, audio)
    state = MCPState(
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
        menu=menu,
    )
    result_q: q_mod.Queue = q_mod.Queue()
    state._action_queue.put((["quit"], 0, result_q))
    result = state.update(1.0 / 60.0, ParticleSystem())
    assert result is menu
    assert result_q.get()["game_over"] == state.game_over


def test_mcp_state_start_game_after_game_over():
    """start_game resets a topped-out board within the same session."""
    import queue as q_mod

    state = _make_mcp_state(start_server=False)
    state.game_over = True
    result_q: q_mod.Queue = q_mod.Queue()
    state._action_queue.put((["start_game"], 0, result_q))
    result = state.update(1.0 / 60.0, ParticleSystem())
    assert result is None
    assert all(cell is None for row in state.board.grid for cell in row)
    assert state.game_over is False


def test_mcp_state_snapshot_lines_cleared_field():
    """_board_snapshot includes lines_cleared only when passed."""
    state = _make_mcp_state(start_server=False)
    snap = state._board_snapshot(["ok"], lines_cleared=2)
    assert "lines_cleared" in snap
    assert snap["lines_cleared"] == 2


def test_mcp_state_lines_cleared_via_queue():
    """A move that completes a row reports lines_cleared == 1."""
    import queue as q_mod

    state = _make_mcp_state(start_server=False)
    for c in range(BOARD_WIDTH - 1):
        state.board.grid[BOARD_HEIGHT - 1][c] = (1, 1, 1)
    state.current_piece = Tetromino("I")
    state.current_piece.rotation = 1
    state.current_piece.shape = get_shape_rot("I", 1)
    state.current_piece.x = BOARD_WIDTH - 3
    state.current_piece.y = 0
    result_q: q_mod.Queue = q_mod.Queue()
    state._action_queue.put((["hard_drop"], 0, result_q))
    state.update(1.0 / 60.0, ParticleSystem())
    snap = result_q.get()
    assert snap["lines_cleared"] == 1
    assert snap["lines"] == 1
    assert snap["game_over"] is False


def test_mcp_state_hold_blocked_when_unavailable():
    """hold reports 'blocked' when _can_hold is False."""
    state = _make_mcp_state(start_server=False)
    state._can_hold = False
    assert state._execute_actions(["hold"]) == ["blocked"]
    state._can_hold = True
    assert state._execute_actions(["hold"]) == ["ok"]


def test_mcp_state_update_swallows_exception():
    """A handler that raises yields an error snapshot; update() never raises."""
    import queue as q_mod

    state = _make_mcp_state(start_server=False)

    def boom() -> None:
        raise RuntimeError("kaboom")

    state._move_left = boom  # type: ignore[method-assign]
    result_q: q_mod.Queue = q_mod.Queue()
    state._action_queue.put((["left"], 0, result_q))
    result = state.update(1.0 / 60.0, ParticleSystem())
    assert result is None
    snap = result_q.get()
    assert "error" in snap
    assert "kaboom" in snap["error"]


def test_shapes_payload():
    """_shapes_payload exposes shapes, kicks, spawn, and board geometry."""
    from tetris.mcp_server import _shapes_payload

    p = _shapes_payload()
    assert {"shapes", "srs_kicks", "spawn", "board"} <= set(p)
    assert len(p["shapes"]["I"]) == 4
    assert len(p["srs_kicks"]["JLSTZ"]) == 8
    assert p["spawn"]["x"] == BOARD_WIDTH // 2 - 2
    assert p["board"]["hidden_rows"] == 2


# ── MCPConfig ─────────────────────────────────────────────────────────


def test_mcp_config_is_frozen():
    """MCPConfig is a frozen dataclass."""
    from dataclasses import is_dataclass

    config = MCPConfig(port=9999)
    assert is_dataclass(config)
    try:
        config.port = 8888  # type: ignore[misc]
        assert False, "Should have raised FrozenInstanceError"
    except AttributeError:
        pass


def test_mcp_config_port():
    """MCPConfig stores port correctly."""
    config = MCPConfig(port=8766)
    assert config.port == 8766


# ── Debug HUD ─────────────────────────────────────────────────────────


def test_mcp_state_draw_debug_hud_no_error():
    """draw() with debug=True renders the MCP HUD without error."""
    state = _make_mcp_state(start_server=False)
    state.debug = True
    screen = pygame.Surface((1500, 800))
    particles = ParticleSystem()
    state.draw(screen, particles=particles)


def test_mcp_state_draw_no_debug_no_hud():
    """draw() with debug=False does not raise."""
    state = _make_mcp_state(start_server=False)
    screen = pygame.Surface((1500, 800))
    particles = ParticleSystem()
    state.draw(screen, particles=particles)


def test_draw_mcp_hud_with_last_tool_call():
    """draw_mcp_hud renders without error when last_tool_call is set."""
    state = _make_mcp_state(start_server=False)
    state._last_tool_call = {"actions": ["left", "rotate_cw"], "frames": 5, "results": ["ok", "ok"]}
    state._last_snapshot = {
        "score": 1000,
        "lines": 5,
        "level": 2,
        "game_over": False,
    }
    screen = pygame.Surface((1500, 800))
    font = pygame.font.Font(None, 24)
    draw_mcp_hud(screen, font, state)


# ── Server lifecycle ─────────────────────────────────────────────────


def test_mcp_state_stop_server_clears_reference():
    """_stop_server clears the server reference."""
    state = _make_mcp_state(start_server=False)
    state._server = None  # already None
    state._stop_server()
    assert state._server is None
