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
from tetris.states.simulator import build_board_repr, simulate_actions


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
            preview_count=3,
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
        "holes",
        "overhangs",
    }
    assert set(snap.keys()) == expected_keys


def test_mcp_state_board_snapshot_no_action_results():
    """_board_snapshot without action_results omits that key."""
    state = _make_mcp_state(start_server=False)
    snap = state._board_snapshot()
    assert "action_results" not in snap


def test_mcp_state_board_snapshot_board_is_2d_list():
    """board field is a 2D list of 0/1 ints (and markers X/O when present)."""
    state = _make_mcp_state(start_server=False)
    snap = state._board_snapshot()
    assert all(isinstance(row, list) for row in snap["board"])
    assert all(cell in (0, 1, "X", "O") for row in snap["board"] for cell in row)


def test_mcp_state_board_snapshot_markers_and_counts():
    """Board repr marks holes as 'X', overhangs as 'O', and reports counts."""
    state = _make_mcp_state(start_server=False)
    g = state.board.grid
    for y in range(22):
        g[y][0] = (255, 0, 0)
        g[y][1] = (255, 0, 0)
        g[y][2] = (255, 0, 0)
    # unreachable holes at bottom of capped columns 0/1
    g[21][0] = None
    g[21][1] = None
    # reachable overhang under a ledge in column 5
    g[0][5] = None
    g[1][5] = (0, 255, 0)
    for y in range(3, 22):
        g[y][5] = (0, 255, 0)
    repr_grid, holes, overhangs = build_board_repr(state.board)
    assert holes == 2
    assert overhangs == 1
    flat = [c for row in repr_grid for c in row]
    assert flat.count("X") == holes
    assert flat.count("O") == overhangs
    snap = state._board_snapshot()
    assert snap["holes"] == holes
    assert snap["overhangs"] == overhangs


def test_mcp_state_reset_game_via_queue():
    """start_game action resets the board and returns a fresh snapshot."""
    import queue as q_mod

    state = _make_mcp_state(start_server=False)
    # Simulate some progress: lock a piece to get non-zero score
    state._hard_drop()
    assert state.stats.score > 0
    # Queue a start_game reset
    result_q: q_mod.Queue = q_mod.Queue()
    state._action_queue.put((["start_game"], 0, result_q, False))
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
    state._action_queue.put((["left"], 0, result_q, False))
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
    state._action_queue.put(([], 60, result_q, False))
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
    state._action_queue.put((["quit"], 0, result_q, False))
    result = state.update(1.0 / 60.0, ParticleSystem())
    assert result is menu
    assert result_q.get()["game_over"] == state.game_over


def test_mcp_state_start_game_after_game_over():
    """start_game resets a topped-out board within the same session."""
    import queue as q_mod

    state = _make_mcp_state(start_server=False)
    state.game_over = True
    result_q: q_mod.Queue = q_mod.Queue()
    state._action_queue.put((["start_game"], 0, result_q, False))
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
    state._action_queue.put((["hard_drop"], 0, result_q, False))
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
    state._action_queue.put((["left"], 0, result_q, False))
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


# ── Simulate (non-mutating) ──────────────────────────────────────────


def test_simulate_actions_returns_snapshot_schema():
    """simulate_actions returns the same snapshot schema as play (no error key)."""
    state = _make_mcp_state(start_server=False)
    dt = 1 / 60.0
    snap = simulate_actions(state, ["left", "hard_drop"], 0, dt)
    assert "error" not in snap
    expected_keys = {
        "board",
        "holes",
        "overhangs",
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
        "lines_cleared",
        "locked_pieces",
    }
    assert set(snap.keys()) == expected_keys
    assert snap["action_results"] == ["ok", "ok"]


def test_simulate_actions_records_locked_pieces_in_order():
    """locked_pieces lists types in lock order; preview drains to empty."""
    state = _make_mcp_state(start_server=False)
    dt = 1 / 60.0
    # Known horizon: I (current), Z (next), J + T (previews).
    state.current_piece = Tetromino("I")
    state.next_piece = Tetromino("Z")
    state.preview_pieces = [Tetromino("J"), Tetromino("T")]
    snap = simulate_actions(state, ["hard_drop", "hard_drop"], 0, dt)
    assert "error" not in snap
    assert snap["locked_pieces"] == ["I", "Z"]
    assert snap["current_piece"] == "J"
    assert snap["next_piece"] == "T"
    assert snap["preview_pieces"] == []


def test_simulate_actions_does_not_mutate_state():
    """simulate_actions leaves board, score, and piece queue untouched."""
    state = _make_mcp_state(start_server=False)
    dt = 1 / 60.0
    pieces_before = state.pieces
    score_before = state.stats.score
    piece_before = state.current_piece
    board_before = [row[:] for row in state.board.grid]
    snap = simulate_actions(state, ["left", "hard_drop"], 0, dt)
    assert "error" not in snap
    assert state.pieces is pieces_before
    assert state.stats.score == score_before
    assert state.current_piece is piece_before
    assert state.board.grid == board_before
    assert state.locked_pieces == []


def test_simulate_actions_matches_real_application():
    """Simulated board equals the board from really applying the same actions."""
    state = _make_mcp_state(start_server=False)
    dt = 1 / 60.0
    actions = ["left", "hard_drop"]
    sim = simulate_actions(state, actions, 0, dt)
    # simulate_actions restores the state in its finally block; re-apply for real.
    state._execute_actions(actions)
    assert sim["board"] == build_board_repr(state.board)[0]


def test_simulate_via_queue_flag_does_not_mutate():
    """update() with simulate=True returns a snapshot without mutating state."""
    import queue as _queue

    state = _make_mcp_state(start_server=False)
    dt = 1 / 60.0
    pieces_before = state.pieces
    piece_before = state.current_piece
    result_q: _queue.Queue = _queue.Queue()
    state._action_queue.put((["left", "hard_drop"], 0, result_q, True))
    snap = state.update(dt, ParticleSystem())
    assert snap is None  # simulate path returns None; result goes to the queue
    out = result_q.get()
    assert "error" not in out
    assert out["action_results"] == ["ok", "ok"]
    assert state.pieces is pieces_before
    assert state.current_piece is piece_before


def test_simulate_actions_horizon_error():
    """A sequence past the known piece horizon returns an explicit error."""
    state = _make_mcp_state(start_server=False)
    dt = 1 / 60.0
    # preview_count=1 -> horizon = current piece + next = 2 pieces (preview_count + 1).
    # (preview_count + 2) hard_drops lock past the horizon; the 3rd needs an unknown piece.
    snap = simulate_actions(state, ["hard_drop"] * (state.preview_count + 2), 0, dt)
    assert "error" in snap
    assert "horizon exceeded" in snap["error"]


def test_simulate_ignores_quit():
    """A simulate request containing 'quit' never leaves MCP or mutates state."""
    import queue as _queue

    state = _make_mcp_state(start_server=False)
    dt = 1 / 60.0
    game_over_before = state.game_over
    result_q: _queue.Queue = _queue.Queue()
    state._action_queue.put((["quit"], 0, result_q, True))
    snap = state.update(dt, ParticleSystem())
    assert snap is None  # simulate path returns None; result goes to the queue
    out = result_q.get()
    assert "error" not in out
    assert out["action_results"] == ["unknown:quit"]
    assert state.game_over is game_over_before


# ── enumerate_drops tool ─────────────────────────────────────────────


def test_enumerate_core_returns_action_lists():
    """gen_placements -> replayable action lists ending in hard_drop."""
    from tetris.game.board import Board
    from tetris.states.simulator import enumerate_hard_drop_actions

    board = Board()
    piece = Tetromino("T")
    drops = enumerate_hard_drop_actions(board, piece)
    assert len(drops) > 0
    valid = {"rotate_cw", "left", "right", "hard_drop"}
    for actions in drops:
        assert actions[-1] == "hard_drop"
        assert all(a in valid for a in actions)


def test_enumerate_drops_via_state():
    """enumerate_drops returns simulate-format boards, each with actions."""
    from tetris.states.simulator import enumerate_drops

    state = _make_mcp_state(start_server=False)
    dt = 1.0 / 60.0
    piece = state.current_piece
    assert piece is not None
    result = enumerate_drops(state, dt)
    assert result["piece_type"] == piece.type
    assert len(result["boards"]) > 0
    for board in result["boards"]:
        assert isinstance(board["actions"], list)
        assert board["actions"][-1] == "hard_drop"
        for key in ("board", "holes", "overhangs", "current_piece", "lines_cleared"):
            assert key in board


def test_enumerate_roundtrip_fidelity():
    """Each enumerated board's actions replay to that exact board."""
    from tetris.states.simulator import enumerate_drops, simulate_actions

    state = _make_mcp_state(start_server=False)
    dt = 1.0 / 60.0
    result = enumerate_drops(state, dt)
    seen_lines = []
    for board in result["boards"]:
        replay = simulate_actions(state, board["actions"], 0, dt)
        assert replay["board"] == board["board"]
        seen_lines.append(board.get("lines_cleared") or 0)
    # ranking is monotonic on lines_cleared (primary key)
    assert seen_lines == sorted(seen_lines, reverse=True)


def test_enumerate_dedup_and_rank():
    """Identical final boards collapse; line clears rank first."""
    from tetris.states.simulator import _dedup_and_rank

    board_a = [[0] * BOARD_WIDTH for _ in range(BOARD_HEIGHT)]
    board_a[BOARD_HEIGHT - 1][3] = 1
    snap_dup1 = {"board": board_a, "lines_cleared": 0, "overhangs": 2, "holes": 1}
    snap_dup2 = {"board": board_a, "lines_cleared": 0, "overhangs": 2, "holes": 1}
    snap_clear = {
        "board": [[0] * BOARD_WIDTH for _ in range(BOARD_HEIGHT)],
        "lines_cleared": 1,
        "overhangs": 0,
        "holes": 0,
    }
    entries = [
        (["left", "hard_drop"], snap_dup1),
        (["right", "hard_drop"], snap_dup2),
        (["hard_drop"], snap_clear),
    ]
    ranked = _dedup_and_rank(entries)
    assert len(ranked) == 2  # two identical boards deduped to one
    assert ranked[0]["lines_cleared"] == 1  # line clear ranks first
    assert "actions" in ranked[0]


def test_enumerate_tool_via_queue():
    """The enumerate_drops MCP tool routes through update() to ranked boards."""
    import queue as q_mod

    from tetris.states.simulator import ENUMERATE_COMMAND

    state = _make_mcp_state(start_server=False)
    particles = ParticleSystem()
    dt = 1.0 / 60.0
    result_q: q_mod.Queue = q_mod.Queue()
    state._action_queue.put((ENUMERATE_COMMAND, 0, result_q, True))
    state.update(dt, particles)
    snap = result_q.get()
    assert "boards" in snap
    assert "piece_type" in snap
    assert len(snap["boards"]) > 0
    # existing play still works afterwards (no regression)
    result_q2: q_mod.Queue = q_mod.Queue()
    state._action_queue.put((["left"], 0, result_q2, False))
    state.update(dt, particles)
    snap2 = result_q2.get()
    assert snap2["action_results"] == ["ok"]


# ── Regression: lines_cleared in simulate_actions (Issue 1) ──────────


def test_simulate_actions_lines_cleared():
    """simulate_actions reports lines_cleared correctly (was always 0 before fix).

    Mirrors test_mcp_state_lines_cleared_via_queue but exercises the simulate path:
    set up a near-complete row, hard_drop a vertical I-piece, assert lines_cleared == 1.
    """
    state = _make_mcp_state(start_server=False)
    dt = 1.0 / 60.0
    for c in range(BOARD_WIDTH - 1):
        state.board.grid[BOARD_HEIGHT - 1][c] = (1, 1, 1)
    state.current_piece = Tetromino("I")
    state.current_piece.rotation = 1
    state.current_piece.shape = get_shape_rot("I", 1)
    state.current_piece.x = BOARD_WIDTH - 3
    state.current_piece.y = 0
    snap = simulate_actions(state, ["hard_drop"], 0, dt)
    assert snap["lines_cleared"] == 1
    assert snap["lines"] == 1
    assert snap["game_over"] is False
    # original state is unmutated (simulate is side-effect-free)
    assert state.stats.total_lines == 0


# ── Regression: _dedup_and_rank holes before overhangs (Issue 5) ─────


def test_enumerate_rank_holes_before_overhangs():
    """_dedup_and_rank prioritizes fewer holes over fewer overhangs (was reversed).

    Board A: 0 overhangs, 5 holes. Board B: 1 overhang, 0 holes.
    B should rank higher (fewer holes wins) after the fix.
    """
    from tetris.states.simulator import _dedup_and_rank

    board_a = [[0] * BOARD_WIDTH for _ in range(BOARD_HEIGHT)]
    board_a[BOARD_HEIGHT - 1][3] = 1
    board_b = [[0] * BOARD_WIDTH for _ in range(BOARD_HEIGHT)]
    board_b[BOARD_HEIGHT - 1][3] = 1
    board_b[BOARD_HEIGHT - 2][4] = 1
    snap_a = {"board": board_a, "lines_cleared": 0, "overhangs": 0, "holes": 5}
    snap_b = {"board": board_b, "lines_cleared": 0, "overhangs": 1, "holes": 0}
    entries = [
        (["left", "hard_drop"], snap_a),
        (["right", "hard_drop"], snap_b),
    ]
    ranked = _dedup_and_rank(entries)
    # B (0 holes) ranks above A (5 holes) despite A having fewer overhangs
    assert ranked[0]["holes"] == 0
    assert ranked[0]["overhangs"] == 1
    assert ranked[1]["holes"] == 5
    assert ranked[1]["overhangs"] == 0
