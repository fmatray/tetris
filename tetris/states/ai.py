"""AI game state: DQN agent plays Tetris autonomously with learning.

Subclasses ``GameState`` (Open/Closed). The AI evaluates each valid
placement (rotation + column + hard-drop) via a V-network, picks the
highest-value candidate, and places the piece. On game over, the
episode is logged and a new episode starts automatically — the agent
learns continuously.

Stats (episode, epsilon, steps, avg/best score, loss) are overlaid on
the HUD for real-time learning feedback.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tetris.states.menu import MenuState

import numpy as np
import pygame

from tetris.ai.agent import DQNAgent
from tetris.ai.rewards import (
    board_to_grid,
    compute_reward,
    dellacherie_value,
    extract_features,
    hard_drop_y,
    place_and_clear,
    soft_drop_placements,
)
from tetris.ai.trainer import TrainingLog
from tetris.audio import AudioManager
from tetris.game.board import Board
from tetris.game.piece_provider import PieceProvider
from tetris.game.tetromino import Tetromino
from tetris.logger import get_logger
from tetris.settings import (
    AI_ACTION_DELAY_MS,
    AI_MODEL_SAVE_INTERVAL,
    BOARD_HEIGHT,
    BOARD_WIDTH,
    CURRICULUM_ORDER,
    HUD_POSITIONS,
    LEARN_PER_ACTION,
    LOG_PATH,
    MODEL_PATH,
    RED,
    SCREEN_WIDTH,
    SHAPES,
)
from tetris.states.base import State
from tetris.states.game import GameState
from tetris.visuals.fonts import LINE_HEIGHT_SMALL
from tetris.visuals.particles import ParticleSystem

NUM_ROTATIONS = 4

logger = get_logger("ai")


class AIState(GameState):
    """Autonomous DQN agent playing Tetris with continuous learning.

    Inherits board, pieces, stats, and rendering from ``GameState``.
    Overrides ``update`` to place pieces via per-candidate V-function
    evaluation, ``_lock_and_spawn`` to capture state transitions for
    reward computation (delayed storage), and ``render`` to draw the
    AI HUD overlay.
    """

    def __init__(
        self,
        screen: pygame.Surface,
        font: pygame.font.Font,
        audio: AudioManager,
        handicap: int,
        sound_enabled: bool = True,
        piece_provider: PieceProvider | None = None,
        speed: str = "fast",
        menu: MenuState | None = None,
        epsilon_decay: float = 0.999,
        epsilon_end: float = 0.1,
        lr: float = 1e-3,
        gamma: float = 0.97,
        batch_size: int = 64,
        buffer_size: int = 50_000,
        ai_mode: str = "learning",
        curriculum: bool = False,
        curriculum_freq: int = 50,
        curriculum_epsilon: str = "reset",
        warm_start: bool = True,
        learn_per_action: int = LEARN_PER_ACTION,
        lookahead: bool = True,
        soft_drop: bool = True,
        debug: bool = False,
    ) -> None:
        # Curriculum: restrict piece pool BEFORE super().__init__() spawns pieces
        if curriculum and ai_mode == "learning" and piece_provider is not None:
            piece_provider.set_allowed_types(["O"])
        super().__init__(screen, font, audio, handicap, sound_enabled, piece_provider, menu, debug=debug)
        self.agent = DQNAgent(
            epsilon_decay=epsilon_decay,
            epsilon_end=epsilon_end,
            lr=lr,
            gamma=gamma,
            batch_size=batch_size,
            buffer_size=buffer_size,
        )
        self.log = TrainingLog(LOG_PATH)
        self.episode = self.log.total_episodes
        self.speed = speed
        self.ai_mode = ai_mode
        self.learn_per_action = learn_per_action
        self.lookahead = lookahead
        self.soft_drop = soft_drop
        # Candidate placements for soft-drop: [(rot, px, py), ...]
        self._candidate_placements: list[tuple[int, int, int]] = []
        # Per-episode tracking
        self.episode_steps = 0
        self.episode_start_grid: np.ndarray = board_to_grid(self.board)

        # Pending transition data (delayed storage: state set after placement,
        # stored when NEXT placement provides next_state)
        self._prev_state: np.ndarray | None = None
        self._prev_reward: float | None = None
        self._prev_done: bool = False
        self._prev_action: int | None = None

        # Action delay accumulator (normal mode only — human-like reaction speed)
        self._action_timer: float = 0.0

        # Load existing model if available
        if os.path.exists(MODEL_PATH):
            try:
                self.agent.load(MODEL_PATH)
            except (OSError, RuntimeError, KeyError) as e:
                logger.error("Failed to load AI model: %s", e)

        # In playing mode: always greedy (no exploration, no learning)
        if self.ai_mode == "playing":
            self.agent.epsilon = 0.0

        # Curriculum learning: restrict piece pool in learning mode
        self.curriculum = curriculum
        self.warm_start = warm_start
        self.curriculum_freq = curriculum_freq
        self.curriculum_epsilon = curriculum_epsilon
        if curriculum and self.ai_mode == "learning":
            self._curriculum_types = ["O"]
            self._curriculum_level = 0
            self._curriculum_episode_count = 0
        else:
            self._curriculum_types = None

    # --- Candidate generation -------------------------------------------

    def _is_valid_placement(self, piece, rotation: int, column: int) -> bool:
        """Check if piece can be placed at (column, rotation) at spawn height."""
        shapes = SHAPES[piece.type]
        shape = shapes[rotation % len(shapes)]
        min_bx = min(bx for bx, _ in shape)
        px = column - min_bx
        py = 0
        for bx, by in shape:
            x, y = px + bx, py + by
            if x < 0 or x >= BOARD_WIDTH or y >= BOARD_HEIGHT:
                return False
            if y >= 0 and self.board.grid[y][x] is not None:
                return False
        return True

    def _best_next_placement(self, grid: np.ndarray, piece_type: str) -> np.ndarray:
        """Simulate best placement of next piece on grid (2-piece look-ahead).

        Uses hard-drop for speed — look-ahead only needs approximate board quality.
        """
        best_grid = grid
        best_val = float("inf")  # Dellacherie is negative; lower = better
        num_rots = len(SHAPES[piece_type])
        for rot in range(num_rots):
            shape = SHAPES[piece_type][rot]
            min_bx = min(bx for bx, _ in shape)
            max_bx = max(bx for bx, _ in shape)
            for col in range(BOARD_WIDTH):
                px = col - min_bx
                if px < 0 or px + max_bx >= BOARD_WIDTH:
                    continue
                py = hard_drop_y(grid, shape, px)
                if py < 0:
                    continue
                sim_grid, _ = place_and_clear(grid, shape, px, py)
                val = dellacherie_value(sim_grid)
                if val < best_val:
                    best_val = val
                    best_grid = sim_grid
        return best_grid

    def _get_candidate_states(self) -> tuple[np.ndarray, list[int], np.ndarray]:
        """Enumerate valid placements, simulate drop + line clear, extract features.

        Returns (candidate_states[N,17], action_ids[N], dellacherie_values[N]).
        action_id = placement index (0..N-1). Placements stored in
        self._candidate_placements as [(rot, px, py), ...].
        """
        piece = self.current_piece
        base_grid = board_to_grid(self.board)
        next_piece_type = self.next_piece.type

        candidates = []
        actions = []
        dellacherie_values = []
        self._candidate_placements = []

        if self.soft_drop:
            placements = soft_drop_placements(base_grid, piece.type)
            for shape, px, py, rot in placements:
                sim_grid, lines_cleared = place_and_clear(base_grid, shape, px, py)
                if self.lookahead:
                    sim_grid = self._best_next_placement(sim_grid, next_piece_type)
                features = extract_features(sim_grid, lines_cleared, next_piece_type)
                candidates.append(features)
                actions.append(len(self._candidate_placements))
                self._candidate_placements.append((rot, px, py))
                dellacherie_values.append(dellacherie_value(sim_grid))
        else:
            num_rots = len(SHAPES[piece.type])
            for rot in range(NUM_ROTATIONS):
                if rot >= num_rots:
                    continue
                shape = SHAPES[piece.type][rot]
                min_bx = min(bx for bx, _ in shape)
                max_bx = max(bx for bx, _ in shape)
                for col in range(BOARD_WIDTH):
                    px = col - min_bx
                    if px < 0 or px + max_bx >= BOARD_WIDTH:
                        continue
                    if not self._is_valid_placement(piece, rot, col):
                        continue
                    py = hard_drop_y(base_grid, shape, px)
                    if py < 0:
                        continue
                    sim_grid, lines_cleared = place_and_clear(base_grid, shape, px, py)
                    if self.lookahead:
                        sim_grid = self._best_next_placement(sim_grid, next_piece_type)
                    features = extract_features(sim_grid, lines_cleared, next_piece_type)
                    candidates.append(features)
                    actions.append(len(self._candidate_placements))
                    self._candidate_placements.append((rot, px, py))
                    dellacherie_values.append(dellacherie_value(sim_grid))

        if not candidates:
            return np.empty((0, 17), dtype=np.float32), [], np.empty(0, dtype=np.float32)

        return (
            np.array(candidates, dtype=np.float32),
            actions,
            np.array(dellacherie_values, dtype=np.float32),
        )

    # --- Macro-action execution -----------------------------------------

    def _execute_macro_action(self, action: int) -> None:
        """Rotate, move to target position, then drop and lock."""
        rot, px, py = self._candidate_placements[action]
        piece = self.current_piece

        # Rotate to target rotation
        num_rots = len(SHAPES[piece.type])
        target_rot = rot % num_rots
        while piece.rotation != target_rot:
            piece.rotate(1)

        # Move to target x
        target_x = px
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

        # Soft-drop to target y (or hard-drop if soft_drop off)
        if not self.paused:
            if self.soft_drop:
                drop_cells = 0
                while piece.y < py and self.board.is_valid_move(piece, dy=1):
                    piece.move(0, 1)
                    drop_cells += 1
                self.stats.add_soft_drop(drop_cells)
                self._lock_and_spawn()
            else:
                distance = self.board.hard_drop(piece)
                self.stats.add_hard_drop(distance)
                self._lock_and_spawn()

    # --- Override _lock_and_spawn to capture RL transitions --------------

    def _lock_and_spawn(self) -> tuple[int, list]:
        """Intercept piece locking to compute reward and store transition (delayed)."""
        cleared, rows_data = super()._lock_and_spawn()

        new_grid = board_to_grid(self.board)
        reward = compute_reward(
            lines_cleared=cleared,
            prev_grid=self.episode_start_grid,
            new_grid=new_grid,
            game_over=self.game_over,
            step_survived=True,
            gamma=self.agent.gamma,
        )

        # current_piece is now the NEXT piece (P_{t+1}) after super()._lock_and_spawn
        current_state = extract_features(new_grid, cleared, self.current_piece.type)

        if self.ai_mode == "learning":
            # Store previous transition (delayed: prev_state + current as next_state)
            if self._prev_state is not None:
                self.agent.store(
                    self._prev_state,
                    0,
                    self._prev_reward,
                    current_state,
                    self._prev_done,
                )
            # Terminal: store current transition
            if self.game_over:
                self.agent.store(current_state, 0, reward, current_state, True)
            # Multiple gradient updates per piece for faster learning
            for _ in range(self.learn_per_action):
                self.agent.learn()

        # Update pending state for next transition
        if self.game_over:
            self._prev_state = None
            self._prev_reward = None
            self._prev_done = False
        else:
            self._prev_state = current_state
            self._prev_reward = reward
            self._prev_done = False

        self._prev_action = None
        self.episode_start_grid = new_grid

        return cleared, rows_data

    # --- Update: AI macro-action per piece ------------------------------
    def update(self, dt: float, particles: ParticleSystem) -> State | None:
        if self.paused or self.game_over:
            return self._on_episode_end()

        # Normal mode: throttle decisions to ~80ms for human-like reaction speed.
        # Fast mode: act immediately — no artificial delay for faster training.
        if self.speed == "normal" and self._prev_action is None and not self.game_over:
            self._action_timer += dt
            if self._action_timer < AI_ACTION_DELAY_MS:
                new_state = super().update(dt, particles)
                return self._on_episode_end() if new_state is not None else None
            self._action_timer = 0.0

        if self._prev_action is None and not self.game_over:
            candidates, actions, dellacherie_values = self._get_candidate_states()
            if len(candidates) > 0:
                dellvals = dellacherie_values if self.warm_start else None
                chosen_idx = self.agent.select_action(candidates, dellvals)
                self._prev_action = actions[chosen_idx]
                self.episode_steps += 1
                self._execute_macro_action(actions[chosen_idx])

        # Natural gravity drop (inherited from GameState.update)
        new_state = super().update(dt, particles)

        if new_state is not None:
            return self._on_episode_end()

        return None

    # --- Episode management ---------------------------------------------

    def _on_episode_end(self) -> State | None:
        """Log episode, save model, and restart a new episode."""
        if not self.game_over:
            return None

        # Only log and learn in learning mode
        if self.ai_mode == "learning":
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
            logger.debug("Episode %d ended | score=%d, eps=%.4f", self.episode, self.stats.score, self.agent.epsilon)
            # Decay epsilon once per episode (not per transition)
            self.agent.decay_epsilon()

            # Curriculum: add next piece type if enough episodes elapsed
            if self.curriculum and self._maybe_advance_curriculum():
                self._apply_epsilon_policy()
            if self.episode % AI_MODEL_SAVE_INTERVAL == 0:
                try:
                    self.agent.save(MODEL_PATH)
                except (OSError, RuntimeError) as e:
                    logger.error("Failed to save AI model: %s", e)
            # Flush remaining n-step transitions before new episode
            self.agent.flush_n_step()

        # Start new episode (reset game state)
        self.episode = self.log.total_episodes
        self.episode_steps = 0
        self.game_over = False
        self.paused = False
        self.drop_time = 0
        self._action_timer = 0.0
        self.down_pressed = False
        self._prev_state = None
        self._prev_reward = None
        self._prev_done = False
        self._prev_action = None

        # Reset pieces (re-arm first-piece restriction) and board
        self.pieces.reset()
        self.board = Board()
        # Fresh board for learning diversity — no handicap carried over
        self.current_piece = Tetromino(self.pieces.next_type())
        self.next_piece = Tetromino(self.pieces.next_type())
        self.stats = type(self.stats)()
        self.episode_start_grid = board_to_grid(self.board)

        return None  # Stay in AIState — keep playing

    def _maybe_advance_curriculum(self) -> bool:
        """Add next piece from CURRICULUM_ORDER if enough episodes elapsed."""
        if self._curriculum_level >= len(CURRICULUM_ORDER) - 1:
            return False  # all pieces already available
        self._curriculum_episode_count += 1
        if self._curriculum_episode_count >= self.curriculum_freq:
            self._curriculum_episode_count = 0
            self._curriculum_level += 1
            self._curriculum_types = CURRICULUM_ORDER[: 1 + self._curriculum_level]
            self.pieces.set_allowed_types(self._curriculum_types)
            logger.debug("Curriculum level %d, pieces=%s", self._curriculum_level, self._curriculum_types)
            return True
        return False

    def _apply_epsilon_policy(self) -> None:
        """Adjust epsilon when new piece added, per user setting."""
        if self.curriculum_epsilon == "reset":
            self.agent.epsilon = 1.0
        elif self.curriculum_epsilon == "boost":
            self.agent.epsilon = max(self.agent.epsilon, 0.5)
        # "decay" = do nothing, keep normal decay

    # --- Rendering with AI HUD overlay ----------------------------------

    def draw(self, screen: pygame.Surface, *, particles: ParticleSystem | None = None) -> None:
        if particles is not None:
            self.renderer.render_frame(self, particles)
            self._draw_ai_hud()

    def _draw_ai_hud(self) -> None:
        """Overlay training parameters and a statistics table on the game screen."""
        x0 = HUD_POSITIONS["ai_stats"][0]
        y = HUD_POSITIONS["ai_stats"][1]
        lh = LINE_HEIGHT_SMALL  # line height

        # --- Training section (3 columns) ---
        mode_label = "Apprentissage" if self.ai_mode == "learning" else "Jeu"
        training_items = [
            f"Mode: {mode_label}",
            f"Vitesse: {'Rapide' if self.speed == 'fast' else 'Normal'}",
            f"Episode: {self.episode}",
            f"Epsilon: {self.agent.epsilon:.5f}",
            f"Epsilon decay: {self.agent.epsilon_decay:.4f}",
            f"Epsilon end: {self.agent.epsilon_end:.2f}",
            f"LR: {self.agent.optimizer.param_groups[0]['lr']:.1e}",
            f"Gamma: {self.agent.gamma:.3f}",
            f"Batch: {self.agent.batch_size}",
            f"Loss: {self.agent.last_loss:.4f}",
            f"Curriculum: {'ON' if self.curriculum else 'OFF'}",
            f"Pieces: {''.join(self._curriculum_types) if self._curriculum_types else 'ALL'}",
            f"Warm-start: {'ON' if self.warm_start else 'OFF'}",
            f"Look-ahead: {'ON' if self.lookahead else 'OFF'}",
            f"Soft-drop: {'ON' if self.soft_drop else 'OFF'}",
            f"Maj/pièce: {self.learn_per_action}",
        ]
        col_w = (SCREEN_WIDTH - x0) // 3
        for i, item in enumerate(training_items):
            col = i % 3
            row = i // 3
            surf = self.font.render(item, True, RED)
            self.screen.blit(surf, (x0 + col * col_w, y + row * lh))
        y += (len(training_items) // 3 + (1 if len(training_items) % 3 else 0)) * lh

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
        """Build the 6 statistics rows: Current, Total, Best, Average, Last 100, Trend."""
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
            ["Trend",
             self._trend_arrow(log._trend("steps")),
             self._trend_arrow(log._trend("lines")),
             self._trend_arrow(log._trend("score")),
             self._trend_arrow(log._trend("level"))],
        ]

    @staticmethod
    def _trend_arrow(trend: str) -> str:
        """Convert a trend string to an arrow symbol."""
        return {"up": "↑", "down": "↓", "stable": "→"}.get(trend, "→")
    # --- ESC handling (return to menu) -----------------------------------

    def handle_event(self, event: pygame.event.Event) -> State | None:
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self.pieces.save()
            self.log.flush()
            try:
                self.agent.save(MODEL_PATH)
            except (OSError, RuntimeError) as e:
                logger.error("Failed to save AI model: %s", e)
            return self._return_to_menu()
        # Ignore other key input — AI controls the game
        return None