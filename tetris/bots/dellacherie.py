"""Dellacherie bot: pure selection algorithm, no game-state dependencies."""

from __future__ import annotations

import numpy as np


def dellacherie_pick(dellvals: np.ndarray) -> int:
    """Index of the best Dellacherie placement (ties resolved to lowest index)."""
    return int(np.argmax(dellvals))
