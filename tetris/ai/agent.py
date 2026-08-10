"""DQN Agent: per-candidate V-function evaluation and learning.

The agent encapsulates two networks (online + target), a prioritized
experience replay buffer with n-step returns, and the training update
step. It is framework-agnostic regarding the game — it only sees state
vectors, rewards, and done flags.
"""

from __future__ import annotations

import random
from collections import deque

import numpy as np
import torch
from torch import nn, optim

from tetris.ai.network import DQNetwork
from tetris.ai.replay_buffer import PrioritizedReplayBuffer
from tetris.ai.rewards import FEATURE_SIZE

# Temperature for Dellacherie-weighted softmax during exploration (warm-start).
# Calibrated to typical Dellacherie value range (-200 to -10).
WARM_START_TEMP: float = 30.0

# N-step return horizon for multi-step Bellman targets.
N_STEP = 3


def _softmax(x: np.ndarray) -> np.ndarray:
    """Numerically stable softmax."""
    e = np.exp(x - x.max())
    return e / e.sum()


class DQNAgent:
    """V-network DQN agent with PER, n-step returns, and target network.

    Hyperparameters: lr=1e-3, gamma=0.97, epsilon 1.0→0.10 (decay 0.999/episode),
    batch=64, Polyak τ=0.005 (soft target update every step), SmoothL1Loss + grad clipping at 1.0.
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
        device: str = "cpu",
    ) -> None:
        self.state_size = state_size
        self.gamma = gamma
        self.epsilon = epsilon_start
        self.epsilon_end = epsilon_end
        self.epsilon_decay = epsilon_decay
        self.batch_size = batch_size
        self.tau: float = 0.005
        self.device = torch.device(device)

        self.online_net = DQNetwork(state_size).to(self.device)
        self.target_net = DQNetwork(state_size).to(self.device)
        self.target_net.load_state_dict(self.online_net.state_dict())
        self.target_net.eval()

        self.optimizer = optim.Adam(self.online_net.parameters(), lr=lr)
        self.loss_fn = nn.SmoothL1Loss(reduction="none")
        self.buffer = PrioritizedReplayBuffer(buffer_size)

        # N-step transition buffer: accumulates N transitions before pushing
        self._n_step_buffer: deque = deque(maxlen=N_STEP)

        self.steps = 0
        self.last_loss: float = 0.0

    # --- Action selection -----------------------------------------------

    def select_action(
        self, candidate_states: np.ndarray, dellacherie_values: np.ndarray | None = None
    ) -> int:
        """ε-greedy: random candidate with prob ε, greedy (max V) otherwise.

        During exploration, uses Dellacherie-weighted softmax (warm-start)
        instead of uniform random when ``dellacherie_values`` is provided.

        Args:
            candidate_states: (N, 17) array of feature vectors for valid placements.
            dellacherie_values: (N,) array of Dellacherie board values for warm-start.
        Returns:
            Index of the chosen candidate (0..N-1).
        """
        n = len(candidate_states)
        if random.random() < self.epsilon:
            if dellacherie_values is not None and len(dellacherie_values) == n:
                # Warm-start: softmax over Dellacherie values (directed exploration)
                probs = _softmax(dellacherie_values / WARM_START_TEMP)
                return int(np.random.choice(n, p=probs))
            return random.randint(0, n - 1)
        with torch.no_grad():
            states = torch.from_numpy(candidate_states).float().to(self.device)
            values = self.online_net(states).squeeze(-1)
            return values.argmax(dim=0).item()

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
        self._n_step_buffer.append((state, action, reward, next_state, done))
        if done:
            # Flush all partial n-step transitions immediately
            self.flush_n_step()
        elif len(self._n_step_buffer) == N_STEP:
            self._push_n_step()

    def _push_n_step(self) -> None:
        """Compute n-step return from buffer and push to PER."""
        s0, a0, _, _, _ = self._n_step_buffer[0]
        r = 0.0
        for i, (_, _, ri, _, di) in enumerate(self._n_step_buffer):
            r += (self.gamma ** i) * ri
            if di:
                break
        sn = self._n_step_buffer[-1][3]
        done_n = any(t[4] for t in self._n_step_buffer)
        self.buffer.push(s0, a0, r, sn, done_n)
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

        batch, weights, indices = self.buffer.sample(self.batch_size)
        states = np.array([t[0] for t in batch])
        rewards = np.array([t[2] for t in batch])
        next_states = np.array([t[3] for t in batch])
        dones = np.array([t[4] for t in batch])

        states_t = torch.from_numpy(states).float().to(self.device)
        rewards_t = torch.from_numpy(rewards).float().to(self.device)
        next_states_t = torch.from_numpy(next_states).float().to(self.device)
        dones_t = torch.from_numpy(dones).float().to(self.device)
        weights_t = torch.from_numpy(weights).float().to(self.device)

        # Current V-values
        current_v = self.online_net(states_t).squeeze(-1)

        # Target V = r + gamma^n * V_target(s') * (1 - done)
        with torch.no_grad():
            target_v = self.target_net(next_states_t).squeeze(-1)
            target_v = rewards_t + (self.gamma ** N_STEP) * target_v * (1 - dones_t)

        td_errors = (current_v - target_v).detach()
        loss = (self.loss_fn(current_v, target_v) * weights_t).mean()
        self.optimizer.zero_grad()
        loss.backward()
        torch.nn.utils.clip_grad_norm_(self.online_net.parameters(), 1.0)
        self.optimizer.step()

        # Update priorities based on TD errors
        self.buffer.update_priorities(indices, td_errors.cpu().numpy())

        self.last_loss = loss.item()
        self.steps += 1

        # Polyak soft target update (every step)
        self._sync_target()

        return self.last_loss

    def _sync_target(self) -> None:
        """Polyak averaging: blend target toward online by τ."""
        with torch.no_grad():
            for tp, op in zip(self.target_net.parameters(), self.online_net.parameters()):
                tp.mul_(1 - self.tau).add_(self.tau * op)

    # --- Persistence -----------------------------------------------------

    def save(self, path: str) -> None:
        """Save model weights, optimizer state, and training progress."""
        torch.save(
            {
                "online_net": self.online_net.state_dict(),
                "target_net": self.target_net.state_dict(),
                "optimizer": self.optimizer.state_dict(),
                "epsilon": self.epsilon,
                "steps": self.steps,
                "state_size": self.state_size,
            },
            path,
        )

    def load(self, path: str) -> None:
        """Load model weights and resume training from checkpoint."""
        checkpoint = torch.load(path, map_location=self.device, weights_only=False)
        self.online_net.load_state_dict(checkpoint["online_net"])
        self.target_net.load_state_dict(checkpoint["target_net"])
        self.optimizer.load_state_dict(checkpoint["optimizer"])
        self.epsilon = checkpoint.get("epsilon", self.epsilon)
        self.steps = checkpoint.get("steps", 0)