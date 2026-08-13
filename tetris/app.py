"""Application runner: pygame init, FSM loop, state transitions.

This is the only module that owns the main loop and the top-level
``State`` variable. It wires concrete dependencies (screen, font,
audio, particles) into states and drives ``handle_event`` / ``update``
/ ``draw`` at a single layer of abstraction (SLAP).
"""

from __future__ import annotations

import sys

import pygame

from tetris.audio import AudioManager
from tetris.logger import configure_logging, get_logger
from tetris.settings import SCREEN_HEIGHT, SCREEN_WIDTH, ensure_data_dir
from tetris.states.base import State
from tetris.states.menu import MenuState
from tetris.visuals.fonts import get_small_font
from tetris.visuals.particles import ParticleSystem


class TetrisApp:
    """Owns pygame initialization and the FSM main loop."""

    def __init__(self) -> None:
        ensure_data_dir()
        configure_logging(False)
        pygame.init()
        pygame.mixer.init()
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        self.clock = pygame.time.Clock()
        pygame.display.set_caption("Tetris Python")
        self.font = get_small_font()
        self.audio = AudioManager()
        self.particles = ParticleSystem()
        self.state: State = MenuState(self.screen, self.font, self.audio)

    def run(self) -> None:
        logger = get_logger("app")
        logger.info("Starting Tetris...")
        while True:
            try:
                self._frame()
            except Exception:  # top-level safety net
                logger.exception("Runtime error in main loop")
                break

    def _frame(self) -> None:
        dt = self.clock.tick(60)
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            new_state = self.state.handle_event(event)
            if new_state:
                self.state = new_state

        new_state = (
            self.state.update(dt, self.particles)
            if hasattr(self.state, "update")
            else None
        )
        if new_state:
            self.state = new_state

        self.state.draw(self.screen, particles=self.particles)
        pygame.display.flip()

        self.particles.update()


def run() -> None:
    """Public entry point — create and run the Tetris app."""
    TetrisApp().run()