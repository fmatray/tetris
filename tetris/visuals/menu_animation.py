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
        "age", "blocks", "color", "explode_delay", "rot_index",
        "rot_timer", "shape_key", "x", "y",
    )

    def __init__(self, shape_key: str) -> None:
        """Initialize a falling tetromino at a random horizontal position.

        The piece starts just above the visible area (y < 0) at a random
        x coordinate.  ``explode_delay`` is rolled once here so that the
        explosion gate is deterministic per-piece rather than re-rolled
        every frame.

        Args:
            shape_key: Key into ``SHAPES``/``SHAPES_COLORS`` (e.g. ``"I"``).
        """
        self.shape_key = shape_key
        self.blocks = SHAPES[shape_key]
        self.rot_index = 0
        self.color = SHAPES_COLORS[shape_key]
        # Always start at top; random horizontal position across screen.
        self.x = random.uniform(0, max(0, SCREEN_WIDTH - MENU_ANIM_BLOCK_SIZE * 4))
        self.y: float = -MENU_ANIM_BLOCK_SIZE * 4  # just above visible area
        self.age = 0.0
        self.explode_delay = random.uniform(*MENU_ANIM_EXPLODE_DELAY)
        self.rot_timer = random.uniform(*MENU_ANIM_ROT_INTERVAL)

    @property
    def cells(self) -> list[tuple[int, int]]:
        """Current rotation's (col, row) offsets."""
        return self.blocks[self.rot_index]

    def rotate(self, direction: int) -> None:
        """Advance the rotation index, wrapping around the piece's rotations.

        Args:
            direction: ``+1`` for CW, ``-1`` for CCW.
        """
        n = len(self.blocks)
        self.rot_index = (self.rot_index + direction) % n

    def max_row(self) -> int:
        """Largest row offset in the current rotation (used for bottom-edge math)."""
        return max(r for _, r in self.cells)


    def update(self, dt: float) -> None:
        """Advance fall position, age, and rotation timer.

        When the rotation timer expires, a random CW/CCW rotation is
        applied and the timer is re-rolled within ``MENU_ANIM_ROT_INTERVAL``.

        Args:
            dt: Elapsed seconds since the last update.
        """
        self.age += dt
        self.y += MENU_ANIM_FALL_SPEED * dt
        self.rot_timer -= dt
        if self.rot_timer <= 0:
            direction = 1 if random.random() < MENU_ANIM_ROT_CHANCE else -1
            self.rotate(direction)
            self.rot_timer = random.uniform(*MENU_ANIM_ROT_INTERVAL)
    def should_explode(self) -> bool:
        """Whether the piece should explode this frame.

        Returns ``True`` only after ``explode_delay`` seconds have elapsed
        **and** a per-frame ``MENU_ANIM_EXPLODE_CHANCE`` roll succeeds.
        The delay is fixed at construction; only the chance is re-rolled.
        """
        return self.age > self.explode_delay and random.random() < MENU_ANIM_EXPLODE_CHANCE

    def is_offscreen(self) -> bool:
        """Whether the piece's bottom edge has passed the screen height."""
        return self.y + self.max_row() * MENU_ANIM_BLOCK_SIZE > SCREEN_HEIGHT

    def fade_alpha(self) -> float:
        """1.0 while fully visible, linearly → 0 in the last ``FADE_DISTANCE`` px."""
        bottom = self.y + self.max_row() * MENU_ANIM_BLOCK_SIZE
        fade_start = SCREEN_HEIGHT - MENU_ANIM_FADE_DISTANCE
        if bottom <= fade_start:
            return 1.0
        return max(0.0, 1.0 - (bottom - fade_start) / MENU_ANIM_FADE_DISTANCE)

    def draw(self, screen: pygame.Surface) -> None:
        """Draw the piece, applying alpha fade near the bottom of the screen.

        When ``fade_alpha()`` returns ``< 1.0``, each cell's RGB is scaled
        by the alpha value (cheap fade without per-pixel alpha surfaces).
        Fully transparent pieces are skipped entirely.

        Args:
            screen: Target surface to draw onto.
        """
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
    """Manages spawning, updating, and drawing falling menu tetrominos.

    Holds a pool of :class:`_FallingPiece` objects, spawning new ones at
    random intervals (capped at ``MENU_ANIM_MAX_PIECES``).  Each update
    advances pieces, triggers explosions into the shared
    :class:`~tetris.visuals.particles.ParticleSystem`, and removes pieces
    that have exploded or fully faded past the bottom edge.
    """

    def __init__(self) -> None:
        """Initialize an empty pool with a random first-spawn countdown."""
        self._pieces: list[_FallingPiece] = []
        self._spawn_timer = random.uniform(
            MENU_ANIM_MIN_SPAWN_INTERVAL, MENU_ANIM_MAX_SPAWN_INTERVAL,
        )

    def update(self, dt: float, particles: ParticleSystem) -> None:
        """Spawn, advance, and cull falling pieces.

        New pieces are spawned when the spawn timer expires and the pool
        is below ``MENU_ANIM_MAX_PIECES``.  Each piece is then updated;
        pieces that ``should_explode()`` emit particles and are removed.
        Pieces that have gone fully off-screen with zero alpha are also
        removed.  Surviving pieces are retained for the next frame.

        Args:
            dt: Elapsed seconds since the last update.
            particles: Shared particle system to receive explosion bursts.
        """
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
        """Emit explosion particles centered on each cell of *piece*.

        Particles per cell = ``MENU_ANIM_EXPLODE_PARTICLES // len(cells)``,
        so the total particle count is roughly constant regardless of
        piece shape.

        Args:
            particles: Shared particle system to emit into.
            piece: The piece being exploded.
        """
        for col, row in piece.cells:
            px = piece.x + col * MENU_ANIM_BLOCK_SIZE + MENU_ANIM_BLOCK_SIZE // 2
            py = piece.y + row * MENU_ANIM_BLOCK_SIZE + MENU_ANIM_BLOCK_SIZE // 2
            particles.emit(px, py, piece.color, MENU_ANIM_EXPLODE_PARTICLES // len(piece.cells))

    def draw(self, screen: pygame.Surface) -> None:
        """Draw all active pieces onto *screen*.

        Args:
            screen: Target surface to draw onto.
        """
        for piece in self._pieces:
            piece.draw(screen)