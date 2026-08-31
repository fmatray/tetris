"""Base class for menu states with shared navigation and rendering."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pygame

from tetris.settings import BLACK, GRAY, SCREEN_WIDTH, WHITE
from tetris.i18n import tr
from tetris.states.base import State
from tetris.visuals.fonts import (
    CONTENT_Y,
    INSTRUCTIONS_Y,
    LINE_HEIGHT_SMALL,
    TITLE_Y,
    get_large_font,
)
from tetris.visuals.menu_animation import MenuBackgroundAnimation

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
    """

    _OPTIONS: tuple[str, ...] = ()
    _title: str = ""
    _toggle_indices: frozenset[int] = frozenset()
    _title_y: int = TITLE_Y
    _options_y: int = CONTENT_Y
    _item_spacing: int = LINE_HEIGHT_SMALL
    _instructions: str = "Arrows: Navigate | Enter: Select | Esc: Back"
    _disabled_color: tuple[int, int, int] = (64, 64, 64)

    def __init__(self, screen, font, audio) -> None:
        """Initialize the menu with a fresh background animation instance.

        Each menu state owns its own :class:`MenuBackgroundAnimation`;
        the animation resets on every menu transition.

        Args:
            screen: Pygame display surface.
            font: Font for menu option text.
            audio: Audio manager for navigation sounds.
        """
        self.screen, self.font, self.audio = screen, font, audio
        self.selection = 0
        self.bg_anim = MenuBackgroundAnimation()

    # --- Update: drive background animation ---------------------------

    def update(self, dt: float, particles: ParticleSystem) -> State | None:
        """Drive the background animation; never transitions state.

        Args:
            dt: Milliseconds since last frame (from ``clock.tick(60)``);
                converted to seconds for the animation.
            particles: Shared particle system for explosion bursts.

        Returns:
            Always ``None`` — menus stay until user navigates away.
        """
        self.bg_anim.update(dt / 1000.0, particles)
        return None

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
        """Template-method event handler for menu navigation.

        Dispatches arrow keys (up/down navigate, left/right toggle),
        Enter (select), and Escape (back) to subclass hooks.

        Returns a new :class:`State` on transition, or ``None`` to stay.
        """
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

    def draw(self, screen: pygame.Surface, *, particles: ParticleSystem | None = None) -> None:
        """Render the menu: background animation, particles, title, options.

        Draw order (back to front): black fill → falling tetrominos →
        explosion particles → title → option rows → instructions.  This
        keeps the UI text readable above the animation.

        Args:
            screen: Target surface to draw onto.
            particles: Shared particle system; if provided, its particles
                are drawn between the animation and the UI text.
        """
        screen.fill(BLACK)
        self.bg_anim.draw(screen)
        if particles is not None:
            particles.draw(screen)

        title = get_large_font().render(tr(self._title), True, WHITE)
        screen.blit(title, (SCREEN_WIDTH // 2 - title.get_width() // 2, self._title_y))

        for i, option in enumerate(self._OPTIONS):
            is_sel = i == self.selection
            disabled = self._is_disabled(i)
            color = self._option_color(i, is_sel, disabled)
            text = self._option_text(i, is_sel)
            surf = self.font.render(text, True, color)
            screen.blit(
                surf,
                (SCREEN_WIDTH // 2 - surf.get_width() // 2, self._options_y + i * self._item_spacing),
            )

        instr = self.font.render(tr(self._instructions), True, GRAY)
        screen.blit(
            instr,
            (SCREEN_WIDTH // 2 - instr.get_width() // 2, INSTRUCTIONS_Y),
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
        value = tr(self._value_label(i))
        return f"{prefix}{tr(self._OPTIONS[i])}" + (f" : {value}" if value else "")

    def _option_color(self, i: int, is_sel: bool, disabled: bool) -> tuple[int, int, int]:
        if disabled:
            return self._disabled_color
        return WHITE if is_sel else GRAY
