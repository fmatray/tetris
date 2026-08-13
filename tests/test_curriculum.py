"""Tests for curriculum learning in AIState.

Headless: conftest.py sets SDL_VIDEODRIVER=dummy + SDL_AUDIODRIVER=dummy.
"""

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame
import pytest

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
        handicap=0,
        sound_volume=0,
        music_volume=0,
        piece_provider=provider,
        speed="fast",
        menu=None,
        ai_mode="learning",
        curriculum=curriculum,
        curriculum_freq=freq,
        curriculum_epsilon=epsilon_policy,
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
            handicap=0,
            sound_volume=0,
            music_volume=0,
            piece_provider=provider,
            speed="fast",
            menu=None,
            ai_mode="playing",
            curriculum=True,
        )
        assert ai._curriculum_types is None
        assert ai.pieces.allowed_types is None


class TestCurriculumAdvancement:
    def test_advance_adds_piece_at_freq(self, audio):
        ai = _make_ai(audio, curriculum=True, freq=2)
        # Need 2 episode ends to advance
        assert ai._maybe_advance_curriculum() is False  # count=1
        added = ai._maybe_advance_curriculum()  # count=2 → advance
        assert added is True
        assert ai._curriculum_types == ["O", "I"]
        assert ai.pieces.allowed_types == ["O", "I"]

    def test_no_advance_before_freq(self, audio):
        ai = _make_ai(audio, curriculum=True, freq=10)
        for _ in range(9):
            assert ai._maybe_advance_curriculum() is False
        assert ai._curriculum_types == ["O"]

    def test_advances_through_all_pieces(self, audio):
        ai = _make_ai(audio, curriculum=True, freq=1)
        for _ in range(len(CURRICULUM_ORDER) - 1):
            assert ai._maybe_advance_curriculum() is True
        assert ai._curriculum_types == list(CURRICULUM_ORDER)
        assert ai._maybe_advance_curriculum() is False

    def test_advance_persists_to_piece_provider(self, audio):
        ai = _make_ai(audio, curriculum=True, freq=2)
        ai._maybe_advance_curriculum()  # count=1, no advance
        ai._maybe_advance_curriculum()  # count=2 → advance
        for _ in range(50):
            assert ai.pieces.next_type() in ("O", "I")

    def test_counter_resets_after_advance(self, audio):
        ai = _make_ai(audio, curriculum=True, freq=3)
        ai._maybe_advance_curriculum()  # count=1
        ai._maybe_advance_curriculum()  # count=2
        ai._maybe_advance_curriculum()  # count=3 → advance, reset
        assert ai._curriculum_episode_count == 0
        assert ai._curriculum_types == ["O", "I"]
        # Need 3 more for next advance
        ai._maybe_advance_curriculum()  # count=1
        assert ai._curriculum_types == ["O", "I"]


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
        candidates, _, dellvals = ai._get_candidate_states()
        assert len(candidates) > 0
        assert len(dellvals) == len(candidates)

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
        provider = PieceProvider(
            mode="normal", path="/tmp/_test_curr_7bag.json", generator="7bag"
        )
        ai = AIState(
            _screen,
            _font,
            audio,
            handicap=0,
            sound_volume=0,
            music_volume=0,
            piece_provider=provider,
            speed="fast",
            menu=None,
            ai_mode="learning",
            curriculum=True,
            curriculum_freq=2,
            curriculum_epsilon="reset",
        )
        assert ai.pieces.generator == "7bag"
        assert ai.pieces.allowed_types == ["O"]
        for _ in range(50):
            assert ai.pieces.next_type() == "O"