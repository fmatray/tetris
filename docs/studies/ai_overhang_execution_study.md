# Study: AI Overhang Handling and Macro-Action Execution

**Date:** 2026-08-19
**Status:** Analysis only — no implementation.

---

## 1. Executive Summary

The AI evaluates candidate placements and executes them via a simplified
macro-action sequence: rotate → move horizontally → drop vertically. This
sequence cannot replicate the full range of placements the BFS finds,
particularly under overhangs. The result is a mismatch: the agent evaluates
a board state assuming the piece reaches `(px, py)`, but the execution may
fall short and lock the piece in the wrong position.

This study maps the three candidate/execution paths, identifies where each
breaks down for overhangs, and proposes redesign options.

---

## 2. Background: The Overhang Bug

A prior bug (fixed in commit `c99a26a`) revealed that `hard_drop_y` scanned
from `y=0` downward, ignoring the piece's current position. A piece already
under an overhang would be teleported **on top of** the overhang instead of
dropping further down. The fix added a `start_y` parameter so `Board.hard_drop`
scans from the piece's current row.

That fix covers the **human** hard-drop path. The AI uses a different
execution model — macro-actions — which has its own overhang limitations,
unrelated to the `hard_drop_y` fix.

---

## 3. The Three AI Paths

### 3.1 Soft-Drop Candidate Generation (BFS)

**Code:** `soft_drop_placements` in `tetris/game/rules.py`, called when
`soft_drop=True` (the default in both training and playing).

The BFS explores `(x, y, rotation)` states from spawn, trying left, right,
soft-drop, and both rotation directions (with SRS wall kicks). Any state
where the piece can't drop further is recorded as a landing placement.

**Overhang capability:** Full. The BFS explores all reachable positions,
including those under overhangs. The docstring states: *"This includes
placements under overhangs that hard-drop cannot reach."*

**The catch:** The BFS finds *reachable* positions, but doesn't record the
*path* to reach them. An overhang placement may require interleaving drops
with rotations or horizontal moves (e.g., drop partway, rotate, slide left,
drop more). The BFS proves the position is reachable; the execution must
reconstruct the path.

### 3.2 Hard-Drop Candidate Generation

**Code:** `gen_placements` in `tetris/ai/candidates.py`, `else` branch when
`soft_drop=False`.

Iterates all `(rotation, column)` pairs, calls `hard_drop_y(grid, shape, px)`
with `start_y=0` (default), and yields the landing position.

**Overhang capability:** None. Hard-drop from spawn can only land on top of
the highest obstruction in each column. Under-overhang placements are
invisible to this path.

### 3.3 Macro-Action Execution

**Code:** `_execute_macro_action` in `tetris/states/ai.py` (lines 237–281).

After the agent selects a candidate, the execution follows a fixed sequence:

1. **Hold** (if the candidate requires it)
2. **Rotate** to target rotation (CW only, with SRS wall kicks)
3. **Move horizontally** to target column (one cell at a time, collision-checked)
4. **Drop** to target row:
   - `soft_drop=True`: soft-drop vertically (`while piece.y < py`) — locks via
     lock delay in `super().update()`
   - `soft_drop=False`: `board.hard_drop(piece)` then immediate
     `_lock_and_spawn(hard_drop=True)`

**The gap:** Steps 2–4 are strictly sequential. The piece rotates and moves
at its current height, then drops straight down. There is no interleaving
of drop with rotation or horizontal movement. If a placement requires:

- Drop partway, then rotate (to fit under a ledge)
- Drop, slide horizontally under an overhang, then drop more
- Rotate into a niche from above

...the execution cannot reproduce it. The `while piece.y < py` loop stops
when the piece collides, leaving it short of the target.

### 3.4 Normal Gravity (Inherited)

Not used for AI placement decisions. `super().update()` runs gravity between
AI decisions, but the AI has already positioned the piece via macro-action.
Gravity respects overhangs correctly (step-by-step collision), but it's not
the placement mechanism.

---

## 4. The Execution Mismatch

The core problem is a **contract violation** between candidate generation and
execution:

| Component | Assumes | Reality |
|---|---|---|
| Candidate generation (BFS) | Placement at `(px, py)` is reachable | True — BFS proves it |
| Feature extraction / V-network | Board state after placing at `(px, py)` | Computed from simulated placement |
| Macro-action execution | Piece will arrive at `(px, py)` | **False for overhang placements** — simplified sequence can't follow the BFS path |

When execution fails to reach `py`, the piece locks wherever it gets stuck.
The agent receives a reward for a board state it never actually achieved —
the simulated placement differs from the real one. This poisons the learning
signal: the V-network learns from transitions where the action label doesn't
match the observed outcome.

---

## 5. Severity Assessment

**How often does this matter?**

Overhang placements are a minority of all placements in typical Tetris play.
Most pieces land on top of the stack in open columns. The mismatch only
manifests when:

1. The BFS finds an under-overhang placement
2. The V-network selects it as the best candidate
3. The execution can't reach it

In early training (random epsilon-greedy), condition 2 is hit randomly. As
the network learns, it may learn to *avoid* overhang placements because they
yield unpredictable rewards (the piece lands in the wrong spot), creating a
negative feedback loop: the agent avoids overhangs because execution fails,
and execution fails because the agent never trains on successful overhang
placements.

**Impact on training quality:** Moderate. The agent learns a subset of
Tetris — flat stacking without overhang utilization. It can still clear
lines and score, but misses T-spin setups, overhang-based combos, and
efficient well-filling.

**Impact on playing mode:** The same execution path is used. A trained
model that somehow learned to prefer overhang placements would mis-execute
them in playing mode too.

---

## 6. Redesign Options

### Option A: Record and Replay BFS Paths

**Change:** `soft_drop_placements` returns the path (sequence of moves) to
each placement, not just the final `(x, y, rot)`. `_execute_macro_action`
replays the path step by step.

**Pros:**
- Exact reproduction of BFS-reachable placements
- No execution mismatch — the path is proven reachable
- Overhang placements work correctly

**Cons:**
- `soft_drop_placements` return type changes (adds path data)
- Execution becomes step-by-step (slower in real-time, but AI already runs
  at macro-action speed — one piece per decision)
- Path storage increases memory per candidate (minor — paths are short)
- Hard-drop path still can't find overhangs (unchanged, but less relevant
  since soft-drop is the default)

**Effort:** Medium. BFS already explores the path; recording it is a matter
of storing parent pointers or the move sequence in the frontier.

### Option B: Execution-Time BFS (On-Demand Pathfinding)

**Change:** Keep candidate generation as-is (final positions only). When
executing, run a fresh BFS from the current piece position to the target
`(px, py, rot)` to find a valid move sequence.

**Pros:**
- Candidate generation unchanged — no API breakage
- Path found only for the selected candidate (not all candidates)
- Clean separation: candidate generation evaluates, execution navigates

**Cons:**
- Extra BFS per piece (small — board is 10×22, state space is tiny)
- Target may be unreachable from current position if hold/rotation state
  differs from what candidate generation assumed (edge case)
- More complex than Option A

**Effort:** Medium. A targeted BFS from current state to target state is
straightforward but adds a new code path.

### Option C: Simplify — Drop Overhang Candidates

**Change:** Filter out placements from `soft_drop_placements` that can't be
reached by the simplified macro-action sequence (rotate → move → drop).

**Pros:**
- Eliminates the mismatch — execution always reaches `py`
- Simplest change: a post-filter on BFS results
- Training signal stays clean (evaluated state = actual state)

**Cons:**
- AI permanently loses overhang capability
- Reduces placement space — fewer candidates, weaker play
- The filter itself is non-trivial: determining "can rotate→move→drop reach
  this?" requires checking that the piece can rotate and move at spawn height
  without collision, then drop straight to `py`

**Effort:** Low-Medium. The filter logic is the tricky part — it's
essentially simulating the macro-action sequence for each candidate.

### Option D: Full Move Sequence Execution (Tetris Bot Standard)

**Change:** Replace the simplified macro-action with a full move planner.
Candidate generation produces a move sequence (list of atomic actions:
rotate, left, right, soft-drop, hard-drop). Execution replays it.

This is how competitive Tetris bots (e.g., TETRIS-Python, Zeta) work — they
plan a full move sequence, not just a target position.

**Pros:**
- Complete overhang support
- No mismatch between evaluation and execution
- Foundation for more advanced techniques (T-spins, perfect clears)

**Cons:**
- Largest refactor — changes candidate generation, execution, and the
  action representation
- Move sequences are longer than `(rot, px, py, hold)` — more data to store
  and manage
- Hard-drop mode would need a separate path (or be removed)

**Effort:** High. Full redesign of the candidate→execution pipeline.

---

## 7. Recommendation

**Option A (Record and Replay BFS Paths)** is the best balance of
correctness, effort, and minimal disruption.

The BFS already explores the full path to each placement — it just discards
it. Recording parent pointers or the move sequence in the frontier is a
small change to `soft_drop_placements`. Execution replays the path, which
guarantees the piece reaches `(px, py, rot)`.

Option C (filter overhang candidates) is a tempting quick fix but permanently
cripples the AI. Option D is the "right" long-term design but is a large
refactor better suited to a dedicated AI overhaul.

**Priority:** Low-Medium. The AI currently trains and plays acceptably
without overhang support. The mismatch degrades learning quality but doesn't
prevent convergence. It should be fixed before investing in advanced
techniques (T-spins, perfect clears) that depend on overhang placement.

---

## 8. Affected Files

| File | Role | Change (Option A) |
|---|---|---|
| `tetris/game/rules.py` | `soft_drop_placements` | Return path data alongside placement |
| `tetris/ai/candidates.py` | `gen_placements`, `get_candidate_states` | Propagate path data through the pipeline |
| `tetris/states/ai.py` | `_execute_macro_action` | Replay path instead of rotate→move→drop |
| `tetris/ai/rewards.py` | Feature extraction | Unchanged — still operates on final board state |
| `tests/test_rules_batch.py` | BFS tests | Update for new return type |
| `tests/test_ai_states.py` | AI state tests | Update if execution behavior changes |

---

## 9. Open Questions

1. **Hold interaction:** When the AI holds a piece, the candidate generation
   re-runs for the held piece. Does the BFS path account for the hold, or
   does it assume spawn position? Current code holds first, then executes —
   the path should start from the held piece's spawn, not the original.

2. **Lock delay gaming:** The BFS finds positions where the piece can't drop
   further. In execution, lock delay allows the piece to rotate/move after
   grounding. Should the BFS exploit lock delay resets for even more
   placements (e.g., infinite spin to slide under an overhang)? Currently it
   doesn't — it only explores positions reachable while the piece is falling.

3. **Speed impact:** Option A adds path replay (multiple moves per piece
   instead of 3 steps). In `speed="fast"` mode, this is negligible (no
   rendering delay). In `speed="normal"` mode (80ms throttle), the path
   replay happens within a single frame — no visible difference. Training
   speed is unaffected since the bottleneck is `learn()`, not execution.

4. **Hard-drop mode future:** If soft-drop with path replay becomes the
   default, is there any reason to keep `soft_drop=False` (hard-drop mode)?
   It produces fewer candidates and can't reach overhangs. It may be
   candidates for deprecation.