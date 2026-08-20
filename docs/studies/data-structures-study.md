# Data Structures Study

## Goal

Replace opaque positional tuples with named data structures (NamedTuple/dataclass) across the codebase for readability, maintainability, and extensiveness. No new features, no behavior modification, no slowdown.

## Changes

### Placement (NamedTuple) — `tetris/ai/candidates.py`

Unified AI candidate placement. Previously two separate tuple formats:
- BFS results: `(shape, px, py, rot)` where `shape: list[tuple[int, int]]`
- AI candidate: `(rot, px, py, hold)`

Now a single `Placement(piece_type, rot, px, py, hold)`. The `shape` field was eliminated — it's always derivable as `SHAPES[piece_type][rot]`. This removes the most complex nested type (`list[tuple[int, int]]`) from placement data.

### soft_drop_placements moved to `tetris/ai/candidates.py`

`soft_drop_placements` had exactly one production caller (`gen_placements` in `candidates.py`). No human-gameplay or Board code called it. Moved from `tetris/game/rules.py` to `tetris/ai/candidates.py` — it's an AI-only function.

### MoveRecord (NamedTuple) — `tetris/states/ai.py`

AI last-move HUD records: `(piece, rot, col, hold)` → `MoveRecord(piece, rot, col, hold)`.

### MidiNote (NamedTuple) — `tetris/audio/__init__.py`

Parsed MIDI notes: `(start, duration, note)` → `MidiNote(start, duration, note)`.

### ColumnDef (NamedTuple) — `tetris/visuals/leaderboard_view.py`

Leaderboard column definitions: `(label, width, align)` → `ColumnDef(label, width, align)`.

### PendingTransition (dataclass) — `tetris/states/ai.py`

Grouped 3 ungrouped `self._prev_*` fields (`_prev_state`, `_prev_reward`, `_prev_done`) into a single `PendingTransition(state, reward, done)` dataclass. `_prev_action` kept separate — it's a "macro-action executed?" guard, not transition data.

## Decisions

- **NamedTuple over dataclass for tuples**: All target tuples are consumed via unpacking/indexing. NamedTuple is tuple-compatible — existing `for p in ...` and `p[3]` patterns continue to work.
- **`shape` eliminated from Placement**: Storing `piece_type` (str) instead of `shape` (list[tuple[int, int]]) simplifies the type and eliminates redundancy. `shape = SHAPES[piece_type][rot]` is O(1) and derived at call sites.
- **`iter_column_positions` left as 3-tuple**: Internal helper, only 2 callers, both need the actual `shape` list. Not worth a NamedTuple.
- **SFX `Tone` skipped**: Inline `(freq, duration)` literals are self-documenting; wrapping each in `Tone(...)` would double line count.
- **HUD_POSITIONS, RGB colors, SRS kicks, SHAPES skipped**: Static data tables / pygame idioms — NamedTuple would add verbosity without readability gain.