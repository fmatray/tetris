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

import json
import os
import random
import statistics


from dataclasses import dataclass


@dataclass(frozen=True)
class AIConfig:
    """DQN hyperparameters."""

    epsilon_decay: float
    epsilon_end: float
    lr: float
    gamma: float
    batch_size: int
    buffer_size: int
    ai_mode: str
    curriculum: bool
    curriculum_freq: int
    curriculum_epsilon: str
    warm_start: bool
    learn_per_action: int
    lookahead: bool
    lookahead_depth: int


from typing import TYPE_CHECKING, NamedTuple

if TYPE_CHECKING:
    from tetris.states.menu import MenuState

import numpy as np
import pygame
import torch

from tetris.ai.candidates import NUM_ROTATIONS, Placement, get_candidate_states  # noqa: F401
from tetris.ai.hud import draw_ai_hud
from tetris.ai.agent import DQNAgent
from tetris.ai.rewards import (
    board_to_grid,
    compute_reward,
    compute_reward_components,
    extract_features,
)
from tetris.ai.trainer import TrainingLog
from tetris.audio import AudioManager
from tetris.game.board import Board, LineClearResult
from tetris.game.piece_provider import PieceProvider
from tetris.game.stats import GameStats
from tetris.game.tetromino import Tetromino
from tetris.settings import (
    AI_ACTION_DELAY_MS,
    AI_MODEL_SAVE_INTERVAL,
    BEHAVIOR_LOG_PATH,
    BOARD_WIDTH,
    CURRICULUM_ORDER,
    LOCK_DELAY_MS,
    LOG_PATH,
    MODEL_PATH,
    PLAYING_BEHAVIOR_LOG_PATH,
    PLAYING_LOG_PATH,
    STEP_LOG_PATH,
    TB_LOG_DIR,
)
from tetris.states.base import State
from tetris.states.game import GameConfig, GameState
from tetris.logger import get_logger
from tetris.visuals.particles import ParticleSystem


logger = get_logger("ai")


@dataclass
class PendingTransition:
    """Delayed RL transition: state/reward set after placement, stored when
    the NEXT placement provides the next_state."""

    state: np.ndarray
    reward: float
    done: bool = False


class MoveRecord(NamedTuple):
    """A recorded AI move for HUD display: piece type, rotation, column, hold."""

    piece: str
    rot: int
    col: int
    hold: bool


class AIState(GameState):
    """Autonomous DQN agent playing Tetris with continuous learning.

    Inherits board, pieces, stats, and rendering from ``GameState``.
    Overrides ``update`` to place pieces via per-candidate V-function
    evaluation, ``_lock_and_spawn`` to capture state transitions for
    reward computation (delayed storage), and ``render`` to draw the
    AI HUD overlay.
    """

    _curriculum_types: list[str] | None

    def __init__(
        self,
        screen: pygame.Surface,
        font: pygame.font.Font,
        audio: AudioManager,
        config: GameConfig,
        ai_config: AIConfig,
        piece_provider: PieceProvider | None = None,
        speed: str = "fast",
        menu: MenuState | None = None,
        seed: int | None = None,
        device: str = "auto",
    ) -> None:
        """Initialize the AI gameplay/training state.

        Calls ``super().__init__`` to set up the board and pieces, then
        creates the :class:`DQNAgent`, loads any existing model, and
        configures curriculum learning if enabled.

        Args:
            screen: Pygame display surface.
            font: Font for HUD text.
            audio: Audio manager.
            config: Gameplay settings (handicap, sound, debug, etc.).
            ai_config: DQN hyperparameters.
            piece_provider: Spawn controller.
            speed: ``"fast"`` (act immediately) or ``"normal"`` (80ms delay).
            menu: Parent :class:`MenuState`.
            seed: Random seed for reproducible training (``None`` = non-deterministic).
            device: Torch device (``"auto"``, ``"cpu"``, or ``"cuda"``).
        """
        # Curriculum: restrict piece pool BEFORE super().__init__() spawns pieces
        if ai_config.curriculum and ai_config.ai_mode == "learning" and piece_provider is not None:
            piece_provider.set_allowed_types(["O"])
        super().__init__(
            screen,
            font,
            audio,
            config,
            piece_provider,
            menu,
        )
        self._handicap = config.handicap
        self.seed: int | None = seed
        self._episode_seed: int = seed if seed is not None else random.randint(0, 999_999_999)
        self.agent = DQNAgent(
            epsilon_decay=ai_config.epsilon_decay,
            epsilon_end=ai_config.epsilon_end,
            lr=ai_config.lr,
            gamma=ai_config.gamma,
            batch_size=ai_config.batch_size,
            buffer_size=ai_config.buffer_size,
            device=device,
            seed=seed,
            step_log_path=STEP_LOG_PATH if ai_config.ai_mode == "learning" else None,
            tb_log_dir=TB_LOG_DIR if ai_config.ai_mode == "learning" else None,
        )
        if ai_config.ai_mode == "learning":
            self.log = TrainingLog(LOG_PATH)
            self._behavior_log_path = BEHAVIOR_LOG_PATH
        else:
            self.log = TrainingLog(PLAYING_LOG_PATH)
            self._behavior_log_path = PLAYING_BEHAVIOR_LOG_PATH
        self.episode = self.log.total_episodes
        self.speed = speed
        self.ai_mode = ai_config.ai_mode
        self.learn_per_action = ai_config.learn_per_action
        self.lookahead = ai_config.lookahead
        self.lookahead_depth = ai_config.lookahead_depth
        self._candidate_placements: list[Placement] = []
        # Last 5 moves for HUD display
        self._last_moves: list[MoveRecord] = []
        # Per-episode observability counters
        self._ep_n_random: int = 0
        self._ep_n_greedy: int = 0
        self._ep_n_hold: int = 0
        self._ep_candidates: list[int] = []
        self._ep_move_lens: list[int] = []
        self._ep_losses: list[float] = []
        self._ep_rewards: list[float] = []
        self._ep_reward_components: list[dict[str, float]] = []
        self._ep_col_hist: list[int] = []
        self._ep_rot_hist: list[int] = []
        self._ep_placement_success: list[bool] = []
        # Per-episode tracking
        self.episode_steps = 0
        self.episode_start_grid: np.ndarray = board_to_grid(self.board)

        # Pending transition (delayed storage: state set after placement,
        # stored when NEXT placement provides next_state)
        self._pending: PendingTransition | None = None
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
        self.curriculum: bool = ai_config.curriculum
        self.warm_start: bool = ai_config.warm_start
        self.curriculum_freq: int = ai_config.curriculum_freq
        self.curriculum_epsilon: str = ai_config.curriculum_epsilon
        self._curriculum_types: list[str] | None = None
        if ai_config.curriculum and self.ai_mode == "learning":
            self._curriculum_types = CURRICULUM_ORDER[: 1 + self.agent.curriculum_level]
            self.pieces.set_allowed_types(self._curriculum_types)

    # --- Candidate generation -------------------------------------------
    def _get_candidate_states(self) -> tuple[np.ndarray, list[int], np.ndarray]:
        """Enumerate valid placements, simulate, extract features.

        Delegates to :func:`tetris.ai.candidates.get_candidate_states`.
        Stores placements in ``self._candidate_placements``.
        """
        hold_type = self.hold_piece.type if self.hold_piece is not None else None
        preview_types = [p.type for p in self.preview_pieces]
        candidates, actions, dellvals, placements = get_candidate_states(
            base_grid=board_to_grid(self.board),
            current_piece_type=self.current_piece.type,
            hold_piece_type=hold_type,
            next_piece_type=self.next_piece.type,
            preview_piece_types=preview_types,
            can_hold=self._can_hold,
            lookahead=self.lookahead,
            lookahead_depth=self.lookahead_depth,
        )
        self._candidate_placements = placements
        return candidates, actions, dellvals

    # --- Move-sequence execution ----------------------------------------

    def _execute_move_sequence(self, action: int) -> None:
        """Replay the placement's recorded move sequence (from BFS path).

        Guarantees the piece reaches the exact (px, py, rot) that the
        V-network evaluated — no execution mismatch.
        """
        p = self._candidate_placements[action]

        if p.hold:
            self._hold()

        piece = self.current_piece

        for move in p.moves:
            if move == "left":
                if self.board.is_valid_move(piece, dx=-1):
                    piece.move(-1, 0)
            elif move == "right":
                if self.board.is_valid_move(piece, dx=1):
                    piece.move(1, 0)
            elif move == "soft_drop":
                if self.board.is_valid_move(piece, dy=1):
                    piece.move(0, 1)
            elif move == "rot_cw":
                self.board.try_rotate(piece, 1)
            elif move == "rot_ccw":
                self.board.try_rotate(piece, -1)

        # Lock delay: super().update() detects grounded piece and starts
        # the lock timer (LOCK_DELAY_MS). In learning mode, lock delay is
        # fast-forwarded in update().

    # --- Override _lock_and_spawn to capture RL transitions --------------

    def _lock_and_spawn(self, hard_drop: bool = False) -> LineClearResult:
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
        # Observability: reward tracking
        self._ep_rewards.append(reward)
        self._ep_reward_components.append(
            compute_reward_components(
                lines_cleared=cleared,
                prev_grid=self.episode_start_grid,
                new_grid=new_grid,
                game_over=self.game_over,
                step_survived=True,
                gamma=self.agent.gamma,
            )
        )
        # ponytail: placement success ≈ !game_over this lock. Overhang
        # placements that cause immediate top-out are the failure case.
        self._ep_placement_success.append(not self.game_over)

        # current_piece is now the NEXT piece (P_{t+1}) after super()._lock_and_spawn
        current_state = extract_features(new_grid, cleared, self.current_piece.type)

        if self.ai_mode == "learning":
            # Store previous transition (delayed: _pending.state + current as next_state)
            if self._pending is not None:
                self.agent.store(
                    self._pending.state,
                    0,
                    self._pending.reward,
                    current_state,
                    self._pending.done,
                )
            # Terminal: store current transition
            if self.game_over:
                self.agent.store(current_state, 0, reward, current_state, True)
            # Multiple gradient updates per piece for faster learning
            for _ in range(self.learn_per_action):
                self.agent.learn()
            if self.agent.last_loss is not None:
                self._ep_losses.append(self.agent.last_loss)

        # Update pending transition for next lock
        if self.game_over:
            self._pending = None
        else:
            self._pending = PendingTransition(state=current_state, reward=reward)

        self._prev_action = None
        self.episode_start_grid = new_grid

        return LineClearResult(cleared, rows_data)

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
                p = self._candidate_placements[chosen_idx]
                rot, px, hold = p.rot, p.px, p.hold
                # Observability: behavioral tracking
                self._ep_candidates.append(len(candidates))
                if hold:
                    self._ep_n_hold += 1
                self._ep_move_lens.append(len(p.moves))
                self._ep_col_hist.append(px)
                self._ep_rot_hist.append(rot)
                if self.agent.last_action_was_random:
                    self._ep_n_random += 1
                else:
                    self._ep_n_greedy += 1
                if hold:
                    placed = self.hold_piece.type if self.hold_piece else self.next_piece.type
                else:
                    placed = self.current_piece.type
                self._last_moves.append(MoveRecord(placed, rot, px, hold))
                if len(self._last_moves) > 5:
                    self._last_moves.pop(0)
                self._execute_move_sequence(actions[chosen_idx])

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
        else:
            self._log_playing()
        self._reset_episode()
        return None

    def _ep_avg(self, values: list[float]) -> float:
        return statistics.fmean(values) if values else 0.0

    def _log_and_learn(self) -> None:
        """Record episode stats, decay epsilon, advance curriculum, save model."""
        tm = self.agent.training_metrics()
        # Reward component averages
        if self._ep_reward_components:
            comp_keys = self._ep_reward_components[0].keys()
            reward_comp = {f"reward_{k}": self._ep_avg([c[k] for c in self._ep_reward_components]) for k in comp_keys}
        else:
            reward_comp = {}
        self.log.record(
            episode=self.episode,
            score=self.stats.score,
            lines=self.stats.total_lines,
            level=self.stats.level,
            steps=self.episode_steps,
            epsilon=self.agent.epsilon,
            loss=self.agent.last_loss,
            seed=self._episode_seed,
            # Training dynamics
            avg_loss=self._ep_avg(self._ep_losses),
            max_td_error=self.agent.last_td_error_max,
            avg_td_error=self.agent.last_td_error_mean,
            lr=tm["lr"],
            buffer_fill=tm["buffer_fill"],
            grad_norm=self.agent.last_grad_norm,
            target_syncs=tm["target_syncs"],
            beta=tm["beta"],
            # Network behavior
            avg_v_spread=self.agent.last_v_spread,
            avg_v_margin=self.agent.last_v_margin,
            # Agent behavior
            avg_candidates=self._ep_avg([float(c) for c in self._ep_candidates]),
            n_random=self._ep_n_random,
            n_greedy=self._ep_n_greedy,
            n_hold=self._ep_n_hold,
            avg_move_len=self._ep_avg([float(m) for m in self._ep_move_lens]),
            # Reward
            avg_reward=self._ep_avg(self._ep_rewards),
            curriculum_level=self.agent.curriculum_level,
            **reward_comp,
        )
        self._write_behavior_log()
        logger.debug("Episode %d ended | score=%d, eps=%.4f", self.episode, self.stats.score, self.agent.epsilon)
        # Decay epsilon once per episode (not per transition)
        self.agent.decay_epsilon()

        # Curriculum: advance level via agent (persisted in checkpoint)
        if self.curriculum and self.agent.advance_curriculum(len(CURRICULUM_ORDER) - 1, self.curriculum_freq):
            self._curriculum_types = CURRICULUM_ORDER[: 1 + self.agent.curriculum_level]
            self.pieces.set_allowed_types(self._curriculum_types)
            self._apply_epsilon_policy()
        if self.episode % AI_MODEL_SAVE_INTERVAL == 0:
            try:
                self.agent.save(MODEL_PATH)
            except (OSError, RuntimeError) as e:
                logger.error("Failed to save AI model: %s", e)
        # Flush remaining n-step transitions before new episode
        self.agent.flush_n_step()

    def _log_playing(self) -> None:
        """Record playing-mode episode stats (no learning, no model save)."""
        self.log.record(
            episode=self.episode,
            score=self.stats.score,
            lines=self.stats.total_lines,
            level=self.stats.level,
            steps=self.episode_steps,
            epsilon=0.0,
            loss=0.0,
            seed=self._episode_seed,
            piece_count=self.stats.piece_count,
            clear_single=self.stats.clear_counts.single,
            clear_double=self.stats.clear_counts.double,
            clear_triple=self.stats.clear_counts.triple,
            clear_tetris=self.stats.clear_counts.tetris,
            n_greedy=self._ep_n_greedy,
            n_hold=self._ep_n_hold,
            avg_candidates=self._ep_avg([float(c) for c in self._ep_candidates]),
            avg_move_len=self._ep_avg([float(m) for m in self._ep_move_lens]),
            avg_reward=self._ep_avg(self._ep_rewards),
        )
        self._write_behavior_log()
        logger.debug("Playing episode %d | score=%d", self.episode, self.stats.score)

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
        self._pending: PendingTransition | None = None
        self._prev_action: int | None = None
        self._last_level = 0
        self._last_moves: list[MoveRecord] = []
        self._pending_level_up = False
        # Observability: reset per-episode counters
        self._ep_n_random = 0
        self._ep_n_greedy = 0
        self._ep_n_hold = 0
        self._ep_candidates = []
        self._ep_move_lens = []
        self._ep_losses = []
        self._ep_rewards = []
        self._ep_reward_components = []
        self._ep_col_hist = []
        self._ep_rot_hist = []
        self._ep_placement_success = []
        self.audio.set_music_speed(1.0)

        # Derive per-episode seed for reproducible training
        if self.seed is not None:
            self._episode_seed = self.seed + self.episode
        else:
            self._episode_seed = random.randint(0, 999_999_999)

        # Re-seed global RNG for reproducible exploration
        random.seed(self._episode_seed)
        np.random.seed(self._episode_seed)
        torch.manual_seed(self._episode_seed)

        rng = random.Random(self._episode_seed)

        # Reset pieces (re-seed for reproducible sequence) and board
        gen_name = self.pieces.generator
        self.pieces = PieceProvider(generator=gen_name, seed=self._episode_seed)
        # Restore curriculum restriction on the new provider
        curriculum_types = self._curriculum_types
        if self.curriculum and self.ai_mode == "learning" and curriculum_types is not None:
            self.pieces.set_allowed_types(curriculum_types)
        self.board = Board()
        self.board.apply_handicap(self._handicap, rng)
        self.current_piece = Tetromino(self.pieces.next_type())
        self.next_piece = Tetromino(self.pieces.next_type())
        self.preview_pieces = [Tetromino(self.pieces.next_type()) for _ in range(max(0, self.preview_count - 1))]
        self.hold_piece = None
        self._can_hold = True
        self.stats: GameStats = GameStats()

    def _apply_epsilon_policy(self) -> None:
        """Adjust epsilon when new piece added, per user setting."""
        match self.curriculum_epsilon:
            case "reset":
                self.agent.epsilon = 1.0
            case "boost":
                self.agent.epsilon = max(self.agent.epsilon, 0.5)
            # "decay" = do nothing, keep normal decay

    # --- Rendering with AI HUD overlay ----------------------------------

    def draw(self, screen: pygame.Surface, *, particles: ParticleSystem | None = None) -> None:
        """Render the game frame plus the AI training HUD overlay."""
        super().draw(screen, particles=particles)
        if particles is not None:
            draw_ai_hud(self)

    # --- ESC handling (return to menu) -----------------------------------

    def _write_behavior_log(self) -> None:
        """Append one JSONL line of per-episode behavioral analytics."""
        from pathlib import Path

        col_dist = [self._ep_col_hist.count(c) for c in range(BOARD_WIDTH)]
        rot_dist = [self._ep_rot_hist.count(r) for r in range(4)]
        success_rate = (
            sum(self._ep_placement_success) / len(self._ep_placement_success) if self._ep_placement_success else 0.0
        )
        entry = {
            "episode": self.episode,
            "score": self.stats.score,
            "steps": self.episode_steps,
            "placement_success_rate": success_rate,
            "col_hist": col_dist,
            "rot_hist": rot_dist,
        }
        try:
            path = Path(self._behavior_log_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "a") as f:
                f.write(json.dumps(entry) + "\n")
        except OSError:
            pass  # ponytail: behavior log is best-effort

    def _on_exit(self) -> None:
        """Save model and flush log before returning to menu on ESC.

        Playing mode never writes training artifacts — the model, training
        log, and TB writer stay untouched so the trained checkpoint is not
        polluted (e.g. epsilon=0 overwriting the training epsilon).
        """
        if self.ai_mode == "learning":
            self.log.flush()
            self.agent.flush_logs()
            try:
                self.agent.save(MODEL_PATH)
            except (OSError, RuntimeError) as e:
                logger.error("Failed to save AI model: %s", e)
        elif self.ai_mode == "playing":
            self.log.flush()
