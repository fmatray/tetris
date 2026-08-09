"""DQN neural network: 220 → 256 → 128 → 64 → 40 Q-values."""

from __future__ import annotations

import torch
from torch import nn


class DQNetwork(nn.Module):
    """Feed-forward Q-network mapping state features to per-action Q-values.

    Architecture (per AI.md §5):
        Input (220) → Dense(256, ReLU) → Dense(128, ReLU)
        → Dense(64, ReLU) → Output (40, Linear)
    """

    def __init__(self, state_size: int = 220, action_size: int = 40) -> None:
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