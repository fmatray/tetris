"""Procedural audio: NumPy-generated sounds, no external files."""

import numpy as np
import pygame


class AudioManager:
    """Generates and plays short procedural sounds.

    All sounds are synthesized from sine waves with attack/release
    envelopes via NumPy. Toggling ``enabled`` mutes playback without
    destroying the generated buffers.
    """

    _SAMPLE_RATE = 44100

    def __init__(self, enabled: bool = True) -> None:
        self.enabled = enabled
        self.sounds: dict[str, pygame.mixer.Sound] = {}
        self._init_sounds()

    def _init_sounds(self) -> None:
        # Line clears — one melody per clear count (1-4)
        self.sounds["clear_1"] = self.generate_melody(
            [(261.63, 0.08), (392.00, 0.08), (523.25, 0.2)]
        )
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
        self.sounds["clear_4"] = self.generate_melody(
            [(261.63, 0.05), (523.25, 0.05), (783.99, 0.05), (1046.50, 0.4)]
        )
        # Rotations
        self.sounds["rotate_cw"] = self.generate_melody([(440.0, 0.05), (659.25, 0.05)])
        self.sounds["rotate_ccw"] = self.generate_melody(
            [(659.25, 0.05), (440.0, 0.05)]
        )
        # Game state
        self.sounds["game_over"] = self.generate_melody(
            [(261.63, 0.2), (196.00, 0.2), (130.81, 0.5)]
        )
        self.sounds["glitch"] = self.generate_melody([(880.0, 0.01), (1760.0, 0.01)])
        self.sounds["lock"] = self.generate_melody([(600.0, 0.05), (400.0, 0.05)])

    def generate_melody(self, notes: list[tuple[float, float]]) -> pygame.mixer.Sound:
        """Synthesize a sequence of ``(freq, duration)`` notes into a Sound."""
        full_buf = []
        try:
            for freq, duration in notes:
                n_samples = int(self._SAMPLE_RATE * duration)
                buf = np.zeros((n_samples, 2), dtype=np.int16)
                for i in range(n_samples):
                    envelope = 1.0
                    if i < 100:
                        envelope = i / 100
                    if i > n_samples - 100:
                        envelope = (n_samples - i) / 100
                    val = int(
                        32767 * np.sin(2 * np.pi * freq * i / self._SAMPLE_RATE)
                        * envelope
                    )
                    buf[i][0] = buf[i][1] = val
                full_buf.append(buf)
            combined_buf = np.concatenate(full_buf, axis=0)
            return pygame.sndarray.make_sound(combined_buf)
        except Exception as e:
            print(f"Audio error: {e}")
            return pygame.mixer.Sound(
                buffer=np.zeros((self._SAMPLE_RATE, 2), dtype=np.int16)
            )

    def play(self, key: str) -> None:
        if self.enabled and key in self.sounds and not pygame.mixer.get_busy():
            self.sounds[key].play()