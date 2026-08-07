"""AI game state: DQN agent plays Tetris autonomously with learning.

Subclasses ``GameState`` (Open/Closed). The AI takes actions at
human-like cadence (~12 actions/sec, every 80ms) while natural gravity
continues to pull pieces down. On game over, the episode is logged and
a new episode starts automatically — the agent learns continuously.

Stats (episode, epsilon, steps, avg/best score, loss) are overlaid on
the HUD for real-time learning feedback.
"""

from __future__ import annotations

from typing import Optional

import numpy as np
import pygame

from tetris.ai.agent import DQNAgent
from tetris.ai.rewards import (
    compute_reward,
    extract_state,
    board_to_grid,
)
from tetris.ai.trainer import TrainingLog
from tetris.audio import AudioManager
from tetris.states.base import State
from tetris.states.game import GameState
from tetris.visuals.particles import ParticleSystem

# AI action set (maps action_id → GameState method)
AI_ACTIONS = ["_move_left", "_move_right", "_rotate_cw", "_rotate_ccw", "_soft_drop", "_hard_drop"]

# Cadence: AI acts every ~80ms (~12 actions/sec) — human reaction speed
AI_ACTION_INTERVAL_MS = 80

MODEL_PATH = "ai_model.pt"
LOG_PATH = "ai_training_log.json"


class AIState(GameState):
    """Autonomous DQN agent playing Tetris with continuous learning.

    Inherits board, pieces, stats, and rendering from ``GameState``.
    Overrides ``update`` to inject AI actions, ``_lock_and_spawn`` to
    capture state transitions for reward computation, and ``render`` to
    draw the AI HUD overlay.
    """

    def __init__(
        self,
        screen: pygame.Surface,
        font: pygame.font.Font,
        audio: AudioManager,
        handicap: int,
        sound_enabled: bool = True,
    ) -> None:
        super().__init__(screen, font, audio, handicap, sound_enabled)
        self.agent = DQNAgent()
        self.log = TrainingLog(LOG_PATH)
        self.episode = self.log.total_episodes

        # Per-episode tracking
        self.episode_steps = 0
        self.episode_score = 0
        self.episode_start_grid: np.ndarray = board_to_grid(self.board)

        # RL state: previous (state, action) before each lock
        self.prev_state: np.ndarray | None = None
        self.prev_action: int | None = None

        # AI action timer
        self.ai_timer = 0.0

        # Load existing model if available
        import os

        if os.path.exists(MODEL_PATH):
            try:
                self.agent.load(MODEL_PATH)
            except Exception as e:
                print(f"Failed to load AI model: {e}")

        # Capture initial state for first transition
        self._current_state = extract_state(self.board, self.current_piece, self.next_piece)

    # --- AI action execution --------------------------------------------

    def _execute_ai_action(self, action: int) -> None:
        """Execute one AI action on the game (same mechanics as human input)."""
        if action == 4:  # soft drop
            self.down_pressed = True
        elif action == 5:  # hard drop
            self._hard_drop()
        else:
            method = getattr(self, AI_ACTIONS[action])
            method()

    # --- Override _lock_and_spawn to capture RL transitions --------------

    def _lock_and_spawn(self) -> tuple[int, list]:
        """Intercept piece locking to compute reward and store experience."""
        cleared, rows_data = super()._lock_and_spawn()

        new_grid = board_to_grid(self.board)
        reward = compute_reward(
            lines_cleared=cleared,
            prev_grid=self.episode_start_grid,
            new_grid=new_grid,
            game_over=self.game_over,
            step_survived=True,
        )

        next_state = extract_state(self.board, self.current_piece, self.next_piece)

        # Store the transition from before the action sequence that led here
        if self.prev_state is not None and self.prev_action is not None:
            self.agent.store(
                self.prev_state,
                self.prev_action,
                reward,
                next_state,
                self.game_over,
            )
            self.agent.learn()

        # Reset for next piece
        self.episode_start_grid = new_grid
        self._current_state = next_state

        return cleared, rows_data

    # --- Update: AI action + natural drop -------------------------------

    def update(self, dt: float, particles: ParticleSystem) -> Optional[State]:
        if self.paused or self.game_over:
            return self._on_episode_end()

        # AI takes action at regular interval (human-like cadence)
        self.ai_timer += dt
        if self.ai_timer >= AI_ACTION_INTERVAL_MS:
            self.ai_timer = 0.0
            action = self.agent.select_action(self._current_state)
            self.prev_state = self._current_state.copy()
            self.prev_action = action
            self._execute_ai_action(action)
            self.episode_steps += 1

            # Recompute state after action (piece may have moved)
            if not self.game_over:
                self._current_state = extract_state(
                    self.board, self.current_piece, self.next_piece
                )

        # Natural gravity drop (inherited from GameState.update)
        new_state = super().update(dt, particles)
        if new_state is not None:
            # GameState.update returned GameOverState — but we handle it ourselves
            return self._on_episode_end()

        return None

    # --- Episode management ---------------------------------------------

    def _on_episode_end(self) -> Optional[State]:
        """Log episode, save model, and restart a new episode."""
        if not self.game_over:
            return None

        # Record episode stats
        self.log.record(
            episode=self.episode,
            score=self.stats.score,
            lines=self.stats.total_lines,
            level=self.stats.level,
            steps=self.episode_steps,
            epsilon=self.agent.epsilon,
            loss=self.agent.last_loss,
        )

        # Save model
        try:
            self.agent.save(MODEL_PATH)
        except Exception as e:
            print(f"Failed to save AI model: {e}")

        # Start new episode (reset game state)
        self.episode = self.log.total_episodes
        self.episode_steps = 0
        self.episode_score = 0
        self.game_over = False
        self.paused = False
        self.drop_time = 0
        self.down_pressed = False
        self.ai_timer = 0.0
        self.prev_state = None
        self.prev_action = None

        # Reset board and pieces
        from tetris.game.board import Board
        from tetris.game.tetromino import Tetromino

        self.board = Board()

        # Fresh board for learning diversity — no handicap carried over
        self.current_piece = Tetromino()
        self.next_piece = Tetromino()
        self.stats = type(self.stats)()
        self.episode_start_grid = board_to_grid(self.board)
        self._current_state = extract_state(
            self.board, self.current_piece, self.next_piece
        )

        return None  # Stay in AIState — keep playing

    # --- Rendering with AI HUD overlay ----------------------------------

    def render(self, particles: ParticleSystem) -> None:
        super().render(particles)
        self._draw_ai_hud()
        pygame.display.flip()

    def _draw_ai_hud(self) -> None:
        """Overlay learning statistics on the game screen."""
        from tetris.settings import RED, SCREEN_WIDTH, WHITE

        hud_lines = [
            "AI MODE",
            f"Episode: {self.episode}",
            f"Epsilon: {self.agent.epsilon:.3f}",
            f"Steps: {self.episode_steps}",
            f"Total Steps: {self.log.total_steps + self.episode_steps}",
            f"Avg Score: {self.log.avg_score:.0f}",
            f"Best Score: {self.log.best_score}",
            f"Last 100 Avg: {self.log.last_100_avg:.0f}",
            f"Total Lines: {self.log.total_lines}",
            f"Loss: {self.agent.last_loss:.4f}",
            "ESC: Menu",
        ]

        y = 160
        for i, line in enumerate(hud_lines):
            color = WHITE if i == 0 else RED
            surf = self.font.render(line, True, color)
            self.screen.blit(surf, (SCREEN_WIDTH - surf.get_width() - 20, y))
            y += 28

    # --- ESC handling (return to menu without saving) -------------------

    def handle_event(self, event: pygame.event.Event) -> Optional[State]:
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            from tetris.states.menu import MenuState

            return MenuState(self.screen, self.font, self.audio)
        # Ignore other key input — AI controls the game
        return None
