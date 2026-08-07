"""Experience replay buffer for DQN training stabilization."""

from __future__ import annotations

import random
from collections import deque

import numpy as np


class ReplayBuffer:
    """Fixed-capacity FIFO buffer storing (s, a, r, s', done) transitions.

    Random sampling breaks temporal correlation between consecutive
    experiences, stabilizing gradient updates (see AI.md §1.1).
    """

    def __init__(self, capacity: int = 50_000) -> None:
        self.buffer: deque = deque(maxlen=capacity)

    def push(
        self,
        state: np.ndarray,
        action: int,
        reward: float,
        next_state: np.ndarray,
        done: bool,
    ) -> None:
        self.buffer.append((state, action, reward, next_state, done))

    def sample(self, batch_size: int) -> list[tuple]:
        return random.sample(self.buffer, min(batch_size, len(self.buffer)))

    def __len__(self) -> int:
        return len(self.buffer)