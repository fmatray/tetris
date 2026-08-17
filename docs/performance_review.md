# Performance Review

## Methodology

Profiling conducted on the AIv2 branch with the following tools:

- **cProfile** — deterministic call-graph profiling (500 training frames, depth=1, preview=1)
- **line_profiler** — line-level timing on hot functions
- **py-spy** — native sampling profiler (low overhead, flamegraph output)
- **memory_profiler** — memory usage tracking

All measurements use headless mode (`SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy`) with `AIState` in learning mode (`lookahead_depth=1`, `preview_count=1`, `soft_drop=True`, `warm_start=True`, `learn_per_action=2`).

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

## Remaining bottlenecks (for future review)

- **`list.append` in scatter loop** (1.58M calls, 0.176s) — the Python loop in `place_and_clear_batch` that builds flat arrays for the vectorized scatter. Could be replaced with pre-allocated numpy arrays if the total cell count is known upfront, but the gain is marginal (~0.18s on 1.5s total).
- **`shape_fits`/`is_occupied` in BFS** (0.24s combined, 690K calls) — BFS grid access is inherently per-cell. Already optimized with `grid.tolist()` conversion. Further vectorization would require rewriting the BFS algorithm.
- **`try_rotation` in BFS** (0.055s, 55K calls) — SRS kick table lookup is inherently per-rotation. No vectorization possible without rewriting the SRS algorithm.
- **`hard_drop_y_batch`** (0.163s, 2048 calls) — Python loop to flatten (shape, cell) pairs. Could pre-allocate arrays but the gain is marginal.