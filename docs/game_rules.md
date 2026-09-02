# Tetris Game Rules — Guideline Compliance and Human/AI Alignment

## Overview

This document consolidates the Tetris Guideline compliance audit and the Human vs AI rule alignment analysis. All items previously marked as missing or incomplete have been **implemented**. All rule divergences between human and AI play have been **fixed**.

## Guideline Compliance Status

| # | Rule | Status | Notes |
|---|------|--------|-------|
| 1 | 22-row board (20 visible + 2 hidden) | ✅ Implemented | `HIDDEN_ROWS = 2` in `settings.py`, `BOARD_HEIGHT = 22`, spawn at y=0 in hidden buffer |
| 2 | SRS wall kicks for human play | ✅ Implemented | `Board.try_rotate()` uses `SRS_KICKS_JLSTZ` / `SRS_KICKS_I` from `rules.py` |
| 3 | Hold piece | ✅ Implemented | `_hold()` in `GameState`, keybind in menu, hold panel in renderer |
| 4 | Non-locking soft drop | ✅ Compliant | Soft drop accelerates gravity; piece locks only via lock delay |
| 5 | Lock delay (~0.5s with reset on move/rotate) | ✅ Implemented | `LOCK_DELAY_MS = 500`, `LOCK_DELAY_RESETS = 15` |
| 6 | Top-out on lock above visible field | ✅ Implemented | Checks spawn overlap OR lock entirely above row 20 |
| 7 | 4 rotation states for all pieces (except O) | ✅ Implemented | `SHAPES` in `shapes.py` has 4 states for I, J, L, S, T, Z |
| 8 | 3+ piece preview queue | ✅ Implemented | Configurable `preview_count` (0, 1, 3) via `GameRulesMenuState` |
| 9 | T-Spin detection & rewarding | ✅ Implemented | `Board.is_tspin()` 3-corner rule, `ScoreEngine.tspin_points()` |
| 10 | Back-to-Back chains | ✅ Implemented | `GameStats.b2b` + `ScoreEngine.b2b_bonus()` ×1.5 |
| 11 | DAS (Delayed Auto Shift) | ✅ Implemented | `DAS_DELAY_MS = 170`, `DAS_REPEAT_MS = 50` |
| 12 | ARE (entry delay) + IRS/IHS | ✅ Implemented | `ARE_MS = 100` in `settings.py`, `_are_timer` in `GameState` |

All 12 indispensable/recommended rules are now **implemented**.

---

## Rule-by-Rule Detail

### 1. 22-Row Board (20 Visible + 2 Hidden)

**Implementation:**
- `HIDDEN_ROWS = 2` in `settings.py`
- `BOARD_HEIGHT = 22` (10×22 grid)
- Visible area: rows 2–21 (0-indexed), rendered rows 0–19
- Spawn position: x=3, y=0 (in hidden buffer)
- Top-out triggers on: spawn overlap OR piece locks entirely above row 20 (visible field)

**Files:**
- `tetris/settings.py` — `HIDDEN_ROWS`, `BOARD_HEIGHT`
- `tetris/game/board.py` — `Board` class, `apply_handicap`, `is_tspin`, `find_holes`
- `tetris/visuals/renderer.py` — renders only visible rows

### 2. SRS Wall Kicks

**Implementation:**
- Kick tables: `SRS_KICKS_JLSTZ`, `SRS_KICKS_I` in `tetris/game/rules.py`
- `Board.try_rotate(direction)` applies kicks in order until valid
- Used by both human (`GameState._rotate_cw/ccw`) and AI (`candidates.py::soft_drop_placements`)
- I-piece has separate kick table; J/L/S/T/Z share standard table

**Files:**
- `tetris/game/rules.py` — `try_rotation()`, kick tables
- `tetris/game/board.py` — `try_rotate()` delegates to `rules.try_rotation()`

### 3. Hold Piece

**Implementation:**
- `_hold()` in `GameState`: swaps current piece with held piece, marks `_can_hold=False` until next lock
- Hold keybind configurable in Keybind menu (default `C`)
- Hold panel in renderer shows held piece type and color
- AI hold: candidates enumerate hold placements alongside normal placements

**Files:**
- `tetris/states/game.py` — `_hold()` method
- `tetris/states/human.py` — keybind setup includes hold
- `tetris/visuals/renderer.py` — `draw_hold()`
- `tetris/ai/candidates.py` — hold candidate enumeration

### 4. Non-Locking Soft Drop

**Implementation:**
- Holding Down accelerates gravity by `SOFT_DROP_FACTOR = 20`
- Piece does NOT lock on soft-drop contact; locks only via lock delay timer
- Works identically for human and AI

**Files:**
- `tetris/states/game.py` — gravity acceleration in `update()`, `LOCK_DELAY_MS` logic

### 5. Lock Delay

**Implementation:**
- `LOCK_DELAY_MS = 500` — piece locks after 500ms of being grounded
- `LOCK_DELAY_RESETS = 15` — moving/rotating resets timer (max 15 resets)
- Timer managed in `GameState.update()` — resets on valid move/rotate
- **AI difference (by design)**: Learning mode fast-forwards lock delay (piece already positioned by BFS); playing mode respects full lock delay

**Files:**
- `tetris/settings.py` — `LOCK_DELAY_MS`, `LOCK_DELAY_RESETS`
- `tetris/states/game.py` — lock delay timer logic in `update()`
- `tetris/states/ai.py` — learning mode fast-forward, playing mode respects delay

### 6. Top-Out Conditions

**Implementation:**
1. **Spawn overlap**: `Board` checks if spawn position (3,0) collides with existing blocks
2. **Lock above visible**: After lock delay expires, if piece's cells are all at y < 20 (hidden rows), game over

**Files:**
- `tetris/game/board.py` — spawn check in `_spawn_piece()`, lock check in `_lock_and_spawn()`

### 7. 4 Rotation States

**Implementation:**
- `SHAPES` in `tetris/game/shapes.py` defines 4 rotation states for all pieces except O (1 state)
- Rotation indices: 0=spawn, 1=90° CW, 2=180°, 3=270° CW (90° CCW)
- SRS kick tables match 4-state rotation

**Files:**
- `tetris/game/shapes.py` — `SHAPES` dict, `num_shape_rot()`, `get_shape_rot()`

### 8. Piece Preview (3+)

**Implementation:**
- Configurable via `GameRulesMenuState`: `preview_count` = 0 / 1 / 3
- `PieceProvider` maintains `next_piece` + `preview_pieces` list
- Renderer draws preview queue in side panel

**Files:**
- `tetris/states/game_rules_menu.py` — menu option
- `tetris/game/piece_provider.py` — `preview_pieces` management
- `tetris/visuals/renderer.py` — `draw_next()`

### 9. T-Spin Detection & Rewarding

**Implementation:**
- **3-Corner T Rule**: T-piece locks with 3 of 4 corners occupied by existing blocks/walls → T-Spin
- `Board.is_tspin(piece, rotation, kick_used)` implements the rule
- Mini T-Spin (kick used) and full T-Spin scored differently
- `ScoreEngine.tspin_points(lines, level, mini)` — points table matches Guideline

| Lines | Mini T-Spin | Full T-Spin |
|-------|-------------|-------------|
| 0 | 100 × level | 400 × level |
| 1 | 200 × level | 800 × level |
| 2 | 400 × level | 1200 × level |
| 3 | 600 × level | 1600 × level |

**Files:**
- `tetris/game/board.py` — `is_tspin()`
- `tetris/game/scoring.py` — `ScoreEngine.tspin_points()`

### 10. Back-to-Back (B2B) Chains

**Implementation:**
- `GameStats.b2b` tracks consecutive B2B-eligible clears (Tetris or T-Spin)
- `ScoreEngine.b2b_bonus(base_points)` returns `int(base_points * 1.5)`
- B2B chain continues until a non-Tetris/non-T-Spin clear occurs

**Files:**
- `tetris/game/stats.py` — `GameStats.b2b`, `on_lines_cleared()`
- `tetris/game/scoring.py` — `b2b_bonus()`

### 11. DAS (Delayed Auto Shift)

**Implementation:**
- `DAS_DELAY_MS = 170` — initial delay before auto-repeat
- `DAS_REPEAT_MS = 50` — repeat interval
- Key held → wait `DAS_DELAY_MS` → repeat move every `DAS_REPEAT_MS`
- Works for Left, Right, Rotate CW, Rotate CCW

**Files:**
- `tetris/settings.py` — `DAS_DELAY_MS`, `DAS_REPEAT_MS`
- `tetris/states/human.py` — DAS handling in `update()`


### 12. ARE (Appearance Delay) + IRS/IHS

**Implementation:**
- `ARE_MS = 100` — after a piece locks, the next piece stays inactive for 100 ms
- ARE gates piece activity: gravity, movement, and rendering are on hold
- **IRS** (Initial Rotation System): rotation input during ARE buffers into `_irs_pending` (last input wins) and applies at spawn with SRS kicks
- **IHS** (Initial Hold System): hold input during ARE buffers into `_ihs_pending` and swaps at spawn
- Held soft drop continues through ARE (`down_pressed` persists)
- Applies to all player types: Human, AI, Bot (El-Tetris), MCP. AI learning mode fast-forwards ARE for training speed
- Toggle: Game Rules menu → "ARE" (default ON); `GameConfig.are` keyword (default `False` keeps legacy behavior)

**Files:**
- `tetris/settings.py` — `ARE_MS`
- `tetris/states/game.py` — `_are_timer`, `_irs_pending`, `_ihs_pending`, `_finalize_spawn()`, `are_active` property
- `tests/test_are.py` — ARE/IRS/IHS coverage

---

## Human vs AI Rule Alignment

All divergences identified in the Human vs AI analysis have been **fixed**. The AI now follows identical game rules to the human player.

### Fixed Divergences

| # | Divergence | Fix Applied | Location |
|---|------------|-------------|----------|
| 1 | AI rotation bypassed SRS wall kicks | `_execute_move_sequence` uses `board.try_rotate()` | `tetris/bots/moves.py` |
| 2 | AI never used hold mechanic | Hold candidates enumerated in candidate generation | `tetris/ai/candidates.py` |
| 3 | AI dropped handicap on episode reset | `_reset_episode` re-applies `board.apply_handicap()` | `tetris/states/ai.py` |
| 4 | AI skipped lock delay (instant lock) | Learning mode fast-forwards (by design); playing mode respects full delay | `tetris/states/ai.py` |

### Rule Engine Centralization

**Before:** Game rules duplicated in `Board` (list-of-lists) and `tetris/ai/rewards.py` (numpy arrays).

**After:** Single grid-agnostic rule engine in `tetris/game/rules.py` with two implementations:

| Function | Board (list) | AI Simulation (numpy) |
|----------|--------------|----------------------|
| `shape_fits(grid, shape, x, y)` | `Board.is_valid_move()` | `candidates.py` |
| `try_rotation(grid, shape, x, y, rot, kicks)` | `Board.try_rotate()` | `candidates.py` |
| `hard_drop_y(grid, shape, x, y)` | `Board.hard_drop()` | `candidates.py` |
| `place_cells(grid, shape, x, y, value)` | `Board.lock_tetromino()` | `candidates.py` |
| `find_full_rows(grid)` | `Board.clear_lines()` | `candidates.py` |

**Files:**
- `tetris/game/rules.py` — single rule engine
- `tetris/game/board.py` — calls `rules.py` functions
- `tetris/ai/candidates.py` — calls `rules.py` functions on numpy arrays

### Remaining Intentional Differences

| Aspect | Human | AI | Reason |
|--------|-------|-----|--------|
| Episode end | `GameOverState` (name entry, leaderboard) | Auto-restart via `_reset_episode()` | AI games don't pollute human stats |
| Curriculum learning | N/A | `PieceProvider.set_allowed_types()` | AI-only feature |
| Replay mode | Human only | N/A | Human-only feature |
| Lock delay (learning) | Full 500ms | Fast-forwarded | Training speed; playing mode matches human |

---

## Scoring Summary

| Clear Type | Base Points | T-Spin Bonus | B2B Bonus |
|------------|-------------|--------------|-----------|
| Single | 100 × level | +800 × level (full) / +200 × level (mini) | ×1.5 |
| Double | 300 × level | +1200 × level (full) / +400 × level (mini) | ×1.5 |
| Triple | 500 × level | +1600 × level (full) / +600 × level (mini) | ×1.5 |
| Tetris | 800 × level | N/A | ×1.5 |
| T-Spin 0 lines | 400 × level (full) / 100 × level (mini) | — | ×1.5 |
| T-Spin Single | 800 × level (full) / 200 × level (mini) | — | ×1.5 |
| T-Spin Double | 1200 × level (full) / 400 × level (mini) | — | ×1.5 |
| T-Spin Triple | 1600 × level (full) / 600 × level (mini) | — | ×1.5 |

**Combo Bonus:** `50 × combo × level` per line clear after the first in a combo chain.

**Files:** `tetris/game/scoring.py` — `ScoreEngine.line_points()`, `tspin_points()`, `b2b_bonus()`

---

## Configuration Reference

All game rule settings are configurable via the **Game Rules** menu and persisted to `data/settings.json`:

| Setting | Values | Default | Description |
| Generator | Random / 7-Bag / 35-Bag / Weighted | 7-Bag | Piece generation algorithm |
| ARE | On / Off | On | Entry delay (100 ms) with IRS/IHS buffering |
| Preview | 0 / 1 / 3 | 1 | Number of next pieces shown |
| Handicap | 0–5 | 0 | Initial garbage rows |
| Speed Mode | None / Easy / Normal / Medium / Hard / Crazy / Insane | Normal | Gravity curve preset |
| Ghost Piece | On / Off | On | Show piece landing preview |
| Piece Generator | Same as Generator | 7-Bag | (Duplicate — legacy) |

**Files:** `tetris/settings.py` — `GENERATOR_LABELS`, `SPEED_MODE_LABELS`, `DEFAULT_SETTINGS`

---

## Summary

**All Tetris Guideline rules implemented.** **All human/AI rule divergences fixed.** Single rule engine in `tetris/game/rules.py` serves both human gameplay (list-of-lists) and AI simulation (numpy). AI has full SRS wall kicks, hold, handicap persistence, and lock delay (in playing mode). Only intentional differences remain: AI episode flow (auto-restart, no leaderboard), curriculum learning, and replay mode.