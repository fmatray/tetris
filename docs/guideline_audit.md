# Tetris Guideline Compliance Audit

Source: [harddrop.com/wiki/Tetris_Guideline](https://harddrop.com/wiki/Tetris_Guideline)

Date: 2026-08-14

## Indispensable rules — missing or incomplete

### 1. 22-row board (20 visible + 2 hidden)

**Status:** ❌ Missing

**Current:** `BOARD_HEIGHT = 20` (`settings.py:21`) — no hidden buffer. Pieces spawn at y=0 in visible area.

**Guideline:** Playfield is 10 cells wide and at least 22 cells tall, rows above 20 hidden/obstructed.

**Impact:** Structural change to `BOARD_HEIGHT`, spawn position, rendering. Blocks top-out-on-lock-above-visible.

---

### 2. SRS wall kicks for human play

**Status:** ❌ Missing

**Current:** SRS kick tables exist only in `tetris/ai/rewards.py:411-431` (AI candidate generation). Human `_rotate_cw`/`_rotate_ccw` (`game.py:114-126`) do a single `is_valid_move` — if rotation fails, it's blocked. No kick attempts.

**Guideline:** SRS specifies tetromino rotation with wall kicks.

**Impact:** Player can't T-spin, wall-slide, or recover from edge-locked rotations.

---

### 3. Hold piece

**Status:** ❌ Missing

**Current:** No hold mechanism anywhere in the codebase.

**Guideline:** Press button → swap falling piece with held piece; can't hold again until lock.

**Impact:** New UI panel, keybind, state tracking, swap logic.

---

### 4. Non-locking soft drop

**Status:** ✅ Compliant

**Current:** `game.py` — when `down_pressed`, `update()` accelerates gravity via `SOFT_DROP_FACTOR`; piece locks only via lock delay.

**Guideline:** Non-locking soft drop (accelerated gravity, piece doesn't lock until it rests naturally).

**Impact:** Soft drop is decoupled from `_lock_and_spawn` — pieces lock only via lock delay, not on soft-drop contact.

---

### 5. Lock delay (~0.5s with reset on move/rotate)

**Status:** ❌ Missing

**Current:** `game.py:230-231` — when piece can't move down, `_lock_and_spawn()` fires immediately on the same tick.

**Guideline:** ~0.5s lock delay allowing floor-slide maneuvers; resets on move/rotate.

**Impact:** New timer in `update()`, reset logic on piece movement.

---

### 6. Top-out on lock above visible field

**Status:** ⚠️ Partial

**Current:** `game.py:155-156` only checks spawn overlap. "Locks completely above visible field" can't trigger because there are no hidden rows.

**Guideline:** Top out when piece spawns overlapping, OR locks completely above visible field.

**Impact:** Depends on 22-row board (#1) being implemented first.

---

### 7. 4 rotation states for I/S/Z

**Status:** ⚠️ Partial

**Current:** `SHAPES` in `settings.py:42-64`: I/S/Z have only 2 rotation states (should be 4 in SRS). J/L/T have 4, O has 1.

**Guideline:** SRS defines 4 rotation states per piece (except O).

**Impact:** Add 180° states, update kick tables for I, S, Z.

---

## Indispensable rules — already compliant

| Rule | Status | Evidence |
|------|--------|----------|
| Playfield 10 wide | ✅ | `BOARD_WIDTH = 10` |
| Tetromino colors | ✅ | All 7 match guideline exactly |
| Spawn locations | ✅ | All spawn at x=3 (SRS standard); J/L/T flat-side first |
| Random Generator (7-bag) | ✅ | `PieceProvider` with `generator="7bag"`, default |
| Ghost piece | ✅ | Setting + `draw_ghost()` in renderer |
| Level up by clearing lines | ✅ | `level = total_lines // 10` |
| Korobeiniki song | ✅ | MIDI file present in `media/` |
| Soft drop speed | ✅ | `SOFT_DROP_FACTOR = 0.1` (10× gravity) |

---

## Recommended (non-mandatory) — missing

### 8. 3+ piece preview queue

**Status:** ⚠️ Only 1 preview

**Current:** `game.py:77` — only `self.next_piece`. Renderer draws one next piece.

**Guideline:** Display at least 3 next-coming tetrominoes.

**Impact:** Expand `next_piece` to a preview queue, update renderer.

---

### 9. T-Spin detection & rewarding

**Status:** ❌ Missing

**Current:** No T-Spin detection. Only referenced as AI hyperparam label text.

**Guideline:** 3-corner T rule (2005) or 3-corner T no kick (2006) + scoring bonus.

**Impact:** Detection logic in `_lock_and_spawn`, bonus scoring in `ScoreEngine`.

---

### 10. Back-to-Back chains

**Status:** ❌ Missing

**Current:** No B2B tracking in `GameStats` or `ScoreEngine`.

**Guideline:** Reward consecutive T-Spin/Tetris clears with ×1.5 bonus.

**Impact:** Track last clear type, apply multiplier in scoring.

---

### 11. DAS (Delayed Auto Shift)

**Status:** ❌ Missing

**Current:** `game.py:193` — one `KEYDOWN` = one cell move. No auto-repeat with initial delay + repeat rate. Holding left/right moves 1 cell only.

**Guideline:** DAS no faster than Tetris Zone.

**Impact:** Key-hold auto-shift with configurable delay/resolution in `update()`.