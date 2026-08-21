"""Tests for visual modules: particles, renderer, leaderboard_view, menu_animation, graph_view, fonts."""

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

pygame.init()
pygame.mixer.init()


from tetris.audio import AudioManager
from tetris.settings import BLOCK_SIZE, BOARD_OFFSET_X, BOARD_OFFSET_Y, HIDDEN_ROWS
from tetris.states.game import GameConfig
from tetris.states.human import HumanState
from tetris.visuals.fonts import (
    CONTENT_Y,
    INSTRUCTIONS_Y,
    LINE_HEIGHT_SMALL,
    TITLE_Y,
    get_large_font,
    get_small_font,
)
from tetris.visuals.graph_view import render_score_graph
from tetris.visuals.leaderboard_view import draw_leaderboard
from tetris.visuals.menu_animation import MenuBackgroundAnimation
from tetris.visuals.particles import Particle, ParticleSystem
from tetris.visuals.renderer import Renderer


def _screen() -> pygame.Surface:
    return pygame.Surface((640, 480))


def _font() -> pygame.font.Font:
    return pygame.font.Font(None, 20)


def _make_game(**kwargs) -> HumanState:
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
        **kwargs,
    )


# ---------------------------------------------------------------------------
# ParticleSystem & Particle
# ---------------------------------------------------------------------------


class TestParticleSystem:
    def test_emit_creates_particles(self) -> None:
        ps = ParticleSystem()
        assert len(ps.particles) == 0
        ps.emit(10, 20, (255, 0, 0), count=5)
        assert len(ps.particles) == 5
        for p in ps.particles:
            assert p.x == 10
            assert p.y == 20
            assert p.color == (255, 0, 0)

    def test_emit_default_count(self) -> None:
        ps = ParticleSystem()
        ps.emit(0, 0, (0, 255, 0))
        assert len(ps.particles) == 1

    def test_emit_zero_count(self) -> None:
        ps = ParticleSystem()
        ps.emit(0, 0, (0, 255, 0), count=0)
        assert len(ps.particles) == 0

    def test_update_moves_particles(self) -> None:
        ps = ParticleSystem()
        ps.emit(100, 100, (255, 255, 255), count=3)
        old_positions = [(p.x, p.y) for p in ps.particles]
        ps.update()
        new_positions = [(p.x, p.y) for p in ps.particles]
        assert new_positions != old_positions

    def test_update_removes_dead_particles(self) -> None:
        ps = ParticleSystem()
        ps.emit(0, 0, (255, 0, 0), count=10)
        # Kill all particles by zeroing life
        for p in ps.particles:
            p.life = -1
        ps.update()
        assert len(ps.particles) == 0

    def test_draw_renders_without_error(self) -> None:
        screen = _screen()
        ps = ParticleSystem()
        ps.emit(50, 50, (255, 0, 0), count=10)
        ps.draw(screen)  # should not raise

    def test_draw_empty_system(self) -> None:
        screen = _screen()
        ps = ParticleSystem()
        ps.draw(screen)  # should not raise

    def test_particles_die_over_time(self) -> None:
        ps = ParticleSystem()
        ps.emit(0, 0, (255, 0, 0), count=20)
        # Update many times until all are dead
        for _ in range(200):
            ps.update()
        assert len(ps.particles) == 0


class TestParticle:
    def test_particle_init_random_values(self) -> None:
        p = Particle(10, 20, (255, 0, 0))
        assert p.x == 10
        assert p.y == 20
        assert p.color == (255, 0, 0)
        assert -8 <= p.vx <= 8
        assert -12 <= p.vy <= -4
        assert 0.6 <= p.life <= 1.4
        assert 0.01 <= p.decay <= 0.03
        assert 2 <= p.size <= 6

    def test_particle_update_advances_position(self) -> None:
        p = Particle(100, 100, (0, 0, 255))
        old_x, old_y, old_life = p.x, p.y, p.life
        p.update()
        assert p.x != old_x or p.y != old_y  # position changed
        assert p.life < old_life  # life decreased
        assert p.vy > -12  # gravity applied

    def test_particle_update_applies_friction(self) -> None:
        p = Particle(0, 0, (0, 0, 255))
        old_vx = p.vx
        p.update()
        assert abs(p.vx) < abs(old_vx) or old_vx == 0  # friction reduces vx

    def test_particle_draw_alive(self) -> None:
        screen = _screen()
        p = Particle(50, 50, (255, 255, 255))
        p.draw(screen)  # should not raise

    def test_particle_draw_dead_skips(self) -> None:
        screen = _screen()
        p = Particle(50, 50, (255, 255, 255))
        p.life = 0
        p.draw(screen)  # should not raise, does nothing

    def test_particle_draw_negative_life(self) -> None:
        screen = _screen()
        p = Particle(50, 50, (255, 255, 255))
        p.life = -5
        p.draw(screen)  # should not raise


# ---------------------------------------------------------------------------
# Renderer
# ---------------------------------------------------------------------------


class TestRendererHelpers:
    def test_cell_rect_basic(self) -> None:
        rect = Renderer._cell_rect(0, HIDDEN_ROWS, BOARD_OFFSET_X, BOARD_OFFSET_Y)
        assert rect.x == BOARD_OFFSET_X
        assert rect.y == BOARD_OFFSET_Y
        assert rect.width == BLOCK_SIZE
        assert rect.height == BLOCK_SIZE

    def test_cell_rect_hidden_row_offset(self) -> None:
        # A row in the hidden zone should produce a negative screen_y
        rect = Renderer._cell_rect(0, 0, BOARD_OFFSET_X, BOARD_OFFSET_Y)
        assert rect.y < BOARD_OFFSET_Y  # hidden row maps above the board

    def test_panel_rect_basic(self) -> None:
        rect = Renderer._panel_rect(1, 2, 100, 200)
        assert rect.x == 1 * BLOCK_SIZE + 100
        assert rect.y == 2 * BLOCK_SIZE + 200
        assert rect.width == BLOCK_SIZE
        assert rect.height == BLOCK_SIZE


class TestRendererFrame:
    def test_render_frame_smoke(self) -> None:
        game = _make_game()
        particles = ParticleSystem()
        game.renderer.render_frame(game, particles)

    def test_render_frame_no_ghost(self) -> None:
        game = _make_game(ghost_piece=False)
        particles = ParticleSystem()
        game.renderer.render_frame(game, particles)

    def test_render_frame_no_preview(self) -> None:
        game = _make_game(preview_count=0)
        particles = ParticleSystem()
        game.renderer.render_frame(game, particles)

    def test_render_frame_with_hold(self) -> None:
        game = _make_game()
        game.hold_piece = game.current_piece
        particles = ParticleSystem()
        game.renderer.render_frame(game, particles)

    def test_render_frame_with_debug(self) -> None:
        game = _make_game(debug=True)
        particles = ParticleSystem()
        game.renderer.render_frame(game, particles)

    def test_render_frame_paused(self) -> None:
        game = _make_game()
        game.paused = True
        particles = ParticleSystem()
        game.renderer.render_frame(game, particles)

    def test_render_frame_with_combo(self) -> None:
        game = _make_game()
        game.stats.combo = 2
        particles = ParticleSystem()
        game.renderer.render_frame(game, particles)

    def test_draw_grid(self) -> None:
        screen = _screen()
        renderer = Renderer(screen, _font())
        from tetris.game.board import Board

        board = Board()
        renderer.draw_grid(board)

    def test_draw_tetromino(self) -> None:
        screen = _screen()
        renderer = Renderer(screen, _font())
        from tetris.game.tetromino import Tetromino

        tetromino = Tetromino("I")
        renderer.draw_tetromino(tetromino)

    def test_draw_ghost(self) -> None:
        screen = _screen()
        renderer = Renderer(screen, _font())
        from tetris.game.board import Board
        from tetris.game.tetromino import Tetromino

        board = Board()
        tetromino = Tetromino("I")
        renderer.draw_ghost(tetromino, board)

    def test_draw_panel_pieces(self) -> None:
        screen = _screen()
        renderer = Renderer(screen, _font())
        from tetris.game.tetromino import Tetromino

        pieces = [Tetromino("I"), Tetromino("O")]
        renderer.draw_panel_pieces(pieces, 100, 100)

    def test_draw_panel_pieces_dim_bool(self) -> None:
        screen = _screen()
        renderer = Renderer(screen, _font())
        from tetris.game.tetromino import Tetromino

        pieces = [Tetromino("I"), Tetromino("O")]
        renderer.draw_panel_pieces(pieces, 100, 100, dim=True)

    def test_draw_panel_pieces_dim_list(self) -> None:
        screen = _screen()
        renderer = Renderer(screen, _font())
        from tetris.game.tetromino import Tetromino

        pieces = [Tetromino("I"), Tetromino("O")]
        renderer.draw_panel_pieces(pieces, 100, 100, dim=[True, False])

    def test_render_glitch_board(self) -> None:
        game = _make_game()
        screen = _screen()
        renderer = Renderer(screen, _font())
        renderer._render_glitch_board(game, 0, 0, 0.5)

    def test_render_glitch_board_high_glitch(self) -> None:
        game = _make_game()
        screen = _screen()
        renderer = Renderer(screen, _font())
        renderer._render_glitch_board(game, 5, 5, 0.99)

    def test_render_game_over_text(self) -> None:
        screen = _screen()
        renderer = Renderer(screen, _font())
        renderer._render_game_over_text(1000)

    def test_normalized_blocks(self) -> None:
        from tetris.game.tetromino import Tetromino

        t = Tetromino("I")
        blocks = Renderer._normalized_blocks(t)
        assert all(x >= 0 and y >= 0 for x, y in blocks)
        assert min(x for x, _ in blocks) == 0
        assert min(y for _, y in blocks) == 0


# ---------------------------------------------------------------------------
# draw_leaderboard
# ---------------------------------------------------------------------------


class TestDrawLeaderboard:
    def test_empty_scores(self) -> None:
        screen = _screen()
        font = _font()
        draw_leaderboard(screen, font, [])
        # should not raise

    def test_none_scores_loads_from_disk(self) -> None:
        screen = _screen()
        font = _font()
        # scores=None triggers disk load; may be empty file → no crash
        draw_leaderboard(screen, font, None)

    def test_populated_scores(self) -> None:
        screen = _screen()
        font = _font()
        scores = [
            {
                "name": "AAA",
                "score": 9999,
                "level": 10,
                "lines": 100,
                "generator": "7bag",
                "mode": "Normal",
                "speed_mode": "normal",
                "date": "2025-01-01",
            },
            {
                "name": "BBB",
                "score": 5000,
                "level": 5,
                "lines": 50,
                "generator": "random",
                "mode": "Sprint",
                "speed_mode": "crazy",
                "date": "2025-01-02",
            },
            {
                "name": "CCC",
                "score": 1000,
                "level": 2,
                "lines": 10,
                "generator": "35bag",
                "mode": None,
                "speed_mode": None,
                "date": "2025-01-03",
            },
        ]
        draw_leaderboard(screen, font, scores)

    def test_more_than_10_scores_truncated(self) -> None:
        screen = _screen()
        font = _font()
        scores = [
            {
                "name": f"P{i}",
                "score": 1000 - i,
                "level": i,
                "lines": i * 10,
                "generator": "7bag",
                "mode": "Normal",
                "speed_mode": "normal",
                "date": "2025-01-01",
            }
            for i in range(20)
        ]
        draw_leaderboard(screen, font, scores)

    def test_missing_optional_fields(self) -> None:
        screen = _screen()
        font = _font()
        scores = [
            {
                "name": "X",
                "score": 100,
                "level": 1,
                "lines": 5,
                # generator, mode, date omitted
            }
        ]
        draw_leaderboard(screen, font, scores)

    def test_unknown_generator_falls_back(self) -> None:
        screen = _screen()
        font = _font()
        scores = [
            {
                "name": "X",
                "score": 100,
                "level": 1,
                "lines": 5,
                "generator": "unknown_gen",
                "mode": "Normal",
                "speed_mode": "normal",
                "date": "2025-01-01",
            }
        ]
        draw_leaderboard(screen, font, scores)


# ---------------------------------------------------------------------------
# MenuBackgroundAnimation
# ---------------------------------------------------------------------------


class TestMenuBackgroundAnimation:
    def test_init_empty(self) -> None:
        anim = MenuBackgroundAnimation()
        assert anim._pieces == []

    def test_update_no_pieces(self) -> None:
        anim = MenuBackgroundAnimation()
        ps = ParticleSystem()
        anim.update(0.016, ps)
        # May or may not spawn a piece, but should not crash
        assert isinstance(anim._pieces, list)

    def test_update_spawns_pieces_over_time(self) -> None:
        anim = MenuBackgroundAnimation()
        ps = ParticleSystem()
        # Force spawn timer to 0 so next update spawns
        anim._spawn_timer = 0.0
        anim.update(0.016, ps)
        assert len(anim._pieces) >= 1

    def test_draw_without_error(self) -> None:
        screen = _screen()
        anim = MenuBackgroundAnimation()
        anim.draw(screen)

    def test_draw_with_pieces(self) -> None:
        screen = _screen()
        anim = MenuBackgroundAnimation()
        ps = ParticleSystem()
        # Spawn pieces by running updates with expired timer
        for _ in range(10):
            anim._spawn_timer = 0.0
            anim.update(0.016, ps)
        anim.draw(screen)

    def test_update_many_frames(self) -> None:
        anim = MenuBackgroundAnimation()
        ps = ParticleSystem()
        for _ in range(300):
            anim.update(0.016, ps)
        anim.draw(_screen())

    def test_explode_produces_particles(self) -> None:
        anim = MenuBackgroundAnimation()
        ps = ParticleSystem()
        # Force spawn a piece, then force it to explode
        anim._spawn_timer = 0.0
        anim.update(0.016, ps)
        if anim._pieces:
            piece = anim._pieces[0]
            piece.age = 999.0  # exceed explode_delay
            piece.explode_delay = 0.0
            # Force should_explode by patching random check
            import random

            orig = random.random
            random.random = lambda: 0.0  # always < EXPLODE_CHANCE
            anim.update(0.016, ps)
            random.random = orig
            assert len(ps.particles) > 0


class TestFallingPiece:
    def test_init(self) -> None:
        from tetris.visuals.menu_animation import _FallingPiece

        piece = _FallingPiece("I")
        assert piece.shape_key == "I"
        assert piece.rot_index == 0
        assert piece.age == 0.0

    def test_rotate(self) -> None:
        from tetris.visuals.menu_animation import _FallingPiece

        piece = _FallingPiece("I")
        n = len(piece.blocks)
        piece.rotate(1)
        assert piece.rot_index == 1 % n
        piece.rotate(-1)
        assert piece.rot_index == 0

    def test_max_row(self) -> None:
        from tetris.visuals.menu_animation import _FallingPiece

        piece = _FallingPiece("I")
        assert piece.max_row() >= 0

    def test_update_advances(self) -> None:
        from tetris.visuals.menu_animation import _FallingPiece

        piece = _FallingPiece("O")
        old_y = piece.y
        old_age = piece.age
        piece.update(0.1)
        assert piece.y > old_y
        assert piece.age > old_age

    def test_is_offscreen(self) -> None:
        from tetris.visuals.menu_animation import _FallingPiece

        piece = _FallingPiece("I")
        piece.y = 9999.0
        assert piece.is_offscreen()

    def test_fade_alpha_full(self) -> None:
        from tetris.visuals.menu_animation import _FallingPiece

        piece = _FallingPiece("I")
        piece.y = -100.0  # well above fade zone
        assert piece.fade_alpha() == 1.0

    def test_fade_alpha_zero(self) -> None:
        from tetris.visuals.menu_animation import _FallingPiece

        piece = _FallingPiece("I")
        piece.y = 9999.0
        assert piece.fade_alpha() == 0.0

    def test_draw(self) -> None:
        from tetris.visuals.menu_animation import _FallingPiece

        screen = _screen()
        piece = _FallingPiece("I")
        piece.draw(screen)

    def test_draw_faded(self) -> None:
        from tetris.visuals.menu_animation import _FallingPiece

        screen = _screen()
        piece = _FallingPiece("O")
        piece.y = 9999.0  # fully faded
        piece.draw(screen)  # should skip (alpha <= 0)

    def test_should_explode_requires_age(self) -> None:
        from tetris.visuals.menu_animation import _FallingPiece

        piece = _FallingPiece("I")
        piece.age = 0.0
        piece.explode_delay = 100.0
        assert not piece.should_explode()


# ---------------------------------------------------------------------------
# render_score_graph
# ---------------------------------------------------------------------------


class TestRenderScoreGraph:
    def test_empty_data(self) -> None:
        surf = render_score_graph([], [])
        assert isinstance(surf, pygame.Surface)
        assert surf.get_width() > 0
        assert surf.get_height() > 0

    def test_populated_data(self) -> None:
        episodes = list(range(1, 51))
        scores = [100 * i for i in range(1, 51)]
        surf = render_score_graph(episodes, scores)
        assert isinstance(surf, pygame.Surface)
        assert surf.get_width() > 0
        assert surf.get_height() > 0

    def test_single_episode(self) -> None:
        surf = render_score_graph([1], [500])
        assert isinstance(surf, pygame.Surface)

    def test_few_episodes(self) -> None:
        surf = render_score_graph([1, 2, 3], [100, 200, 150])
        assert isinstance(surf, pygame.Surface)

    def test_moving_average_short_window(self) -> None:
        from tetris.visuals.graph_view import _moving_average

        result = _moving_average([10, 20, 30], window=2)
        assert len(result) == 3
        assert result[0] == 10.0
        assert result[1] == 15.0  # (10+20)/2
        assert result[2] == 25.0  # (20+30)/2

    def test_moving_average_empty(self) -> None:
        from tetris.visuals.graph_view import _moving_average

        assert _moving_average([], window=5) == []

    def test_moving_average_large_window(self) -> None:
        from tetris.visuals.graph_view import _moving_average

        result = _moving_average([1, 2, 3], window=10)
        # window larger than data → all values averaged
        assert result == [1.0, 1.5, 2.0]


# ---------------------------------------------------------------------------
# fonts
# ---------------------------------------------------------------------------


class TestFonts:
    def test_get_large_font(self) -> None:
        font = get_large_font()
        assert isinstance(font, pygame.font.Font)

    def test_get_small_font(self) -> None:
        font = get_small_font()
        assert isinstance(font, pygame.font.Font)

    def test_get_large_font_cached(self) -> None:
        font1 = get_large_font()
        font2 = get_large_font()
        assert font1 is font2

    def test_get_small_font_cached(self) -> None:
        font1 = get_small_font()
        font2 = get_small_font()
        assert font1 is font2

    def test_layout_constants(self) -> None:
        assert isinstance(TITLE_Y, int)
        assert isinstance(CONTENT_Y, int)
        assert isinstance(LINE_HEIGHT_SMALL, int)
        assert isinstance(INSTRUCTIONS_Y, int)
        assert TITLE_Y < CONTENT_Y
        assert LINE_HEIGHT_SMALL > 0
