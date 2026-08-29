"""Dellacherie bot game state: deterministic heuristic player.

Picks the candidate placement maximizing the El-Tetris evaluation
(:func:`tetris.ai.candidates.get_candidate_states` returns the values).
No learning, no logging, no persistence — a watch/benchmark player.

Independent of ``AIState``: shares only ``BotMovesMixin`` (candidate
enumeration + BFS move replay) via the ``tetris.bots`` library.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import pygame

from tetris.ai.candidates import Placement
from tetris.bots.dellacherie import dellacherie_pick
from tetris.bots.moves import BotMovesMixin
from tetris.game.board import LineClearResult
from tetris.settings import AI_ACTION_DELAY_MS
from tetris.states.game import GameConfig, GameState
from tetris.visuals.particles import ParticleSystem

if TYPE_CHECKING:
    from tetris.audio import AudioManager
    from tetris.game.piece_provider import PieceProvider
    from tetris.states.base import State
    from tetris.states.menu import MenuState


@dataclass(frozen=True)
class BotConfig:
    """Dellacherie bot settings."""

    lookahead: bool
    lookahead_depth: int


class DellacherieState(BotMovesMixin, GameState):
    """Dellacherie heuristic bot playing Tetris.

    Inherits board, pieces, stats, and rendering from ``GameState``.
    Each piece: enumerate candidates, pick ``argmax`` Dellacherie value,
    replay the BFS move sequence. Plays at ``"normal"`` speed (~80ms
    per decision) so a human can watch.
    """

    def __init__(
        self,
        screen: pygame.Surface,
        font: pygame.font.Font,
        audio: AudioManager,
        config: GameConfig,
        piece_provider: PieceProvider | None = None,
        menu: MenuState | None = None,
        bot_config: BotConfig | None = None,
    ) -> None:
        """Initialize the Dellacherie bot state.

        Args:
            screen: Pygame display surface.
            font: Font for HUD text.
            audio: Audio manager.
            config: Gameplay settings (handicap, sound, debug, etc.).
            piece_provider: Spawn controller.
            menu: Parent :class:`MenuState`.
            bot_config: Lookahead settings (``None`` = no lookahead).
        """
        super().__init__(screen, font, audio, config, piece_provider, menu)
        self.player_type = "Bot"
        self._handicap = config.handicap
        bot = bot_config or BotConfig(lookahead=False, lookahead_depth=1)
        self.lookahead: bool = bot.lookahead
        self.lookahead_depth: int = bot.lookahead_depth
        self._candidate_placements: list[Placement] = []
        self._prev_action: int | None = None
        self._action_timer: float = 0.0
        self.episode_steps = 0

    def update(self, dt: float, particles: ParticleSystem) -> State | None:
        """Select and execute one Dellacherie macro-action per piece."""
        if self.paused or self.game_over:
            return super().update(dt, particles)

        # Human-watchable pace: throttle decisions to ~80ms, capped so
        # pre-fall (and the snap-back in _execute_move_sequence) stays
        # small. Replay is exact regardless because the mixin re-anchors
        # the piece to spawn before replaying.
        if self._prev_action is None:
            self._action_timer += dt
            delay = min(AI_ACTION_DELAY_MS, self.current_speed * 4000)
            if self._action_timer < delay:
                return super().update(dt, particles)
            self._action_timer = 0.0

            candidates, actions, _ = self._get_candidate_states()
            if len(candidates) > 0:
                chosen_idx = dellacherie_pick(self._pick_values)
                self._prev_action = actions[chosen_idx]
                self.episode_steps += 1
                self._execute_move_sequence(actions[chosen_idx])

        # Natural gravity drop, lock delay (inherited from GameState.update)
        return super().update(dt, particles)

    def _lock_and_spawn(self, hard_drop: bool = False) -> LineClearResult:
        """Reset the action latch on lock so the bot selects the next piece."""
        result = super()._lock_and_spawn(hard_drop=hard_drop)
        self._prev_action = None
        return result
