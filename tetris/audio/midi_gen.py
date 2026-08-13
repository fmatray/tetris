"""Generate MIDI files for game music (Korobeiniki, Kalinka).

Run standalone:  python -m tetris.audio.midi_gen
At import time:   ensure_midi_files() creates missing files in data/midi/.
"""

from __future__ import annotations

import os

import mido

from tetris.settings import MUSIC_MIDI_DIR, MUSIC_SONG_PATHS, ensure_data_dir

# --- Note helpers -------------------------------------------------------
# MIDI note numbers: C-1=0, A4=69 (440 Hz). We build from note names.

_NOTE_OFFSETS = {"C": 0, "C#": 1, "D": 2, "D#": 3, "E": 4, "F": 5,
                 "F#": 6, "G": 7, "G#": 8, "A": 9, "A#": 10, "B": 11}


def _note(name: str, octave: int) -> int:
    """Convert note name + octave to MIDI note number."""
    return _NOTE_OFFSETS[name] + (octave + 1) * 12


# --- Song definitions --------------------------------------------------
# Each track: list of (note_name, octave, duration_in_beats, channel).
# note_name="R" means rest (silence).
# Duration in beats; 1 = quarter note, 0.5 = eighth, 0.25 = sixteenth.

_KOROBEINIKI_TEMPO = 120  # BPM
_KOROBEINIKI = {
    "tempo": _KOROBEINIKI_TEMPO,
    "tracks": [
        # Melody (channel 0)
        [
            ("E", 5, 1.0, 0), ("B", 4, 0.5, 0), ("C", 5, 0.5, 0), ("D", 5, 1.0, 0),
            ("C", 5, 0.5, 0), ("B", 4, 0.5, 0), ("A", 4, 1.0, 0), ("A", 4, 0.5, 0),
            ("R", 0, 0.5, 0), ("C", 5, 0.5, 0), ("E", 5, 0.5, 0), ("D", 5, 0.5, 0),
            ("C", 5, 0.5, 0), ("B", 4, 1.0, 0), ("C", 5, 0.5, 0), ("D", 5, 0.5, 0),
            ("E", 5, 1.0, 0), ("C", 5, 1.0, 0), ("A", 4, 1.0, 0), ("A", 4, 0.5, 0),
            ("R", 0, 0.5, 0),
        ],
        # Bass (channel 1)
        [
            ("A", 2, 2.0, 1), ("A", 2, 2.0, 1), ("A", 2, 1.0, 1), ("E", 3, 1.0, 1),
            ("A", 2, 2.0, 1), ("E", 3, 2.0, 1), ("A", 2, 2.0, 1), ("E", 3, 1.0, 1),
            ("A", 2, 2.0, 1), ("A", 2, 2.0, 1), ("A", 2, 1.0, 1), ("E", 3, 1.0, 1),
            ("A", 2, 2.0, 1), ("E", 3, 2.0, 1), ("A", 2, 2.0, 1), ("E", 3, 1.0, 1),
        ],
    ],
}

_KALINKA_TEMPO = 132
_KALINKA = {
    "tempo": _KALINKA_TEMPO,
    "tracks": [
        # Melody (channel 0)
        [
            ("D", 4, 0.5, 0), ("E", 4, 0.5, 0), ("G", 4, 0.5, 0), ("F", 4, 0.5, 0),
            ("E", 4, 0.5, 0), ("D", 4, 1.0, 0), ("E", 4, 0.5, 0), ("G", 4, 0.5, 0),
            ("A", 4, 1.0, 0), ("B", 4, 1.0, 0), ("A", 4, 0.5, 0), ("G", 4, 0.5, 0),
            ("F", 4, 0.5, 0), ("E", 4, 0.5, 0), ("D", 4, 1.5, 0),
        ],
        # Bass (channel 1)
        [
            ("D", 3, 1.0, 1), ("D", 3, 1.0, 1), ("D", 3, 1.0, 1), ("D", 3, 1.0, 1),
            ("D", 3, 1.0, 1), ("D", 3, 1.0, 1), ("G", 3, 1.0, 1), ("G", 3, 1.0, 1),
            ("G", 3, 1.0, 1), ("G", 3, 1.0, 1), ("G", 3, 1.0, 1), ("G", 3, 1.0, 1),
            ("D", 3, 1.0, 1), ("D", 3, 1.0, 1), ("D", 3, 1.0, 1),
        ],
    ],
}

_SONGS = {
    "korobeiniki": _KOROBEINIKI,
    "kalinka": _KALINKA,
}


def _build_track(notes: list, ticks_per_beat: int) -> mido.MidiTrack:
    """Build a MIDI track from (note_name, octave, beats, channel) tuples."""
    track = mido.MidiTrack()
    for name, octave, beats, channel in notes:
        duration = int(beats * ticks_per_beat)
        if name == "R":
            track.append(mido.Message("note_off", note=0, velocity=0,
                                      time=duration, channel=channel))
        else:
            note_num = _note(name, octave)
            track.append(mido.Message("note_on", note=note_num, velocity=100,
                                      time=0, channel=channel))
            track.append(mido.Message("note_off", note=note_num, velocity=0,
                                      time=duration, channel=channel))
    return track


def _generate_midi(song_name: str, path: str) -> None:
    """Generate a MIDI file for the given song."""
    song = _SONGS[song_name]
    mid = mido.MidiFile(ticks_per_beat=480)
    # Tempo track (track 0)
    tempo_track = mido.MidiTrack()
    tempo_track.append(mido.MetaMessage("set_tempo",
                                        tempo=mido.bpm2tempo(song["tempo"])))
    tempo_track.append(mido.MetaMessage("track_name", name=song_name))
    mid.tracks.append(tempo_track)
    # Music tracks
    for notes in song["tracks"]:
        mid.tracks.append(_build_track(notes, mid.ticks_per_beat))
    mid.save(path)


def ensure_midi_files() -> None:
    """Generate MIDI files if they don't exist in data/midi/."""
    ensure_data_dir()
    os.makedirs(MUSIC_MIDI_DIR, exist_ok=True)
    for song_name, path in MUSIC_SONG_PATHS.items():
        if not os.path.exists(path):
            _generate_midi(song_name, path)


if __name__ == "__main__":
    ensure_midi_files()
    for name, path in MUSIC_SONG_PATHS.items():
        mid = mido.MidiFile(path)
        print(f"{name}: {len(mid.tracks)} tracks, {len(mid.tracks[1])} msg in melody")
    print("MIDI files generated.")