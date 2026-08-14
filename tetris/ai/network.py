"""V-network: 17 → 128 → 64 → 1 board value."""

from __future__ import annotations

import torch
from torch import nn


class DQNetwork(nn.Module):
    """Feed-forward V-network mapping DT-20 features to a board value.

    Architecture (per AI.md §5):
        Input (17) → Dense(128, ReLU) → Dense(64, ReLU) → Output (1, Linear)
    """
    def __init__(self, state_size: int = 17) -> None:
        """Build the 3-layer MLP.

        Args:
            state_size: Input feature dimension (default 17 for DT-20 features).
        """
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(state_size, 128),
            nn.ReLU(),
            nn.Linear(128, 64),
            nn.ReLU(),
            nn.Linear(64, 1),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """Return the V-value (board quality) for a batch of state vectors."""
        return self.net(x)