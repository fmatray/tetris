"""Menu background animation: tetrominos slowly falling from the top.

Up to ``MENU_ANIM_MAX_PIECES`` tetrominos drift downward at random x
positions, randomly rotating CW/CCW.  After a delay they may randomly
explode into particles (reusing :class:`~tetris.visuals.particles.ParticleSystem`);
otherwise they fade out near the bottom and are removed.
"""

from __future__ import annotations

import random

import pygame

from tetris.settings import (
    MENU_ANIM_BLOCK_SIZE,
    MENU_ANIM_EXPLODE_CHANCE,
    MENU_ANIM_EXPLODE_DELAY,
    MENU_ANIM_EXPLODE_PARTICLES,
    MENU_ANIM_FADE_DISTANCE,
    MENU_ANIM_FALL_SPEED,
    MENU_ANIM_MAX_PIECES,
    MENU_ANIM_MAX_SPAWN_INTERVAL,
    MENU_ANIM_MIN_SPAWN_INTERVAL,
    MENU_ANIM_ROT_CHANCE,
    MENU_ANIM_ROT_INTERVAL,
    SCREEN_HEIGHT,
    SCREEN_WIDTH,
    SHAPES,
    SHAPES_COLORS,
)
from tetris.visuals.particles import ParticleSystem


class _FallingPiece:
    """A single tetromino falling down the screen.

    ``_blocks`` are relative coordinates (col, row) into ``SHAPES``; the
    piece is drawn at pixel ``(x, y)`` with ``BLOCK_SIZE``-sized cells.
    Rotation wraps around the list of rotations for the piece type.
    """

    __slots__ = (
        "age", "blocks", "color", "rot_index", "rot_timer",
        "shape_key", "x", "y",
    )

    def __init__(self, shape_key: str) -> None:
        self.shape_key = shape_key
        self.blocks = SHAPES[shape_key]
        self.rot_index = 0
        self.color = SHAPES_COLORS[shape_key]
        # Always start at top; random horizontal position across screen.
        self.x = random.uniform(0, max(0, SCREEN_WIDTH - MENU_ANIM_BLOCK_SIZE * 4))
        self.y = -MENU_ANIM_BLOCK_SIZE * 4  # just above visible area
        self.age = 0.0
        self.rot_timer = random.uniform(*MENU_ANIM_ROT_INTERVAL)

    @property
    def cells(self) -> list[tuple[int, int]]:
        """Current rotation's (col, row) offsets."""
        return self.blocks[self.rot_index]

    def rotate(self, direction: int) -> None:
        n = len(self.blocks)
        self.rot_index = (self.rot_index + direction) % n

    def max_row(self) -> int:
        return max(r for _, r in self.cells)

    def max_col(self) -> int:
        return max(c for c, _ in self.cells)

    def update(self, dt: float) -> None:
        self.age += dt
        self.y += MENU_ANIM_FALL_SPEED * dt
        self.rot_timer -= dt
        if self.rot_timer <= 0:
            direction = 1 if random.random() < MENU_ANIM_ROT_CHANCE else -1
            self.rotate(direction)
            self.rot_timer = random.uniform(*MENU_ANIM_ROT_INTERVAL)

    def should_explode(self) -> bool:
        delay = random.uniform(*MENU_ANIM_EXPLODE_DELAY)
        return self.age > delay and random.random() < MENU_ANIM_EXPLODE_CHANCE

    def is_offscreen(self) -> bool:
        return self.y + self.max_row() * MENU_ANIM_BLOCK_SIZE > SCREEN_HEIGHT

    def fade_alpha(self) -> float:
        """1.0 while fully visible, linearly → 0 in the last ``FADE_DISTANCE`` px."""
        bottom = self.y + self.max_row() * MENU_ANIM_BLOCK_SIZE
        fade_start = SCREEN_HEIGHT - MENU_ANIM_FADE_DISTANCE
        if bottom <= fade_start:
            return 1.0
        return max(0.0, 1.0 - (bottom - fade_start) / MENU_ANIM_FADE_DISTANCE)

    def draw(self, screen: pygame.Surface) -> None:
        alpha = self.fade_alpha()
        if alpha <= 0:
            return
        for col, row in self.cells:
            rect = pygame.Rect(
                int(self.x + col * MENU_ANIM_BLOCK_SIZE),
                int(self.y + row * MENU_ANIM_BLOCK_SIZE),
                MENU_ANIM_BLOCK_SIZE,
                MENU_ANIM_BLOCK_SIZE,
            )
            if alpha < 1.0:
                faded = tuple(int(c * alpha) for c in self.color)
                pygame.draw.rect(screen, faded, rect)
            else:
                pygame.draw.rect(screen, self.color, rect)


class MenuBackgroundAnimation:
    """Manages spawning, updating, and drawing falling menu tetrominos."""

    def __init__(self) -> None:
        self._pieces: list[_FallingPiece] = []
        self._spawn_timer = random.uniform(
            MENU_ANIM_MIN_SPAWN_INTERVAL, MENU_ANIM_MAX_SPAWN_INTERVAL,
        )

    def update(self, dt: float, particles: ParticleSystem) -> None:
        # Spawn new pieces up to the cap.
        self._spawn_timer -= dt
        if self._spawn_timer <= 0 and len(self._pieces) < MENU_ANIM_MAX_PIECES:
            self._pieces.append(_FallingPiece(random.choice(list(SHAPES))))
            self._spawn_timer = random.uniform(
                MENU_ANIM_MIN_SPAWN_INTERVAL, MENU_ANIM_MAX_SPAWN_INTERVAL,
            )

        surviving: list[_FallingPiece] = []
        for piece in self._pieces:
            piece.update(dt)
            if piece.should_explode():
                self._explode(particles, piece)
                continue
            if piece.is_offscreen() and piece.fade_alpha() <= 0:
                continue
            surviving.append(piece)
        self._pieces = surviving

    def _explode(self, particles: ParticleSystem, piece: _FallingPiece) -> None:
        for col, row in piece.cells:
            px = piece.x + col * MENU_ANIM_BLOCK_SIZE + MENU_ANIM_BLOCK_SIZE // 2
            py = piece.y + row * MENU_ANIM_BLOCK_SIZE + MENU_ANIM_BLOCK_SIZE // 2
            particles.emit(px, py, piece.color, MENU_ANIM_EXPLODE_PARTICLES // len(piece.cells))

    def draw(self, screen: pygame.Surface) -> None:
        for piece in self._pieces:
            piece.draw(screen)