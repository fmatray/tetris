"""DQN neural network: 218 → 256 → 128 → 64 → 6 Q-values."""

from __future__ import annotations

import torch
import torch.nn as nn


class DQNetwork(nn.Module):
    """Feed-forward Q-network mapping state features to per-action Q-values.

    Architecture (per AI.md §5):
        Input (218) → Dense(256, ReLU) → Dense(128, ReLU)
        → Dense(64, ReLU) → Output (6, Linear)
    """

    def __init__(self, state_size: int = 218, action_size: int = 6) -> None:
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(state_size, 256),
            nn.ReLU(),
            nn.Linear(256, 128),
            nn.ReLU(),
            nn.Linear(128, 64),
            nn.ReLU(),
            nn.Linear(64, action_size),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.net(x)