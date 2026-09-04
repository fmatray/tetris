# Human Player

## Overview

The human player mode provides a complete Tetris Guideline-compliant experience with keyboard controls, DAS (Delayed Auto-Shift), hold piece, ghost piece, configurable keybindings, and seed-based replay.

**Entry Point:** Main Menu → **Humain** → **Mode** (Normal/Replay)

---

## Gameplay Features

### Core Mechanics (Guideline Compliant)

| Feature | Implementation |
|---------|----------------|
| **Board** | 10×22 (20 visible + 2 hidden buffer) |
| **Pieces** | 7 tetrominos (I, J, L, O, S, T, Z) with SRS rotation |
| **SRS Wall Kicks** | JLSTZ + I kick tables from `tetris/game/rules.py` |
| **Lock Delay** | 500ms, max 15 move/rotate resets |
| **Hold** | Once per lock (C by default), swap with next piece if empty |
| **Ghost Piece** | Configurable (shows hard-drop landing position) |
| **Preview** | 0, 1, or 3 next pieces (configurable) |
| **DAS** | 170ms initial delay, 50ms repeat interval |
| **Soft Drop** | 10× gravity (0.1× drop interval) |
| **Hard Drop** | Instant lock (Space by default) |
| **Scoring** | Standard Guideline (1/3/5/8 per line × level, T-Spin, B2B ×1.5) |
| **Levels** | 10 lines per level, super-exponential gravity |

### Piece Generators

| Generator | Description |
|-----------|-------------|
| **Random** | Uniform random each piece |
| **7-Bag** | Random permutation of 7 pieces, repeat |
| **35-Bag** | 5 consecutive 7-bags (reduces drought) |
| **Weighted** | Custom weights (S/Z/O less frequent) |
| **Replay** | Pre-recorded sequence from `data/replay_pieces.json` |

### Special Modes (Sprint & Blitz)

The Mode option in the human menu cycles `Normal → Replay → Sprint → Blitz`.
Sprint and Blitz only change win/lose conditions and add a timer; all other
gameplay (SRS, hold, lock delay, scoring) is identical to Marathon. AI, Bot,
and MCP players always play Marathon.

| Mode | Goal | End condition | HUD timer |
|------|------|---------------|-----------|
| **Marathon** | Score as much as possible | Top-out | — |
| **Sprint** | Clear 40 lines as fast as possible | 40 lines reached (win) or top-out | Elapsed (`TIME:`) |
| **Blitz** | Score as much as possible in 2 minutes | 120 s elapsed (time out) or top-out | Remaining (`TIME LEFT:`) |

Timer constants: `SPRINT_TARGET_LINES = 40`, `BLITZ_DURATION_MS = 120_000`
(`tetris/settings.py`). End conditions are checked in
`HumanState._check_mode_end` after each update, so the line clear or lock of
that frame counts before the game ends. Sprint results only enter the
leaderboard on a completed 40-line run.

### Efficiency Stats (PPS & Finesse)

Every finished human game records:

- **PPS** (pieces per second): `piece_count / elapsed_seconds`, computed in
  `GameOverState` and stored as `pps` in `human_stats.json`.
- **Finesse faults**: inputs beyond the theoretical minimum per piece
  (one rotation at most plus lateral distance from spawn). The counter is an
  approximation — it ignores SRS kick lateral credit and overhang detours.

Both are optional keyword-only fields of `save_human_game()`; records saved
before v3.7 simply lack them, and the stats screen aggregates with `.get()`.
The stats screen shows average PPS and total finesse faults below the
summary table.

---

## Input System

### Default Keybindings

| Action | Default Key | French Label |
|--------|-------------|--------------|
| Move Left | `←` (Left Arrow) | Gauche |
| Move Right | `→` (Right Arrow) | Droite |
| Rotate CW | `↑` (Up Arrow) | Rotation horaire |
| Rotate CCW | `S` | Rotation anti-horaire |
| Soft Drop | `↓` (Down Arrow) | Chute douce |
| Hard Drop | `Space` | Chute rapide |
| Hold | `C` | Réserve |
| Pause | `P` | Pause |
| Mute | `M` | Muet |

### DAS (Delayed Auto-Shift)

- **Initial delay**: 170ms (`DAS_DELAY_MS`) — held direction does nothing
- **Repeat interval**: 50ms (`DAS_REPEAT_MS`) — auto-shift repeats every 50ms
- **Independent per direction** — left and right tracked separately
- **Stops on key release** or piece lock

### ARE (Entry Delay)

When a piece locks, the next piece stays inactive for 100ms (`ARE_MS`). Rotation or hold input during this delay is buffered (IRS/IHS) and applied when the next piece appears. See [game_rules.md §12](game_rules.md#12-are-appearance-delay-irs-ihs) for details.

### Soft Drop

- Holding `Down` accelerates gravity to 10× normal (`SOFT_DROP_FACTOR = 0.1`)
- Releases immediately on key up
- Does **not** lock the piece — lock delay still applies

### Hold

- Press `C` (default) to swap current piece with hold slot
- If hold empty: current piece → hold, next piece spawns
- Once per lock (`_can_hold` flag, reset on lock)
- Ghost piece updates for held piece

### Pause

- `P` toggles pause
- Game frozen, music pauses
- All input ignored except `P` to unpause or `ESC` to menu

---

## Keybind Configuration

### Menu Path: Main → Humain → Touches

**KeybindState** (`tetris/states/keybind.py`):
- Up/Down: navigate actions
- Enter: enter "listening" mode (shows `...`)
- Next key press: rebinds action
- ESC: cancel listening / return to menu
- **Reset option** at bottom: restores all defaults

### Conflict Detection

- Reserved keys (cannot be rebound): `↑`, `↓`, `←`, `→`, `Enter`, `ESC`
- Conflict check: if new key already used by another action → rejected with "Utilisé par: {label}"
- Changes persist immediately via `MenuState.save_settings()`

### Persistence

- Stored in `data/settings.json` under `keybinds` (action → pygame keycode int)
- Loaded by `MenuState._load_settings()`
- Applied in `HumanState._setup_keybinds()` on game start

---

## Seed & Replay

### Seed Entry (Main → Humain → Graine)

**SeedEntryState** (`tetris/states/seed_entry.py`):
- Numeric text input (max 10 digits)
- Empty = random (`None`)
- Digits append, Backspace deletes, Enter confirms, ESC cancels
- Seed stored on `MenuState.seed`, persisted to `settings.json`

### Replay Mode

- **Mode** toggle in Humain menu: Normal ↔ Replay
- Replay uses `PieceProvider(generator="replay")` with sequence from `data/replay_pieces.json`
- Useful for: practicing specific sequences, debugging, fair comparison

---

## Human State Implementation

### Class: `HumanState` (inherits `GameState`)

Located in `tetris/states/human.py`.

**Inherited from `GameState`:**
- Board, pieces, stats, lock delay, gravity, movement primitives (`_move_left`, `_move_right`, `_rotate_cw`, `_rotate_ccw`, `_soft_drop`, `_hard_drop`, `_hold`)
- SRS wall kicks via `Board.try_rotate()`
- Line clear, T-Spin, B2B, combo handling
- Rendering via `Renderer`

**Added by `HumanState`:**
- `input_map: dict[keycode, Callable]` — built from `MenuState.keybinds`
- `_das_held: dict[keycode, float]` — DAS timer per held key
- `_pause_key`, `_soft_drop_key`, `_left_key`, `_right_key`, `_hold_key` — cached keycodes

**Methods:**

| Method | Purpose |
|--------|---------|
| `_setup_keybinds(menu)` | Build `input_map` from menu keybinds or defaults |
| `handle_event(event)` | Process KEYDOWN/KEYUP: pause, movement, hold, DAS start/stop |
| `update(dt, particles)` | Advance DAS timers, auto-repeat held directions, call `super().update()` |

**Event Handling Flow:**
```python
def handle_event(self, event):
    # 1. Parent handles ESC/mute → returns new State if ESC
    result = super().handle_event(event)
    if result: return result
    
    if event.type == KEYDOWN:
        if event.key == pause_key:
            self.paused = not self.paused
        elif event.key in input_map:
            input_map[event.key]()  # execute movement
            if event.key in (left_key, right_key):
                _das_held[event.key] = 0.0  # start DAS timer
    elif event.type == KEYUP:
        if event.key == soft_drop_key:
            down_pressed = False
        if event.key in _das_held:
            del _das_held[event.key]  # stop DAS
```

**DAS Update:**
```python
def update(self, dt, particles):
    if not game_over and not paused:
        for key in list(_das_held):
            _das_held[key] += dt
            if _das_held[key] >= DAS_DELAY_MS:
                since_last = _das_held[key] - DAS_DELAY_MS
                if since_last >= DAS_REPEAT_MS:
                    _das_held[key] = DAS_DELAY_MS  # reset for next repeat
                    input_map[key]()  # auto-shift
    return super().update(dt, particles)
```

---

## Human Menu Structure

```
Main Menu
└── Humain
    ├── Mode: Normal / Replay
    ├── Graine: [SeedEntryState] — numeric input
    ├── Touches: [KeybindState] — rebind all actions
    ├── Statistiques: [HumanStatsState] — history viewer
    └── Retour
```

### HumanMenuState (`tetris/states/human_menu.py`)

- Inherits `MenuBase` (cursor navigation, selection handling)
- Options: `("Mode", "Graine", "Touches", "Statistiques", "Retour")`
- `_toggle_indices = {0}` — only "Mode" toggles
- `_value_label(i)` shows current mode/seed
- `_on_select()` routes to sub-states

---

## Statistics

### HumanStatsState (`tetris/states/human_stats.py`)

Displays persistent game history from `data/human_stats.json`:

- **Total games played**
- **Best score / lines / level**
- **Average score / lines / level / duration**
- **Total play time**
- **Recent games list** (last 20) with score, lines, level, date

**Data Model** (per game entry):
```json
{
  "score": 45200,
  "lines": 123,
  "level": 12,
  "duration": 342.5,
  "date": "2026-08-31T14:22:10",
  "mode": "Normal",
  "handicap": 0,
  "generator": "7bag",
  "seed": 12345
}
```

**Architectural Guarantee:** AI games **never** pollute human stats.
- `save_human_game()` only called in `GameOverState._handle_name_entry()`
- `AIState` has its own `_on_episode_end()` and never creates `GameOverState`
- Separate log files: `ai_training_log.json` / `ai_playing_log.json`

### Placement Recording (Imitation Data)

Every human game also records each locked placement (piece type, rotation,
column, hold flag) to `data/human_placements.jsonl` via `PlacementsLog`
(`tetris/game/imitation.py`). The [AI imitation warm-start](ai.md) replays
these records to pre-train the V-network. The same architectural guarantee
holds: only `HumanState` attaches a recorder, so AI/bot games never write
to the placement log. Writes are best-effort and never crash gameplay.

---

## Game Over

### GameOverState (`tetris/states/game_over.py`)

- Shows final score, lines, level
- **Name entry** for leaderboard (A-Z, 0-9, max 15 chars)
- Leaderboard capped at 10 entries (`LEADERBOARD_SIZE`)
- Saves to `data/leaderboard.json` and `data/human_stats.json`
- Returns to `MenuState` on confirm

---

## Rendering

### HUD Elements (from `tetris/visuals/renderer.py`)

| Element | Position | Source |
|---------|----------|--------|
| Score | `HUD_POSITIONS["score"]` | `GameStats.score` |
| Lines | `HUD_POSITIONS["lines"]` | `GameStats.total_lines` |
| Level | `HUD_POSITIONS["level"]` | `GameStats.level` |
| Combo | `HUD_POSITIONS["combo"]` | `GameStats.combo` |
| B2B | `HUD_POSITIONS["b2b"]` | `GameStats.b2b` |
| Next Piece | `HUD_POSITIONS["next_piece"]` | `next_piece` |
| Preview Pieces | `HUD_POSITIONS["preview"]` | `preview_pieces` |
| Hold Piece | `HUD_POSITIONS["hold"]` | `hold_piece` / `_can_hold` |
| Ghost Piece | On board (outline) | `Renderer._draw_ghost()` |
| Clear Counts | Left HUD panel | `GameStats.clear_counts` |

### Debug Overlay (Press `d` during gameplay)

- 7-bag visualization (next pieces in current bag)
- Current speed info (drop interval, level)
- Hole/overhang debug markers
- Toggles `GameState.debug` live (does not affect logging level)

---

## Configuration (from `tetris/settings.py`)

### GameConfig (passed to HumanState)

```python
@dataclass
class GameConfig:
    handicap: int = 0              # 0-5 garbage rows at start
    sound_volume: int = 2          # 0-3 (Off/Bas/Moyen/Max)
    music_volume: int = 2          # 0-3
    music_song: str = "korobeiniki"  # "korobeiniki" / "kalinka"
    debug: bool = False            # debug overlay + logging
    ghost_piece: bool = True       # show ghost
    preview_count: int = 1         # 0/1/3
    speed_mode: str = "normal"     # none/easy/normal/medium/hard/crazy/insane
```

### Menu Settings (persisted in `settings.json`)

```json
{
  "player": "Humain",
  "mode": "Normal",
  "handicap": 0,
  "sound": 2,
  "music": 2,
  "song": "korobeiniki",
  "debug": false,
  "ghost_piece": true,
  "preview_count": 1,
  "piece_generator": "7bag",
  "speed_mode": "normal",
  "seed": 12345,
  "keybinds": {
    "move_left": 276,
    "move_right": 275,
    "rotate_cw": 273,
    "rotate_ccw": 115,
    "soft_drop": 274,
    "hard_drop": 32,
    "hold": 99,
    "pause": 112,
    "mute": 109
  }
}
```

---

## Code Locations

| File | Purpose |
|------|---------|
| `tetris/states/human.py` | HumanState — keyboard input, DAS, pause |
| `tetris/states/human_menu.py` | HumanMenuState — sub-menu |
| `tetris/states/keybind.py` | KeybindState — interactive rebinding |
| `tetris/states/seed_entry.py` | SeedEntryState — numeric seed input |
| `tetris/states/human_stats.py` | HumanStatsState — history viewer |
| `tetris/states/game_over.py` | GameOverState — name entry, leaderboard |
| `tetris/states/game.py` | GameState — shared gameplay engine |
| `tetris/settings.py` | DEFAULT_KEYBINDS, KEYBIND_LABELS, GameConfig |
| `tetris/game/rules.py` | SRS kicks, shape_fits, try_rotation (shared with AI/Bot) |

---

## Extending Human Input

### Adding a New Action

1. Add to `DEFAULT_KEYBINDS` and `KEYBIND_LABELS` in `settings.py`
2. Add method to `GameState` (e.g., `_my_action`)
3. Add to `input_map` in `HumanState._setup_keybinds()`
4. Add to `_ACTIONS` list in `keybind.py` (for rebind UI)

### Adding a New Sub-Menu

1. Create new State class inheriting `MenuBase`
2. Add entry to `HumanMenuState._OPTIONS`
3. Handle in `HumanMenuState._on_select()`

---

## Testing

```bash
# Headless human gameplay test
SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy python3 -c "
import pygame
from tetris.states.menu import MenuState
# ... navigate to HumanState, inject key events ...
pygame.event.Event(pygame.KEYDOWN, key=pygame.K_LEFT)
"

# Run human-related tests
SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy python -m pytest tests/ -k "human or keybind or seed" -q
```