"""AI game state: DQN agent plays Tetris autonomously with learning.

Subclasses ``GameState`` (Open/Closed). The AI uses macro-actions: one
decision per piece (column + rotation), then hard-drop. On game over,
the episode is logged and a new episode starts automatically — the agent
learns continuously.

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
from tetris.settings import BOARD_WIDTH, SHAPES
from tetris.game.piece_provider import PieceProvider
from tetris.states.base import State
from tetris.states.game import GameState
from tetris.visuals.particles import ParticleSystem

# Macro-action space: 10 columns × 4 rotations = 40 actions.
# action_id = rotation * BOARD_WIDTH + column
NUM_ROTATIONS = 4
NUM_ACTIONS = NUM_ROTATIONS * BOARD_WIDTH  # 40

# Gradient updates per piece placement (accelerates training)
LEARN_PER_ACTION = 2

MODEL_PATH = "ai_model.pt"
LOG_PATH = "ai_training_log.json"


class AIState(GameState):
    """Autonomous DQN agent playing Tetris with continuous learning.

    Inherits board, pieces, stats, and rendering from ``GameState``.
    Overrides ``update`` to place pieces via macro-actions, ``_lock_and_spawn``
    to capture state transitions for reward computation, and ``render`` to
    draw the AI HUD overlay.
    """

    def __init__(
        self,
        screen: pygame.Surface,
        font: pygame.font.Font,
        audio: AudioManager,
        handicap: int,
        sound_enabled: bool = True,
        piece_provider: "PieceProvider | None" = None,
    ) -> None:
        super().__init__(screen, font, audio, handicap, sound_enabled, piece_provider)
        self.agent = DQNAgent()
        self.log = TrainingLog(LOG_PATH)
        self.episode = self.log.total_episodes

        # Per-episode tracking
        self.episode_steps = 0
        self.episode_start_grid: np.ndarray = board_to_grid(self.board)

        # Pending transition data (set after AI places a piece)
        self._prev_state: np.ndarray | None = None
        self._prev_action: int | None = None

        # Load existing model if available
        import os

        if os.path.exists(MODEL_PATH):
            try:
                self.agent.load(MODEL_PATH)
            except Exception as e:
                print(f"Failed to load AI model: {e}")

        # Capture initial state for first transition
        self._current_state = extract_state(self.board, self.current_piece, self.next_piece)

    # --- Macro-action helpers -------------------------------------------

    def _get_valid_actions(self) -> list[bool]:
        """Build a validity mask for all 40 macro-actions.

        An action is valid if the piece can be rotated to that rotation
        and shifted to that column without colliding.
        """
        mask = [False] * NUM_ACTIONS
        piece = self.current_piece
        num_rots = len(SHAPES[piece.type])

        for rot in range(NUM_ROTATIONS):
            if rot >= num_rots:
                continue  # this piece doesn't have this rotation
            for col in range(BOARD_WIDTH):
                if self._is_valid_placement(piece, rot, col):
                    mask[rot * BOARD_WIDTH + col] = True
        return mask

    def _is_valid_placement(self, piece, rotation: int, column: int) -> bool:
        """Check if piece can be placed at (column, rotation) at spawn height."""
        from tetris.game.tetromino import Tetromino

        temp = Tetromino()
        temp.type = piece.type
        temp.color = piece.color
        temp.rotation = rotation
        temp.shape = temp.get_current_shape()

        # Use shape's relative offsets to compute piece width
        shape_offsets = temp.shape  # list of (bx, by) relative to piece origin
        min_bx = min(bx for bx, _ in shape_offsets)

        # For column to be the leftmost: piece.x + min_bx = column => piece.x = column - min_bx
        temp.x = column - min_bx
        temp.y = 0

        # Check if piece fits within board bounds at spawn position
        if not self.board.is_valid_move(temp):
            return False

        # Simulate hard drop to verify it can land
        while self.board.is_valid_move(temp, dy=1):
            temp.move(0, 1)

        return True

    def _execute_macro_action(self, action: int) -> None:
        """Rotate and move piece to target (rotation, column), then hard-drop."""
        rotation = action // BOARD_WIDTH
        column = action % BOARD_WIDTH

        piece = self.current_piece

        # Rotate to target rotation
        num_rots = len(SHAPES[piece.type])
        target_rot = rotation % num_rots
        while piece.rotation != target_rot:
            piece.rotate(1)

        # Move to target column
        min_bx = min(bx for bx, _ in piece.shape)
        target_x = column - min_bx
        dx = target_x - piece.x
        if dx > 0:
            for _ in range(dx):
                if self.board.is_valid_move(piece, dx=1):
                    piece.move(1, 0)
                else:
                    break
        elif dx < 0:
            for _ in range(-dx):
                if self.board.is_valid_move(piece, dx=-1):
                    piece.move(-1, 0)
                else:
                    break

        # Hard drop to lock
        self._hard_drop()

    # --- Override _lock_and_spawn to capture RL transitions --------------

    def _lock_and_spawn(self) -> tuple[int, list]:
        """Intercept piece locking to compute reward and store transition."""
        cleared, rows_data = super()._lock_and_spawn()

        new_grid = board_to_grid(self.board)
        reward = compute_reward(
            lines_cleared=cleared,
            prev_grid=self.episode_start_grid,
            new_grid=new_grid,
            game_over=self.game_over,
            step_survived=True,
        )

        # Update current state for the new board
        self._current_state = extract_state(
            self.board, self.current_piece, self.next_piece
        )

        # Store transition: (prev_state, prev_action, reward, new_state, done)
        if self._prev_state is not None and self._prev_action is not None:
            done = self.game_over
            self.agent.store(
                self._prev_state,
                self._prev_action,
                reward,
                self._current_state,
                done,
            )
            # Multiple gradient updates per piece for faster learning
            for _ in range(LEARN_PER_ACTION):
                self.agent.learn()

        # Reset for next piece
        self._prev_state = None
        self._prev_action = None
        self.episode_start_grid = new_grid

        return cleared, rows_data

    # --- Update: AI macro-action per piece ------------------------------

    def update(self, dt: float, particles: ParticleSystem) -> Optional[State]:
        if self.paused or self.game_over:
            return self._on_episode_end()

        # Act immediately — no artificial delay for faster training
        if self._prev_action is None and not self.game_over:
            valid_mask = self._get_valid_actions()
            action = self.agent.select_action(self._current_state, valid_mask)
            self._prev_state = self._current_state.copy()
            self._prev_action = action
            self.episode_steps += 1
            self._execute_macro_action(action)

        # Natural gravity drop (inherited from GameState.update)
        new_state = super().update(dt, particles)

        if new_state is not None:
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
        # Decay epsilon once per episode (not per transition)
        self.agent.decay_epsilon()

        # Save model periodically (not every episode — too slow)
        if self.episode % 50 == 0:
            try:
                self.agent.save(MODEL_PATH)
            except Exception as e:
                print(f"Failed to save AI model: {e}")

        # Start new episode (reset game state)
        self.episode = self.log.total_episodes
        self.episode_steps = 0
        self.game_over = False
        self.paused = False
        self.drop_time = 0
        self.down_pressed = False
        self._prev_state = None
        self._prev_action = None

        # Reset board and pieces
        from tetris.game.board import Board
        from tetris.game.tetromino import Tetromino

        self.board = Board()
        # Fresh board for learning diversity — no handicap carried over
        self.current_piece = Tetromino(self.pieces.next_type())
        self.next_piece = Tetromino(self.pieces.next_type())
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
        from tetris.settings import RED, SCREEN_WIDTH

        hud_lines = [
            "AI MODE",
            f"Episode: {self.episode}",
            f"Epsilon: {self.agent.epsilon:.3f}",
            f"Pieces: {self.episode_steps}",
            f"Total Pieces: {self.log.total_steps + self.episode_steps}",
            f"Avg Score: {self.log.avg_score:.0f}",
            f"Best Score: {self.log.best_score}",
            f"Last 100 Avg: {self.log.last_100_avg:.0f}",
            f"Total Lines: {self.log.total_lines}",
            f"Loss: {self.agent.last_loss:.4f}",
        ]

        y = 180
        for line in hud_lines:
            surf = self.font.render(line, True, RED)
            self.screen.blit(surf, (SCREEN_WIDTH - surf.get_width() - 20, y))
            y += 28

    # --- ESC handling (return to menu) -----------------------------------

    def handle_event(self, event: pygame.event.Event) -> Optional[State]:
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self.pieces.save()
            try:
                self.agent.save(MODEL_PATH)
            except Exception as e:
                print(f"Failed to save AI model: {e}")
            from tetris.states.menu import MenuState

            return MenuState(self.screen, self.font, self.audio)
        # Ignore other key input — AI controls the game
        return None