"""El-Tetris bot game state: deterministic heuristic player.

Picks the candidate placement maximizing the El-Tetris evaluation
(:func:`tetris.ai.candidates.get_candidate_states` returns the values).
No learning, no RL logging, no persistence of its own — a
watch/benchmark player. God-level games additionally record placements
(``BOT_PLACEMENTS_PATH``) for AI imitation warm-start.

Independent of ``AIState``: shares only ``BotMovesMixin`` (candidate
enumeration + BFS move replay) via the ``tetris.bots`` library.

El-Tetris (Yiyuan Lee, 2009) improves on Pierre Dellacherie's classic
heuristic; the bot descends from that feature family.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import TYPE_CHECKING

import pygame

from tetris.ai.candidates import Placement
from tetris.bots.moves import BotMovesMixin, level_select
from tetris.game.board import LineClearResult
from tetris.game.rules import hard_drop_y
from tetris.game.shapes import get_shape_rot
from tetris.settings import (
    AI_ACTION_DELAY_MS,
    BOT_PLACEMENTS_PATH,
    BOARD_HEIGHT,
    BOARD_WIDTH,
    PLAYER_LEVEL_PROFILES,
)
from tetris.states.base import State
from tetris.states.game import GameConfig, GameState
from tetris.visuals.particles import ParticleSystem

if TYPE_CHECKING:
    from tetris.audio import AudioManager
    from tetris.game.piece_provider import PieceProvider
    from tetris.states.menu import MenuState


@dataclass(frozen=True)
class BotConfig:
    """El-Tetris bot settings."""

    lookahead: bool
    lookahead_depth: int
    level: str = "god"


class ElTetrisState(BotMovesMixin, GameState):
    """El-Tetris heuristic bot playing Tetris.

    Inherits board, pieces, stats, and rendering from ``GameState``.
    Each piece: enumerate candidates, pick the argmax El-Tetris value,
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
        """Initialize the El-Tetris bot state.

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
        self._reserve_column = True  # bot-only column reservation (AIState stays off)
        self._reserved_column: int | None = None  # committed I-column, chosen from board state
        self._handicap = config.handicap
        bot = bot_config or BotConfig(lookahead=False, lookahead_depth=1)
        self.level: str = bot.level
        self._level_profile = PLAYER_LEVEL_PROFILES[bot.level]
        self._level_rng = random.Random()
        # Imitation data: record god-level bot placements for AI warm-start.
        if self.level == "god":
            from tetris.game.imitation import PlacementsLog

            self._placement_recorder = PlacementsLog(BOT_PLACEMENTS_PATH)
            self._placement_recorder.start_game(seed=self.seed, handicap=config.handicap)
        # Anticipation cap: lower levels see fewer upcoming pieces.
        cap = self._level_profile["lookahead_cap"]
        self.lookahead: bool = bot.lookahead and cap > 0
        self.lookahead_depth: int = min(bot.lookahead_depth, int(cap))
        self._candidate_placements: list[Placement] = []
        self._prev_action: int | None = None
        self._action_timer: float = 0.0
        self.episode_steps = 0

    def update(self, dt: float, particles: ParticleSystem) -> State | None:
        """Select and execute one El-Tetris macro-action per piece."""
        if self.paused or self.game_over:
            return super().update(dt, particles)
        if self._are_timer > 0:
            # ARE gates bot selection; replayed moves need an active piece
            return super().update(dt, particles)

        # Human-watchable pace: throttle decisions to ~80ms, capped so
        # pre-fall (and the snap-back in _execute_move_sequence) stays
        # small. Replay is exact regardless because the mixin re-anchors
        # the piece to spawn before replaying.
        if self._prev_action is None:
            self._action_timer += dt
            delay = min(
                AI_ACTION_DELAY_MS * self._level_profile["delay_mult"],
                self.current_speed * 4000,
            )
            if self._action_timer < delay:
                return super().update(dt, particles)
            self._action_timer = 0.0

            self._update_reserved_column()
            candidates, actions, _ = self._get_candidate_states()
            if len(candidates) > 0:
                prof = self._level_profile
                chosen_idx = level_select(self._pick_values, prof["misstep"], prof["temp"], self._level_rng)
                self._prev_action = actions[chosen_idx]
                self.episode_steps += 1
                self._execute_move_sequence(actions[chosen_idx])

        # Natural gravity drop, lock delay (inherited from GameState.update)
        return super().update(dt, particles)

    def _update_reserved_column(self) -> None:
        """Re-choose the committed I-column when it is dirty or unset.

        Choice (situation-related, all columns eligible), maximize in order:
          1. cleanliness — a column with any filled cell is not a candidate
             (a tetris needs an empty column);
          2. readiness — lines a vertical I would clear if hard-dropped
             into that column now (exploits an existing well);
          3. higher column index (deterministic; on a flat empty board
             this preserves the proven col-9 behavior).
        No clean column -> reservation off (None) until a clear opens one.
        """
        col = self._reserved_column
        if col is not None and not any(self.board.grid[y][col] is not None for y in range(BOARD_HEIGHT)):
            return  # committed column still clean — keep it (no thrash)
        i_vertical = get_shape_rot("I", 1)  # [(2,0),(2,1),(2,2),(2,3)]
        best: int | None = None
        best_readiness = -1
        for c in range(BOARD_WIDTH):
            if any(self.board.grid[y][c] is not None for y in range(BOARD_HEIGHT)):
                continue  # dirty — not a candidate
            drop_y = hard_drop_y(self.board.grid, i_vertical, c - 2, 0)
            readiness = sum(
                1
                for y in range(drop_y, drop_y + 4)
                if all(self.board.grid[y][x] is not None for x in range(BOARD_WIDTH) if x != c)
            )
            if readiness > best_readiness or (readiness == best_readiness and (best is None or c > best)):
                best = c
                best_readiness = readiness
        self._reserved_column = best

    def _lock_and_spawn(self, hard_drop: bool = False) -> LineClearResult:
        """Reset the action latch on lock so the bot selects the next piece."""
        result = super()._lock_and_spawn(hard_drop)
        self._prev_action = None
        return result

    def _do_game_over(self) -> State:
        """Write the game-end summary, close the recorder, then delegate."""
        if self._placement_recorder is not None:
            stats = self.stats
            self._placement_recorder.end_game(
                score=stats.score,
                tetris=stats.clear_counts.tetris,
                triple=stats.clear_counts.triple,
                lines=stats.total_lines,
                pieces=stats.piece_count,
            )
            self._placement_recorder.close()
            self._placement_recorder = None
        return super()._do_game_over()

    def _on_exit(self) -> None:
        """Close the recorder without a game_end record (game abandoned)."""
        if self._placement_recorder is not None:
            self._placement_recorder.close()
            self._placement_recorder = None
        super()._on_exit()
