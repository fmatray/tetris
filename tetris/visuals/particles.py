"""Particle system for line-clear and game-over explosions."""

import random

import pygame


class Particle:
    """A single particle with gravity, friction, and life decay."""

    __slots__ = ("color", "decay", "life", "size", "vx", "vy", "x", "y")

    def __init__(self, x: float, y: float, color: tuple[int, int, int]) -> None:
        self.x, self.y, self.color = x, y, color
        self.vx = random.uniform(-8, 8)
        self.vy = random.uniform(-12, -4)
        self.life = random.uniform(0.6, 1.4)
        self.decay = random.uniform(0.01, 0.03)
        self.size = random.randint(2, 6)

    def update(self) -> None:
        self.x += self.vx
        self.y += self.vy
        self.vy += 0.1
        self.vx *= 0.95
        self.life -= self.decay

    def draw(self, screen: pygame.Surface) -> None:
        if self.life > 0:
            try:
                current_size = max(1, int(self.size * self.life))
                color_fade = [max(0, min(255, int(c * self.life))) for c in self.color]
                pygame.draw.rect(
                    screen, color_fade, (self.x, self.y, current_size, current_size)
                )
            except (ValueError, TypeError):
                pass


class ParticleSystem:
    """Manages a collection of particles: emit, update, draw."""

    def __init__(self) -> None:
        self.particles: list[Particle] = []

    def emit(
        self, x: float, y: float, color: tuple[int, int, int], count: int = 1
    ) -> None:
        for _ in range(count):
            self.particles.append(Particle(x, y, color))

    def update(self) -> None:
        for p in self.particles:
            p.update()
        self.particles = [p for p in self.particles if p.life > 0]

    def draw(self, screen: pygame.Surface) -> None:
        for p in self.particles:
            p.draw(screen)