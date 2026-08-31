"""Tests for curriculum learning in AIState.

Headless: conftest.py sets SDL_VIDEODRIVER=dummy + SDL_AUDIODRIVER=dummy.
"""

import pygame
import pytest

from tests.helpers import make_game_config
from tetris.states.ai import AIConfig
from tetris.game.piece_provider import PieceProvider
from tetris.settings import CURRICULUM_ORDER
from tetris.states.ai import AIState

pygame.init()
_screen = pygame.display.set_mode((100, 100))
_font = pygame.font.Font(None, 16)


@pytest.fixture
def audio():
    from tetris.audio import AudioManager

    return AudioManager(sound_volume=0, music_volume=0)


def _make_ai(audio, curriculum=True, freq=2, epsilon_policy="reset"):
    provider = PieceProvider(mode="normal", path="/tmp/_test_curr_ai.json")
    return AIState(
        _screen,
        _font,
        audio,
        make_game_config(preview_count=3),
        AIConfig(
            epsilon_decay=0.999,
            epsilon_end=0.1,
            lr=1e-3,
            gamma=0.97,
            batch_size=64,
            buffer_size=50_000,
            ai_mode="learning",
            curriculum=curriculum,
            curriculum_freq=freq,
            curriculum_epsilon=epsilon_policy,
            warm_start=True,
            learn_per_action=2,
            lookahead=True,
            lookahead_depth=3,
        ),
        provider,
        speed="fast",
        menu=None,
    )


class TestCurriculumInit:
    def test_curriculum_off_no_restriction(self, audio):
        ai = _make_ai(audio, curriculum=False)
        assert ai._curriculum_types is None
        assert ai.pieces.allowed_types is None

    def test_curriculum_on_restricts_to_IO(self, audio):
        ai = _make_ai(audio, curriculum=True)
        assert ai._curriculum_types == ["O"]
        assert ai.pieces.allowed_types == ["O"]
        for _ in range(50):
            assert ai.pieces.next_type() in ("O",)

    def test_curriculum_playing_mode_no_restriction(self, audio):
        provider = PieceProvider(mode="normal", path="/tmp/_test_curr_play.json")
        ai = AIState(
            _screen,
            _font,
            audio,
            make_game_config(preview_count=3),
            AIConfig(
                epsilon_decay=0.999,
                epsilon_end=0.1,
                lr=1e-3,
                gamma=0.97,
                batch_size=64,
                buffer_size=50_000,
                ai_mode="playing",
                curriculum=True,
                curriculum_freq=50,
                curriculum_epsilon="reset",
                warm_start=True,
                learn_per_action=2,
                lookahead=True,
                lookahead_depth=3,
            ),
            provider,
            speed="fast",
            menu=None,
        )
        assert ai._curriculum_types is None
        assert ai.pieces.allowed_types is None


class TestCurriculumAdvancement:
    def test_advance_adds_piece_at_freq(self, audio):
        ai = _make_ai(audio, curriculum=True, freq=2)
        max_level = len(CURRICULUM_ORDER) - 1
        # Need 2 calls to advance
        assert ai.agent.advance_curriculum(max_level, 2) is False  # count=1
        assert ai.agent.advance_curriculum(max_level, 2) is True  # count=2 → advance
        assert ai.agent.curriculum_level == 1

    def test_no_advance_before_freq(self, audio):
        ai = _make_ai(audio, curriculum=True, freq=10)
        max_level = len(CURRICULUM_ORDER) - 1
        for _ in range(9):
            assert ai.agent.advance_curriculum(max_level, 10) is False
        assert ai.agent.curriculum_level == 0

    def test_advances_through_all_pieces(self, audio):
        ai = _make_ai(audio, curriculum=True, freq=1)
        max_level = len(CURRICULUM_ORDER) - 1
        for _ in range(max_level):
            assert ai.agent.advance_curriculum(max_level, 1) is True
        assert ai.agent.curriculum_level == max_level
        assert ai.agent.advance_curriculum(max_level, 1) is False

    def test_counter_resets_after_advance(self, audio):
        ai = _make_ai(audio, curriculum=True, freq=3)
        max_level = len(CURRICULUM_ORDER) - 1
        ai.agent.advance_curriculum(max_level, 3)  # count=1
        ai.agent.advance_curriculum(max_level, 3)  # count=2
        ai.agent.advance_curriculum(max_level, 3)  # count=3 → advance, reset
        assert ai.agent.curriculum_episode_count == 0
        assert ai.agent.curriculum_level == 1
        # Need 3 more for next advance
        ai.agent.advance_curriculum(max_level, 3)  # count=1
        assert ai.agent.curriculum_level == 1

    def test_curriculum_restored_after_reset(self, audio):
        """_reset_episode restores allowed_types on the new PieceProvider."""
        ai = _make_ai(audio, curriculum=True, freq=10)
        assert ai.pieces.allowed_types == ["O"]
        ai._reset_episode()
        assert ai.pieces.allowed_types == ["O"]

    def test_curriculum_resume_from_saved_model(self, audio):
        """Save model with curriculum_level=3, load, verify level restored."""
        import os
        from tetris.settings import MODEL_PATH

        # Clean any existing model
        if os.path.exists(MODEL_PATH):
            os.unlink(MODEL_PATH)
        try:
            ai = _make_ai(audio, curriculum=True, freq=1)
            # Advance to level 3
            for _ in range(3):
                ai.agent.advance_curriculum(len(CURRICULUM_ORDER) - 1, 1)
            assert ai.agent.curriculum_level == 3
            # Save to MODEL_PATH so the new AIState loads it
            ai.agent.save(MODEL_PATH)
            # Create a fresh AIState and verify level is restored from loaded model
            ai2 = _make_ai(audio, curriculum=True, freq=1)
            assert ai2.agent.curriculum_level == 3
            assert ai2._curriculum_types == CURRICULUM_ORDER[:4]
        finally:
            if os.path.exists(MODEL_PATH):
                os.unlink(MODEL_PATH)


class TestEpsilonPolicy:
    def test_reset_sets_epsilon_to_1(self, audio):
        ai = _make_ai(audio, curriculum=True, epsilon_policy="reset")
        ai.agent.epsilon = 0.3
        ai._apply_epsilon_policy()
        assert ai.agent.epsilon == 1.0

    def test_boost_raises_to_0_5(self, audio):
        ai = _make_ai(audio, curriculum=True, epsilon_policy="boost")
        ai.agent.epsilon = 0.2
        ai._apply_epsilon_policy()
        assert ai.agent.epsilon == 0.5

    def test_boost_does_not_lower(self, audio):
        ai = _make_ai(audio, curriculum=True, epsilon_policy="boost")
        ai.agent.epsilon = 0.8
        ai._apply_epsilon_policy()
        assert ai.agent.epsilon == 0.8

    def test_decay_unchanged(self, audio):
        ai = _make_ai(audio, curriculum=True, epsilon_policy="decay")
        ai.agent.epsilon = 0.42
        ai._apply_epsilon_policy()
        assert ai.agent.epsilon == 0.42


class TestWarmStart:
    def test_warm_start_on_by_default(self, audio):
        ai = _make_ai(audio, curriculum=False)
        assert ai.warm_start is True

    def test_warm_start_off(self, audio):
        ai = _make_ai(audio, curriculum=False)
        ai.warm_start = False
        candidates, _, _ = ai._get_candidate_states()
        assert len(candidates) > 0
        # With warm_start off, select_action gets None → uniform random
        idx = ai.agent.select_action(candidates, None)
        assert 0 <= idx < len(candidates)

    def test_warm_start_on_passes_dellacherie(self, audio):
        ai = _make_ai(audio, curriculum=False)
        assert ai.warm_start is True
        candidates, _, eval_values = ai._get_candidate_states()
        assert len(candidates) > 0
        assert len(eval_values) == len(candidates)

    def test_warm_start_setting_persisted(self, audio):
        """MenuState persists ai_warm_start via settings."""
        from tetris.states.menu import MenuState

        m = MenuState(_screen, _font, None)
        m.ai_warm_start = False
        m.save_settings()
        m2 = MenuState(_screen, _font, None)
        assert m2.ai_warm_start is False
        # Restore default
        m2.ai_warm_start = True
        m2.save_settings()


class TestCurriculum7Bag:
    def test_curriculum_7bag_restricts_initial_pieces(self, audio):
        """7-bag generator with curriculum restriction deals only O initially."""
        provider = PieceProvider(mode="normal", path="/tmp/_test_curr_7bag.json", generator="7bag")
        ai = AIState(
            _screen,
            _font,
            audio,
            make_game_config(preview_count=3),
            AIConfig(
                epsilon_decay=0.999,
                epsilon_end=0.1,
                lr=1e-3,
                gamma=0.97,
                batch_size=64,
                buffer_size=50_000,
                ai_mode="learning",
                curriculum=True,
                curriculum_freq=2,
                curriculum_epsilon="reset",
                warm_start=True,
                learn_per_action=2,
                lookahead=True,
                lookahead_depth=3,
            ),
            provider,
            speed="fast",
            menu=None,
        )
        assert ai.pieces.generator == "7bag"
        assert ai.pieces.allowed_types == ["O"]
        for _ in range(50):
            assert ai.pieces.next_type() == "O"
