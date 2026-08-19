# Study: Dataclass Usage to Simplify the Codebase

**Date:** 2026-08-19
**Status:** Implemented — `Transition`, `NStepTransition`, `ClearedRow`, `LineClearResult` (NamedTuple), `EpisodeRecord` (TypedDict), `GameStats` (@dataclass). See plan `dataclass-refactor-plan.md`.
**Scope:** Evaluate where `@dataclass` (stdlib `dataclasses`) would reduce boilerplate, improve readability, and clarify intent across the tetris codebase. No implementation — analysis only.

---

## 1. Summary

The codebase uses hand-written `__init__` methods across ~30 classes. Most of these classes are **behavioral** (state machines, game engines, audio managers) with complex initialization logic — dataclasses would not help there. However, a small set of **data-container** classes and patterns would benefit significantly.

**Verdict: 5 candidate areas, 3 high-value, 2 marginal. Total boilerplate reduction: ~60-80 lines.**

The biggest win is not line count but **clarity**: replacing opaque tuple indexing with named fields.

---

## 2. Candidate Areas

### 2.1 HIGH: PER Transition Tuple → NamedTuple

**File:** `tetris/ai/replay_buffer.py`, `tetris/ai/agent.py`

**Current:**
```python
# replay_buffer.py:62
self.buffer.append((state, action, reward, next_state, done, n))

# agent.py:149 — n-step return computation
s0, a0, _, _, _ = self._n_step_buffer[0]
for i, (_, _, ri, _, di) in enumerate(self._n_step_buffer):
    ...
sn = self._n_step_buffer[-1][3]
done_n = any(t[4] for t in self._n_step_buffer)

# agent.py:179 — batch sampling
states = np.array([t[0] for t in batch])
rewards = np.array([t[2] for t in batch])
next_states = np.array([t[3] for t in batch])
dones = np.array([t[4] for t in batch])
n_steps = np.array([t[5] for t in batch])
```

**Problem:** 6-element positional tuples indexed by magic number. `t[3]` is `next_state` only if you remember the order. This is the most opaque pattern in the codebase.

**Proposed:** `NamedTuple` (not `@dataclass` — frozen, zero memory overhead, tuple-compatible):

```python
class Transition(NamedTuple):
    state: np.ndarray
    action: int
    reward: float
    next_state: np.ndarray
    done: bool
    n: int
```

**Impact:**
- `t[3]` → `t.next_state`, `t[4]` → `t.done`
- NamedTuple is still a tuple: `np.array([t.state for t in batch])` works, no API change to the buffer
- Zero runtime cost (NamedTuple compiles to a C tuple)
- ~15 lines changed, readability improvement is massive

**Risk:** None. NamedTuple is a drop-in for tuple.

---

### 2.2 HIGH: Line-Clear Return Type → NamedTuple

**File:** `tetris/game/board.py`, `tetris/states/game.py`, `tetris/states/ai.py`

**Current:**
```python
# board.py:71
def lock_tetromino(self, tetromino) -> tuple[int, list[tuple[int, list]]]:
    ...
    return lines_cleared, cleared_rows_data

# board.py:103
def clear_lines(self) -> tuple[int, list[tuple[int, list]]]:
    ...
    return lines_cleared, cleared_rows_data

# game.py:205, 308, ai.py:407
cleared, rows_data = self.board.lock_tetromino(self.current_piece)
```

**Problem:** The type signature `tuple[int, list[tuple[int, list]]]` is unreadable. The inner `list[tuple[int, list]]` is `(row_index, list_of_cell_colors)` — you need the docstring to know this.

**Proposed:**
```python
class ClearedRow(NamedTuple):
    row_index: int
    cell_colors: list  # list of RGB tuples

class LineClearResult(NamedTuple):
    lines_cleared: int
    cleared_rows: list[ClearedRow]
```

**Impact:**
- Return type becomes `LineClearResult` instead of `tuple[int, list[tuple[int, list]]]`
- `cleared, rows_data` → `result.lines_cleared, result.cleared_rows`
- Particle emission: `for r_idx, colors in rows_data` → `for row in result.cleared_rows: row.row_index, row.cell_colors`
- ~10 lines changed, type signatures become self-documenting

**Risk:** Low. Only 3 call sites. NamedTuple is tuple-compatible so existing unpacking `cleared, rows_data = ...` still works unchanged if we don't want to update call sites immediately.

---

### 2.3 MEDIUM: TrainingLog Episode Record → TypedDict

**File:** `tetris/ai/trainer.py:54-65`

**Current:**
```python
self.episodes.append({
    "episode": episode,
    "score": score,
    "lines": lines,
    "level": level,
    "steps": steps,
    "epsilon": epsilon,
    "loss": loss,
    "timestamp": datetime.now(timezone.utc).isoformat(),
})
```

Then accessed everywhere as `e["score"]`, `e["lines"]`, etc.

**Problem:** No type safety on dict keys. A typo like `e["scroe"]` fails at runtime, not at type-check time. The 8-field dict is constructed identically every time.

**Proposed:** `TypedDict` (not dataclass — these are JSON-serialized dicts, must stay dicts):

```python
from typing import TypedDict

class EpisodeRecord(TypedDict):
    episode: int
    score: int
    lines: int
    level: int
    steps: int
    epsilon: float
    loss: float
    timestamp: str
```

**Impact:**
- Type checker catches `e["scroe"]` typos
- Construction becomes `EpisodeRecord(episode=episode, score=score, ...)`
- JSON serialization unchanged (it's still a dict)
- `_safe_sum`, `_safe_avg`, `_safe_max` all benefit from typed key access
- ~12 lines added, 1 line changed per constructor call

**Risk:** None. TypedDict is a dict subclass at runtime, JSON-compatible.

---

### 2.4 LOW: GameStats → Dataclass (Marginal)

**File:** `tetris/game/stats.py`

**Current:**
```python
class GameStats:
    def __init__(self) -> None:
        self.score = 0
        self.total_lines = 0
        self.level = 0
        self.piece_count = 0
        self.combo = -1
        self.b2b = False
```

**Analysis:** This is a mutable state container, not a value object. Dataclass would work but gains little:
```python
@dataclass
class GameStats:
    score: int = 0
    total_lines: int = 0
    level: int = 0
    piece_count: int = 0
    combo: int = -1
    b2b: bool = False
```

**Benefit:** Slightly cleaner field declarations, auto-generated `__repr__` (useful for debugging). But the class has 3 methods (`on_piece_locked`, `add_soft_drop`, `add_hard_drop`) that do real logic — it's not a pure data bag.

**Verdict:** Marginal. 2 lines saved on `__init__`, `__repr__` is nice-to-have. Only worth it if we also want `__repr__` or if other classes are being converted. Not worth a standalone change.

---

### 2.5 LOW: Tetromino → Dataclass (Marginal)

**File:** `tetris/game/tetromino.py`

**Current:**
```python
class Tetromino:
    def __init__(self, piece_type: str | None = None) -> None:
        self.type = piece_type if piece_type is not None else random.choice(...)
        self.color = SHAPES_COLORS[self.type]
        self.rotation = 0
        self.x = BOARD_WIDTH // 2 - 2
        self.y = 0
        self.shape = self.get_current_shape()
```

**Problem:** Dataclass doesn't fit well here:
- `self.type` has conditional initialization (random if None) — doesn't map to dataclass fields
- `self.shape` is derived from `self.type` and `self.rotation` — not an independent field
- `get_current_shape()`, `rotate()`, `move()`, `get_blocks()` are behavior, not data

**Verdict:** Skip. Dataclass would force awkward `__post_init__` for the conditional and derived fields, making it less readable than the current form.

---

## 3. Areas Explicitly Excluded

### 3.1 State Classes (State, GameState, HumanState, AIState, MenuState, etc.)

All FSM states have complex `__init__` with side effects (pygame setup, audio config, model loading, board creation). Dataclass adds nothing — these are behavioral classes, not data containers. Converting would require `__post_init__` of 30+ lines, strictly worse.

### 3.2 Board, PieceProvider, AudioManager, Renderer, ParticleSystem

Same reasoning — rich behavior, complex initialization with side effects. Dataclass is the wrong tool.

### 3.3 DQNAgent, DQNetwork, PrioritizedReplayBuffer

DQNetwork is `nn.Module` (PyTorch convention, not dataclass). DQNAgent and PER buffer have complex initialization logic with conditional branching and dependency construction.

### 3.4 ScoreEngine

Pure static methods, no instance state. Dataclass irrelevant.

### 3.5 Particle, _FallingPiece

Already use `__slots__` for memory efficiency (particles are spawned hundreds at a time). Converting to dataclass would lose `__slots__` benefit unless using `@dataclass(slots=True)`, but the current form is already clean and explicit.

---

## 4. Recommended Priority

| Priority | Change | File(s) | Effort | Readability Gain |
|----------|--------|---------|--------|-----------------|
| 1 | `Transition(NamedTuple)` | `replay_buffer.py`, `agent.py` | Small | **High** — eliminates 6 magic indices |
| 2 | `LineClearResult(NamedTuple)` | `board.py`, `game.py`, `ai.py` | Small | **High** — self-documenting return types |
| 3 | `EpisodeRecord(TypedDict)` | `trainer.py` | Small | **Medium** — type-safe dict keys |
| 4 | `GameStats @dataclass` | `stats.py` | Trivial | Low — marginal cleanup |
| 5 | `Tetromino @dataclass` | `tetromino.py` | N/A | Skip — wrong fit |

---

## 5. Key Decisions

- **NamedTuple over @dataclass for tuples (2.1, 2.2):** The values flow through tuple-unpacking and list comprehensions. NamedTuple preserves tuple semantics (unpackable, indexable, zero memory overhead) while adding named access. Dataclass would require rewriting all call sites.
- **TypedDict over @dataclass for episode records (2.3):** The records are JSON-serialized as plain dicts. TypedDict is the correct tool — it stays a dict at runtime while gaining static type checking.
- **Skip behavior-heavy classes:** Dataclass shines for data containers. When `__init__` does real work (pygame init, model loading, board setup), converting to dataclass makes the code less clear, not more.
- **Skip `__slots__`-optimized classes:** Particle already uses `__slots__`; converting to `@dataclass(slots=True)` is possible but adds no value over the current clean form.

---

## 6. File Inventory

No new files needed. All types would live in their existing module:

| Type | Location |
|------|----------|
| `Transition` | `tetris/ai/replay_buffer.py` (top-level, imported by `agent.py`) |
| `ClearedRow`, `LineClearResult` | `tetris/game/board.py` (top-level, imported by `states/game.py` and `states/ai.py`) |
| `EpisodeRecord` | `tetris/ai/trainer.py` (top-level, used internally) |