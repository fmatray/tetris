"""Seed entry state: numeric text input for the human game seed.

Displays a prompt with the current seed value. Digits append, BACKSPACE
deletes, ENTER confirms (empty = random/None), ESC cancels.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pygame

from tetris.i18n import tr
from tetris.settings import BLACK, GRAY, SCREEN_WIDTH, WHITE
from tetris.states.base import State
from tetris.visuals.fonts import LINE_HEIGHT_SMALL, get_large_font, get_small_font

if TYPE_CHECKING:
    from tetris.states.menu import MenuState
    from tetris.visuals.particles import ParticleSystem

_PROMPT = "Seed"
_HINT = "Digits: type | Backspace: delete | Enter: confirm | Esc: cancel"
_EMPTY_LABEL = "Random"


class SeedEntryState(State):
    """Numeric text input for a game seed.

    Empty string maps to ``None`` (random). The seed is stored on the
    parent :class:`MenuState` and persisted via ``save_settings``.
    """

    def __init__(self, screen, font, audio, menu: MenuState) -> None:
        self.screen, self.font, self.audio = screen, font, audio
        self.menu = menu
        self.text = str(menu.seed) if menu.seed is not None else ""

    def handle_event(self, event: pygame.event.Event) -> State | None:
        if event.type != pygame.KEYDOWN:
            return None
        if event.key == pygame.K_RETURN:
            self.menu.seed = int(self.text) if self.text.strip() else None
            self.menu.save_settings()
            return self.menu
        if event.key == pygame.K_ESCAPE:
            return self.menu
        if event.key == pygame.K_BACKSPACE:
            self.text = self.text[:-1]
        elif event.unicode.isdigit() and len(self.text) < 10:
            self.text += event.unicode
        return None

    def update(self, dt: float, particles: ParticleSystem) -> State | None:
        return None

    def draw(self, screen: pygame.Surface, *, particles: ParticleSystem | None = None) -> None:
        screen.fill(BLACK)
        large = get_large_font()
        small = get_small_font()

        title = large.render(tr(_PROMPT), True, WHITE)
        screen.blit(title, ((SCREEN_WIDTH - title.get_width()) // 2, 200))

        display = self.text if self.text else tr(_EMPTY_LABEL)
        color = WHITE if self.text else GRAY
        value = large.render(display, True, color)
        screen.blit(value, ((SCREEN_WIDTH - value.get_width()) // 2, 280))

        hint = small.render(tr(_HINT), True, GRAY)
        screen.blit(hint, ((SCREEN_WIDTH - hint.get_width()) // 2, 280 + LINE_HEIGHT_SMALL * 2))
