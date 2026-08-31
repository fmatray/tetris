"""Audio sub-menu: sound volume, music volume, song, back."""

from __future__ import annotations

from tetris.i18n import tr
from tetris.settings import (
    MUSIC_SONG_LABELS,
    MUSIC_SONGS,
    VOLUME_LABELS,
)
from tetris.states.base import State
from tetris.states.menu_base import MenuBase


class AudioMenuState(MenuBase):
    """Audio sub-menu: sound volume, music volume, song selection, back."""

    _OPTIONS = ("Sound", "Music", "Song", "Back")
    _toggle_indices = frozenset({0, 1, 2})
    _title = "Audio"

    def __init__(self, screen, font, audio, menu) -> None:
        super().__init__(screen, font, audio)
        self.menu = menu

    # --- Hooks ----------------------------------------------------------

    def _value_label(self, i: int) -> str:
        match i:
            case 0:
                return tr(VOLUME_LABELS[self.menu.sound_volume])
            case 1:
                return tr(VOLUME_LABELS[self.menu.music_volume])
            case 2:
                return tr(MUSIC_SONG_LABELS[self.menu.music_song])
            case _:
                return ""

    def _toggle(self, direction: int) -> None:
        match self.selection:
            case 0:
                self.menu.sound_volume = (self.menu.sound_volume + direction) % 4
            case 1:
                self.menu.music_volume = (self.menu.music_volume + direction) % 4
            case 2:
                idx = MUSIC_SONGS.index(self.menu.music_song)
                self.menu.music_song = MUSIC_SONGS[(idx + direction) % len(MUSIC_SONGS)]

    def _save(self) -> None:
        self.menu.save_settings()

    def _on_back(self) -> State | None:
        return self.menu

    def _on_select(self) -> State | None:
        sel = self.selection
        if sel == 3:  # Back
            return self.menu
        self._toggle(1)
        self._save()
        return None
