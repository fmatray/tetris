"""Keybinding state: view and rebind human player controls.

Lists each action with its current key. Press ENTER to enter "listening"
mode for the selected action — the next key press rebinds it. Conflicts
are detected and rejected. Keybindings persist via the parent MenuState.
ESC returns to the human menu.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pygame

from tetris.settings import (
    BLACK,
    DEFAULT_KEYBINDS,
    GRAY,
    KEYBIND_LABELS,
    RED,
    SCREEN_WIDTH,
    WHITE,
)
from tetris.states.base import State
from tetris.visuals.fonts import (
    CONTENT_Y,
    INSTRUCTIONS_Y,
    LINE_HEIGHT_SMALL,
    TITLE_Y,
    get_large_font,
)


def key_name(key: int) -> str:
    """Human-readable name for a pygame key constant (French where ambiguous)."""
    _SPECIALS = {
        pygame.K_LEFT: "←",
        pygame.K_RIGHT: "→",
        pygame.K_UP: "↑",
        pygame.K_DOWN: "↓",
        pygame.K_SPACE: "Espace",
        pygame.K_RETURN: "Entrée",
        pygame.K_ESCAPE: "Échap",
        pygame.K_TAB: "Tab",
        pygame.K_BACKSPACE: "Retour",
        pygame.K_LSHIFT: "Maj G",
        pygame.K_RSHIFT: "Maj D",
        pygame.K_LCTRL: "Ctrl G",
        pygame.K_RCTRL: "Ctrl D",
        pygame.K_LALT: "Alt G",
        pygame.K_RALT: "Alt D",
    }
    if key in _SPECIALS:
        return _SPECIALS[key]
    name = pygame.key.name(key)
    if len(name) == 1:
        return name.upper()
    return name

if TYPE_CHECKING:
    from tetris.states.human_menu import HumanMenuState
    from tetris.visuals.particles import ParticleSystem

# Keys that cannot be rebound (reserved for navigation / quit).
_RESERVED = {pygame.K_UP, pygame.K_DOWN, pygame.K_LEFT, pygame.K_RIGHT,
             pygame.K_RETURN, pygame.K_ESCAPE}

# Action names in display order.
_ACTIONS = list(DEFAULT_KEYBINDS.keys())

# Total menu entries: actions + reset option.
_NUM_ENTRIES = len(_ACTIONS) + 1
_RESET_INDEX = len(_ACTIONS)


class KeybindState(State):
    """Interactive keybinding configuration.

    Up/Down selects an action. ENTER starts listening for a new key.
    The next non-reserved KEYDOWN rebinds the action. Conflicts (same
    key already used by another action) are rejected with a message.
    ESC returns to the human menu.
    """

    def __init__(self, screen, font, audio, human_menu: HumanMenuState) -> None:
        self.screen, self.font, self.audio = screen, font, audio
        self.human_menu = human_menu
        self.selection = 0
        self._listening = False
        self._conflict_msg = ""

    @property
    def menu(self):
        """Access the root MenuState through the human menu."""
        return self.human_menu.menu

    def _keybinds(self) -> dict[str, int]:
        return self.menu.keybinds

    def handle_event(self, event: pygame.event.Event) -> State | None:
        if event.type != pygame.KEYDOWN:
            return None

        if self._listening:
            return self._handle_listening(event)

        if event.key == pygame.K_UP:
            self.selection = (self.selection - 1) % _NUM_ENTRIES
            self._conflict_msg = ""
        elif event.key == pygame.K_DOWN:
            self.selection = (self.selection + 1) % _NUM_ENTRIES
            self._conflict_msg = ""
        elif event.key == pygame.K_RETURN:
            if self.selection == _RESET_INDEX:
                self._reset_defaults()
            else:
                self._listening = True
                self._conflict_msg = ""
        elif event.key == pygame.K_ESCAPE:
            return self.human_menu
        return None

    def _reset_defaults(self) -> None:
        """Reset all keybindings to their default values."""
        self.menu.keybinds = dict(DEFAULT_KEYBINDS)
        self.menu.save_settings()
        self._conflict_msg = ""

    def _handle_listening(self, event: pygame.event.Event) -> State | None:
        """Rebind the selected action to the pressed key."""
        if event.key == pygame.K_ESCAPE:
            # Cancel rebinding
            self._listening = False
            return None

        if event.key in _RESERVED:
            self._conflict_msg = "Touche réservée"
            self._listening = False
            return None

        action = _ACTIONS[self.selection]
        keybinds = self._keybinds()

        # Check for conflict: same key used by a different action
        for other_action, other_key in keybinds.items():
            if other_action != action and other_key == event.key:
                label = KEYBIND_LABELS[other_action]
                self._conflict_msg = f"Utilisé par: {label}"
                self._listening = False
                return None

        # Apply rebind
        keybinds[action] = event.key
        self.menu.save_settings()
        self._listening = False
        self._conflict_msg = ""
        return None

    # --- Rendering ------------------------------------------------------

    def draw(self, screen: pygame.Surface, *, particles: ParticleSystem | None = None) -> None:
        screen.fill(BLACK)

        title = get_large_font().render("Touches", True, WHITE)
        screen.blit(title, (SCREEN_WIDTH // 2 - title.get_width() // 2, TITLE_Y))

        keybinds = self._keybinds()
        y = CONTENT_Y
        for i, action in enumerate(_ACTIONS):
            is_sel = i == self.selection
            label = KEYBIND_LABELS[action]
            key_str = key_name(keybinds[action])

            if self._listening and is_sel:
                color = RED
                text = f"> {label} : ..."
            else:
                color = WHITE if is_sel else GRAY
                prefix = "> " if is_sel else "  "
                text = f"{prefix}{label} : {key_str}"

            surf = self.font.render(text, True, color)
            screen.blit(surf, (SCREEN_WIDTH // 2 - surf.get_width() // 2, y))
            y += LINE_HEIGHT_SMALL

        # Reset option
        is_reset_sel = self.selection == _RESET_INDEX
        reset_color = WHITE if is_reset_sel else GRAY
        reset_prefix = "> " if is_reset_sel else "  "
        reset_text = f"{reset_prefix}Réinitialiser"
        reset_surf = self.font.render(reset_text, True, reset_color)
        screen.blit(reset_surf, (SCREEN_WIDTH // 2 - reset_surf.get_width() // 2, y))

        # Conflict message
        if self._conflict_msg:
            msg = self.font.render(self._conflict_msg, True, RED)
            screen.blit(msg, (SCREEN_WIDTH // 2 - msg.get_width() // 2, y + LINE_HEIGHT_SMALL))

        # Instructions
        if self._listening:
            instr_text = "Appuyez sur une touche | Échap: Annuler"
        else:
            instr_text = "Entrée: Modifier | Échap: Retour"
        instr = self.font.render(instr_text, True, GRAY)
        screen.blit(
            instr,
            (SCREEN_WIDTH // 2 - instr.get_width() // 2, INSTRUCTIONS_Y),
        )