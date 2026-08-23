"""MCP sub-menu: port selection."""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from tetris.states.base import State
from tetris.states.menu_base import MenuBase

if TYPE_CHECKING:
    from tetris.states.menu import MenuState


class MCPMenuState(MenuBase):
    """MCP sub-menu: port configuration and back."""

    _OPTIONS = ("Port", "Retour")
    _toggle_indices = frozenset({0})  # only Port toggles
    _title = "MCP"
    _instructions = "← →: Changer    Entrée: Valider    Échap: Retour"

    _PORTS: ClassVar[list[int]] = [8765, 8766, 8767, 8768]

    def __init__(self, screen, font, audio, menu: MenuState) -> None:
        super().__init__(screen, font, audio)
        self.menu = menu
        self.mcp_port = getattr(menu, "mcp_port", 8765)

    def _value_label(self, i: int) -> str:
        if i == 0:
            return str(self.mcp_port)
        return ""

    def _toggle(self, direction: int) -> None:
        if self.selection == 0:
            idx = self._PORTS.index(self.mcp_port) if self.mcp_port in self._PORTS else 0
            idx = (idx + direction) % len(self._PORTS)
            self.mcp_port = self._PORTS[idx]
            self.menu.mcp_port = self.mcp_port

    def _save(self) -> None:
        self.menu.save_settings()

    def _on_back(self) -> State | None:
        self.menu.mcp_port = self.mcp_port
        self.menu.save_settings()
        return self.menu

    def _on_select(self) -> State | None:
        match self.selection:
            case 0:  # Port — toggle only
                return None
            case 1:  # Retour
                return self._on_back()
        return None
