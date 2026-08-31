# Music and Sound

## Overview

The audio system provides **procedural SFX** (NumPy synthesis) and **polyphonic MIDI-based music**. All audio is generated at runtime — no external audio files required except MIDI files for music (auto-generated on first run).

---

## Architecture

```
AudioManager (singleton per game session)
├── SFX Channel (dedicated pygame.mixer.Channel)
│   ├── generate_melody() — sequence of (freq, duration) → Sound
│   └── Pre-generated: move, rotate, lock, clear_1..4, level_up, game_over, hold
├── Music Channel (dedicated pygame.mixer.Channel)
│   ├── _parse_midi() — MIDI file → list of MidiNote (start, duration, note)
│   ├── _generate_music() — raw buffer synthesis at 1.0x speed
│   ├── _build_music_sound() — slice buffer at current speed → looping Sound
│   └── Crossfade on speed change
└── Settings
    ├── sound_volume: 0-3 (Off/Bas/Moyen/Max)
    ├── music_volume: 0-3
    ├── music_song: "korobeiniki" / "kalinka"
    └── mute: boolean
```

**Key Constants** (from `tetris/settings.py`):
- `_SAMPLE_RATE = 44100` Hz
- `VOLUME_LEVELS = [0.0, 0.25, 0.5, 1.0]`
- `MUSIC_BASE_SPEED = 1.0`, `MUSIC_SPEED_PER_LEVEL = 0.05`, `MUSIC_MAX_SPEED = 2.0`

---

## SFX (Sound Effects)

### Generation

All SFX are synthesized via `AudioManager.generate_melody(notes: list[(freq, duration)])`:

```python
def generate_melody(self, notes):
    # For each (freq, duration):
    #   t = np.linspace(0, duration, n_samples)
    #   wave = sin(2π × freq × t) × envelope
    #   envelope = attack (0→1) + sustain + release (1→0)
    # Mix all notes sequentially → stereo int16 buffer → pygame.mixer.Sound
```

### Pre-defined SFX

| Key | Melody | Trigger |
|-----|--------|---------|
| `move` | C4 (0.04s) | Left/Right move |
| `rotate` | E4 (0.04s) | Rotate CW/CCW |
| `lock` | G4 (0.06s) | Piece locks |
| `clear_1` | C4-E4-G4 (0.36s) | 1 line clear |
| `clear_2` | C4-E4-G4-C5 (0.44s) | 2 lines |
| `clear_3` | C4-E4-G4-C5-E5 (0.52s) | 3 lines |
| `clear_4` | C4-E4-G4-C5-E5-G5 (0.6s) | 4 lines (Tetris) |
| `level_up` | C5-E5-G5-C6 (0.44s) | Level up |
| `game_over` | Descending C5→C4 (0.8s) | Top-out |
| `hold` | A4 (0.06s) | Hold piece swap |

### Playback

```python
def play(self, key: str) -> bool:
    if self.muted or self.sound_volume == 0: return False
    sound = self.sounds[key]
    sound.set_volume(VOLUME_LEVELS[self.sound_volume])
    self._sfx_channel.play(sound)
    return True
```

- Dedicated channel (`_sfx_channel`) — SFX never interrupt music
- Volume applied per-play (respects runtime volume changes)
- Returns `False` if muted or volume=0

---

## Music

### MIDI Files

Two songs included, auto-generated on first run:

| Song | File | Tempo | Tracks |
|------|------|-------|--------|
| Korobeiniki | `media/korobeiniki.mid` | 120 BPM | Melody (ch 0) + Bass (ch 1) |
| Kalinka | `media/kalinka.mid` | 132 BPM | Melody (ch 0) + Bass (ch 1) |

**Generation** (`tetris/audio/midi_gen.py`):
- `ensure_midi_files()` called at `AudioManager.__init__`
- Builds MIDI tracks from note data: `(note_name, octave, beats, channel)`
- `note_name="R"` = rest
- Duration: 1 = quarter, 0.5 = eighth, 0.25 = sixteenth
- Saves standard MIDI format 1 (multi-track)

### Synthesis Pipeline

```
MIDI file (.mid)
    │
    ▼
_parse_midi() → list[MidiNote(start_sec, duration_sec, note_num)]
    │
    ▼
_generate_music() at 1.0x speed
    │
    ├─ Allocate buffer: (duration × SAMPLE_RATE, 2) int16
    │
    ├─ For each note:
    │   freq = 440 × 2^((note-69)/12)
    │   t = np.arange(n_samples) / SAMPLE_RATE
    │   wave = sin(2π × freq × t) × envelope
    │   buffer[start:end] += wave (mix all tracks)
    │
    ▼
_raw_music_buffer (stored at 1.0x speed)
```

### Speed Adaptation

Music speed increases with level: `speed = 1.0 + level × 0.05`, capped at 2.0×.

**Implementation** — buffer slicing, not re-synthesis:
```python
def _build_music_sound(self, from_pos=0.0, fade_in_ms=0):
    # Calculate scaled duration: raw_duration / speed
    # Slice _raw_music_buffer at scaled positions
    # Apply fade-in/out to prevent clicks
    # Create pygame.mixer.Sound from sliced buffer
    # This is fast — no re-synthesis needed
```

**On speed change** (`set_music_speed()`):
1. Capture current playback position (at 1.0x reference)
2. Rebuild sound at new speed from that position
3. Crossfade: old sound fades out (100ms), new fades in (100ms)
4. Seamless transition — no audio glitch

### Playback Control

```python
def start_music(self):
    if muted or volume=0 or no sound: return
    _music_channel.play(_music_sound, loops=-1)
    _music_start_tick = pygame.time.get_ticks()

def stop_music(self):
    _music_channel.stop()
    _xfade_channel.stop()

def set_music_speed(self, speed):
    if speed == current: return
    _music_speed = clamp(speed, 1.0, 2.0)
    pos_1x = _get_music_pos()  # current position at 1.0x reference
    _build_music_sound(from_pos=pos_1x, fade_in_ms=100)
    # crossfade handled in _build_music_sound
```

### Level Speed Integration

In `GameState.update()`:
```python
if self.stats.level != self._last_level:
    self.audio.set_music_speed(1.0 + self.stats.level * 0.05)
```

---

## Audio Menu

**Menu Path:** Main → **Audio**

### AudioMenuState (`tetris/states/audio_menu.py`)

Options:
| Index | Option | Values | Toggle |
|-------|--------|--------|--------|
| 0 | Son (Sound) | Off / Bas / Moyen / Max | ✓ |
| 1 | Musique (Music) | Off / Bas / Moyen / Max | ✓ |
| 2 | Morceau (Song) | Korobeiniki / Kalinka | ✓ |
| 3 | Retour | — | — |

**Behavior:**
- Left/Right: cycle values (wraps)
- Changes applied immediately via `menu.save_settings()` → `AudioManager.apply_settings()`
- Song change: re-generates music buffer, restarts playback

---

## Settings Persistence

Stored in `data/settings.json`:
```json
{
  "sound": 2,
  "music": 2,
  "song": "korobeiniki"
}
```

- `sound_volume` / `music_volume`: int 0-3 (index into `VOLUME_LEVELS`)
- `music_song`: "korobeiniki" or "kalinka"
- Loaded by `MenuState._load_settings()`, applied on `AudioManager` creation

---

## Mute Toggle

- **Key**: `M` (default, configurable in keybinds)
- **Action**: `AudioManager.toggle_mute()` — flips `self.muted`
- If unmuted and music was playing: `start_music()` resumes
- If muted: `stop_music()` stops both channels

---

## Code Locations

| File | Purpose |
|------|---------|
| `tetris/audio/__init__.py` | AudioManager — SFX synthesis, MIDI parsing, music synthesis, playback |
| `tetris/audio/midi_gen.py` | MIDI file generation (Korobeiniki, Kalinka) |
| `tetris/states/audio_menu.py` | AudioMenuState — volume/song configuration |
| `tetris/settings.py` | VOLUME_LEVELS, MUSIC_SONGS, MUSIC_SONG_PATHS, speed constants |
| `tetris/states/game.py` | GameState.update() — level speed integration |

---

## Technical Details

### Envelope

```python
def _apply_envelope(n, attack_max, release_max):
    envelope = np.ones(n)
    attack = min(attack_max, n // 3)
    release = min(release_max, n // 3)
    envelope[:attack] = np.linspace(0, 1, attack)      # fade in
    envelope[-release:] = np.linspace(1, 0, release)   # fade out
    return envelope
```
- Applied to each note in SFX and music synthesis
- Prevents clicks at note boundaries

### MIDI Note Parsing

```python
@staticmethod
def _parse_midi(path) -> list[MidiNote]:
    mid = mido.MidiFile(path)
    ticks_per_beat = mid.ticks_per_beat
    # Track tempo changes (set_tempo meta messages)
    # Accumulate absolute time in seconds per tick
    # Note-on → note-off pairing (same note, same channel)
    # Returns: (start_sec, duration_sec, note_number)
```
- Handles tempo changes mid-song
- Supports multiple tracks (melody + bass on different channels)
- Ignores note-off without matching note-on

### Buffer Management

- `_raw_music_buffer`: Full song at 1.0x speed, stereo int16, stored as `np.ndarray`
- `_music_sound`: Current `pygame.mixer.Sound` at active speed (rebuilt on speed change)
- `_music_channel`: Dedicated playback channel (loops=-1)
- `_xfade_channel`: Crossfade channel for speed transitions
- Memory: ~song_duration × 44100 × 2 × 2 bytes ≈ few MB per song

### Crossfade Implementation

```python
def _build_music_sound(self, from_pos=0.0, fade_in_ms=0):
    # ... slice buffer at new speed ...
    if self._music_sound is not None and fade_in_ms > 0:
        # Old sound on _xfade_channel, fade out
        self._xfade_channel.play(self._music_sound)
        self._xfade_channel.set_volume(0)
        # Fade out over fade_in_ms
        # New sound on _music_channel, fade in
    self._music_sound = new_sound
    self._music_channel.play(new_sound, loops=-1)
```

---

## Extending Audio

### Adding a New SFX

```python
# In AudioManager._init_sounds():
self.sounds["my_sfx"] = self.generate_melody([
    (440.0, 0.1),   # A4 for 100ms
    (554.37, 0.1),  # C#5 for 100ms
    (659.25, 0.2),  # E5 for 200ms
])

# Trigger:
self.audio.play("my_sfx")
```

### Adding a New Song

1. Add note data to `midi_gen.py`:
```python
_MY_SONG = {
    "tempo": 120,
    "tracks": {
        0: [("C", 4, 1, 0), ("E", 4, 0.5, 0), ...],  # melody
        1: [("C", 2, 2, 1), ("G", 2, 2, 1), ...],    # bass
    }
}
_SONGS["my_song"] = _MY_SONG
```

2. Add to `MUSIC_SONGS` and `MUSIC_SONG_LABELS` in `settings.py`

3. Run `python -m tetris.audio.midi_gen` to generate `.mid` file

---

## Testing

```bash
# Test SFX generation (headless)
SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy python3 -c "
from tetris.audio import AudioManager
audio = AudioManager(sound_volume=3, music_volume=0)
audio.play('clear_4')
import time; time.sleep(1)
"

# Test music synthesis
SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy python3 -c "
from tetris.audio import AudioManager
audio = AudioManager(sound_volume=0, music_volume=3, music_song='korobeiniki')
audio.start_music()
import time; time.sleep(5)
audio.set_music_speed(1.5)  # test speed change
time.sleep(5)
audio.stop_music()
"

# Regenerate MIDI files
python -m tetris.audio.midi_gen
```