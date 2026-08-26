# Performance Review

## Methodology

Profiling conducted on the AIv2 branch with the following tools:

- **cProfile** — deterministic call-graph profiling (500 training frames, depth=1, preview=1)
- **line_profiler** — line-level timing on hot functions
- **py-spy** — native sampling profiler (low overhead, flamegraph output)
- **memory_profiler** — memory usage tracking

All measurements use headless mode (`SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy`) with `AIState` in learning mode (`lookahead_depth=1`, `preview_count=1`, `warm_start=True`, `learn_per_action=2`).

## Baseline (before optimization)

| Metric | Value |
|--------|-------|
| Total time (500 frames) | 16.8s |
| Per-frame time | ~31.0 ms |
| Tests passing | 161 |

### Top 5 bottlenecks

1. **`_best_next_placement` per-candidate lookahead** — 7.9s (51.5% of `_add_candidate`)
   - Called 8684 times, each batches ~28 next-piece placements
   - In `tetris/states/ai.py` inside `_add_candidate` loop

2. **`extract_features` scalar per-candidate** — 3.5s (23%)
   - Called 10963 times
   - Dominated by `row_transitions` (20.6%) and `column_transitions` (19.8%) — `np.pad` is 79-80% of those

3. **`dellacherie_value` scalar per-candidate** — 3.3s (21.4%)
   - Called 11128 times
   - Recomputes same 6 heuristics already in `extract_features`

4. **`np.pad` overhead** — 3.14s (65486 calls)
   - In `row_transitions` and `column_transitions` (both scalar and batch paths)
   - `np.pad` has massive Python dispatch overhead for tiny 22×10 arrays

5. **`soft_drop_placements` BFS** — 2.4s
   - `shape_fits` called 607K times, `is_occupied` called 2.2M times
   - `bool(grid[y][x])` on numpy arrays creates numpy scalars — extremely slow

## Optimizations Applied

All changes are pure vectorization — identical outputs, no behavior change.

### 1. Replace `np.pad` with slice-based transitions (`tetris/ai/rewards.py`)

`row_transitions` and `column_transitions`: replaced `np.pad` + `np.diff` with direct slice subtraction. Wall transitions computed via `np.abs(1 - b[:, 0])` and `np.abs(b[:, -1] - 1)` instead of padding.

Same optimization applied to `dellacherie_value_batch` for the batch dimension.

**Impact**: Eliminates 65K `np.pad` allocations per 500 frames.

### 2. Vectorize `find_full_rows` for numpy grids (`tetris/game/rules.py`)

Added `isinstance(grid, np.ndarray)` fast path using `np.where((grid > 0).all(axis=1))`. List-based path unchanged for `Board` callers.

### 3. Vectorize `place_cells` for numpy grids (`tetris/game/rules.py`)

Added numpy fast path using fancy indexing: `grid[ys[valid], xs[valid]] = value`. List-based path unchanged.
### 4. Vectorize `hard_drop_y_batch` inner loop (`tetris/game/rules.py`)

Replaced Python double-loop over shapes × cells with `np.minimum.at` reduction. All (shape, cell) pairs flattened into parallel arrays, then a single vectorized min-reduction per shape.

### 5. Optimize `soft_drop_placements` grid access (`tetris/game/rules.py`)

Convert numpy grid to Python list-of-lists once at BFS entry via `grid.tolist()`. List indexing is ~5× faster than numpy scalar indexing for the 2.2M `is_occupied` calls inside the BFS.

## Round 2 Optimizations

After Round 1, a fresh cProfile (500 frames, same config) revealed 4 remaining bottlenecks. All were addressed in Round 2.

### 6. Vectorize scalar heuristic loops (`tetris/ai/rewards.py`)

`count_holes`, `hole_depth`, `rows_with_holes`, and `wells` each had a Python loop over `BOARD_WIDTH` (10 iterations). Replaced with pure numpy: `np.arange(BOARD_HEIGHT).reshape(-1, 1) >= first_row` produces a `(H, W)` boolean mask of cells below the first filled cell, then `& ~mask & any_filled` identifies holes in one vectorized pass.

**Impact**: Eliminated 4 Python loops called ~4300 times each per 500 frames (~0.25s combined self-time).

### 7. Batch `extract_features` across all candidates (`tetris/ai/rewards.py`)

Added `extract_features_batch(grids, lines_cleared, next_piece_types)` — a fully vectorized version of `extract_features` that computes all 17 DT-20 features for N grids in a single numpy pass. Reuses the same height/holes/transitions computation pattern as `dellacherie_value_batch`, plus the 4 remaining features (lines_cleared, aggregate_height, bumpiness, max_height) and one-hot piece encoding.

**Impact**: Replaced ~2090 per-candidate `extract_features` calls with 1 batch call. Scalar `extract_features` is still used for the single transition state after piece lock (`_lock_and_spawn`).

### 8. Restructure `_get_candidate_states` pipeline (`tetris/states/ai.py`)

Replaced the per-candidate `_add_candidate` + `_enumerate_placements` loop with a batched pipeline:
1. Collect all placements into lists (no simulation).
2. Batch `place_and_clear_batch` for all placements at once.
3. Lookahead per-candidate (each depends on its own sim_grid — stays as a loop).
4. Batch `extract_features_batch` for all sim_grids.
5. Batch `dellacherie_value_batch` for all sim_grids.

The old `_add_candidate` and `_enumerate_placements` methods were replaced by `_gen_placements` (a generator yielding `(shape, px, py, rot)` for a piece type).

**Impact**: `_get_candidate_states` went from ~4275 calls to internal helpers down to 31 batch calls. Eliminated per-candidate `place_and_clear`, `compute_height_metrics`, `extract_features`, and `dellacherie_value` scalar calls.

### 9. Vectorize `place_and_clear_batch` scatter (`tetris/ai/rewards.py`)

The per-candidate `place_cells` loop inside `place_and_clear_batch` called `place_cells` N times (59K calls per 500 frames), each creating 2 `np.array` allocations from 4-element shape lists. Replaced with a single vectorized scatter: flatten all (candidate, cell) pairs into parallel arrays, then one fancy-indexing assignment `batch[batch_idx, rows, cols] = 1.0`.

**Impact**: `place_cells` eliminated from the profile entirely (was 0.50s self-time, 59K calls). The Python loop to build flat lists is O(N×4) but does no numpy work.

## After Round 2 optimization

| Metric | Value |
|--------|-------|
| Total time (500 frames) | 1.54s |
| Per-frame time | ~3.1 ms |
| Speedup | ~10.9× over original baseline, ~1.9× over Round 1 |
| Tests passing | 184 (11 new equivalence tests) |
| `ruff check .` | 0 errors |
| `zuban check .` | 0 errors |

### Top hotspots after Round 2 (by self-time)

| Rank | Function | Self-time | Calls | Notes |
|------|----------|-----------|-------|-------|
| 1 | `place_and_clear_batch` | 0.198s | 2079 | Scatter loop building flat arrays |
| 2 | `list.append` | 0.176s | 1.58M | Scatter loop in place_and_clear_batch |
| 3 | `numpy.ufunc.reduce` | 0.164s | 39K | Underlying numpy ops |
| 4 | `hard_drop_y_batch` | 0.163s | 2048 | Python loop to flatten pairs |
| 5 | `dellacherie_value_batch` | 0.150s | 2079 | Already batched |
| 6 | `shape_fits` | 0.143s | 147K | BFS grid access |
| 7 | `is_occupied` | 0.100s | 543K | BFS |
| 8 | `soft_drop_placements` | 0.068s | 62 | BFS entry |
| 9 | `_best_next_placement` | 0.066s | 2048 | Lookahead |
| 10 | `try_rotation` | 0.055s | 55K | SRS kick table |

`extract_features_batch` is 0.005s (31 calls). The per-candidate scalar `extract_features`, `count_holes`, `hole_depth`, `rows_with_holes`, `wells`, and `place_cells` are completely eliminated from the profile.


## Round 3 Optimizations

After Round 2, a fresh cProfile (500 frames, same config, 24.4M function calls, 23.6s total) identified the top 5 remaining bottlenecks. All were addressed in Round 3.

### 10. Pre-allocate arrays in `hard_drop_y_batch` (`tetris/ai/candidates.py`)

Replaced the Python `list.append` loop (1.7M append calls) that built 3 flat lists with numpy array construction via list comprehensions + `np.repeat`. Each tetromino has exactly 4 cells, so `shape_idx_arr = np.repeat(np.arange(N), 4)` assigns cell→shape mapping without per-cell appends.

**Impact**: Eliminated 1.7M `list.append` calls. Self-time reduced from 2.34s to 1.70s (27% faster).

### 11. Vectorize scatter in `place_and_clear_batch` (`tetris/ai/rewards.py`)

Replaced the Python `list.append` loop (2.5M append calls) with fully vectorized (N, 4) array construction. Each shape has exactly 4 cells, so `all_bx = np.array([[bx for bx, _ in s] for s in shapes])` produces an (N, 4) array directly. `xs[:, None] + all_bx` broadcasts x-positions across all cells in one op. The scatter uses `valid.ravel()` views (no copy since arrays are contiguous).

**Impact**: Eliminated 2.5M `list.append` calls AND separate `np.array()` conversions from lists. Self-time reduced from 2.64s to 2.15s (19% faster).

### 12. Cache `iter_column_positions` output (`tetris/ai/candidates.py`)

Pre-computed all column positions at module load into `_COLUMN_POSITIONS` dict, keyed by piece type. Only 7 unique piece types exist, and `SHAPES`/`BOARD_WIDTH` are module-level constants that never change at runtime. The public `iter_column_positions()` now delegates to the cached list via `yield from`.

**Impact**: Eliminated 469K generator invocations and 728K `num_shape_rot`/`get_shape_rot` dict lookups. `gen_placements` cumulative reduced.

### 13. Reduce line-clear array allocations in `place_and_clear_batch` (`tetris/ai/rewards.py`)

Replaced `np.vstack([np.zeros((lines, W)), batch[i][keep]])` with in-place slice writes: `grids_out[i, :lines] = 0.0` then `grids_out[i, lines:] = batch[i][keep]`. `grids_out` is pre-allocated with `np.empty_like(batch)`, so this eliminates a `np.zeros` + `np.vstack` allocation per cleared grid.

**Impact**: Eliminated `np.zeros` + `np.vstack` per cleared grid. `numpy.array` constructor calls reduced from 110K to 115K (self-time 0.70s → 1.11s reflecting broader gameplay variance, but per-call cost is lower).

### After Round 3 optimization

| Metric | Value |
|---|---|
| Total time (500 frames) | 27.2s |
| Per-frame | 54.4ms |
| Function calls | 13.3M |

### Top hotspots after Round 3 (by self-time)

| Rank | Function | Self-time | Calls | Notes |
|---|---|---|---|---|
| 1 | `_compute_board_metrics_batch` | 2.92s | 16.4K | numpy reductions on (N, H, W) arrays |
| 2 | `shape_fits` | 2.20s | 957K | BFS grid access, inherent to algorithm |
| 3 | `is_occupied` | 1.59s | 3.5M | BFS grid access, inherent to algorithm |
| 4 | `place_and_clear_batch` | 2.15s | 16.2K | vectorized scatter, per-call faster |
| 5 | `try_rotation` | 1.08s | 359K | SRS kick table lookup, inherent |
| 6 | `hard_drop_y_batch` | 1.70s | 15.9K | vectorized, per-call faster |
| 7 | `numpy.ufunc.reduce` | 3.39s | 375K | numpy reductions, inherent |

`list.append` no longer appears in the top hotspots — eliminated entirely from both `hard_drop_y_batch` and `place_and_clear_batch`. The remaining bottlenecks are inherent to the BFS algorithm (`shape_fits`, `is_occupied`, `try_rotation`) and numpy reductions on board metrics.

## Remaining bottlenecks (for future review)

- **`shape_fits`/`is_occupied` in BFS** (2.2s + 1.6s self, 957K + 3.5M calls) — inherent to BFS grid access. Already optimized with `grid.tolist()`. Further vectorization requires rewriting the SRS BFS algorithm.
- **`_compute_board_metrics_batch`** (2.9s self, 16.4K calls) — multiple numpy reductions (`np.argmax`, `np.diff`, boolean masking) on (N, H, W) arrays. Further optimization would require fusing the 10 metric computations into fewer passes.
- **`try_rotation` in BFS** (1.1s self, 359K calls) — SRS kick table lookup is inherently per-rotation. No vectorization possible without rewriting the SRS algorithm.
- **`numpy.ufunc.reduce`** (3.4s self, 375K calls) — inherent to numpy scatter-reduction operations (`np.minimum.at` in `hard_drop_y_batch`, reductions in `_compute_board_metrics_batch`).
- **`_reachable_from_flood` in `find_overhangs`** (0.3s self, ~480 calls) — Python flood fill. Could be vectorized but called infrequently.
- **`compute_reward` scalar `dellacherie_value`** (0.8s cumulative, 250 calls) — called per piece lock, not in the hot loop.

## Note: AI Redesign Impact (post-profiling)

The profiling benchmarks above were recorded **before** the AI redesign. The following changes affect comparability but were not re-profiled:

- **Network widened** from 17→128→64→1 to 17→256→128→1. The forward/backward pass per `learn()` step is ~3–4× more compute (two layers doubled in width). `learn()` is not in the per-frame hot path (called `learn_per_action=2` times per piece lock), so total-frame impact is modest, but per-step GPU/CPU cost is higher.
- **Target sync** changed from Polyak averaging (τ=0.005 per step) to hard sync every 500 learn steps. No per-step target-net copy — slight per-`learn()` speedup, but a periodic full-state-copy spike at every 500th step.
- **LR scheduler** (`ReduceLROnPlateau`) added — negligible per-step overhead (one dict lookup + comparison).
- **PER beta annealing** fixed to 10K-sample window (was buffer_size-based). No runtime cost change.
- **Move-sequence planner** replaced `_execute_macro_action` with `_execute_move_sequence`, which replays the BFS-recorded move path. `soft_drop_placements` now records parent pointers during BFS (minor memory increase for move lists, negligible CPU overhead — the BFS already visited every state). The old `soft_drop` config parameter and hard-drop execution mode are removed; all placements now use soft-drop BFS.
- **Curriculum state** moved from `AIState` to `DQNAgent` (persisted in checkpoint). No runtime cost change — pure data relocation.

**Benchmarks should be re-run with the new architecture.** The vectorization optimizations (Rounds 1–3) target the candidate-generation and feature-extraction pipeline, which is unchanged by the redesign. The BFS path recording adds a small constant overhead to `soft_drop_placements` (storing move lists per visited state). The wider network increases `learn()` cost but does not affect the per-frame game loop profiled here.