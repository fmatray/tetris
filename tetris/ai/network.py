"""V-network: 17 → 256 → 128 → 1 board value (optional dueling head)."""

from __future__ import annotations

import torch
from torch import nn


class DQNetwork(nn.Module):
    """Feed-forward V-network mapping DT-20 features to a board value.

    Architecture (per AI.md §5):
        Input (17) → Dense(256, ReLU) → Dense(128, ReLU) → Output (1, Linear)

    With ``dueling=True`` (Rainbow-family), the trunk splits into a value
    stream (1) and an advantage stream (1). The forward output is
    ``V(s) + A(s)`` — a function of the state alone, with no batch-mean
    advantage centering, so single-sample evaluation and ``learn()`` stay
    valid for the per-candidate V-selection this agent uses.

    The non-dueling layout keeps the original ``net`` Sequential, so
    existing checkpoints (``net.0/net.2/net.4`` keys) load unchanged.
    """

    def __init__(self, state_size: int = 17, dueling: bool = False) -> None:
        """Build the 3-layer MLP, optionally with a dueling head.

        Args:
            state_size: Input feature dimension (default 17 for DT-20 features).
            dueling: Split the output into value + advantage streams.
        """
        super().__init__()
        self.dueling = dueling
        if dueling:
            self.trunk = nn.Sequential(
                nn.Linear(state_size, 256),
                nn.ReLU(),
                nn.Linear(256, 128),
                nn.ReLU(),
            )
            self.value_head = nn.Linear(128, 1)
            self.advantage_head = nn.Linear(128, 1)
        else:
            self.net = nn.Sequential(
                nn.Linear(state_size, 256),
                nn.ReLU(),
                nn.Linear(256, 128),
                nn.ReLU(),
                nn.Linear(128, 1),
            )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """Return the V-value (board quality) for a batch of state vectors."""
        if self.dueling:
            h = self.trunk(x)
            return self.value_head(h) + self.advantage_head(h)
        return self.net(x)
