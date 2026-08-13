"""Audio sub-menu: sound volume, music volume, song, back."""

from __future__ import annotations

from tetris.settings import (
    MUSIC_SONG_LABELS,
    MUSIC_SONGS,
    MUSIC_VOLUME_LABELS,
    SOUND_VOLUME_LABELS,
)
from tetris.states.base import State
from tetris.states.menu_base import MenuBase


class AudioMenuState(MenuBase):
    """Audio sub-menu: sound volume, music volume, song selection, back."""

    _OPTIONS = ("Son", "Musique", "Morceau", "Retour")
    _toggle_indices = frozenset({0, 1, 2})
    _title = "Audio"

    def __init__(self, screen, font, audio, menu) -> None:
        super().__init__(screen, font, audio)
        self.menu = menu

    # --- Hooks ----------------------------------------------------------

    def _value_label(self, i: int) -> str:
        if i == 0:
            return SOUND_VOLUME_LABELS[self.menu.sound_volume]
        if i == 1:
            return MUSIC_VOLUME_LABELS[self.menu.music_volume]
        if i == 2:
            return MUSIC_SONG_LABELS[self.menu.music_song]
        return ""

    def _toggle(self, direction: int) -> None:
        if self.selection == 0:
            self.menu.sound_volume = (self.menu.sound_volume + direction) % 4
        elif self.selection == 1:
            self.menu.music_volume = (self.menu.music_volume + direction) % 4
        elif self.selection == 2:
            idx = MUSIC_SONGS.index(self.menu.music_song)
            self.menu.music_song = MUSIC_SONGS[(idx + direction) % len(MUSIC_SONGS)]

    def _save(self) -> None:
        self.menu.save_settings()

    def _on_back(self) -> State | None:
        return self.menu

    def _on_select(self) -> State | None:
        sel = self.selection
        if sel == 3:  # Retour
            return self.menu
        self._toggle(1)
        self._save()
        return None