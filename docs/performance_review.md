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

## After optimization

| Metric | Value |
|--------|-------|
| Total time (500 frames) | 12.9s |
| Per-frame time | ~25.8 ms |
| Speedup | ~1.3× over baseline |
| Tests passing | 173 (12 new equivalence tests) |
| `ruff check .` | 0 errors |
| `zuban check .` | 0 errors |

The `np.pad` elimination removed 65K allocations. The `soft_drop_placements` list conversion reduced BFS time from 2.4s to 1.7s. The `hard_drop_y_batch` vectorization and `place_cells` numpy path reduced per-candidate overhead. Remaining time is dominated by `place_cells` (2.45s, called 237K times) and `dellacherie_value_batch` (1.67s).

## Remaining bottlenecks (for future review)

- **`extract_features` still called per-candidate** — could be batched across all candidates like `dellacherie_value_batch`, but requires refactoring the AI state pipeline.
- **`count_holes`, `hole_depth`, `rows_with_holes` Python loops** — still loop over `BOARD_WIDTH` in the scalar path; could be vectorized but are less hot than transitions.
- **`try_rotation` in BFS** — 45% of BFS time; SRS kick table lookup is inherently per-rotation.
- **`_get_candidate_states` Python loop** — iterates over all candidates collecting grids; could pre-allocate a batch array.