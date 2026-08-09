"""Base class for menu states with shared navigation and rendering."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pygame

from tetris.settings import BLACK, GRAY, SCREEN_HEIGHT, SCREEN_WIDTH, WHITE
from tetris.states.base import State

if TYPE_CHECKING:
    from tetris.visuals.particles import ParticleSystem


class MenuBase(State):
    """Template for menu states: navigation, toggles, rendering.

    Subclasses define class attributes and override hooks:
    - _OPTIONS: tuple of option labels
    - _title: title text
    - _toggle_indices: frozenset of indices that respond to left/right
    - _value_label(i) -> str: inline value for option i
    - _toggle(direction) -> None: change value (direction = -1 or +1)
    - _on_select() -> State | None: ENTER action
    - _is_disabled(i) -> bool: greyed-out options
    - _on_back() -> State | None: ESC action
    - _on_navigate() -> None: called on up/down (default: pass)
    - _save() -> None: persist settings after a toggle
    - _option_text(i, is_sel) -> str: custom text for an option
    - _option_color(i, is_sel, disabled) -> tuple: custom color
    """

    _OPTIONS: tuple[str, ...] = ()
    _title: str = ""
    _toggle_indices: frozenset[int] = frozenset()
    _title_y: int = 60
    _options_y: int = 140
    _item_spacing: int = 48
    _instructions: str = "Flèches: Navigation | Entrée: Valider | Échap: Retour"
    _disabled_color: tuple[int, int, int] = (64, 64, 64)

    def __init__(self, screen, font, audio) -> None:
        self.screen, self.font, self.audio = screen, font, audio
        self.selection = 0

    # --- Navigation --------------------------------------------------

    def _prev_enabled(self, current: int) -> int:
        n = len(self._OPTIONS)
        for step in range(1, n + 1):
            idx = (current - step) % n
            if not self._is_disabled(idx):
                return idx
        return current

    def _next_enabled(self, current: int) -> int:
        n = len(self._OPTIONS)
        for step in range(1, n + 1):
            idx = (current + step) % n
            if not self._is_disabled(idx):
                return idx
        return current

    # --- Event handling (template method) ----------------------------

    def handle_event(self, event: pygame.event.Event) -> State | None:
        if event.type != pygame.KEYDOWN:
            return None
        if event.key == pygame.K_UP:
            self.selection = self._prev_enabled(self.selection)
            self._on_navigate()
        elif event.key == pygame.K_DOWN:
            self.selection = self._next_enabled(self.selection)
            self._on_navigate()
        elif event.key == pygame.K_LEFT:
            if self.selection in self._toggle_indices:
                self._toggle(-1)
                self._save()
        elif event.key == pygame.K_RIGHT:
            if self.selection in self._toggle_indices:
                self._toggle(1)
                self._save()
        elif event.key == pygame.K_RETURN:
            if not self._is_disabled(self.selection):
                return self._on_select()
        elif event.key == pygame.K_ESCAPE:
            return self._on_back()
        return None

    # --- Rendering (template method) ---------------------------------

    def draw(self, screen: pygame.Surface, *, particles: ParticleSystem | None = None) -> None:
        screen.fill(BLACK)

        title = self.font.render(self._title, True, WHITE)
        screen.blit(title, (SCREEN_WIDTH // 2 - title.get_width() // 2, self._title_y))

        for i, option in enumerate(self._OPTIONS):
            is_sel = i == self.selection
            disabled = self._is_disabled(i)
            color = self._option_color(i, is_sel, disabled)
            text = self._option_text(i, is_sel)
            surf = self.font.render(text, True, color)
            screen.blit(
                surf,
                (SCREEN_WIDTH // 2 - surf.get_width() // 2,
                 self._options_y + i * self._item_spacing),
            )

        instr = self.font.render(self._instructions, True, GRAY)
        screen.blit(
            instr,
            (SCREEN_WIDTH // 2 - instr.get_width() // 2, SCREEN_HEIGHT - 50),
        )

    # --- Hooks (subclasses override) ---------------------------------

    def _value_label(self, i: int) -> str:
        return ""

    def _toggle(self, direction: int) -> None:
        pass

    def _on_select(self) -> State | None:
        return None

    def _is_disabled(self, i: int) -> bool:
        return False

    def _on_back(self) -> State | None:
        return None

    def _on_navigate(self) -> None:
        pass

    def _save(self) -> None:
        pass

    def _option_text(self, i: int, is_sel: bool) -> str:
        prefix = "> " if is_sel else "  "
        value = self._value_label(i)
        return f"{prefix}{self._OPTIONS[i]}" + (f" : {value}" if value else "")

    def _option_color(self, i: int, is_sel: bool, disabled: bool) -> tuple[int, int, int]:
        if disabled:
            return self._disabled_color
        return WHITE if is_sel else GRAY