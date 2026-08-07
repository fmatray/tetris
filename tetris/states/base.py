"""Finite State Machine states for the Tetris game loop.

Each state implements ``handle_event``, ``update`` (optional), and
``draw`` with a uniform signature. Cross-state transitions return a new
``State`` from ``handle_event`` or ``update``; ``None`` means "stay".

States reference each other, so concrete states are imported lazily
inside methods to avoid import cycles while keeping the package API
flat via :mod:`tetris.states`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

import pygame

if TYPE_CHECKING:
    from tetris.visuals.particles import ParticleSystem


class State:
    """Base FSM state. Subclasses override the hooks they need."""

    def handle_event(self, event: pygame.event.Event) -> Optional["State"]:
        return None

    def update(self, dt: float, particles: "ParticleSystem") -> Optional["State"]:
        return None

    def draw(self, screen: pygame.Surface) -> None:
        pass