"""Human gameplay state: keyboard-driven Tetris with DAS auto-shift.

Concrete subclass of :class:`GameState` providing keyboard input handling,
DAS (Delayed Auto-Shift) state, and pause toggle for human play.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tetris.states.menu import MenuState

import pygame

from tetris.audio import AudioManager
from tetris.game.piece_provider import PieceProvider
from tetris.settings import DAS_DELAY_MS, DAS_REPEAT_MS
from tetris.states.base import State
from tetris.states.game import GameConfig, GameState
from tetris.visuals.particles import ParticleSystem


class HumanState(GameState):
    """Human keyboard input on top of the shared :class:`GameState` engine.

    Adds keybind setup, DAS auto-shift, pause toggle, and full keyboard
    event handling. Movement primitives are inherited from :class:`GameState`.
    """

    paused: bool  # inherited from GameState; annotated for zuban type inference

    def __init__(
        self,
        screen: pygame.Surface,
        font: pygame.font.Font,
        audio: AudioManager,
        config: GameConfig,
        piece_provider: PieceProvider | None = None,
        menu: MenuState | None = None,
    ) -> None:
        """Initialize a human gameplay session.

        Sets up the board (with handicap), piece provider, keybinds, lock-delay
        state, DAS state, and the preview/hold piece queues.

            screen: Pygame display surface.
            font: Font for HUD text.
            audio: Audio manager.
            config: Gameplay settings (handicap, sound, debug, etc.).
            piece_provider: Spawn controller (created if ``None``).
            menu: Parent :class:`MenuState` for settings access.
        """
        super().__init__(
            screen,
            font,
            audio,
            config,
            piece_provider,
            menu,
        )
        self._setup_keybinds(menu)
        self._das_held: dict[int, float] = {}

    def _setup_keybinds(self, menu: MenuState | None) -> None:
        """Build key → action map from the menu's keybindings (or defaults)."""
        from tetris.settings import DEFAULT_KEYBINDS

        kb = menu.keybinds if menu is not None else dict(DEFAULT_KEYBINDS)
        self.input_map: dict[int, Callable[[], None]] = {
            kb["move_left"]: self._move_left,
            kb["move_right"]: self._move_right,
            kb["rotate_cw"]: self._rotate_cw,
            kb["rotate_ccw"]: self._rotate_ccw,
            kb["soft_drop"]: self._soft_drop,
            kb["hard_drop"]: self._hard_drop,
            kb["hold"]: self._hold,
        }
        self._pause_key: int = kb["pause"]
        self._soft_drop_key: int = kb["soft_drop"]
        self._left_key: int = kb["move_left"]
        self._right_key: int = kb["move_right"]
        self._hold_key: int = kb["hold"]

    def handle_event(self, event: pygame.event.Event) -> State | None:
        """Process keyboard input: pause, movement, hold, DAS.

        Calls ``super().handle_event`` for ESC/mute first; if it returns a
        new state (ESC pressed), returns it immediately.
        """
        result = super().handle_event(event)
        if result is not None:
            return result
        if event.type == pygame.KEYDOWN:
            if event.key == self._pause_key:
                self.paused = not self.paused
            elif event.key in self.input_map:
                self.input_map[event.key]()
                # Start DAS tracking for left/right
                if event.key in (self._left_key, self._right_key):
                    self._das_held[event.key] = 0.0
        elif event.type == pygame.KEYUP:
            if event.key == self._soft_drop_key:
                self.down_pressed = False
            if event.key in self._das_held:
                del self._das_held[event.key]
        return None

    def update(self, dt: float, particles: ParticleSystem) -> State | None:
        """Advance DAS auto-shift, then delegate to ``super().update``.

        Returns a new :class:`State` on game-over, or ``None`` to stay.
        """
        if not self.game_over and not self.paused:
            for key in list(self._das_held):
                self._das_held[key] += dt
                held = self._das_held[key]
                if held >= DAS_DELAY_MS:
                    since_last = held - DAS_DELAY_MS
                    if since_last >= DAS_REPEAT_MS:
                        self._das_held[key] = DAS_DELAY_MS
                        self.input_map[key]()
        return super().update(dt, particles)
