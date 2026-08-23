"""Tests for HumanState game-over transitions (normal drop, soft drop, hard drop)."""

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

pygame.init()
pygame.mixer.init()


from tetris.audio import AudioManager
from tetris.game.board import Board, ClearedRow
from tetris.settings import (
    BOARD_HEIGHT,
    BOARD_WIDTH,
    DAS_DELAY_MS,
    DAS_REPEAT_MS,
    LOCK_DELAY_MS,
)
from tetris.states.game import GameConfig
from tetris.states.human import HumanState
from tetris.visuals.particles import ParticleSystem

GRAY = (128, 128, 128)


def _make_game():
    screen = pygame.Surface((640, 480))
    font = pygame.font.Font(None, 24)
    audio = AudioManager(sound_volume=0, music_volume=0)
    return HumanState(
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


def _fill_all_but_col0(board: Board) -> None:
    """Fill every cell in columns 1+ so no line clears (col 0 stays empty).

    Any piece whose blocks fall in columns 1+ can't be placed → game_over.
    """
    for y in range(BOARD_HEIGHT):
        for x in range(1, BOARD_WIDTH):
            board.grid[y][x] = GRAY


def _key_down(key):
    return pygame.event.Event(pygame.KEYDOWN, key=key)


def _key_up(key):
    return pygame.event.Event(pygame.KEYUP, key=key)


def test_game_over_via_hard_drop():
    """Hard drop that blocks the next spawn must transition to GameOverState.

    Regression: _hard_drop set game_over during handle_event, but update()
    early-returned on ``self.game_over`` before reaching the transition code,
    so the game froze instead of showing the game-over screen.
    """
    game = _make_game()
    particles = ParticleSystem()
    _fill_all_but_col0(game.board)

    # Current piece spawns at x=3; its blocks are in columns 3+, which are full.
    # hard_drop can't move it down. lock_tetromino overwrites those cells.
    # No line clears (col 0 still empty). Next piece spawns at x=3 → collides.
    game._hard_drop()

    assert game.game_over, "Hard drop should have triggered game_over"

    result = game.update(16, particles)
    assert result is not None, "update() must return a transition when game_over is True"
    assert type(result).__name__ == "GameOverState"


def test_game_over_via_normal_drop():
    """Normal gravity drop that blocks the next spawn must transition to GameOverState."""
    game = _make_game()
    particles = ParticleSystem()
    _fill_all_but_col0(game.board)

    # Piece is grounded immediately (columns 1+ are full). update() runs lock
    # delay; after LOCK_DELAY_MS the piece locks and next piece collides → game_over.
    game.update(600, particles)  # dt > LOCK_DELAY_MS (500ms)

    assert game.game_over, "Normal drop should have triggered game_over"

    result = game.update(16, particles)
    assert result is not None, "update() must return a transition when game_over is True"
    assert type(result).__name__ == "GameOverState"


# --- handle_event -----------------------------------------------------------


def test_handle_event_pause_toggles():
    game = _make_game()
    assert not game.paused
    game.handle_event(_key_down(pygame.K_p))
    game.handle_event(_key_down(pygame.K_p))
    assert not game.paused


def test_handle_event_mute_calls_audio():
    game = _make_game()
    game.handle_event(_key_down(pygame.K_m))
    assert game.audio.muted


def test_handle_event_esc_returns_menu():
    game = _make_game()
    result = game.handle_event(_key_down(pygame.K_ESCAPE))
    assert result is not None
    assert type(result).__name__ == "MenuState"


def test_handle_event_esc_returns_existing_menu():
    from tetris.states.menu import MenuState

    screen = pygame.Surface((640, 480))
    font = pygame.font.Font(None, 24)
    audio = AudioManager(sound_volume=0, music_volume=0)
    menu = MenuState(screen, font, audio)
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
        menu=menu,
    )
    result = game.handle_event(_key_down(pygame.K_ESCAPE))
    assert result is menu


def test_handle_event_move_left():
    game = _make_game()
    start_x = game.current_piece.x
    game.handle_event(_key_down(pygame.K_LEFT))
    assert game.current_piece.x == start_x - 1


def test_handle_event_move_right():
    game = _make_game()
    start_x = game.current_piece.x
    game.handle_event(_key_down(pygame.K_RIGHT))
    assert game.current_piece.x == start_x + 1


def test_handle_event_rotate_cw():
    game = _make_game()
    start_rot = game.current_piece.rotation
    game.handle_event(_key_down(pygame.K_UP))
    assert game.current_piece.rotation != start_rot


def test_handle_event_rotate_ccw():
    game = _make_game()
    start_rot = game.current_piece.rotation
    game.handle_event(_key_down(pygame.K_s))
    assert game.current_piece.rotation != start_rot


def test_handle_event_soft_drop_sets_down_pressed():
    game = _make_game()
    game.handle_event(_key_down(pygame.K_DOWN))
    assert game.down_pressed is True


def test_handle_event_hard_drop():
    game = _make_game()
    game.handle_event(_key_down(pygame.K_SPACE))
    # Piece should have dropped significantly and locked
    assert game.current_piece.y == 0  # new piece spawned at y=0


def test_handle_event_hold():
    game = _make_game()
    initial_type = game.current_piece.type
    game.handle_event(_key_down(pygame.K_c))
    assert game.hold_piece is not None
    assert game.hold_piece.type == initial_type
    assert game._can_hold is False


def test_handle_event_keyup_soft_drop_clears_down():
    game = _make_game()
    game.handle_event(_key_down(pygame.K_DOWN))
    assert game.down_pressed is True
    game.handle_event(_key_up(pygame.K_DOWN))
    assert game.down_pressed is False


def test_handle_event_keyup_clears_das():
    game = _make_game()
    game.handle_event(_key_down(pygame.K_LEFT))
    assert pygame.K_LEFT in game._das_held
    game.handle_event(_key_up(pygame.K_LEFT))
    assert pygame.K_LEFT not in game._das_held


def test_handle_event_pause_blocks_movement():
    game = _make_game()
    start_x = game.current_piece.x
    game.handle_event(_key_down(pygame.K_p))
    game.handle_event(_key_down(pygame.K_LEFT))
    assert game.current_piece.x == start_x


# --- update -----------------------------------------------------------------


def test_update_gravity_moves_piece():
    game = _make_game()
    particles = ParticleSystem()
    start_y = game.current_piece.y
    # dt in ms; level 0 drop interval ~1.0s = 1000ms
    game.update(1100, particles)
    assert game.current_piece.y > start_y


def test_update_das_auto_shift():
    game = _make_game()
    particles = ParticleSystem()
    start_x = game.current_piece.x
    game.handle_event(_key_down(pygame.K_LEFT))
    # DAS_DELAY_MS=170, DAS_REPEAT_MS=50
    game.update(DAS_DELAY_MS + DAS_REPEAT_MS + 10, particles)
    assert game.current_piece.x < start_x - 1  # moved more than initial press


def test_update_lock_delay_locks_piece():
    game = _make_game()
    particles = ParticleSystem()
    # Move piece to bottom so it's grounded
    game.board.hard_drop(game.current_piece)
    game.update(LOCK_DELAY_MS + 10, particles)
    # After lock, a new piece spawns; the old piece's blocks are on the grid
    assert game.current_piece.y == 0  # new piece


def test_update_level_up_triggers_pending():
    game = _make_game()
    particles = ParticleSystem()
    # Force stats to level 1 (need 10 lines)
    game.stats.total_lines = 10
    game.stats.level = 1
    game._last_level = 0
    game.update(16, particles)
    assert game._pending_level_up is True or game._last_level == 1


def test_update_paused_returns_none():
    game = _make_game()
    particles = ParticleSystem()
    game.paused = True
    result = game.update(16, particles)
    assert result is None


# --- _move_left / _move_right ------------------------------------------------


def test_move_left_valid():
    game = _make_game()
    start_x = game.current_piece.x
    game._move_left()
    assert game.current_piece.x == start_x - 1


def test_move_left_blocked():
    game = _make_game()
    # Move piece to left wall
    while game.board.is_valid_move(game.current_piece, dx=-1):
        game.current_piece.move(-1, 0)
    blocked_x = game.current_piece.x
    game._move_left()
    assert game.current_piece.x == blocked_x


def test_move_right_valid():
    game = _make_game()
    start_x = game.current_piece.x
    game._move_right()
    assert game.current_piece.x == start_x + 1


def test_move_right_blocked():
    game = _make_game()
    while game.board.is_valid_move(game.current_piece, dx=1):
        game.current_piece.move(1, 0)
    blocked_x = game.current_piece.x
    game._move_right()
    assert game.current_piece.x == blocked_x


# --- _rotate_cw / _rotate_ccw ------------------------------------------------


def test_rotate_cw_success():
    game = _make_game()
    start_rot = game.current_piece.rotation
    game._rotate_cw()
    assert game.current_piece.rotation != start_rot


def test_rotate_cw_blocked():
    game = _make_game()
    # Fill cells around the piece so rotation can't succeed
    _fill_all_but_col0(game.board)
    start_rot = game.current_piece.rotation
    game._rotate_cw()
    assert game.current_piece.rotation == start_rot


def test_rotate_ccw_success():
    game = _make_game()
    start_rot = game.current_piece.rotation
    game._rotate_ccw()
    assert game.current_piece.rotation != start_rot


def test_rotate_ccw_blocked():
    game = _make_game()
    _fill_all_but_col0(game.board)
    start_rot = game.current_piece.rotation
    game._rotate_ccw()
    assert game.current_piece.rotation == start_rot


# --- _hard_drop --------------------------------------------------------------


def test_hard_drop_locks_and_spawns():
    game = _make_game()
    initial_type = game.current_piece.type
    game._hard_drop()
    # New piece spawned, hold reset
    assert game._can_hold is True
    assert game.current_piece.type != initial_type or game.current_piece.y == 0


def test_hard_drop_paused_noop():
    game = _make_game()
    game.paused = True
    start_y = game.current_piece.y
    game._hard_drop()
    assert game.current_piece.y == start_y


# --- _hold -------------------------------------------------------------------


def test_hold_first_swap():
    game = _make_game()
    initial_type = game.current_piece.type
    game._hold()
    assert game.hold_piece.type == initial_type
    assert game._can_hold is False


def test_hold_second_blocked():
    game = _make_game()
    game._hold()
    first_held = game.hold_piece.type
    current_after_first = game.current_piece.type
    game._hold()  # should be blocked
    assert game.hold_piece.type == first_held
    assert game.current_piece.type == current_after_first
    assert game._can_hold is False


def test_hold_with_existing_held_swaps():
    game = _make_game()
    first_type = game.current_piece.type
    game._hold()
    # Lock the piece to reset _can_hold
    game._can_hold = True
    second_type = game.current_piece.type
    game._hold()
    assert game.hold_piece.type == second_type
    assert game.current_piece.type == first_type


def test_hold_paused_noop():
    game = _make_game()
    game.paused = True
    game._hold()
    assert game.hold_piece is None


# --- _lock_and_spawn ---------------------------------------------------------


def test_lock_and_spawn_valid():
    game = _make_game()
    game.board.hard_drop(game.current_piece)
    game._lock_and_spawn()
    assert not game.game_over
    assert game.current_piece.y == 0  # new piece spawned


def test_lock_and_spawn_top_out():
    """Piece locked entirely in hidden rows → game_over."""
    game = _make_game()
    # Keep piece at y=0 (hidden rows are 0 and 1; piece at y=0 is hidden)
    game.current_piece.y = 0
    # Fill the board so the piece can't move down, staying in hidden rows
    for y in range(2, BOARD_HEIGHT):
        for x in range(BOARD_WIDTH):
            game.board.grid[y][x] = GRAY
    game._lock_and_spawn()
    assert game.game_over


# --- draw --------------------------------------------------------------------


def test_draw_with_particles():
    game = _make_game()
    screen = pygame.Surface((640, 480))
    particles = ParticleSystem()
    game.draw(screen, particles=particles)


def test_draw_without_particles():
    game = _make_game()
    screen = pygame.Surface((640, 480))
    game.draw(screen)


# --- _on_piece_moved (lock reset) ---------------------------------------------


def test_on_piece_moved_resets_lock_when_grounded():
    game = _make_game()
    game._grounded = True
    game._lock_timer = 100.0
    game._on_piece_moved()
    assert game._lock_timer == 0.0
    assert game._lock_resets == 1


def test_on_piece_moved_no_reset_when_not_grounded():
    game = _make_game()
    game._grounded = False
    game._lock_timer = 100.0
    game._on_piece_moved()
    assert game._lock_timer == 100.0
    assert game._lock_resets == 0


def test_on_piece_moved_stops_after_max_resets():
    game = _make_game()
    game._grounded = True
    from tetris.settings import LOCK_DELAY_RESETS

    game._lock_resets = LOCK_DELAY_RESETS
    game._lock_timer = 100.0
    game._on_piece_moved()
    assert game._lock_timer == 100.0  # not reset


# --- _soft_drop ---------------------------------------------------------------


def test_soft_drop_sets_down_pressed():
    game = _make_game()
    game._soft_drop()
    assert game.down_pressed is True


# --- _emit_line_particles -----------------------------------------------------


def test_emit_line_particles():
    game = _make_game()
    particles = ParticleSystem()
    rows_data = [ClearedRow(BOARD_HEIGHT - 1, [GRAY] * BOARD_WIDTH)]
    game._emit_line_particles(particles, rows_data)
    assert len(particles.particles) > 0


# --- _return_to_menu ---------------------------------------------------------


def test_return_to_menu_with_existing():
    from tetris.states.menu import MenuState

    screen = pygame.Surface((640, 480))
    font = pygame.font.Font(None, 24)
    audio = AudioManager(sound_volume=0, music_volume=0)
    menu = MenuState(screen, font, audio)
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
        menu=menu,
    )
    assert game._return_to_menu() is menu


def test_return_to_menu_creates_new():
    game = _make_game()
    result = game._return_to_menu()
    assert type(result).__name__ == "MenuState"


# --- _do_game_over -----------------------------------------------------------


def test_do_game_over_returns_state():
    game = _make_game()
    result = game._do_game_over()
    assert type(result).__name__ == "GameOverState"
    assert result is not None


def test_holes_overhangs_markers_rendered_for_human():
    """HumanState carries holes_overhangs_help and draws X/O markers."""
    from tetris.visuals.particles import ParticleSystem
    from tetris.visuals.renderer import Renderer

    screen = pygame.Surface((1500, 800))
    font = pygame.font.Font(None, 24)
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
            preview_count=1,
            speed_mode="normal",
            holes_overhangs_help="both",
        ),
    )
    assert game.holes_overhangs_help == "both"
    # craft a single unreachable hole (capped columns 0/1, bottom gap)
    g = game.board.grid
    for y in range(22):
        g[y][0] = (255, 0, 0)
        g[y][1] = (255, 0, 0)
        g[y][2] = (255, 0, 0)
    g[21][0] = None
    g[21][1] = None
    drawn = []
    orig = Renderer._draw_cell_letter

    def _spy(self, letter, rect, color):
        drawn.append(letter)

    Renderer._draw_cell_letter = _spy  # type: ignore[method-assign]  # intentional spy
    try:
        game.renderer.render_frame(game, ParticleSystem())
    finally:
        Renderer._draw_cell_letter = orig  # type: ignore[method-assign]  # restore
    assert drawn.count("X") == 2
