"""Procedural audio: NumPy-generated SFX + MIDI-based polyphonic music."""

from typing import NamedTuple
import mido
import numpy as np
import pygame

from tetris.audio.midi_gen import ensure_midi_files
from tetris.logger import get_logger
from tetris.settings import (
    MUSIC_SONG_PATHS,
    VOLUME_LEVELS,
)


class MidiNote(NamedTuple):
    """A parsed MIDI note: start time, duration, MIDI note number."""

    start: float
    duration: float
    note: int


class AudioManager:
    """Generates SFX and plays polyphonic music from MIDI files.

    SFX play on a dedicated channel (1); music loops on channel 0.
    Volume is a 0–3 index into ``VOLUME_LEVELS``.
    """

    _SAMPLE_RATE = 44100

    def __init__(
        self,
        sound_volume: int = 3,
        music_volume: int = 3,
        song: str = "korobeiniki",
    ) -> None:
        self.sound_volume = sound_volume
        self.music_volume = music_volume
        self.song = song
        self.muted = False
        self._music_speed = 1.0
        self._music_start_tick = 0  # pygame.time.get_ticks() when music started
        self._music_pos_sec = 0.0  # position within the song when speed changes
        self.sounds: dict[str, pygame.mixer.Sound] = {}
        pygame.mixer.set_reserved(3)
        self._music_channel = pygame.mixer.Channel(0)
        self._sfx_channel = pygame.mixer.Channel(1)
        self._xfade_channel = pygame.mixer.Channel(2)  # crossfade target
        self._music_buffer: np.ndarray | None = None  # raw float64 buffer at 1.0x
        self._music_duration: float = 0.0  # total duration at 1.0x speed
        self._music_sound: pygame.mixer.Sound | None = None
        ensure_midi_files()
        self._init_sounds()
        self._generate_music()

    def _init_sounds(self) -> None:
        # Line clears — one melody per clear count (1-4)
        self.sounds["clear_1"] = self.generate_melody([(261.63, 0.08), (392.00, 0.08), (523.25, 0.2)])
        self.sounds["clear_2"] = self.generate_melody(
            [
                (261.63, 0.06),
                (392.00, 0.06),
                (261.63, 0.06),
                (392.00, 0.06),
                (523.25, 0.2),
            ]
        )
        self.sounds["clear_3"] = self.generate_melody(
            [
                (261.63, 0.06),
                (329.63, 0.06),
                (392.00, 0.06),
                (493.88, 0.06),
                (523.25, 0.3),
            ]
        )
        self.sounds["clear_4"] = self.generate_melody([(261.63, 0.05), (523.25, 0.05), (783.99, 0.05), (1046.50, 0.4)])
        # Rotations
        self.sounds["rotate_cw"] = self.generate_melody([(440.0, 0.05), (659.25, 0.05)])
        self.sounds["rotate_ccw"] = self.generate_melody([(659.25, 0.05), (440.0, 0.05)])
        # Game state
        self.sounds["game_over"] = self.generate_melody([(261.63, 0.2), (196.00, 0.2), (130.81, 0.5)])
        self.sounds["glitch"] = self.generate_melody([(880.0, 0.01), (1760.0, 0.01)])
        # Piece events
        self.sounds["spawn"] = self.generate_melody([(880.0, 0.03)])
        self.sounds["soft_drop"] = self.generate_melody([(220.0, 0.02)])
        self.sounds["hard_drop"] = self.generate_melody([(150.0, 0.05), (100.0, 0.1)])
        self.sounds["level_up"] = self.generate_melody([(523.25, 0.08), (659.25, 0.08), (783.99, 0.08), (1046.50, 0.2)])

    # --- MIDI parsing ---------------------------------------------------

    @staticmethod
    def _parse_midi(path: str) -> list[MidiNote]:
        """Parse a MIDI file into a list of (start_sec, duration_sec, note).

        Handles tempo changes mid-file. Overlapping notes are preserved
        for polyphony. Returns notes sorted by start time.
        """
        mid = mido.MidiFile(path)
        notes: list[MidiNote] = []
        # Iterate merged tracks — mido yields events in chronological order
        # across all tracks, with correct delta times including tempo changes.
        abs_sec = 0.0
        active: dict[int, float] = {}
        for msg in mid:
            abs_sec += msg.time
            if msg.type == "note_on" and msg.velocity > 0:
                active[msg.note] = abs_sec
            elif msg.type == "note_off" or (msg.type == "note_on" and msg.velocity == 0):
                start = active.pop(msg.note, None)
                if start is not None:
                    notes.append(MidiNote(start, abs_sec - start, msg.note))
        notes.sort(key=lambda n: n[0])
        return notes

    @staticmethod
    def _apply_envelope(n: int, attack_max: int, release_max: int) -> np.ndarray:
        envelope = np.ones(n)
        attack = min(attack_max, n)
        release = min(release_max, n)
        if attack > 0:
            envelope[:attack] = np.linspace(0, 1, attack)
        if release > 0:
            envelope[-release:] = np.linspace(1, 0, release)
        return envelope

    def _generate_music(self) -> None:
        """Synthesize the raw music buffer at 1.0x speed from the MIDI file."""
        path = MUSIC_SONG_PATHS.get(self.song)
        if path is None:
            return
        notes = self._parse_midi(path)
        if not notes:
            return
        self._music_duration = max(n.start + n.duration for n in notes)
        total_samples = int(self._SAMPLE_RATE * self._music_duration)
        if total_samples <= 0:
            return
        buffer = np.zeros(total_samples, dtype=np.float64)
        for start, duration, note_num in notes:
            freq = 440.0 * 2 ** ((note_num - 69) / 12)
            s0 = int(start * self._SAMPLE_RATE)
            s1 = min(int((start + duration) * self._SAMPLE_RATE), total_samples)
            n = s1 - s0
            if n <= 0:
                continue
            t = np.arange(n) / self._SAMPLE_RATE
            envelope = self._apply_envelope(n, 200, 200)
            buffer[s0:s1] += np.sin(2 * np.pi * freq * t) * envelope
        # Normalize to prevent clipping with polyphony
        peak = np.max(np.abs(buffer))
        if peak > 1.0:
            buffer /= peak
        self._music_buffer = buffer
        self._build_music_sound()

    def _build_music_sound(self, from_pos: float = 0.0, fade_in_ms: int = 0) -> None:
        """Build a full-length looping Sound at current speed from the raw buffer.

        Resamples the entire 1.0x buffer by ``_music_speed`` (compressing time),
        then rolls it so ``from_pos`` maps to index 0. This produces a
        seamless infinite loop at the new tempo starting from the same
        musical position — no slice, no truncated loop, no restart.
        """
        if self._music_buffer is None:
            return
        n_orig = len(self._music_buffer)
        if n_orig == 0:
            return
        # Resample the entire buffer at the new speed
        n_new = int(n_orig / self._music_speed)
        old_idx = np.linspace(0, n_orig - 1, n_orig)
        new_idx = np.linspace(0, n_orig - 1, n_new)
        resampled = np.interp(new_idx, old_idx, self._music_buffer)
        # Roll so the current position maps to index 0 for seamless start
        roll_amount = int(from_pos * self._SAMPLE_RATE / self._music_speed) % n_new
        resampled = np.roll(resampled, -roll_amount)
        # Optional fade-in for crossfade transitions
        if fade_in_ms > 0:
            fade_samples = min(int(self._SAMPLE_RATE * fade_in_ms / 1000), n_new)
            if fade_samples > 0:
                resampled[:fade_samples] *= np.linspace(0, 1, fade_samples)
        wave = (32767 * resampled).astype(np.int16)
        stereo = np.column_stack([wave, wave])
        try:
            self._music_sound = pygame.sndarray.make_sound(stereo)
        except (ValueError, pygame.error) as e:
            get_logger("audio").error("Music synthesis error: %s", e)
            self._music_sound = pygame.mixer.Sound(buffer=np.zeros((self._SAMPLE_RATE, 2), dtype=np.int16))

    # --- SFX synthesis --------------------------------------------------

    def generate_melody(self, notes: list[tuple[float, float]]) -> pygame.mixer.Sound:
        """Synthesize a sequence of ``(freq, duration)`` notes into a Sound."""
        try:
            buffers = []
            for freq, duration in notes:
                n = int(self._SAMPLE_RATE * duration)
                t = np.arange(n) / self._SAMPLE_RATE
                envelope = self._apply_envelope(n, 100, 100)
                wave = 32767 * np.sin(2 * np.pi * freq * t) * envelope
                buf = np.column_stack([wave, wave]).astype(np.int16)
                buffers.append(buf)
            combined = np.concatenate(buffers, axis=0)
            return pygame.sndarray.make_sound(combined)
        except (ValueError, pygame.error) as e:
            get_logger("audio").error("Audio error: %s", e)
            return pygame.mixer.Sound(buffer=np.zeros((self._SAMPLE_RATE, 2), dtype=np.int16))

    # --- Playback -------------------------------------------------------

    def play(self, key: str) -> bool:
        """Play a SFX on the dedicated channel. Returns True if played."""
        if self.muted or self.sound_volume == 0:
            return False
        if key not in self.sounds:
            return False
        if self._sfx_channel.get_busy():
            return False
        self._sfx_channel.set_volume(VOLUME_LEVELS[self.sound_volume])
        self._sfx_channel.play(self.sounds[key])
        return True

    def _get_music_pos(self) -> float:
        """Return the current position in the song (at 1.0x speed), in seconds."""
        if not self._music_channel.get_busy() or self._music_duration <= 0:
            return 0.0
        elapsed_ms = pygame.time.get_ticks() - self._music_start_tick
        elapsed_sec = elapsed_ms / 1000.0
        # Position in the scaled timeline, wrapped to song length
        scaled_duration = self._music_duration / self._music_speed
        pos_in_scaled = elapsed_sec % scaled_duration
        # Convert back to 1.0x position
        return pos_in_scaled * self._music_speed

    def start_music(self) -> None:
        if self.muted or self.music_volume == 0 or self._music_sound is None:
            return
        self._music_channel.set_volume(VOLUME_LEVELS[self.music_volume])
        self._music_channel.play(self._music_sound, loops=-1)
        self._music_start_tick = pygame.time.get_ticks()

    def stop_music(self) -> None:
        self._music_channel.stop()
        self._xfade_channel.stop()

    def set_music_speed(self, speed: float) -> None:
        if speed == self._music_speed:
            return
        was_playing = self._music_channel.get_busy()
        if was_playing:
            pos = self._get_music_pos()
        else:
            pos = 0.0
        self._music_speed = speed
        self._build_music_sound(from_pos=pos, fade_in_ms=500)
        if not was_playing or self.muted or self.music_volume == 0:
            return
        # Crossfade: new buffer fades in over 500ms while old fades out
        vol = VOLUME_LEVELS[self.music_volume]
        self._xfade_channel.set_volume(vol)
        assert self._music_sound is not None  # set by _build_music_sound above
        self._xfade_channel.play(self._music_sound, loops=-1)
        self._music_channel.fadeout(500)
        # Swap channels: xfade becomes the main music channel
        self._music_channel, self._xfade_channel = (self._xfade_channel, self._music_channel)
        self._music_start_tick = pygame.time.get_ticks()

    def toggle_mute(self) -> None:
        self.muted = not self.muted
        if self.muted:
            self.stop_music()
        else:
            self.start_music()

    def apply_settings(self, sound_volume: int, music_volume: int, song: str) -> None:
        self.sound_volume = sound_volume
        self.music_volume = music_volume
        self.muted = False
        self.stop_music()
        self._music_speed = 1.0
        self.song = song
        self._generate_music()
        self.start_music()
