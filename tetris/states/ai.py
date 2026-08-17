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
    dellacherie_value_batch,
    extract_features,
    extract_features_batch,
    place_and_clear_batch,
)
from tetris.ai.trainer import TrainingLog
from tetris.audio import AudioManager
from tetris.game import rules
from tetris.game.board import Board
from tetris.game.piece_provider import PieceProvider
from tetris.game.rules import hard_drop_y, hard_drop_y_batch, soft_drop_placements
from tetris.game.stats import GameStats
from tetris.game.tetromino import Tetromino
from tetris.logger import get_logger
from tetris.settings import (
    AI_ACTION_DELAY_MS,
    AI_MODEL_SAVE_INTERVAL,
    BOARD_WIDTH,
    CURRICULUM_ORDER,
    HUD_POSITIONS,
    LEARN_PER_ACTION,
    LOCK_DELAY_MS,
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
        sound_volume: int = 3,
        music_volume: int = 3,
        music_song: str = "korobeiniki",
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
        lookahead_depth: int = 3,
        soft_drop: bool = True,
        preview_count: int = 3,
        debug: bool = False,
    ) -> None:
        """Initialize the AI gameplay/training state.

        Calls ``super().__init__`` to set up the board and pieces, then
        creates the :class:`DQNAgent`, loads any existing model, and
        configures curriculum learning if enabled.

        Args:
            screen: Pygame display surface.
            font: Font for HUD text.
            audio: Audio manager.
            handicap: Pre-filled bottom rows (0–5).
            sound_volume: SFX volume (0–3).
            music_volume: Music volume (0–3).
            music_song: Song key.
            piece_provider: Spawn controller.
            speed: ``"fast"`` (act immediately) or ``"normal"`` (80ms delay).
            menu: Parent :class:`MenuState`.
            epsilon_decay: Per-episode exploration decay.
            epsilon_end: Minimum exploration rate.
            lr: Learning rate.
            gamma: Discount factor.
            batch_size: Training mini-batch size.
            buffer_size: Replay buffer capacity.
            ai_mode: ``"learning"`` (train + log) or ``"playing"`` (greedy).
            curriculum: Restrict piece pool progressively.
            curriculum_freq: Episodes between curriculum level-ups.
            curriculum_epsilon: Epsilon policy on level-up (``"reset"``,
                ``"boost"``, ``"decay"``).
            warm_start: Use Dellacherie values for warm-start selection.
            learn_per_action: Gradient updates per locked piece.
            lookahead: Enable chained look-ahead through preview pieces.
            lookahead_depth: Number of upcoming pieces to simulate (1–3).
            soft_drop: Use soft-drop BFS for candidate generation.
            debug: Enable debug overlays.
        """
        # Curriculum: restrict piece pool BEFORE super().__init__() spawns pieces
        if curriculum and ai_mode == "learning" and piece_provider is not None:
            piece_provider.set_allowed_types(["O"])
        super().__init__(screen, font, audio, handicap, sound_volume, music_volume, music_song, piece_provider, menu, preview_count=preview_count, debug=debug)
        self._handicap = handicap
        self.ghost_piece = False  # AI never shows ghost piece
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
        self.lookahead_depth = lookahead_depth
        self.soft_drop = soft_drop
        # Candidate placements: [(rot, px, py, hold), ...]
        self._candidate_placements: list[tuple[int, int, int, bool]] = []
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
        self.curriculum: bool = curriculum
        self.warm_start: bool = warm_start
        self.curriculum_freq: int = curriculum_freq
        self.curriculum_epsilon: str = curriculum_epsilon
        self._curriculum_types: list[str] | None = None
        if curriculum and self.ai_mode == "learning":
            self._curriculum_types = ["O"]
            self._curriculum_level = 0
            self._curriculum_episode_count = 0

    # --- Candidate generation -------------------------------------------
    def _is_valid_placement(self, piece, rotation: int, column: int) -> bool:
        """Check if piece can be placed at (column, rotation) at spawn height."""
        shape = SHAPES[piece.type][rotation % len(SHAPES[piece.type])]
        min_bx = min(bx for bx, _ in shape)
        px = column - min_bx
        return rules.shape_fits(self.board.grid, shape, px, 0)

    def _best_next_placement(self, grid: np.ndarray, piece_type: str) -> np.ndarray:
        """Simulate best placement of next piece on grid (2-piece look-ahead).

        Uses hard-drop for speed — look-ahead only needs approximate board quality.
        Batches all (rotation, column) candidates and evaluates Dellacherie
        in one vectorized pass.
        """
        shapes: list[list[tuple[int, int]]] = []
        x_positions: list[int] = []
        num_rots = len(SHAPES[piece_type])
        for rot in range(num_rots):
            shape = SHAPES[piece_type][rot]
            min_bx = min(bx for bx, _ in shape)
            max_bx = max(bx for bx, _ in shape)
            for col in range(BOARD_WIDTH):
                px = col - min_bx
                if px < 0 or px + max_bx >= BOARD_WIDTH:
                    continue
                shapes.append(shape)
                x_positions.append(px)
        if not shapes:
            return grid
        py_batch = hard_drop_y_batch(grid, shapes, x_positions)
        valid = py_batch >= 0
        if not valid.any():
            return grid
        v_shapes = [s for s, v in zip(shapes, valid) if v]
        v_xs = [x for x, v in zip(x_positions, valid) if v]
        v_pys = [int(y) for y, v in zip(py_batch, valid) if v]
        sim_grids, _ = place_and_clear_batch(grid, v_shapes, v_xs, v_pys)
        vals = dellacherie_value_batch(sim_grids)
        best_idx = int(np.argmin(vals))
        return sim_grids[best_idx]

    def _gen_placements(self, base_grid: np.ndarray, piece_type: str):
        """Yield (shape, px, py, rot) for all valid placements of a piece type."""
        if self.soft_drop:
            yield from soft_drop_placements(base_grid, piece_type)
        else:
            num_rots = len(SHAPES[piece_type])
            for rot in range(NUM_ROTATIONS):
                if rot >= num_rots:
                    continue
                shape = SHAPES[piece_type][rot]
                min_bx = min(bx for bx, _ in shape)
                max_bx = max(bx for bx, _ in shape)
                for col in range(BOARD_WIDTH):
                    px = col - min_bx
                    if px < 0 or px + max_bx >= BOARD_WIDTH:
                        continue
                    if not rules.shape_fits(base_grid, shape, px, 0):
                        continue
                    py = hard_drop_y(base_grid, shape, px)
                    if py < 0:
                        continue
                    yield (shape, px, py, rot)

    def _get_candidate_states(self) -> tuple[np.ndarray, list[int], np.ndarray]:
        """Enumerate valid placements, simulate drop + line clear, extract features.

        Returns (candidate_states[N,17], action_ids[N], dellacherie_values[N]).
        action_id = placement index (0..N-1). Placements stored in
        self._candidate_placements as [(rot, px, py, hold), ...].
        Includes hold candidates when ``_can_hold`` is True.

        Batched: collects all placements first, then runs place_and_clear_batch,
        lookahead, extract_features_batch, and dellacherie_value_batch in two
        vectorized passes instead of per-candidate scalar calls.
        """
        piece = self.current_piece
        base_grid = board_to_grid(self.board)
        upcoming_types = [self.next_piece.type] + [p.type for p in self.preview_pieces]

        all_shapes: list[list[tuple[int, int]]] = []
        all_pxs: list[int] = []
        all_pys: list[int] = []
        all_rots: list[int] = []
        all_holds: list[bool] = []
        all_next_piece_types: list[str] = []

        # Non-hold candidates: place current piece
        for shape, px, py, rot in self._gen_placements(base_grid, piece.type):
            all_shapes.append(shape)
            all_pxs.append(px)
            all_pys.append(py)
            all_rots.append(rot)
            all_holds.append(False)
            all_next_piece_types.append(upcoming_types[0] if upcoming_types else "I")

        # Hold candidates (if can hold): place the held/next piece instead
        if self._can_hold:
            if self.hold_piece is not None:
                # Swap: current → hold, held → current. Next unchanged.
                hold_upcoming = upcoming_types
            else:
                # No held piece: current → hold, next → current, preview shifts.
                hold_upcoming = [p.type for p in self.preview_pieces]
            hold_piece_type = self.hold_piece.type if self.hold_piece else self.next_piece.type
            for shape, px, py, rot in self._gen_placements(base_grid, hold_piece_type):
                all_shapes.append(shape)
                all_pxs.append(px)
                all_pys.append(py)
                all_rots.append(rot)
                all_holds.append(True)
                all_next_piece_types.append(hold_upcoming[0] if hold_upcoming else "I")

        if not all_shapes:
            self._candidate_placements = []
            return np.empty((0, 17), dtype=np.float32), [], np.empty(0, dtype=np.float32)

        self._candidate_placements = list(zip(all_rots, all_pxs, all_pys, all_holds))

        # Batch place + clear
        sim_grids, lines_cleared = place_and_clear_batch(
            base_grid, all_shapes, all_pxs, all_pys
        )

        # Lookahead (per-candidate — each depends on its own sim_grid)
        if self.lookahead:
            for i in range(len(all_shapes)):
                for pt in upcoming_types[:self.lookahead_depth]:
                    sim_grids[i] = self._best_next_placement(sim_grids[i], pt)

        # Batch feature extraction + Dellacherie
        candidates = extract_features_batch(sim_grids, lines_cleared, all_next_piece_types)
        dellacherie_values = dellacherie_value_batch(sim_grids)

        actions = list(range(len(all_shapes)))
        return candidates, actions, dellacherie_values

    # --- Macro-action execution -----------------------------------------

    def _execute_macro_action(self, action: int) -> None:
        """Rotate, move to target position, then drop (and lock if hard-drop)."""
        rot, px, py, hold = self._candidate_placements[action]

        if hold:
            self._hold()  # GameState._hold swaps current with held/next

        piece = self.current_piece  # piece after hold (if any)

        # Rotate to target rotation with SRS wall kicks
        num_rots = len(SHAPES[piece.type])
        target_rot = rot % num_rots
        while piece.rotation != target_rot:
            if not self.board.try_rotate(piece, 1):
                break

        # Move to target x
        dx = px - piece.x
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
                # Lock delay: don't lock here. super().update() will detect
                # the grounded piece and start the lock timer (LOCK_DELAY_MS).
            else:
                distance = self.board.hard_drop(piece)
                self.stats.add_hard_drop(distance)
                self._lock_and_spawn(hard_drop=True)

    # --- Override _lock_and_spawn to capture RL transitions --------------

    def _lock_and_spawn(self, hard_drop: bool = False) -> tuple[int, list]:
        """Intercept piece locking to compute reward and store transition (delayed)."""
        cleared, rows_data = super()._lock_and_spawn(hard_drop=hard_drop)

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
                assert self._prev_reward is not None  # set alongside _prev_state
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
        """Select and execute one AI macro-action per piece, then run gravity.

        In ``"normal"`` speed, throttles decisions to ~80ms. In ``"fast"``,
        acts immediately. In learning mode, fast-forwards lock delay when the
        piece is grounded (no re-selection possible). Calls ``super().update``
        for gravity/lock-delay.

        Returns a new :class:`State` on episode end, or ``None``.
        """
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

        # Learning mode: fast-forward lock delay — piece is already positioned,
        # _prev_action blocks re-selection, so 500ms wait is pure overhead.
        if self.ai_mode == "learning" and self._grounded and self._prev_action is not None:
            self._lock_timer = LOCK_DELAY_MS

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
        if self.ai_mode == "learning":
            self._log_and_learn()
        self._reset_episode()
        return None

    def _log_and_learn(self) -> None:
        """Record episode stats, decay epsilon, advance curriculum, save model."""
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

    def _reset_episode(self) -> None:
        """Reset game state for a new episode."""
        self.episode = self.log.total_episodes
        self.episode_steps = 0
        self.game_over = False
        self.paused = False
        self.drop_time: float = 0.0
        self._action_timer: float = 0.0
        self.down_pressed = False
        self._lock_timer: float = 0.0
        self._lock_resets: int = 0
        self._grounded: bool = False
        self._das_held: dict[int, float] = {}
        self._prev_state: np.ndarray | None = None
        self._prev_reward: float | None = None
        self._prev_done: bool = False
        self._prev_action: int | None = None
        self._last_level = 0
        self._pending_level_up = False
        self.audio.set_music_speed(1.0)

        # Reset pieces (re-arm first-piece restriction) and board
        self.pieces.reset()
        self.board = Board()
        self.board.apply_handicap(self._handicap)
        self.current_piece = Tetromino(self.pieces.next_type())
        self.next_piece = Tetromino(self.pieces.next_type())
        self.preview_pieces = [Tetromino(self.pieces.next_type()) for _ in range(max(0, self.preview_count - 1))]
        self.hold_piece = None
        self._can_hold = True
        self.stats: GameStats = GameStats()

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
        """Render the game frame plus the AI training HUD overlay."""
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
            f"Look-ahead: {'ON' if self.lookahead else 'OFF'} (depth={self.lookahead_depth})",
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
        """Handle ESC (save + return to menu) and mute. Ignore all other keys."""
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self.audio.stop_music()
                self.pieces.save()
                self.log.flush()
                try:
                    self.agent.save(MODEL_PATH)
                except (OSError, RuntimeError) as e:
                    logger.error("Failed to save AI model: %s", e)
                return self._return_to_menu()
            if event.key == self._mute_key:
                self.audio.toggle_mute()
        # Ignore other key input — AI controls the game
        return None