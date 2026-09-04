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

from tetris.game.board import LineClearResult
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
        # Imitation data: record placements for AI warm-start (roadmap #5).
        from tetris.game.imitation import PlacementsLog

        self._placement_recorder = PlacementsLog()
        self._placement_recorder.start_game(seed=self.seed, handicap=config.handicap)
        self._das_held: dict[int, float] = {}
        # Special modes (Sprint/Blitz) and efficiency accounting. AI/Bot/MCP
        # states never set these: they stay marathon with no timer/finesse.
        self.game_mode: str = {
            "Sprint": "sprint",
            "Blitz": "blitz",
        }.get(menu.mode if menu is not None else "Normal", "marathon")
        self.elapsed_ms: float = 0.0
        # Finesse accounting: lateral/rotation inputs for the current piece.
        self._piece_inputs: int = 0
        self._spawn_x: int | None = self.current_piece.x if self.current_piece is not None else None
        self.finesse_faults: int = 0
        # Wrap movement/rotation handlers to count finesse inputs.
        for key, action in list(self.input_map.items()):
            if action in (self._move_left, self._move_right, self._rotate_cw, self._rotate_ccw):
                self.input_map[key] = self._counted(action)

    def _counted(self, action: Callable[[], None]) -> Callable[[], None]:
        """Wrap an input handler so it also counts as a finesse input."""

        def wrapper() -> None:
            self._piece_inputs += 1
            action()

        return wrapper

    def _note_spawn(self) -> None:
        """Record spawn position and reset the per-piece input counter."""
        self._piece_inputs = 0
        piece = self.current_piece
        self._spawn_x = piece.x if piece is not None else None

    def _check_finesse(self) -> None:
        """Charge a finesse fault if inputs exceeded the theoretical minimum.

        # ponytail: approximate finesse — ignores SRS kick lateral credit and
        # overhang detours; upgrade to BFS shortest-path if the metric needs
        # to be exact.
        """
        if self._spawn_x is None or self.current_piece is None:
            return
        piece = self.current_piece
        from tetris.game.shapes import num_shape_rot

        min_rot = min(piece.rotation, num_shape_rot(piece.type) - piece.rotation)
        min_inputs = min_rot + abs(piece.x - self._spawn_x)
        if self._piece_inputs > min_inputs:
            self.finesse_faults += 1

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
            self.elapsed_ms += dt
            for key in list(self._das_held):
                self._das_held[key] += dt
                held = self._das_held[key]
                if held >= DAS_DELAY_MS:
                    since_last = held - DAS_DELAY_MS
                    if since_last >= DAS_REPEAT_MS:
                        self._das_held[key] = DAS_DELAY_MS
                        self.input_map[key]()
        result = super().update(dt, particles)
        if result is not None or self.game_over:
            return result
        return self._check_mode_end()

    def _check_mode_end(self) -> State | None:
        """End Sprint on 40 lines and Blitz when the 2-minute budget runs out."""
        from tetris.settings import BLITZ_DURATION_MS, SPRINT_TARGET_LINES

        if self.game_mode == "sprint" and self.stats.total_lines >= SPRINT_TARGET_LINES:
            self.game_over = True
            return self._do_game_over()
        if self.game_mode == "blitz" and self.elapsed_ms >= BLITZ_DURATION_MS:
            self.game_over = True
            return self._do_game_over()
        return None

    def _hold(self) -> None:
        """Hold piece swap, then reset finesse accounting for the swapped piece."""
        super()._hold()
        self._note_spawn()

    def _lock_and_spawn(self, hard_drop: bool = False) -> LineClearResult:
        """Lock with finesse fault check before the piece leaves the field."""
        self._check_finesse()
        result = super()._lock_and_spawn(hard_drop)
        self._note_spawn()
        return result

    def _on_exit(self) -> None:
        """Close the imitation placement recorder before leaving the state."""
        if self._placement_recorder is not None:
            self._placement_recorder.close()
            self._placement_recorder = None
        super()._on_exit()
