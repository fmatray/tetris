# Human vs AI Game Rules Analysis

## Objective

Verify that identical game rules apply to human and AI play, identify
duplicated game-rule code between the two paths, propose a refactoring
architecture, and present an implementation plan.

**Status: Implemented.** All divergences fixed and duplicated code extracted to `tetris/game/rules.py`. See git history for details.

---

## 1. Situation Evaluation

### 1.1 Architecture Overview

```
GameState (tetris/states/game.py) — ABSTRACT BASE
├── Owns: Board, PieceProvider, Tetromino, GameStats, Renderer, AudioManager
├── Game rules: gravity, lock delay, SRS rotation, line clear, scoring,
│                hold, hard drop, soft drop, top-out, handicap
├── Input handlers: _move_left, _move_right, _rotate_cw, _rotate_ccw,
│                    _soft_drop, _hard_drop, _hold
├── Shared handle_event: mute key + ESC (back to menu)
└── _on_exit() hook: overridden by AIState for model save
         │
         ▼
HumanState(GameState) (tetris/states/human.py)
├── Adds: keybind setup, DAS auto-shift, pause toggle, full keyboard
└── Input: keyboard via input_map
         │
         ▼
AIState(GameState) (tetris/states/ai.py)
├── Inherits: ALL game rules from GameState
├── Overrides:
│   ├── update()         → AI macro-action selection + super().update()
│   ├── _lock_and_spawn() → RL transition capture + super()._lock_and_spawn()
│   ├── _on_exit()       → save model + flush log (replaces handle_event override)
│   └── draw()            → super().draw() + AI HUD overlay
└── Adds: DQNAgent, TrainingLog, candidate generation, curriculum, episode loop
```

**Verdict: The inheritance model is sound at the structural level.**
`GameState` is now an abstract base; `HumanState` and `AIState` both inherit
from it. `AIState` delegates to `super()` for gravity, lock delay, scoring,
and line clears. The AI does not re-implement game rules in its play path —
it calls the same `_lock_and_spawn`, `board.lock_tetromino`,
`board.clear_lines`, `stats.on_piece_locked` as the human.

### 1.2 Rule-by-Rule Comparison

| Game Rule | Human Path | AI Path | Identical? | Notes |
|---|---|---|---|---|
| **Gravity / drop speed** | `GameState.update()` → `_drop_interval(level)` (shared); DAS via `HumanState.update()` | `super().update()` (same code) | ✅ Yes | AI calls `super().update()` for gravity after placing the piece |
| **Soft drop scoring** | `stats.add_soft_drop(1)` per gravity cell when `down_pressed` | `stats.add_soft_drop(drop_cells)` in `_execute_macro_action` | ✅ Yes | Both call `ScoreEngine.soft_drop_points(cells)` → 1 pt/cell |
| **Hard drop** | `board.hard_drop()` + `stats.add_hard_drop(distance)` + `_lock_and_spawn(hard_drop=True)` | Same in `_execute_macro_action` when `soft_drop=False` | ✅ Yes | Identical code path |
| **Lock delay** | `GameState.update()` → `_lock_timer += dt`, `LOCK_DELAY_MS=500`, `LOCK_DELAY_RESETS=15` | `super().update()` (same code) | ✅ Yes | AI inherits lock delay; but see §1.3 for a behavioral divergence |
| **SRS rotation + wall kicks** | `board.try_rotate()` using `SRS_KICKS_JLSTZ` / `SRS_KICKS_I` | AI uses `rewards.py::_try_rotation()` for *simulation*, but `_execute_macro_action` calls `piece.rotate()` directly (no wall kicks) | ⚠️ Divergence | See §1.3 finding #1 |
| **Line clearing** | `board.lock_tetino()` → `board.clear_lines()` | `super()._lock_and_spawn()` → same `board.lock_tetromino()` | ✅ Yes | AI simulation uses `rewards.py::place_and_clear()` which is a *copy* — see §2 |
| **Scoring (line clears, T-spin, B2B, combo)** | `stats.on_piece_locked(cleared, tspin)` | Same via `super()._lock_and_spawn()` | ✅ Yes | Identical |
| **T-Spin detection** | `board.is_tspin(self.current_piece)` in `_lock_and_spawn` | Same via `super()._lock_and_spawn()` | ✅ Yes | Identical |
| **Top-out detection** | `_lock_and_spawn`: all blocks above visible field | Same via `super()._lock_and_spawn()` | ✅ Yes | Identical |
| **Game over (spawn collision)** | `board.is_valid_move(self.current_piece)` check after spawn | Same via `super()._lock_and_spawn()` | ✅ Yes | Identical |
| **Hold piece** | `_hold()` — swap current with held, `_can_hold` flag | **AI never uses hold** | ⚠️ Divergence | See §1.3 finding #2 |
| **Handicap** | `board.apply_handicap(handicap)` in `__init__` | Same via `super().__init__` (first episode) | ⚠️ Divergence | See §1.3 finding #3 |
| **Ghost piece** | Configurable via menu (`ghost_piece` setting) | Force-disabled: `self.ghost_piece = False` | ⚠️ Divergence | Cosmetic only — not a game rule |
| **Piece generator (7-bag etc.)** | `PieceProvider(generator=self.piece_generator)` | `PieceProvider(generator=self.piece_generator)` | ✅ Yes | Same generator setting from menu |
| **First-piece restriction** | `PieceProvider._first_piece_choice()` | Same | ✅ Yes | Identical |
| **Preview count** | Configurable (0, 1, 3) via menu | Same setting from menu | ✅ Yes | Identical |
| **Level progression** | `LINES_PER_LEVEL=10` via `stats.on_piece_locked` | Same | ✅ Yes | Identical |
| **Music speed scaling** | `_music_speed_for_level(level)` in `update()` | Same via `super().update()` | ✅ Yes | Identical |
| **Replay mode** | `PieceProvider(mode="replay")` | **AI always uses `mode="normal"`** | ✅ Exception | Intended: replay is human-only per spec |
| **Curriculum** | N/A | `piece_provider.set_allowed_types()` restricts pool | ✅ Exception | Intended: curriculum is AI-only per spec |
| **Game over flow** | `_do_game_over()` → `GameOverState` (name entry, leaderboard) | `_on_episode_end()` → `_reset_episode()` (auto-restart) | ⚠️ Divergence | See §1.3 finding #4 |

### 1.3 Findings — Rule Divergences

#### Finding #1: AI rotation bypasses SRS wall kicks (CRITICAL)

**Location:** `ai.py:317-318` (`_execute_macro_action`)

```python
while piece.rotation != target_rot:
    piece.rotate(1)  # ← raw rotation, no wall kicks
```

The AI rotates the piece by directly incrementing `piece.rotation` without
calling `board.try_rotate()`. This means:
- SRS wall kicks are **not applied** during AI piece placement.
- If the target rotation requires a wall kick to be reachable, the AI
  will place the piece in a position that a human player **could not
  reach** — or conversely, the AI may fail to reach positions that are
  reachable via wall kicks.

The AI's *candidate generation* (`soft_drop_placements` in `rewards.py`)
**does** simulate SRS wall kicks via `_try_rotation()`, so the candidate
list is correct. But `_execute_macro_action` doesn't use wall kicks when
actually moving the piece — it just force-rotates and then slides
horizontally. If the BFS found a placement reachable only via a wall kick
(e.g., rotating into a niche), the execution phase will fail to reproduce
that placement.

**Impact:** The AI may play positions that are physically unreachable in
the human game, or fail to execute positions it evaluated as optimal.

**Severity:** Critical — violates "same game rules" principle.

#### Finding #2: AI never uses the hold mechanic

**Location:** `ai.py` — no call to `_hold()` anywhere; `handle_event`
ignores all movement keys including hold.

The AI inherits the hold infrastructure (`self.hold_piece`,
`self._can_hold`, `self._hold()`) from `GameState` but never invokes it.
The hold piece is always `None` during AI play.

**Impact:** The AI plays with a strictly simpler game (no hold) than the
human. This is a game-rule difference, not just a strategy choice.

**Severity:** Medium — the AI has a reduced action space. Whether this is
intentional is a design question. If the AI should have the same rules,
hold must be part of candidate generation.

#### Finding #3: AI drops handicap on episode reset

**Location:** `ai.py:499-500` (`_reset_episode`)

```python
self.board = Board()
# Fresh board for learning diversity — no handicap carried over
```

The first AI episode applies handicap via `super().__init__()` →
`board.apply_handicap(handicap)`. But every subsequent episode resets to
a clean `Board()` without re-applying handicap. The human player always
plays with handicap for the entire game.

**Impact:** If handicap > 0, the AI's first episode has it, subsequent
episodes don't. Inconsistent game rules within AI play itself, and
divergent from human play.

**Severity:** Medium — only affects AI training with handicap > 0.

#### Finding #4: AI skips lock delay for AI-placed pieces

**Location:** `ai.py:338-348` (`_execute_macro_action`)

```python
if self.soft_drop:
    while piece.y < py and self.board.is_valid_move(piece, dy=1):
        piece.move(0, 1)
    self._lock_and_spawn()        # ← immediate lock, no lock delay
else:
    distance = self.board.hard_drop(piece)
    self._lock_and_spawn(hard_drop=True)  # ← immediate lock
```

When the AI places a piece via `_execute_macro_action`, it calls
`_lock_and_spawn()` **immediately** — bypassing the lock delay timer
entirely. The human player must wait `LOCK_DELAY_MS` (500ms) with
`LOCK_DELAY_RESETS` (15) resets before a grounded piece locks.

After the AI's `_lock_and_spawn`, `super().update()` runs and may apply
lock delay to the **next** piece if it spawns grounded, but the AI's
own placement never respects lock delay.

**Impact:** The AI gets instant piece locking; the human gets a 500ms
window with resets. This is a game-rule difference.

**Severity:** Medium — affects gameplay timing. Arguably intentional for
training speed, but it IS a rule difference.

#### Finding #5: AI episode reset doesn't go through GameOverState

**Location:** `ai.py:441-448` (`_on_episode_end`)

The human path: `game_over=True` → `_do_game_over()` → `GameOverState`
(name entry, leaderboard save, human stats save).

The AI path: `game_over=True` → `_on_episode_end()` → `_log_and_learn()`
→ `_reset_episode()` (auto-restart).

This is **intentional and correct** per AGENTS.md: "AIState has its own
`_on_episode_end()` and never creates GameOverState — architectural
guarantee that AI games never pollute human stats." This is not a game
rule divergence but a post-game-flow divergence. It is by design.

---

## 2. Duplicated Game-Rule Code

### 2.1 Collision Detection — DUPLICATED

| Location | Code | Data Structure |
|---|---|---|
| `board.py:73-82` `Board._shape_fits()` | Checks bounds + grid occupancy | `list[list[tuple\|None]]` |
| `rewards.py:411-419` `_shape_fits()` | Identical logic | `np.ndarray` (0/1) |

Both check `x < 0 or x >= BOARD_WIDTH or y >= BOARD_HEIGHT` and
`grid[y][x] is not None / > 0`. The only difference is the grid
representation (list vs numpy array).

### 2.2 SRS Wall Kicks — DUPLICATED

| Location | Code |
|---|---|
| `board.py:46-71` `Board.try_rotate()` | Uses `SRS_KICKS_I` / `SRS_KICKS_JLSTZ` |
| `rewards.py:422-434` `_try_rotation()` | Uses same `SRS_KICKS_I` / `SRS_KICKS_JLSTZ` |

Identical kick tables, identical logic (iterate kicks, check fit, return
first valid). The board version mutates the Tetromino; the rewards
version returns `(nx, ny)` for simulation.

### 2.3 Hard Drop — DUPLICATED

| Location | Code |
|---|---|
| `board.py:114-120` `Board.hard_drop()` | `while is_valid_move(dy=1): move(0,1)` |
| `rewards.py:302-316` `hard_drop_y()` | `while True: check fit at y, y += 1` |

Both find the lowest valid Y for a piece. The board version moves the
actual Tetromino; the rewards version returns the Y coordinate on a
numpy grid.

### 2.4 Line Clearing — DUPLICATED

| Location | Code |
|---|---|
| `board.py:138-159` `Board.clear_lines()` | Finds full rows, removes them, inserts empty rows at top |
| `rewards.py:319-341` `place_and_clear()` | Places cells, finds full rows, removes them, vstacks zeros at top |

Identical logic. The board version operates on `list[list]`; the rewards
version on `np.ndarray`.

### 2.5 Piece Placement — DUPLICATED

| Location | Code |
|---|---|
| `board.py:103-112` `Board.lock_tetromino()` | Writes `tetromino.color` to grid cells |
| `rewards.py:326-330` `place_and_clear()` (placement part) | Writes `1.0` to grid cells |

Same cell-by-cell placement. Board stores color tuples; rewards stores
1.0 (binary occupancy).

### 2.6 Summary Table

| Game Rule | `tetris/game/` (authoritative) | `tetris/ai/rewards.py` (duplicate) | Nature |
|---|---|---|---|
| Shape fits / collision | `Board._shape_fits` | `_shape_fits` | Full duplicate |
| SRS wall kicks | `Board.try_rotate` | `_try_rotation` | Full duplicate |
| Hard drop | `Board.hard_drop` | `hard_drop_y` | Full duplicate |
| Line clearing | `Board.clear_lines` | `place_and_clear` (clear part) | Full duplicate |
| Piece placement | `Board.lock_tetromino` | `place_and_clear` (place part) | Full duplicate |

**Root cause:** The AI needs to *simulate* board states (place a piece,
clear lines, evaluate the result) without mutating the real board. The
simulation operates on numpy arrays for vectorized feature extraction.
The `Board` class operates on list-of-lists with color tuples. So the
AI reimplemented the same game rules on a different data structure.

---

## 3. Proposed Architecture

### 3.1 Design Principle

**One rule engine, two representations.**

The game rules (collision, rotation, hard drop, line clear, placement)
should exist in exactly one place. The AI's simulation needs the same
rules but on numpy arrays for vectorized feature extraction. The
solution: a **grid-agnostic rule engine** that operates on an abstract
grid interface, with two concrete implementations.

### 3.2 Proposed Structure

```
tetris/game/
├── board.py          # Board (list grid) — keeps color tuples for rendering
├── tetromino.py      # Tetromino — unchanged
├── scoring.py        # ScoreEngine — unchanged
├── stats.py          # GameStats — unchanged
├── piece_provider.py # PieceProvider — unchanged
└── rules.py          # NEW — pure game-rule functions on abstract grids
```

#### `tetris/game/rules.py` — Grid-Agnostic Rule Engine

```python
"""Pure game-rule functions operating on abstract grids.

All functions accept a grid (list-of-lists or numpy 2D array) and
cell-occupancy predicate. This eliminates the duplication between
Board (list grid) and rewards.py (numpy grid simulation).
"""

from tetris.settings import (
    BOARD_WIDTH, BOARD_HEIGHT, SHAPES,
    SRS_KICKS_I, SRS_KICKS_JLSTZ,
)

# --- Occupancy abstraction ---------------------------------------------

def is_occupied(grid, x: int, y: int) -> bool:
    """Check if cell (x, y) is filled. Works for list[list] and np.ndarray."""
    if x < 0 or x >= BOARD_WIDTH or y < 0 or y >= BOARD_HEIGHT:
        return False  # out of bounds above is "empty" (spawn area)
    if y >= BOARD_HEIGHT:
        return True   # below board is "occupied" (floor)
    cell = grid[y][x]
    # list grid: cell is None or (r,g,b); numpy: cell is 0.0 or 1.0
    return cell is not None if isinstance(cell, (tuple, type(None))) else cell > 0


def shape_fits(grid, shape, x: int, y: int) -> bool:
    """Check if shape fits at (x, y) without collision."""
    for bx, by in shape:
        cx, cy = x + bx, y + by
        if cx < 0 or cx >= BOARD_WIDTH or cy >= BOARD_HEIGHT:
            return False
        if cy >= 0 and is_occupied(grid, cx, cy):
            return False
    return True


def try_rotation(grid, piece_type, from_rot, to_rot, x, y):
    """SRS wall kicks. Returns (nx, ny) or None."""
    if piece_type == "O":
        return (x, y) if shape_fits(grid, SHAPES[piece_type][to_rot], x, y) else None
    kicks = SRS_KICKS_I if piece_type == "I" else SRS_KICKS_JLSTZ
    key = (from_rot % len(SHAPES[piece_type]), to_rot % len(SHAPES[piece_type]))
    for dx, dy in kicks.get(key, [(0, 0)]):
        nx, ny = x + dx, y - dy
        if shape_fits(grid, SHAPES[piece_type][to_rot], nx, ny):
            return (nx, ny)
    return None


def hard_drop_y(grid, shape, x: int) -> int:
    """Find lowest y where shape fits at column x."""
    py = 0
    while True:
        if not shape_fits(grid, shape, x, py):
            return py - 1 if py > 0 else 0
        py += 1


def soft_drop_placements(grid, piece_type):
    """BFS enumeration of all reachable placements (SRS-aware)."""
    # ... same BFS logic, using shape_fits() and try_rotation() ...


def place_piece(grid, shape, x, y, value=None):
    """Write shape cells into grid. Returns new grid (copy)."""
    # ... works for both list and numpy ...


def clear_lines(grid):
    """Remove full rows, insert empty rows at top. Returns (new_grid, cleared_count, cleared_data)."""
    # ... unified logic ...
```

#### Migration of Existing Code

| Current | After Refactoring |
|---|---|
| `Board._shape_fits` | Calls `rules.shape_fits(self.grid, ...)` |
| `Board.try_rotate` | Calls `rules.try_rotation(self.grid, ...)` then mutates tetromino |
| `Board.hard_drop` | Calls `rules.hard_drop_y(self.grid, ...)` then moves tetromino |
| `Board.clear_lines` | Calls `rules.clear_lines(self.grid)` |
| `Board.lock_tetromino` | Calls `rules.place_piece(self.grid, ...)` + `rules.clear_lines(self.grid)` |
| `rewards.py::_shape_fits` | **Deleted** — uses `rules.shape_fits` |
| `rewards.py::_try_rotation` | **Deleted** — uses `rules.try_rotation` |
| `rewards.py::hard_drop_y` | **Deleted** — uses `rules.hard_drop_y` |
| `rewards.py::place_and_clear` | **Deleted** — uses `rules.place_piece` + `rules.clear_lines` |
| `rewards.py::soft_drop_placements` | **Deleted** — uses `rules.soft_drop_placements` |

### 3.3 Fixing the Divergences

#### Fix #1: AI rotation must use SRS wall kicks

`_execute_macro_action` should use `board.try_rotate()` instead of raw
`piece.rotate(1)`:

```python
# Before (broken):
while piece.rotation != target_rot:
    piece.rotate(1)

# After (correct):
while piece.rotation != target_rot:
    if not self.board.try_rotate(piece, 1):
        break  # rotation not reachable — placement invalid
```

This ensures the AI can only reach positions that a human player could
also reach via the same SRS rules.

#### Fix #2: AI must support hold (confirmed by user)

Add hold to the AI's candidate generation. Each candidate becomes
`(placement, hold_action)` where `hold_action` is either "place current"
or "hold and place next/swap". This expands the candidate space but
gives the AI the same game rules as the human. The `_can_hold` flag
resets on lock, same as human.

#### Fix #3: AI episode reset must re-apply handicap

```python
# In _reset_episode:
self.board = Board()
self.board.apply_handicap(self._handicap)  # ← add this
```

Store `self._handicap = handicap` in `__init__` for reuse.

#### Fix #4: AI placement must respect lock delay (confirmed by user)

Don't call `_lock_and_spawn()` directly in `_execute_macro_action`.
Instead, position the piece at the target (x, y, rotation) and let
`super().update()` handle the grounded state and lock timer naturally.
The piece will lock after `LOCK_DELAY_MS` (500ms) with
`LOCK_DELAY_RESETS` (15) resets, same as human play.

---
## 4. Implementation Plan

### Phase 1: Extract Rule Engine (no behavior change)

**Goal:** Centralize game rules into `tetris/game/rules.py` without
changing any behavior.

1. Create `tetris/game/rules.py` with grid-agnostic functions:
   - `shape_fits(grid, shape, x, y)`
   - `try_rotation(grid, piece_type, from_rot, to_rot, x, y)`
   - `hard_drop_y(grid, shape, x)`
   - `place_piece(grid, shape, x, y, value=...)`
   - `clear_lines(grid)` → `(new_grid, count, cleared_data)`
   - `soft_drop_placements(grid, piece_type)`

2. Refactor `Board` methods to delegate to `rules.py`:
   - `Board._shape_fits` → `rules.shape_fits(self.grid, ...)`
   - `Board.try_rotate` → `rules.try_rotation(self.grid, ...)`
   - `Board.hard_drop` → `rules.hard_drop_y(self.grid, ...)`
   - `Board.clear_lines` → `rules.clear_lines(self.grid)`
   - `Board.lock_tetromino` → `rules.place_piece` + `rules.clear_lines`

3. Refactor `rewards.py` to use `rules.py`:
   - Delete `_shape_fits`, `_try_rotation`, `hard_drop_y`,
     `place_and_clear`, `soft_drop_placements`
   - Import and re-export from `rules.py` for backward compatibility
   - Keep only AI-specific code: feature extraction, reward computation,
     Dellacherie value, board-to-grid conversion

4. Run full test suite — all 144 tests must pass.

### Phase 2: Fix Rule Divergences (all confirmed by user)

5. **Fix AI rotation** (`ai.py:317-318`): Replace `piece.rotate(1)` with
   `self.board.try_rotate(piece, 1)`. Break if rotation fails (placement
   unreachable via SRS — candidate should not have been generated).

6. **Fix handicap on episode reset** (`ai.py:499`): Store
   `self._handicap = handicap` in `__init__`, call
   `self.board.apply_handicap(self._handicap)` in `_reset_episode`.
   Remove the "fresh board for learning diversity" comment.

7. **Add hold support to AI**: Expand `_get_candidate_states` to
   enumerate hold candidates alongside placement candidates:
   - "Place current piece" candidates (existing logic)
   - "Hold current, place next/swap" candidates (new)
   Each hold candidate simulates: swap current with held (or spawn next
   if no held piece), then enumerate placements for the new current.
   The V-network evaluates all candidates uniformly; `select_action`
   picks the best. `_execute_macro_action` must handle hold+place
   sequences. `_can_hold` flag resets on lock, same as human.

8. **Respect lock delay in AI placement**: `_execute_macro_action`
   should position the piece at the target (x, y, rotation) but **not**
   call `_lock_and_spawn()` directly. Instead, let `super().update()`
   handle the grounded state and lock timer naturally. The piece is
   moved to its target position; gravity/lock-delay in
   `GameState.update()` will lock it after `LOCK_DELAY_MS` with resets.
   Remove the explicit `_lock_and_spawn()` call at the end of
   `_execute_macro_action`.

### Phase 3: Verification

9. Run `ruff check .` — only 2 pre-existing issues.
10. Run `pytest tests/ -q` — all 144 tests pass.
11. Run headless AI training validation:
    `SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy python -m tetris.verify_training`
12. Run headless human smoke test to confirm no regression.
13. Verify AI training metrics haven't degraded significantly
    (best_score > 10000, avg_score > 1000 per verify_training criteria).

### Phase 4: Documentation

14. Update `AGENTS.md`:
    - Add `tetris/game/rules.py` to the directory table
    - Update the duplicated-code note in the AI section
    - Document that AI now uses hold, lock delay, and persistent handicap
    - Update exceptions list: only replay (human only) and curriculum
      (AI only) remain
15. Update `docs/class_diagram.md` if it exists.
16. Git commit and push with comprehensive message.

---

## 5. Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| `rules.py` grid abstraction has edge-case bugs (list vs numpy) | Medium | High | Comprehensive unit tests for each function with both grid types |
| AI training performance degrades after wall-kick fix | Low | Medium | Run `verify_training` before/after, compare metrics |
| Lock delay slows AI training significantly (500ms per piece) | High | Medium | `ai_speed="fast"` still runs at 60 FPS; lock delay is 500ms real-time but the game loop processes it. Consider reducing `LOCK_DELAY_MS` globally if training throughput is unacceptable, but this would change human rules too |
| Hold support doubles+ candidate space, slows training | High | Medium | Hold candidates are only generated when `_can_hold=True` (once per lock). Profile and optimize candidate enumeration if needed |
| `soft_drop_placements` BFS behavior changes after refactor | Low | High | Keep BFS algorithm identical, only swap collision/rotation calls to `rules.py` |
| Lock delay makes AI `_execute_macro_action` + `super().update()` interaction complex | Medium | High | The AI positions the piece; gravity in `super().update()` handles the rest. If piece is already grounded after positioning, lock timer starts immediately. Test thoroughly |

---

## 6. Resolved Decisions (User-Confirmed)

All three divergences are to be **fixed** — the AI must follow the same
game rules as the human. No new exceptions beyond the two already
declared (replay = human only, curriculum = AI only).

1. **Hold mechanic for AI**: ✅ **Add hold to AI.** Expand candidate
   generation to include hold actions. The AI will have the same hold
   capability as the human player. Implementation: each candidate becomes
   `(placement, hold_action)` where `hold_action` is "place current" or
   "hold current, then place next (or swapped piece)". This adds hold
   state to the feature vector or candidate enumeration.

2. **Lock delay for AI**: ✅ **Respect lock delay.** The AI must wait the
   same `LOCK_DELAY_MS` (500ms) with `LOCK_DELAY_RESETS` (15) before a
   grounded piece locks. The `_execute_macro_action` should position the
   piece at the target location and let `super().update()` handle lock
   delay naturally, rather than calling `_lock_and_spawn()` directly.
   In `ai_speed="fast"` mode, the game loop runs at 60 FPS so lock delay
   still applies but wall-clock time is ~500ms real time.

3. **Handicap on episode reset**: ✅ **Re-apply handicap.** Every AI
   episode must start with `board.apply_handicap(handicap)`, identical
   to human play. Store `self._handicap = handicap` in `__init__` and
   call `self.board.apply_handicap(self._handicap)` in `_reset_episode`.
   Remove the "fresh board for learning diversity" comment.
---

## Appendix A: File Inventory

| File | Lines | Role |
|---|---|---|
| `tetris/states/game.py` | 381 | Human gameplay state — all game rules |
| `tetris/states/ai.py` | 652 | AI gameplay state — inherits + overrides |
| `tetris/game/board.py` | 159 | Board grid, collision, line clear, handicap |
| `tetris/game/tetromino.py` | 53 | Piece model |
| `tetris/game/scoring.py` | 39 | Scoring rules (pure functions) |
| `tetris/game/stats.py` | 65 | Running stats |
| `tetris/game/piece_provider.py` | 161 | Piece spawning (random/7-bag/replay) |
| `tetris/ai/rewards.py` | 491 | Feature extraction + reward + **duplicated game rules** |
| `tetris/states/menu.py` | 236 | Menu — constructs HumanState/AIState with settings |
| `tetris/states/game_over.py` | 109 | Game-over flow (human only) |

## Appendix B: Duplicated Code Locations (Exact Lines)

| Rule | Board (authoritative) | rewards.py (duplicate) |
|---|---|---|
| Shape fits | `board.py:73-82` | `rewards.py:411-419` |
| SRS wall kicks | `board.py:46-71` | `rewards.py:422-434` |
| Hard drop | `board.py:114-120` | `rewards.py:302-316` |
| Line clearing | `board.py:138-159` | `rewards.py:332-340` |
| Piece placement | `board.py:109-111` | `rewards.py:327-330` |
| Soft-drop BFS | N/A (human uses real-time input) | `rewards.py:437-491` |