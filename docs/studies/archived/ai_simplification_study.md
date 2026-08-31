# Study: Simplify `tetris/states/ai.py`

**Date:** 2026-08-19
**Status:** Implemented (commit on `v3`). Candidate generation extracted to `tetris/ai/candidates.py`, HUD rendering to `tetris/ai/hud.py`, dead code `_is_valid_placement` deleted. `ai.py` reduced from 723 to ~460 lines.

---

## 1. Executive Summary

`ai.py` is 723 lines — more than double the next-largest state file (`game.py` at 339, `human.py` at 143). The file mixes four distinct concerns in one class:

1. **Candidate generation** — enumerate valid piece placements (137 lines)
2. **RL transition management** — reward computation, delayed transition storage, n-step flush (51 lines)
3. **Episode lifecycle** — logging, curriculum, reset, model save/load (106 lines)
4. **HUD rendering** — training params table, stats table, last-5-moves (106 lines)

Plus `__init__` at 146 lines — the largest single method.

**Verdict: 3 actionable items, 1 dead-code removal, 2 extractions. Net reduction: ~300 lines from `ai.py`, zero behavior change.**

The previous `states_split_study.md` already identified this in its conclusion: *"If `ai.py`'s size is a concern, extract its helper logic into `tetris/ai/` rather than reorganizing the states package."* This study picks up that recommendation.

---

## 2. Current Method Inventory

| Lines | Method | Concern |
|-------|--------|---------|
| 146 | `__init__` | Init (31 params) |
| 73 | `_get_candidate_states` | Candidate generation |
| 69 | `_draw_ai_hud` | HUD rendering |
| 54 | `update` | Game loop |
| 51 | `_lock_and_spawn` | RL transitions |
| 48 | `_execute_macro_action` | Candidate execution |
| 33 | `_hud_table_rows` | HUD rendering |
| 32 | `_reset_episode` | Episode lifecycle |
| 26 | `_log_and_learn` | Episode lifecycle |
| 26 | `_best_next_placement` | Candidate generation |
| 15 | `_iter_column_positions` | Candidate generation |
| 14 | `_maybe_advance_curriculum` | Episode lifecycle |
| 13 | `_gen_placements` | Candidate generation |
| 11 | `_apply_epsilon_policy` | Episode lifecycle |
| 9 | `_on_episode_end` | Episode lifecycle |
| 7 | `_is_valid_placement` | **DEAD CODE** |
| 6 | `draw` | Rendering |
| 6 | `_trend_arrow` | HUD rendering |
| 6 | `_on_exit` | Episode lifecycle |
| **723** | **total** | |

---

## 3. Actionable Items

### 3.1 Dead Code: `_is_valid_placement` (7 lines)

**Current:** Method defined at line 222, never called in production code. Only referenced in `tests/test_ai_states.py` (2 assertions) and `docs/class_diagram.md`.

**Problem:** The method checks if a piece can be placed at a given column/rotation at spawn height. But `_gen_placements` and `_iter_column_positions` already cover this — they yield only valid placements. The method is redundant.

**Proposed:** Delete `_is_valid_placement`. Delete the `TestIsValidPlacement` test class (2 tests). Remove from `docs/class_diagram.md`.

**Impact:** -7 lines from `ai.py`, -13 lines from tests. No behavior change.

**Risk:** None. The method is dead code — no production caller exists.

---

### 3.2 HIGH: Extract Candidate Generation to `tetris/ai/candidates.py` (~150 lines)

**Current:** Five methods in `ai.py` handle candidate generation:
- `_iter_column_positions` (15 lines) — static, yields (shape, rot, px) per column/rotation
- `_best_next_placement` (26 lines) — simulates best next-piece placement (look-ahead)
- `_gen_placements` (13 lines) — yields valid placements via soft-drop BFS or hard-drop
- `_get_candidate_states` (73 lines) — orchestrates: enumerate, batch place+clear, lookahead, extract features
- `_is_valid_placement` (7 lines) — dead (see 3.1)

These methods are **pure functions** — they take a grid and piece type, return placements/features. They don't touch `AIState` instance state except `_candidate_placements` (the output list) and config flags (`soft_drop`, `lookahead`, `lookahead_depth`, `warm_start`). The only non-pure part is writing `self._candidate_placements`.

**Proposed:** Move to `tetris/ai/candidates.py` as module-level functions:

```python
# tetris/ai/candidates.py
"""Candidate placement generation for the DQN agent."""

def iter_column_positions(piece_type: str) -> Iterator[tuple[list[tuple[int,int]], int, int]]:
    """Yield (shape, rot, px) for every valid (rotation, column)."""

def best_next_placement(grid: np.ndarray, piece_type: str) -> np.ndarray:
    """Simulate best placement of next piece (Dellacherie look-ahead)."""

def gen_placements(base_grid: np.ndarray, piece_type: str, soft_drop: bool) -> Iterator[tuple]:
    """Yield (shape, px, py, rot) for all valid placements."""

def get_candidate_states(
    grid: np.ndarray,
    current_piece_type: str,
    hold_piece_type: str | None,
    next_piece_type: str,
    preview_types: list[str],
    can_hold: bool,
    soft_drop: bool,
    lookahead: bool,
    lookahead_depth: int,
) -> tuple[np.ndarray, list[int], np.ndarray, list[tuple[int,int,int,bool]]]:
    """Enumerate placements, simulate, extract features.
    Returns (candidates, actions, dellacherie_values, placements).
    """
```

`AIState._get_candidate_states` becomes a thin wrapper:
```python
def _get_candidate_states(self) -> tuple[np.ndarray, list[int], np.ndarray]:
    candidates, actions, dellvals, placements = get_candidate_states(
        board_to_grid(self.board), self.current_piece.type, ...
    )
    self._candidate_placements = placements
    return candidates, actions, dellvals
```

**Impact:**
- `ai.py` loses ~150 lines (5 methods → 1 thin wrapper)
- New file `tetris/ai/candidates.py` ~150 lines — pure functions, easy to test
- Tests: `TestIterColumnPositions`, `TestBestNextPlacement`, `TestGenPlacements`, `TestGetCandidateStates` import from `tetris.ai.candidates` instead of calling `ai._method()`. This is cleaner — they're testing pure functions, not instance methods that happen to not use `self`.

**Why this works:**
- These methods already don't use `self` meaningfully — `_iter_column_positions` is `@staticmethod`, `_best_next_placement` uses only `self._iter_column_positions` (its own static method), `_gen_placements` uses `self.soft_drop` and `self._iter_column_positions`. Only `_get_candidate_states` touches significant instance state.
- The extraction makes the purity explicit: you can see at a glance that candidate generation has zero coupling to pygame, audio, stats, or the FSM.
- `tetris/ai/` is the natural home — it already holds `agent.py`, `rewards.py`, `replay_buffer.py`, `trainer.py`. Candidate generation is an AI concern, not a state-machine concern.

**Risk:** Low. Tests need import updates (mechanical). No behavior change — the functions are pure. The one tricky part is `_get_candidate_states` writing `self._candidate_placements` — the extracted function returns it as a 4th tuple element instead.

**Test impact:**
- `test_ai_states.py`: 4 test classes change from `ai._method(args)` to `module_func(args)`. Simpler — no need to construct an `AIState` just to test a pure function. `TestGetCandidateStates` still needs an `AIState` because it reads `self.current_piece`, `self.next_piece`, etc.
- `test_curriculum.py`: 2 call sites change from `ai._get_candidate_states()` to `get_candidate_states(grid, ...)`.
- `test_rules_batch.py`: references `_best_next_placement` in a comment — update comment.

---

### 3.3 MEDIUM: Extract HUD Rendering to `tetris/ai/hud.py` (~115 lines)

**Current:** Four methods handle the AI HUD:
- `_draw_ai_hud` (69 lines) — training params + stats table
- `_hud_table_rows` (33 lines) — builds the 6-row stats table
- `_trend_arrow` (6 lines) — static, maps trend string to arrow symbol
- Last-5-moves rendering (inline in `_draw_ai_hud`, ~8 lines)

**Proposed:** Move to `tetris/ai/hud.py`:

```python
# tetris/ai/hud.py
"""AI training HUD rendering."""

def draw_ai_hud(screen, font, ai_state) -> None:
    """Render the AI training overlay."""

def _hud_table_rows(log, stats, episode_steps) -> list[list]:
    """Build the 6-row statistics table."""

def _trend_arrow(trend: str) -> str:
    """Convert trend string to arrow."""
```

`AIState.draw` calls `draw_ai_hud(self.screen, self.font, self)`.

**Impact:**
- `ai.py` loses ~115 lines
- New file `tetris/ai/hud.py` ~115 lines
- `AIState.draw` becomes 2 lines (super().draw + draw_ai_hud)

**Why this works:**
- HUD rendering is pure presentation — it reads state, draws text. No game logic.
- The function takes the `AIState` instance but only reads from it (episode, agent, log, stats, config flags). This is the same pattern as `Renderer.render_frame(self, particles)` — the renderer takes the full state object and reads what it needs.
- Keeps rendering concerns in the AI package, not the states package. The base `GameState.draw` delegates to `Renderer`; `AIState.draw` would delegate to `draw_ai_hud`. Same pattern.

**Risk:** Low. Tests `TestDrawAiHud`, `TestHudTableRows`, `TestTrendArrow` update imports — straightforward.

**Caveat:** This introduces a read-only dependency from `tetris/ai/hud.py` to `AIState`'s attribute surface. If `AIState`'s attributes change, the HUD function breaks. But this is already true today — the methods are on `AIState` and read the same attributes. Moving them doesn't change the coupling, just the location. To avoid circular imports, pass a lightweight struct or use `TYPE_CHECKING` + duck typing (the function takes `ai_state` as a protocol-like object, never importing `AIState`).

---

### 3.4 LOW: Simplify `__init__` via Config Dataclass (~15 lines saved)

**Current:** `__init__` takes 31 parameters (16 game + 15 AI-specific). The AI-specific params are stored as instance attributes and never mutated through a config object.

**Proposed:** Group AI hyperparameters into a frozen dataclass:

```python
@dataclass(frozen=True, slots=True)
class AIConfig:
    epsilon_decay: float = 0.999
    epsilon_end: float = 0.1
    lr: float = 1e-3
    gamma: float = 0.97
    batch_size: int = 64
    buffer_size: int = 50_000
    ai_mode: str = "learning"
    curriculum: bool = False
    curriculum_freq: int = 50
    curriculum_epsilon: str = "reset"
    warm_start: bool = True
    learn_per_action: int = LEARN_PER_ACTION
    lookahead: bool = True
    lookahead_depth: int = 3
    soft_drop: bool = True
    seed: int | None = None
    device: str = "auto"
```

**Impact:**
- `__init__` signature: 31 params → 15 game params + 1 `ai_config: AIConfig`
- Config access: `self.lookahead` → `self._ai_config.lookahead` (or unpack: `self.lookahead = ai_config.lookahead`)
- ~15 lines saved on signature; the body is unchanged (still unpacks to `self`).

**Verdict: Marginal.** The `__init__` is long because it has real work to do (curriculum setup, model loading, mode config). A config dataclass saves signature lines but adds a class definition + unpacking boilerplate. The real `__init__` complexity is the body, not the signature.

**Skip unless we're already touching `__init__` for another reason.**

---

## 4. After Refactoring: Expected `ai.py` Structure

```
ai.py (~300 lines, down from 723)
├── __init__              (146 → ~130, unchanged body)
├── _execute_macro_action  (48, unchanged — uses self.board/piece, genuine instance method)
├── _lock_and_spawn        (51, unchanged — RL transition capture, needs self)
├── update                (54, unchanged — game loop orchestration)
├── _on_episode_end        (9, unchanged)
├── _log_and_learn         (26, unchanged — episode logging + curriculum)
├── _reset_episode         (32, unchanged — state reset)
├── _maybe_advance_curriculum (14, unchanged)
├── _apply_epsilon_policy  (11, unchanged)
├── draw                   (6 → 3, delegates to hud.draw_ai_hud)
└── _on_exit               (6, unchanged)
```

**Remaining methods are genuinely instance methods** — they use `self.board`, `self.current_piece`, `self.agent`, `self.stats`, `self.audio`. They can't be extracted without passing the entire `AIState` as a parameter, which is just moving code without reducing coupling.

---

## 5. New Files

| File | Lines | Contents |
|------|-------|----------|
| `tetris/ai/candidates.py` | ~150 | `iter_column_positions`, `best_next_placement`, `gen_placements`, `get_candidate_states` |
| `tetris/ai/hud.py` | ~115 | `draw_ai_hud`, `_hud_table_rows`, `_trend_arrow` |

No sub-packages. No import path changes for external consumers (`from tetris.states.ai import AIState` stays the same).

---

## 6. Test Impact

| Test file | Change |
|-----------|--------|
| `test_ai_states.py` | `TestIsValidPlacement` deleted (dead code). `TestIterColumnPositions`, `TestBestNextPlacement`, `TestGenPlacements` call module functions instead of `ai._method()`. `TestGetCandidateStates` unchanged (still needs `AIState`). `TestDrawAiHud`, `TestHudTableRows`, `TestTrendArrow` call `tetris.ai.hud` functions. |
| `test_curriculum.py` | 2 call sites: `ai._get_candidate_states()` → `get_candidate_states(grid, ...)`. |
| `test_rules_batch.py` | Comment update only. |
| `test_game_state.py` | No change (doesn't touch AI methods). |
| `class_diagram.md` | Remove `_is_valid_placement` from AIState method list. |

**Net test change:** ~20 lines of import/call updates, 2 tests deleted.

---

## 7. What NOT to Do

### 7.1 Don't extract `_lock_and_spawn` / `update` / `_reset_episode`

These are the core FSM lifecycle methods. They orchestrate `self.board`, `self.current_piece`, `self.agent`, `self.stats`, `self.audio` in tight sequences. Extracting them to a module function that takes `ai_state` as a parameter would be code relocation, not simplification — same coupling, more indirection.

### 7.2 Don't split `AIState` into multiple classes

`AIState` is a single FSM state with a single responsibility (AI plays Tetris). Splitting it into `AIState` + `AITrainingManager` + `AICandidateGenerator` would create coordination overhead (who owns `self.agent`? who calls `_reset_episode`?) without reducing complexity. The class is 723 lines because the problem is 723 lines — the right move is to extract the pure-function helpers, not to fragment the state.

### 7.3 Don't use a config dataclass (3.4) unless `__init__` is already being touched

The signature is long but honest. A config object hides the params behind a layer of indirection. The body is where the real complexity is, and it's irreducible (curriculum setup, model loading, mode config).

---

## 8. Priority

| Priority | Change | Effort | Lines saved from `ai.py` | Behavior risk |
|----------|--------|--------|--------------------------|---------------|
| 1 | Delete `_is_valid_placement` (dead code) | Trivial | 7 | None |
| 2 | Extract candidate generation → `tetris/ai/candidates.py` | Small | ~150 | Low |
| 3 | Extract HUD rendering → `tetris/ai/hud.py` | Small | ~115 | Low |
| — | Config dataclass for `__init__` | Small | ~15 | Low (skip) |

**Total `ai.py` reduction: ~272 lines → ~450 lines.** The file goes from 2.1× the next-largest state to 1.3×.

---

## 9. Key Decisions

- **Extract to `tetris/ai/`, not `tetris/states/`:** Candidate generation and HUD rendering are AI concerns. The `tetris/ai/` package already houses the agent, rewards, replay buffer, and trainer. The states package should stay focused on FSM mechanics.
- **Module functions, not classes:** The extracted helpers are pure functions (candidate generation) or read-only renderers (HUD). They don't need state. A function module is the simplest container.
- **Avoid circular imports:** `tetris/ai/hud.py` takes `ai_state` as a duck-typed parameter (reads attributes, never imports `AIState`). `tetris/ai/candidates.py` takes primitives (grid, piece_type, flags) — no `AIState` dependency at all.
- **Keep `_execute_macro_action` on `AIState`:** It manipulates `self.current_piece`, `self.board`, `self.stats` — genuine instance state. Can't be cleanly extracted.
- **Dead code first:** `_is_valid_placement` is the cheapest win and should go first regardless of whether the extractions proceed.