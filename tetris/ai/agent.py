"""DQN Agent: ε-greedy action selection and Q-network learning.

The agent encapsulates two networks (online + target), an experience
replay buffer, and the training update step. It is framework-agnostic
regarding the game — it only sees state vectors, actions, and rewards.
"""

from __future__ import annotations

import random

import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim

from tetris.ai.network import DQNetwork
from tetris.ai.replay_buffer import ReplayBuffer


class DQNAgent:
    """Deep Q-Network agent with experience replay and target network.

    Hyperparameters follow AI.md §1.1 and §5.
    """

    def __init__(
        self,
        state_size: int = 218,
        action_size: int = 6,
        lr: float = 1e-4,
        gamma: float = 0.95,
        epsilon_start: float = 1.0,
        epsilon_end: float = 0.05,
        epsilon_decay: float = 0.9995,
        buffer_size: int = 50_000,
        batch_size: int = 64,
        target_sync_steps: int = 1_000,
        device: str = "cpu",
    ) -> None:
        self.state_size = state_size
        self.action_size = action_size
        self.gamma = gamma
        self.epsilon = epsilon_start
        self.epsilon_end = epsilon_end
        self.epsilon_decay = epsilon_decay
        self.batch_size = batch_size
        self.target_sync_steps = target_sync_steps
        self.device = torch.device(device)

        self.online_net = DQNetwork(state_size, action_size).to(self.device)
        self.target_net = DQNetwork(state_size, action_size).to(self.device)
        self.target_net.load_state_dict(self.online_net.state_dict())
        self.target_net.eval()

        self.optimizer = optim.Adam(self.online_net.parameters(), lr=lr)
        self.loss_fn = nn.MSELoss()
        self.buffer = ReplayBuffer(buffer_size)

        self.steps = 0
        self.last_loss: float = 0.0

    # --- Action selection -----------------------------------------------

    def select_action(self, state: np.ndarray) -> int:
        """ε-greedy: random action with prob ε, greedy otherwise."""
        if random.random() < self.epsilon:
            return random.randrange(self.action_size)
        with torch.no_grad():
            s = torch.from_numpy(state).float().unsqueeze(0).to(self.device)
            q_values = self.online_net(s)
            return q_values.argmax(dim=1).item()

    # --- Learning --------------------------------------------------------

    def store(
        self,
        state: np.ndarray,
        action: int,
        reward: float,
        next_state: np.ndarray,
        done: bool,
    ) -> None:
        self.buffer.push(state, action, reward, next_state, done)

    def learn(self) -> float | None:
        """Run one gradient update from a mini-batch. Returns loss or None."""
        if len(self.buffer) < self.batch_size:
            return None

        batch = self.buffer.sample(self.batch_size)
        states = np.array([t[0] for t in batch])
        actions = np.array([t[1] for t in batch])
        rewards = np.array([t[2] for t in batch])
        next_states = np.array([t[3] for t in batch])
        dones = np.array([t[4] for t in batch])

        states_t = torch.from_numpy(states).float().to(self.device)
        actions_t = torch.from_numpy(actions).long().to(self.device)
        rewards_t = torch.from_numpy(rewards).float().to(self.device)
        next_states_t = torch.from_numpy(next_states).float().to(self.device)
        dones_t = torch.from_numpy(dones).float().to(self.device)

        # Current Q-values for the actions taken
        current_q = (
            self.online_net(states_t)
            .gather(1, actions_t.unsqueeze(1))
            .squeeze(1)
        )

        # Target Q-values: r + γ max_a' Q_target(s', a')
        with torch.no_grad():
            max_next_q = self.target_net(next_states_t).max(dim=1)[0]
            target_q = rewards_t + self.gamma * max_next_q * (1 - dones_t)

        loss = self.loss_fn(current_q, target_q)
        self.optimizer.zero_grad()
        loss.backward()
        self.optimizer.step()

        self.last_loss = loss.item()
        self.steps += 1

        # Decay epsilon
        if self.epsilon > self.epsilon_end:
            self.epsilon = max(self.epsilon_end, self.epsilon * self.epsilon_decay)

        # Sync target network
        if self.steps % self.target_sync_steps == 0:
            self._sync_target()

        return self.last_loss

    def _sync_target(self) -> None:
        self.target_net.load_state_dict(self.online_net.state_dict())

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