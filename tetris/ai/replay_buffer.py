"""Prioritized experience replay buffer for DQN training stabilization.

Proportional PER (Schaul et al. 2015): transitions sampled with
probability proportional to TD-error priority. Importance-sampling
weights correct the induced bias.
"""

from __future__ import annotations

from collections import deque

import numpy as np


class PrioritizedReplayBuffer:
    """Proportional PER buffer storing (s, a, r, s', done) transitions."""

    def __init__(
        self,
        capacity: int = 50_000,
        alpha: float = 0.6,
        beta: float = 0.4,
        beta_increment: float = 0.001,
    ) -> None:
        """Initialize the PER buffer.

        Args:
            capacity: Maximum number of stored transitions.
            alpha: Priority exponent (0 = uniform, 1 = full priority).
            beta: Initial importance-sampling correction (anneals to 1.0).
            beta_increment: Per-sample beta increment.
        """
        self.capacity = capacity
        self.alpha = alpha  # 0=uniform, 1=full priority
        self.beta = beta    # IS correction (anneals to 1.0)
        self.beta_increment = beta_increment
        self.buffer: deque = deque(maxlen=capacity)
        self.priorities: deque = deque(maxlen=capacity)

    def push(
        self,
        state: np.ndarray,
        action: int,
        reward: float,
        next_state: np.ndarray,
        done: bool,
    ) -> None:
        """Store a transition with max-priority (assumed high TD-error).

        Args:
            state: Pre-placement feature vector.
            action: Candidate index chosen.
            reward: Reward received.
            next_state: Post-placement feature vector.
            done: Whether the episode ended.
        """
        self.buffer.append((state, action, reward, next_state, done))
        max_prio = max(self.priorities) if self.priorities else 1.0
        self.priorities.append(max_prio)

    def sample(self, batch_size: int) -> tuple[list, np.ndarray, np.ndarray]:
        """Return (samples, weights, indices). Falls back to uniform if too small."""
        if len(self.buffer) < batch_size:
            return list(self.buffer), np.ones(len(self.buffer)), np.ones(len(self.buffer), dtype=int)
        priorities = np.array(self.priorities, dtype=np.float32)
        probs = priorities ** self.alpha
        probs /= probs.sum()
        indices = np.random.choice(len(self.buffer), size=batch_size, p=probs)
        samples = [self.buffer[i] for i in indices]
        # Importance sampling weights
        weights = (len(self.buffer) * probs[indices]) ** (-self.beta)
        weights /= weights.max()
        self.beta = min(1.0, self.beta + self.beta_increment)
        return samples, weights, indices

    def update_priorities(self, indices: np.ndarray, td_errors: np.ndarray) -> None:
        """Update transition priorities from TD errors.

        Args:
            indices: Buffer indices returned by :meth:`sample`.
            td_errors: Absolute TD errors (priority = ``|error| + 1e-5``).
        """
        for idx, error in zip(indices, td_errors, strict=False):
            self.priorities[idx] = abs(error) + 1e-5

    def __len__(self) -> int:
        """Return the number of stored transitions."""
        return len(self.buffer)