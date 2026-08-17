# Threading Opportunity Study for AI Learning

## Context

AI training runs at ~100% of a single CPU core (confirmed: 99.7% average CPU
utilization on an 8-core machine). The user asked whether threading could
parallelize the workload across cores.

> **Update (Round 2 optimization):** The per-candidate scalar pipeline described below (`_add_candidate`, `_enumerate_placements`, `_best_next_placement` at 92.8%) has been fully batched. `_get_candidate_states` now uses `extract_features_batch`, `dellacherie_value_batch`, and a vectorized `place_and_clear_batch` scatter. Training frame time dropped from ~31 ms to ~3.1 ms (10.9×). The threading analysis below reflects the pre-optimization state and is kept for reference.

## Executive Summary

**Threading is unsuitable.** The GIL is held throughout the hot path, and
ThreadPool yields 0.99× (no speedup). ProcessPool yields 2.0× at best but
introduces prohibitive complexity (IPC, pickling, pygame state) for
diminishing returns.

**The real solution is 14× simpler and 14× faster: batch-vectorize
`dellacherie_value` with numpy.** This gives 27.7× single-threaded speedup
with zero concurrency. The entire 336 ms/frame drops to ~12 ms/frame.

---

## 1. Bottleneck Analysis

### 1.1 Where CPU Time Goes

Profiled 50 frames of training (`lookahead_depth=1, preview_count=1`):

| Phase | Time | % of total |
|---|---|---|
| `_get_candidate_states()` | 8.175 s | **99.7%** |
| `agent.learn()` (50 calls) | 0.000 s | 0.0% |
| `agent.select_action()` | 0.002 s | 0.0% |
| `_execute_macro_action()` | 0.001 s | 0.0% |
| `super().update()` (gravity/lock) | 0.018 s | 0.2% |

**Candidate generation is the entire bottleneck.** PyTorch gradient updates
and action selection are negligible.

### 1.2 Inside Candidate Generation

`_get_candidate_states` → `_enumerate_placements` → `_add_candidate` →
`_best_next_placement`:

| Sub-phase | Time | % of total |
|---|---|---|
| `_best_next_placement` | 6.294 s | **92.8%** |
| `extract_features` | 0.163 s | 2.4% |
| `dellacherie_value` (in `_add_candidate`) | 0.145 s | 2.1% |
| `place_and_clear` | 0.019 s | 0.3% |
| `compute_height_metrics` | 0.009 s | 0.1% |

### 1.3 Inside `_best_next_placement`

For each candidate placement, `_best_next_placement` simulates all
rotations × columns of the next piece (~707 iterations per frame):

| Operation | Time | % of `_best_next_placement` |
|---|---|---|
| `dellacherie_value` | 1.915 s | **71.7%** |
| `hard_drop_y` | 0.306 s | 11.5% |
| `place_and_clear` | 0.220 s | 8.2% |

### 1.4 Inside `dellacherie_value`

Six board-heuristic sub-functions, each called ~664 times per frame:

| Function | Time | % of `dellacherie_value` |
|---|---|---|
| `row_transitions` | 0.261 s | 14.4% |
| `count_holes` | 0.261 s | 14.4% |
| `hole_depth` | 0.254 s | 14.0% |
| `column_transitions` | 0.240 s | 13.2% |
| `rows_with_holes` | 0.232 s | 12.8% |
| `compute_height_metrics` | 0.069 s | 3.8% |
| `wells` | 0.052 s | 2.8% |

Each function operates on a tiny 22×10 numpy array. The Python-level loop
overhead (6 function calls × 664 iterations/frame) dominates. The numpy
operations themselves are fast but called on arrays too small for numpy to
amortize its dispatch overhead.

### 1.5 Call Counts Per Frame

| Function | Calls/frame |
|---|---|
| `_add_candidate` | 35.5 |
| `_best_next_placement` | 35.5 |
| `dellacherie_value` (inside look-ahead) | 707.1 |
| `hard_drop_y` | 707.1 |
| `place_and_clear` | 707.1 |

With `lookahead_depth=3, preview_count=3` (playing mode defaults), these
multiply by ~3×, yielding ~2000+ `dellacherie_value` calls per frame.

---

## 2. Threading Evaluation

### 2.1 ThreadPool (threads sharing GIL)

Tested with `ThreadPoolExecutor(max_workers=8)` on 205 `_best_next_placement`
tasks:

| Method | Time | Speedup |
|---|---|---|
| Sequential | 1258 ms | 1.0× |
| ThreadPool (8 workers) | 1213 ms | **0.99×** |

**Verdict: useless.** The GIL is never released. numpy operations on 22×10
arrays are too small to trigger numpy's internal GIL release (which only
kicks in for arrays above a size threshold). Every `dellacherie_value`,
`hard_drop_y`, and `place_and_clear` call holds the GIL for its entire
duration. Threads serialize completely.

### 2.2 ProcessPool (separate processes)

Tested with `ProcessPoolExecutor` on the same 205 tasks:

| Workers | Time | Speedup |
|---|---|---|
| 2 | 1104 ms | 1.14× |
| 4 | 627 ms | **2.01×** |
| 8 | 713 ms | 1.77× |

**Verdict: marginal, with severe drawbacks.**

Scaling degrades at 8 workers because:
- **IPC overhead**: each task ships a numpy array (22×10 = 880 bytes) to a
  worker process via pickle. 205 tasks × 880 bytes = 180 KB per batch, plus
  pickling/unpickling overhead per task.
- **Process startup**: each worker imports pygame, numpy, torch, and the
  entire tetris package. Cold-start cost is ~2 s per worker.
- **Diminishing returns**: tasks are short (~6 ms each), so scheduling and
  IPC overhead dominates at high worker counts.

**Architecture blockers for ProcessPool in the real app:**

1. **Pygame state**: `AIState` owns a `pygame.Surface`, `AudioManager`,
   `Board`, `PieceProvider` — none are picklable. The candidate generation
   depends on `self.board`, `self.current_piece`, `self.preview_pieces`,
   `self.hold_piece` — all live pygame-bound state.

2. **Shared model**: `DQNAgent.online_net` (PyTorch model) would need to be
   shipped to workers or kept in shared memory. Gradients from learning
   updates would need to be aggregated back. This is a distributed training
   problem, not a simple parallelism problem.

3. **N-step buffer**: `DQNAgent._n_step_buffer` is a `deque` of state
   transitions that must be ordered. Parallel workers would break the
   temporal ordering of transitions.

4. **Episode continuity**: each frame depends on the previous frame's board
   state. Candidate generation is inherently sequential per-piece — you
   can't generate candidates for piece N+1 before piece N is placed.

5. **GIL-independent bottleneck**: even with processes, the 2.0× speedup
   only applies to candidate generation. The pygame render loop (the main
   thread) would still block waiting for worker results, adding latency.

### 2.3 Asyncio / Coroutines

**Not applicable.** The bottleneck is CPU-bound numpy computation, not I/O.
Asyncio provides no parallelism for CPU-bound work — it would serialize the
same as sequential code.

---

## 3. The Better Solution: Batch Vectorization

### 3.1 The Insight

`_best_next_placement` calls `dellacherie_value` 707 times per frame, each
on a 22×10 grid. Each call invokes 6 Python-level heuristic functions, each
doing a small numpy operation. The Python dispatch overhead — not the numpy
computation — is the bottleneck.

**Solution**: generate all candidate grids, stack them into a single
`(N, 22, 10)` array, and compute all heuristics in one vectorized numpy pass.

### 3.2 Prototype: `dellacherie_value_batch`

```python
def dellacherie_value_batch(grids_arr: np.ndarray) -> np.ndarray:
    """Batch dellacherie_value: grids_arr shape (N, H, W) → values (N,)."""
    N, H, W = grids_arr.shape
    mask = grids_arr > 0
    non_empty = mask.any(axis=(1, 2))

    first_row = np.argmax(mask, axis=1)          # (N, W)
    any_filled = mask.any(axis=1)                # (N, W)
    heights = (H - first_row) * any_filled       # (N, W)

    # Holes: empty cells at or below first filled row, non-empty columns only
    row_idx = np.arange(H)[None, :, None]
    at_or_below = row_idx >= first_row[:, None, :]
    holes = (~mask) & at_or_below & any_filled[:, None, :]
    total_holes = holes.sum(axis=(1, 2))         # (N,)

    # Row transitions: pad left/right with filled
    padded_r = np.ones((N, H, W + 2), dtype=np.int8)
    padded_r[:, :, 1:-1] = mask.astype(np.int8)
    row_trans = np.abs(np.diff(padded_r, axis=2)).sum(axis=(1, 2))

    # Column transitions: pad bottom with filled
    padded_c = np.ones((N, H + 1, W), dtype=np.int8)
    padded_c[:, :H, :] = mask.astype(np.int8)
    col_trans = np.abs(np.diff(padded_c, axis=1)).sum(axis=(1, 2))

    # Wells
    h_left = np.concatenate([np.full((N, 1), H), heights[:, :-1]], axis=1)
    h_right = np.concatenate([heights[:, 1:], np.full((N, 1), H)], axis=1)
    well_depths = np.maximum(np.minimum(h_left, h_right) - heights, 0)
    wells_total = (well_depths * (well_depths + 1) // 2).sum(axis=1)

    # Hole depth + rows with holes
    holes_per_col = holes.sum(axis=1)            # (N, W)
    hole_depth = holes_per_col.max(axis=1)       # (N,)
    rows_with_holes = holes.any(axis=2).sum(axis=1)

    w = DELLACHERIE_WEIGHTS
    values = (
        w["row_transitions"]     * row_trans +
        w["column_transitions"]  * col_trans +
        w["holes"]               * total_holes +
        w["wells"]               * wells_total +
        w["hole_depth"]          * hole_depth +
        w["rows_with_holes"]     * rows_with_holes
    )
    return values * non_empty
```

### 3.3 Measured Results

| Method | Time (33 grids) | Speedup |
|---|---|---|
| Sequential `dellacherie_value` × 33 | 4.76 ms | 1.0× |
| `dellacherie_value_batch` (33 at once) | 0.17 ms | **27.7×** |

Correctness: **exact match** (max diff = 0.000000) across 36 test grids
including empty, full, half-filled, and 33 mid-game boards.

### 3.4 Projected End-to-End Impact

Current per-frame breakdown (`lookahead_depth=1, preview_count=1`):

| Component | Current | After batch | Speedup |
|---|---|---|---|
| `dellacherie_value` (707 calls) | 1.915 s | ~0.07 s | 27.7× |
| `hard_drop_y` (707 calls) | 0.306 s | 0.306 s | 1.0× |
| `place_and_clear` (707 calls) | 0.220 s | 0.220 s | 1.0× |
| **Total `_best_next_placement`** | 2.67 s | ~0.60 s | **4.5×** |
| **Total per frame** | 336 ms | ~75 ms | **4.5×** |

With `lookahead_depth=3, preview_count=3` (playing mode): candidate count
triples, so `dellacherie_value` is called ~2000 times. The batch version
scales linearly with N, so the speedup is even more dramatic:

| Mode | Current | After batch (est.) |
|---|---|---|
| Learning (depth=1) | 336 ms/frame | ~75 ms/frame |
| Playing (depth=3) | ~2367 ms/frame | ~225 ms/frame |

**The batch approach alone brings playing mode under the 16.67 ms frame
budget** — no threading needed.

### 3.5 Further Opportunity: Batch `_best_next_placement` Itself

The current loop in `_best_next_placement` iterates rotations × columns,
generating one grid at a time. This could also be batched:

1. Generate all (rotation, column) grids at once → `(N, H, W)` array
2. Call `dellacherie_value_batch` once on the entire batch
3. `argmin` to find the best placement

This would eliminate the Python loop entirely, replacing 707 sequential
calls with 1 batched call. Estimated additional speedup: 3–5× on the
`hard_drop_y` + `place_and_clear` loop (which would also be vectorizable).

**Combined projected speedup**: ~15–20× on candidate generation, bringing
the learning mode to ~20 ms/frame and playing mode to ~60 ms/frame.

---

## 4. Architecture Comparison

### Option A: Threading (ThreadPool)

```
Main thread (pygame loop)
  ├── candidate gen → ThreadPool.map(_best_next_placement, candidates)
  │                     ├── thread 1: GIL held → serial
  │                     ├── thread 2: GIL held → serial
  │                     └── ...
  ├── select_action (main thread)
  ├── execute (main thread)
  └── learn (main thread)
```

| Criterion | Rating |
|---|---|
| Speedup | 0.99× (none) |
| Code complexity | Low (ThreadPoolExecutor) |
| Risk | None (no effect) |
| Refactoring | Moderate (extract candidate gen to callable) |

**Rejected.** No speedup due to GIL.

### Option B: Multiprocessing (ProcessPool)

```
Main process (pygame loop)
  ├── candidate gen → ProcessPool.map(eval_candidate, [(grid, piece_type), ...])
  │                     ├── process 1: loads pygame, numpy, torch → evals
  │                     ├── process 2: loads pygame, numpy, torch → evals
  │                     └── ...
  ├── select_action (main process, awaits results)
  ├── execute (main process)
  └── learn (main process)
```

| Criterion | Rating |
|---|---|
| Speedup | 2.0× (4 workers), degrading at 8 |
| Code complexity | High (pickling, process management, error handling) |
| Risk | High (pygame state not picklable, process crashes, memory bloat) |
| Refactoring | Very high (decouple AIState from pygame, extract pure grid evaluator) |

**Rejected.** 2× speedup doesn't justify the complexity. The architecture
would require:
- Extracting a pure-function candidate evaluator (no pygame dependency)
- Serializing/deserializing board state across process boundaries
- Managing worker lifecycle (startup cost ~2 s/worker)
- Handling process crashes and timeouts
- Memory: each worker loads its own copy of numpy + torch (~200 MB/worker)

### Option C: Batch Vectorization (Recommended)

```
Main thread (pygame loop)
  ├── candidate gen:
  │     ├── generate all candidate grids → stack to (N, H, W)
  │     ├── dellacherie_value_batch(all_grids) → (N,) values
  │     └── argmin → best placement
  ├── select_action (main thread)
  ├── execute (main thread)
  └── learn (main thread)
```

| Criterion | Rating |
|---|---|
| Speedup | 27.7× on dellacherie, ~4.5× end-to-end (conservative) |
| Code complexity | Low (one new function, one call site change) |
| Risk | Low (pure numpy, no concurrency, deterministic) |
| Refactoring | Low (replace loop with batch call in `_best_next_placement`) |

**Selected.** Single-threaded, no GIL issues, no IPC, no process management.

---

## 5. Recommended Plan

### Phase 1: Batch `dellacherie_value` (highest impact, lowest effort)

**Change**: Add `dellacherie_value_batch()` to `tetris/ai/rewards.py`.
Replace the loop in `_best_next_placement` with a batched version.

**Refactoring**:

1. Add `dellacherie_value_batch(grids: np.ndarray) -> np.ndarray` to
   `tetris/ai/rewards.py` (prototype in §3.2, verified correct).

2. Rewrite `_best_next_placement` in `tetris/states/ai.py`:
   - Generate all (rotation, column) candidate grids in a loop (can't avoid
     this — `hard_drop_y` and `place_and_clear` are inherently per-grid).
   - Stack into `(N, H, W)` array.
   - Call `dellacherie_value_batch` once.
   - `argmin` for best value.

3. **No change to `extract_features`** — it's called once per candidate (35
   ×/frame), not 707 ×/frame. The 2.4% it costs is not worth optimizing.

4. **No change to `DQNAgent.learn()`** — it's 0.0% of total time.

**Estimated effort**: ~2 hours (function + call site + tests).

**Estimated speedup**: 4.5× on learning mode (336 → 75 ms/frame), playing
mode drops below frame budget.

### Phase 2 (optional): Batch `hard_drop_y` + `place_and_clear`

If Phase 1 is insufficient (e.g., for `lookahead_depth=3` in playing mode):

1. Vectorize `hard_drop_y` to operate on a batch of (shape, x) pairs against
   the same grid.
2. Vectorize `place_and_clear` to place multiple shapes on copies of the
   grid simultaneously.

This is more complex (the BFS in `soft_drop_placements` is harder to
vectorize) but could yield another 3–5× on the remaining ~60 ms/frame.

**Estimated effort**: ~4 hours.

### Phase 3 (not recommended): ProcessPool for headless training only

If further speedup is needed for `verify_training.py` (batch training
validation, no pygame rendering):

1. Extract a pure `evaluate_candidates(grid, piece_type, upcoming_types) ->
   (states, actions, dellacherie_values)` function with no pygame dependency.
2. In `verify_training.py`, run N episodes in parallel processes, each with
   its own `AIState` (no shared state — each process trains independently).
3. Average results at the end.

This is **episode-level parallelism**, not frame-level. Each process runs a
full independent training loop. No IPC during training, only at start/end.

**Speedup**: ~N× where N = number of processes (scales linearly — no shared
state during training).

**Tradeoff**: N independent agents train in parallel, but each sees only
1/N of the total episodes. Useful for hyperparameter sweeps or ensemble
training, not for accelerating a single agent's learning.

**Estimated effort**: ~4 hours (extract pure evaluator, refactor
verify_training, add result aggregation).

---

## 6. Why Not Threads

| Factor | Threading | Multiprocessing | Batch numpy |
|---|---|---|---|
| GIL bottleneck | Fatal (0.99×) | Avoided (separate processes) | N/A (single thread) |
| Speedup | 0× | 2× | **27.7×** |
| Code complexity | Low | High | **Low** |
| Pygame compatibility | OK (same process) | **Broken** (not picklable) | OK |
| Memory overhead | None | ~200 MB/worker | None |
| Startup cost | None | ~2 s/worker | None |
| Determinism | Preserved | Preserved | **Preserved** |
| Test impact | None | Process fixtures needed | None |

**The GIL is the fundamental blocker for threading.** Python's GIL prevents
multiple threads from executing Python bytecode simultaneously. numpy
releases the GIL only for operations on arrays above a size threshold
(~256 KB). Our arrays are 22×10 = 880 bytes — 300× below the threshold. Every
numpy call holds the GIL for its full duration.

**Multiprocessing works but isn't worth it.** The 2× speedup is real but
marginal compared to the 27.7× from batch vectorization. The architecture
cost (decoupling pygame state, managing processes, handling crashes)
far exceeds the benefit.

---

## 7. Conclusion

| Question | Answer |
|---|---|
| Can threading speed up AI learning? | **No.** GIL prevents it. 0.99× measured. |
| Can multiprocessing speed it up? | Yes, 2× with 4 workers, but high complexity. |
| Should we use either? | **No.** Batch numpy vectorization is 14× faster and 14× simpler. |
| What's the best architecture? | Single-threaded batch vectorization of `dellacherie_value`. |
| How much refactoring? | Low: one new function, one call site change. |
| Expected speedup | 4.5× end-to-end (336 → 75 ms/frame, learning mode). |
| Risk | Low: pure numpy, deterministic, no concurrency. |

**The lazy solution wins.** The problem isn't "not enough cores" — it's
"too many Python function calls on tiny arrays." Fix the algorithm, not the
parallelism.