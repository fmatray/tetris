"""AI game state: DQN agent plays Tetris autonomously with learning.

Subclasses ``GameState`` (Open/Closed). The AI uses macro-actions: one
decision per piece (column + rotation), then BFS soft-drop to the deepest
reachable position — allowing placement under overhangs. On game over,
the episode is logged and a new episode starts automatically — the agent
learns continuously.

Stats (episode, epsilon, steps, avg/best score, loss) are overlaid on
the HUD for real-time learning feedback.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from tetris.states.menu import MenuState

import numpy as np
import pygame

from tetris.ai.agent import DQNAgent
from tetris.ai.rewards import (
    compute_reward,
    count_holes,
    extract_state,
    board_to_grid,
)
from tetris.ai.trainer import TrainingLog
from tetris.audio import AudioManager
from tetris.settings import BOARD_HEIGHT, BOARD_WIDTH, SHAPES, HUD_POSITIONS
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
        speed: str = "fast",
        menu: "MenuState | None" = None,
        epsilon_decay: float = 0.999,
        epsilon_end: float = 0.1,
    ) -> None:
        super().__init__(screen, font, audio, handicap, sound_enabled, piece_provider, menu)
        self.agent = DQNAgent(
            epsilon_decay=epsilon_decay,
            epsilon_end=epsilon_end,
        )
        self.log = TrainingLog(LOG_PATH)
        self.episode = self.log.total_episodes
        self.speed = speed

        # Per-episode tracking
        self.episode_steps = 0
        self.episode_start_grid: np.ndarray = board_to_grid(self.board)

        # Pending transition data (set after AI places a piece)
        self._prev_state: np.ndarray | None = None
        self._prev_action: int | None = None

        # Action delay accumulator (normal mode only — human-like reaction speed)
        self._action_timer: float = 0.0

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

        # Valid if piece fits within board bounds at spawn position
        return self.board.is_valid_move(temp)

    def _piece_fits(self, piece, x: int, y: int, rotation: int) -> bool:
        """Check if piece would be valid at (x, y, rotation) on the board."""
        from tetris.game.tetromino import Tetromino

        temp = Tetromino()
        temp.type = piece.type
        temp.color = piece.color
        temp.rotation = rotation
        temp.shape = temp.get_current_shape()
        temp.x = x
        temp.y = y
        return self.board.is_valid_move(temp)
    def _find_deepest_reachable(self, piece, target_rot: int) -> tuple[int, int]:
        """BFS to find the best reachable (x, y) for the piece.

        Explores soft-drop and lateral slides from the current position.
        Among all terminal positions (can't move down further), picks the
        one that results in the fewest holes after placement. Ties are
        broken by depth (deepest first), ensuring overhang access while
        avoiding unnecessary hole creation.
        """
        from collections import deque

        start = (piece.x, piece.y)
        visited: set[tuple[int, int]] = {start}
        queue: deque[tuple[int, int]] = deque([start])
        terminals: list[tuple[int, int]] = []

        while queue:
            x, y = queue.popleft()

            # Terminal: piece can't move down — candidate placement
            if not self._piece_fits(piece, x, y + 1, target_rot):
                terminals.append((x, y))

            # Explore: down, left, right
            for dx, dy in [(0, 1), (-1, 0), (1, 0)]:
                nx, ny = x + dx, y + dy
                if (nx, ny) not in visited and self._piece_fits(piece, nx, ny, target_rot):
                    visited.add((nx, ny))
                    queue.append((nx, ny))

        if not terminals:
            return start

        # Score each terminal by holes created; tie-break by depth (max y)
        best = start
        best_holes = float("inf")
        best_y = -1

        for x, y in terminals:
            holes = self._evaluate_placement_holes(piece, x, y, target_rot)
            if holes < best_holes or (holes == best_holes and y > best_y):
                best = (x, y)
                best_holes = holes
                best_y = y

        return best

    def _evaluate_placement_holes(
        self, piece, x: int, y: int, rotation: int
    ) -> int:
        """Simulate placing piece at (x, y, rotation) and count resulting holes."""
        from tetris.game.tetromino import Tetromino

        temp_piece = Tetromino()
        temp_piece.type = piece.type
        temp_piece.color = piece.color
        temp_piece.rotation = rotation
        temp_piece.shape = temp_piece.get_current_shape()
        temp_piece.x = x
        temp_piece.y = y

        # Build grid with piece locked
        grid = board_to_grid(self.board)
        for bx, by in temp_piece.get_blocks():
            if 0 <= bx < BOARD_WIDTH and 0 <= by < BOARD_HEIGHT:
                grid[by][bx] = 1

        return count_holes(grid)

    def _execute_macro_action(self, action: int) -> None:
        """Rotate, move to target column, then BFS-drop to deepest reachable position."""
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

        # BFS to deepest reachable position (allows sliding under overhangs)
        final_x, final_y = self._find_deepest_reachable(piece, target_rot)
        piece.x = final_x
        piece.y = final_y

        # Lock piece at final position
        if not self.paused:
            self._lock_and_spawn()

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

        # Normal mode: throttle decisions to ~80ms for human-like reaction speed.
        # Fast mode: act immediately — no artificial delay for faster training.
        if self.speed == "normal" and self._prev_action is None and not self.game_over:
            self._action_timer += dt
            if self._action_timer < 80:
                new_state = super().update(dt, particles)
                return self._on_episode_end() if new_state is not None else None
            self._action_timer = 0.0

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
        self._action_timer = 0.0
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
        self.renderer.render_frame(self, particles)
        self._draw_ai_hud()
        pygame.display.flip()

    def _draw_ai_hud(self) -> None:
        """Overlay training parameters and a statistics table on the game screen."""
        from tetris.settings import RED, SCREEN_WIDTH

        x0 = HUD_POSITIONS["ai_stats"][0]
        y = HUD_POSITIONS["ai_stats"][1]
        lh = 28  # line height

        # --- Training section ---
        training_lines = [
            "AI MODE",
            f"Vitesse: {'Rapide' if self.speed == 'fast' else 'Normal'}",
            f"Episode: {self.episode}",
            f"Epsilon: {self.agent.epsilon:.5f}",
            f"Epsilon decay: {self.agent.epsilon_decay:.4f}",
            f"Epsilon end: {self.agent.epsilon_end:.2f}",
            f"Loss: {self.agent.last_loss:.4f}",
        ]
        for line in training_lines:
            surf = self.font.render(line, True, RED)
            self.screen.blit(surf, (x0, y))
            y += lh

        y += 10  # gap between sections

        # --- Statistics table ---
        # Columns: [Tetromino, Lines, Score, Level] — right-aligned
        # Rows: [Current, Total, Best, Average, Last 100]
        label_w = 130
        margin = 20
        col_w = (SCREEN_WIDTH - x0 - label_w - margin) // 4
        col_x = [x0 + label_w + i * col_w for i in range(5)]

        headers = ["", "Tetromino", "Lines", "Score", "Level"]
        for i in range(1, 5):
            surf = self.font.render(headers[i], True, RED)
            self.screen.blit(surf, (col_x[i] - surf.get_width(), y))
        y += lh

        rows = self._hud_table_rows()
        for row in rows:
            label = row[0]
            surf = self.font.render(label, True, RED)
            self.screen.blit(surf, (x0, y))
            for i in range(1, 5):
                surf = self.font.render(str(row[i]), True, RED)
                self.screen.blit(surf, (col_x[i] - surf.get_width(), y))
            y += lh

    def _hud_table_rows(self) -> list[list]:
        """Build the 5 statistics rows: Current, Total, Best, Average, Last 100."""
        log = self.log
        cur_steps = self.episode_steps
        cur_lines = self.stats.total_lines
        cur_score = self.stats.score
        cur_level = self.stats.level

        total_steps = log.total_steps + cur_steps
        total_lines = log.total_lines + cur_lines
        total_score = log.total_score + cur_score

        return [
            ["Current", cur_steps, cur_lines, cur_score, cur_level],
            ["Total", total_steps, total_lines, total_score, "—"],
            ["Best", log.best_steps, log.best_lines, log.best_score, log.best_level],
            ["Average",
             f"{log.avg_steps:.1f}",
             f"{log.avg_lines:.1f}",
             f"{log.avg_score:.1f}",
             f"{log.avg_level:.1f}"],
            ["Last 100",
             f"{log.last_100_avg_steps:.1f}",
             f"{log.last_100_avg_lines:.1f}",
             f"{log.last_100_avg:.1f}",
             f"{log.last_100_avg_level:.1f}"],
        ]

    # --- ESC handling (return to menu) -----------------------------------

    def handle_event(self, event: pygame.event.Event) -> Optional[State]:
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self.pieces.save()
            try:
                self.agent.save(MODEL_PATH)
            except Exception as e:
                print(f"Failed to save AI model: {e}")
            return self._return_to_menu()
        # Ignore other key input — AI controls the game
        return None
