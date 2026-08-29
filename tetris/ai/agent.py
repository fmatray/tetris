"""DQN Agent: per-candidate V-function evaluation and learning.

The agent encapsulates two networks (online + target), a prioritized
experience replay buffer with n-step returns, and the training update
step. It is framework-agnostic regarding the game — it only sees state
vectors, rewards, and done flags.
"""

from __future__ import annotations

import json
import random
from collections import deque
from pathlib import Path
from typing import NamedTuple

import numpy as np
import torch
from torch import nn, optim

from tetris.ai.network import DQNetwork
from tetris.ai.replay_buffer import N_STEP, PrioritizedReplayBuffer
from tetris.ai.rewards import FEATURE_SIZE
from tetris.settings import STEP_LOG_MAX_LINES


# Temperature for El-Tetris-weighted softmax during exploration (warm-start).
# Calibrated to typical El-Tetris value range (-200 to -10).
WARM_START_TEMP: float = 30.0


class NStepTransition(NamedTuple):
    """A single transition in the n-step return accumulator buffer."""

    state: np.ndarray
    action: int
    reward: float
    next_state: np.ndarray
    done: bool


def _softmax(x: np.ndarray) -> np.ndarray:
    """Numerically stable softmax."""
    e = np.exp(x - x.max())
    return e / e.sum()


class DQNAgent:
    """V-network DQN agent with PER, n-step returns, and target network.

    Hyperparameters: lr=1e-3, gamma=0.97, epsilon 1.0→0.10 (decay 0.999/episode),
    batch=64, hard target sync every 500 steps, SmoothL1Loss + grad clipping at 1.0.
    ReduceLROnPlateau scheduler (factor=0.5, patience=50, min_lr=1e-6).
    State: 17-dim DT-20 features. Action: per-candidate evaluation.
    """

    def __init__(
        self,
        state_size: int = FEATURE_SIZE,
        lr: float = 1e-3,
        gamma: float = 0.97,
        epsilon_start: float = 1.0,
        epsilon_end: float = 0.10,
        epsilon_decay: float = 0.999,
        batch_size: int = 64,
        buffer_size: int = 50_000,
        device: str = "auto",
        seed: int | None = None,
        step_log_path: str | None = None,
        tb_log_dir: str | None = None,
    ) -> None:
        """Initialize the DQN agent: network, target network, optimizer, buffer.

        Args:
            state_size: Input feature dimension.
            lr: Learning rate for the Adam optimizer.
            gamma: Discount factor.
            epsilon_start: Initial exploration rate.
            epsilon_end: Minimum exploration rate.
            epsilon_decay: Per-episode multiplicative decay.
            batch_size: Mini-batch size for learning.
            buffer_size: Replay buffer capacity.
            device: Torch device (``"auto"``, ``"cpu"``, or ``"cuda"``).
            seed: Random seed for reproducibility (``None`` = non-deterministic).
            step_log_path: Path for per-step JSONL log (``None`` disables).
            tb_log_dir: Directory for TensorBoard logs (``None`` disables).
        """
        self.state_size = state_size
        self.gamma = gamma
        self.epsilon = epsilon_start
        self.epsilon_end = epsilon_end
        self.epsilon_decay = epsilon_decay
        self.batch_size = batch_size
        self.target_sync_freq: int = 500
        self.seed = seed
        if seed is not None:
            torch.manual_seed(seed)
            np.random.seed(seed)
            random.seed(seed)
        if device == "auto":
            device = "cuda" if torch.cuda.is_available() else "cpu"
        self.device = torch.device(device)

        self.online_net = DQNetwork(state_size).to(self.device)
        self.target_net = DQNetwork(state_size).to(self.device)
        self.target_net.load_state_dict(self.online_net.state_dict())
        self.target_net.eval()

        self.optimizer = optim.Adam(self.online_net.parameters(), lr=lr)
        self.loss_fn = nn.SmoothL1Loss(reduction="none")
        self.buffer = PrioritizedReplayBuffer(buffer_size)

        # N-step transition buffer: accumulates N transitions before pushing
        self._n_step_buffer: deque[NStepTransition] = deque(maxlen=N_STEP)

        self.steps = 0
        # LR scheduler: reduces LR when loss plateaus
        self.scheduler = optim.lr_scheduler.ReduceLROnPlateau(
            self.optimizer,
            mode="min",
            factor=0.5,
            patience=50,
            min_lr=1e-6,
        )
        # Curriculum state (persisted in checkpoint)
        self.curriculum_level: int = 0
        self.curriculum_episode_count: int = 0
        self.last_loss: float = 0.0
        # --- Observability ---
        self.last_td_error_mean: float = 0.0
        self.last_td_error_max: float = 0.0
        self.last_grad_norm: float = 0.0
        self.target_syncs: int = 0
        self.last_v_spread: float = 0.0
        self.last_v_margin: float = 0.0
        self.last_action_was_random: bool = False
        self.step_log_path = step_log_path
        # TensorBoard writer (None if tensorboard not installed or tb_log_dir is None)
        self._tb_writer = None
        if tb_log_dir is not None:
            try:
                from torch.utils.tensorboard import SummaryWriter

                self._tb_writer = SummaryWriter(tb_log_dir)
            except ImportError:
                pass  # tensorboard not installed — skip

    # --- Action selection -----------------------------------------------

    def select_action(self, candidate_states: np.ndarray, dellacherie_values: np.ndarray | None = None) -> int:
        """ε-greedy: random candidate with prob ε, greedy (max V) otherwise.

        During exploration, uses El-Tetris-weighted softmax (warm-start)
        instead of uniform random when ``dellacherie_values`` is provided.

        Args:
            candidate_states: (N, 17) array of feature vectors for valid placements.
            dellacherie_values: (N,) array of El-Tetris evaluation values for warm-start.
        Returns:
            Index of the chosen candidate (0..N-1).
        """
        n = len(candidate_states)
        if random.random() < self.epsilon:
            self.last_action_was_random = True
            self.last_v_spread = 0.0
            self.last_v_margin = 0.0
            if dellacherie_values is not None and len(dellacherie_values) == n:
                # Warm-start: softmax over El-Tetris values (directed exploration)
                probs = _softmax(dellacherie_values / WARM_START_TEMP)
                return int(np.random.choice(n, p=probs))
            return random.randint(0, n - 1)
        self.last_action_was_random = False
        self.online_net.eval()
        with torch.no_grad():
            states = torch.from_numpy(candidate_states).float().to(self.device)
            values = self.online_net(states).squeeze(-1)
            idx = values.argmax(dim=0).item()
            vals_np = values.cpu().numpy()
            if len(vals_np) >= 2:
                sorted_vals = np.sort(vals_np)
                self.last_v_spread = float(sorted_vals[-1] - sorted_vals[0])
                self.last_v_margin = float(sorted_vals[-1] - sorted_vals[-2])
            else:
                self.last_v_spread = 0.0
                self.last_v_margin = 0.0
            if self._tb_writer is not None and self.steps > 0:
                self._tb_writer.add_scalar("agent/v_spread", self.last_v_spread, self.steps)
                self._tb_writer.add_scalar("agent/v_margin", self.last_v_margin, self.steps)
            return idx

    # --- Learning --------------------------------------------------------

    def store(
        self,
        state: np.ndarray,
        action: int,
        reward: float,
        next_state: np.ndarray,
        done: bool,
    ) -> None:
        """Push transition to n-step buffer; flush completed n-step returns to PER."""
        self._n_step_buffer.append(NStepTransition(state, action, reward, next_state, done))
        if done:
            # Flush all partial n-step transitions immediately
            self.flush_n_step()
        elif len(self._n_step_buffer) == N_STEP:
            self._push_n_step()

    def _push_n_step(self) -> None:
        """Compute n-step return from buffer and push to PER."""
        first = self._n_step_buffer[0]
        s0, a0 = first.state, first.action
        actual_n = len(self._n_step_buffer)
        r = 0.0
        for i, t in enumerate(self._n_step_buffer):
            r += (self.gamma**i) * t.reward
            if t.done:
                break
        sn = self._n_step_buffer[-1].next_state
        done_n = any(t.done for t in self._n_step_buffer)
        self.buffer.push(s0, a0, r, sn, done_n, actual_n)
        # Slide window: remove oldest (keep remaining for overlap)
        self._n_step_buffer.popleft()

    def flush_n_step(self) -> None:
        """Flush all remaining partial n-step transitions at episode end."""
        while self._n_step_buffer:
            self._push_n_step()

    def decay_epsilon(self) -> None:
        """Decay epsilon once per episode (not per transition)."""
        if self.epsilon > self.epsilon_end:
            self.epsilon = max(self.epsilon_end, self.epsilon * self.epsilon_decay)

    def learn(self) -> float | None:
        """Run one V-function Bellman gradient update with PER. Returns loss or None."""
        if len(self.buffer) < self.batch_size:
            return None

        self.online_net.train()
        batch, weights, indices = self.buffer.sample(self.batch_size)
        states = np.array([t.state for t in batch])
        rewards = np.array([t.reward for t in batch])
        next_states = np.array([t.next_state for t in batch])
        dones = np.array([t.done for t in batch])
        n_steps = np.array([t.n for t in batch])

        states_t = torch.from_numpy(states).float().to(self.device)
        rewards_t = torch.from_numpy(rewards).float().to(self.device)
        next_states_t = torch.from_numpy(next_states).float().to(self.device)
        dones_t = torch.from_numpy(dones).float().to(self.device)
        weights_t = torch.from_numpy(weights).float().to(self.device)
        n_steps_t = torch.from_numpy(n_steps).float().to(self.device)

        # Current V-values
        current_v = self.online_net(states_t).squeeze(-1)

        # Target V = r + gamma^n * V_target(s') * (1 - done)
        with torch.no_grad():
            target_v = self.target_net(next_states_t).squeeze(-1)
            target_v = rewards_t + (self.gamma**n_steps_t) * target_v * (1 - dones_t)

        td_errors = (current_v - target_v).detach()
        self.last_td_error_mean = td_errors.abs().mean().item()
        self.last_td_error_max = td_errors.abs().max().item()
        loss = (self.loss_fn(current_v, target_v) * weights_t).mean()
        self.optimizer.zero_grad()
        loss.backward()
        grad_norm = torch.nn.utils.clip_grad_norm_(self.online_net.parameters(), 1.0)
        self.last_grad_norm = float(grad_norm)
        self.optimizer.step()

        # Update priorities based on TD errors
        self.buffer.update_priorities(indices, td_errors.cpu().numpy())

        self.last_loss = loss.item()
        self.steps += 1

        # LR scheduler: reduce LR if loss plateaus
        self.scheduler.step(self.last_loss)

        # TensorBoard scalars
        if self._tb_writer is not None:
            self._tb_writer.add_scalar("train/loss", self.last_loss, self.steps)
            self._tb_writer.add_scalar("train/td_error_mean", self.last_td_error_mean, self.steps)
            self._tb_writer.add_scalar("train/td_error_max", self.last_td_error_max, self.steps)
            self._tb_writer.add_scalar("train/grad_norm", self.last_grad_norm, self.steps)
            self._tb_writer.add_scalar("train/lr", self.optimizer.param_groups[0]["lr"], self.steps)
            self._tb_writer.add_scalar("train/buffer_fill", len(self.buffer), self.steps)
            self._tb_writer.add_scalar("train/beta", self.buffer.beta, self.steps)
            self._tb_writer.add_scalar("train/epsilon", self.epsilon, self.steps)

        # Step-level JSONL log
        if self.step_log_path is not None:
            self._write_step_log()

        # Hard target sync every target_sync_freq steps
        self._sync_target()

        return self.last_loss

    def _sync_target(self) -> None:
        """Hard-sync target network to online every target_sync_freq steps."""
        if self.steps % self.target_sync_freq == 0:
            self.target_net.load_state_dict(self.online_net.state_dict())
            self.target_syncs += 1

    def training_metrics(self) -> dict[str, float | int]:
        """Snapshot of training dynamics for episode logging."""
        return {
            "lr": self.optimizer.param_groups[0]["lr"],
            "buffer_fill": len(self.buffer),
            "beta": self.buffer.beta,
            "td_error_mean": self.last_td_error_mean,
            "td_error_max": self.last_td_error_max,
            "grad_norm": self.last_grad_norm,
            "target_syncs": self.target_syncs,
            "steps": self.steps,
            "v_spread": self.last_v_spread,
            "v_margin": self.last_v_margin,
        }

    def _write_step_log(self) -> None:
        """Append one JSONL line of step-level metrics. Rotate at max lines."""
        entry = {
            "step": self.steps,
            "loss": self.last_loss,
            "td_error_mean": self.last_td_error_mean,
            "td_error_max": self.last_td_error_max,
            "grad_norm": self.last_grad_norm,
            "lr": self.optimizer.param_groups[0]["lr"],
            "buffer_fill": len(self.buffer),
            "beta": self.buffer.beta,
            "epsilon": self.epsilon,
        }
        try:
            assert self.step_log_path is not None  # guarded by caller
            path = Path(self.step_log_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "a") as f:
                f.write(json.dumps(entry) + "\n")
            # Rotate: keep last STEP_LOG_MAX_LINES
            if self.steps % 1000 == 0 and path.exists():
                lines = path.read_text().splitlines()
                if len(lines) > STEP_LOG_MAX_LINES:
                    path.write_text("\n".join(lines[-STEP_LOG_MAX_LINES:]) + "\n")
        except OSError:
            pass  # ponytail: step log is best-effort, training must not crash

    def flush_logs(self) -> None:
        """Flush TensorBoard writer."""
        if self._tb_writer is not None:
            self._tb_writer.flush()

    def advance_curriculum(self, max_level: int, freq: int) -> bool:
        """Advance curriculum level if enough episodes elapsed.

        Returns True if the level was advanced.
        """
        if self.curriculum_level >= max_level:
            return False
        self.curriculum_episode_count += 1
        if self.curriculum_episode_count >= freq:
            self.curriculum_episode_count = 0
            self.curriculum_level += 1
            return True
        return False

    # --- Persistence -----------------------------------------------------

    def save(self, path: str) -> None:
        """Save model weights, optimizer state, and training progress."""
        torch.save(
            {
                "online_net": self.online_net.state_dict(),
                "target_net": self.target_net.state_dict(),
                "optimizer": self.optimizer.state_dict(),
                "scheduler": self.scheduler.state_dict(),
                "epsilon": self.epsilon,
                "steps": self.steps,
                "state_size": self.state_size,
                "curriculum_level": self.curriculum_level,
                "curriculum_episode_count": self.curriculum_episode_count,
                "beta": self.buffer.beta,
                "target_syncs": self.target_syncs,
            },
            path,
        )

    def load(self, path: str) -> None:
        """Load model weights and resume training from checkpoint."""
        checkpoint = torch.load(path, map_location=self.device, weights_only=True)
        self.online_net.load_state_dict(checkpoint["online_net"])
        self.target_net.load_state_dict(checkpoint["target_net"])
        self.optimizer.load_state_dict(checkpoint["optimizer"])
        if "scheduler" in checkpoint:
            self.scheduler.load_state_dict(checkpoint["scheduler"])
        self.epsilon = checkpoint.get("epsilon", self.epsilon)
        self.steps = checkpoint.get("steps", 0)
        self.curriculum_level = checkpoint.get("curriculum_level", 0)
        self.curriculum_episode_count = checkpoint.get("curriculum_episode_count", 0)
        self.target_syncs = checkpoint.get("target_syncs", 0)
        self.buffer.beta = checkpoint.get("beta", self.buffer.beta)
