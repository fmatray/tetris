# AI Player — Design and Implementation

## Overview

When the player selects **Player: AI** in the start menu, an autonomous agent plays Tetris using Reinforcement Learning. The AI is not hard-coded with heuristics — it learns through trial and error using a **V-network Deep Q-Learning (DQN)** architecture.

The AI has two modes:
- **Learning** — ε-greedy exploration, saves model and training log, fast-forwards lock delay
- **Playing** — greedy (ε=0), no learning, respects full lock delay, writes to separate log files

## Learning Algorithm: V-Network DQN

| Component | Choice | Reason |
|-----------|--------|--------|
| Algorithm | DQN with V-function | Evaluates board quality per candidate; no action dimension needed |
| Network | 17→256→128→1 MLP, ReLU hidden, Linear output | Small, fast, sufficient for DT-20 features |
| Optimizer | Adam, lr=1e-3, gradient clipping at 1.0 | Stable convergence |
| Target Network | Hard sync every 500 learn steps | Simpler than Polyak; replaces it |
| Replay Buffer | Prioritized Experience Replay (PER) | Focuses learning on high-TD-error transitions |
| Returns | 3-step n-step returns | Reduces variance, speeds credit assignment |
| LR Scheduler | ReduceLROnPlateau (mode=min, factor=0.5, patience=50, min_lr=1e-6) | Adapts to loss plateau |
| PER β Annealing | 0.4 → 1.0 over 10,000 learn steps | Corrects importance sampling bias over time |

### Why V-Network?

Standard DQN outputs Q(s, a) for each action. Here, the action space is **all valid placements** of the current piece — variable size, up to ~200 candidates. A V-network outputs a single scalar V(s) = board quality. For each candidate placement, we simulate the resulting board and evaluate V(resulting_board). The agent picks `argmax(V)`.

## State Representation: DT-20 Features (17-D)

The AI perceives the board as a 17-dimensional feature vector (10 board features + 7-dim next-piece one-hot). Features are normalized via `(x - mean) / std` using running statistics.

| Index | Feature | Description |
|-------|---------|-------------|
| 0 | lines_cleared | Lines cleared by this placement |
| 1 | holes | Total holes in resulting board |
| 2 | aggregate_height | Sum of column heights |
| 3 | bumpiness | Sum of |height[i] - height[i+1]| |
| 4 | max_height | Maximum column height |
| 5 | row_transitions | Row transitions (empty↔filled) |
| 6 | column_transitions | Column transitions |
| 7 | wells | Sum of well depths |
| 8 | hole_depth | Sum of hole depths |
| 9 | rows_with_holes | Count of rows containing at least one hole |
| 10-16 | next_piece_one_hot | 7-dim one-hot of next piece type |

Feature extraction: `tetris/ai/rewards.py::extract_features()` (scalar) and `extract_features_batch()` (vectorized).

## Action Space: Per-Candidate Evaluation

### Candidate Generation

**Soft-drop BFS** (always on): BFS over (x, y, rotation) states from spawn position (3, 0, rotation=0). Moves: left, right, soft-drop, rotate CW/CCW with SRS wall kicks. Enumerates ALL reachable landing positions, including placements under overhangs that hard-drop cannot reach.

Each placement records its **move sequence** — the list of atomic actions (`left`, `right`, `soft_drop`, `rot_cw`, `rot_ccw`) leading from spawn to landing. The `Placement` NamedTuple carries `moves: list[str]`.

**Hold candidates**: When hold is available (`_can_hold=True`), the AI also enumerates placements for the held piece (or next piece if hold is empty), doubling the candidate space.

**2-piece Look-ahead** (configurable depth 1-3): After simulating current piece placement, simulate the best placement of the NEXT piece on the resulting board (El-Tetris-optimal, argmax). The V-network evaluates the board after both pieces are placed. Look-ahead uses hard-drop internally for speed.

### Selection

1. Generate all candidate placements for current piece (+ hold candidates)
2. For each candidate, simulate placement → extract DT-20 features → V-network evaluates V(resulting_board)
3. Pick `argmax(V)` (greedy) or random (exploration, probability ε)
4. Execute the recorded move sequence atom-by-atom using `Board.is_valid_move` / `Board.try_rotate`

This guarantees the piece reaches the exact `(px, py, rot)` the BFS evaluated — no execution mismatch.

## Reward Function

### Base Reward (delta-based)

```
reward = 100 * lines_cleared
       - 50 * (new_holes - old_holes)
       - 10 * overhangs_created
       - 0.1 * aggregate_height
       - 0.1 * bumpiness
       - 10 * wells
       + 1.0  # survival bonus per piece
       - 500  # game over penalty
```

The hole penalty is **delta-based** (`new_holes - old_holes`): the agent learns which actions create holes rather than inheriting constant penalty for pre-existing holes.

### PBRS (Potential-Based Reward Shaping)

The base reward is augmented with a PBRS term using the Dellacherie board value as potential Φ:

```
r' = r + γ * Φ(s') - Φ(s)
```

Where Φ uses Dellacherie weights (scale 0.1):

| Feature | Weight |
|---------|--------|
| rows_eliminated | +1.0 |
| holes | -4.0 |
| aggregate_height | -0.5 |
| bumpiness | -0.3 |
| wells | -1.0 |
| overhangs | -0.5 |
| row_transitions | -0.1 |
| column_transitions | -0.1 |

PBRS is **policy-preserving** (Ng et al. 1999): speeds convergence without changing optimal policy. For empty grids Φ=0 so PBRS=0. Excludes `landing_height` and `eroded_cells` (placement-specific, not board-state).

`PBRS_SCALE = 0.1` caps PBRS contribution to ±20, keeping it meaningful without dominating base reward (±130).

### Selection Values (Separate from PBRS)

Bot pick and AI warm-start exploration prior use a separate El-Tetris evaluation (`el_tetris_value_batch`) that adds two placement-specific terms:
- `landing_height` (distance from board floor to piece centroid, weight −4.5)
- `rows_eliminated` (weight +3.42)

with published PSO-tuned weights from the [El-Tetris paper](https://imake.ninja/el-tetris-an-improvement-on-pierre-dellacheries-algorithm/).

The PBRS potential (`DELLACHERIE_WEIGHTS`) is unchanged — only the selection prior adds these terms.

## Neural Network Architecture

```
Input(17, normalized) → Dense(256, ReLU) → Dense(128, ReLU) → Output(1, Linear)
```

- **Loss**: Huber loss (δ=1.0) — robust to outliers
- **Target**: `target = reward + γ * V_target(next_state)` (n-step bootstrapped)
- **Online net**: `eval()` during `select_action`, `train()` during `learn` (future-proofs for dropout/BN)
- **Gradient clipping**: max_norm=1.0

### Dueling Head (optional, default OFF)

With `ai_dueling` ON, the trunk stays 17→256→128 and the output splits into
two streams: a value head `V(s)` and an advantage head `A(s)`, each a
`Linear(128, 1)`. The forward output is `V(s) + A(s)` — a function of the
state alone. There is **no batch-mean advantage centering**: this agent
evaluates each candidate placement as a single sample, so the output must
not depend on which other candidates share the batch.

Checkpoints record a `dueling` flag. Loading a dueling checkpoint into a
plain agent (or the reverse) raises `ValueError("checkpoint architecture
mismatch")` instead of a cryptic state-dict error. Non-dueling checkpoints
from older versions (no `dueling` key) load as plain agents unchanged — the
non-dueling layout keeps the original `net.0/2/4` state-dict keys.

## Training Pipeline

### Episode = One Game

An episode runs from game start to game over. One placement per piece:

1. Generate candidate states: soft-drop BFS enumerates all reachable placements, records move sequence, extracts DT-20 features
2. Select action: `DQNAgent.select_action(candidate_states)` → evaluates V per candidate, picks max (or random with ε)
3. Execute: replay recorded move sequence atom-by-atom via `Board.is_valid_move` / `try_rotate`
4. Observe: piece locks, lines clear, stats update
5. Compute reward: `compute_reward()` with PBRS
6. Store transition: `(state, action, reward, next_state, done)` in PER buffer
7. Learn: `learn_per_action` (default 2) gradient updates per locked piece
8. Repeat until game over

### Imitation Warm-Start (optional, default OFF)

With `ai_imitation` ON (learning mode only), the agent pre-trains from
recorded human gameplay before the first episode:

1. Human games record each locked placement to `data/human_placements.jsonl`
   (piece, rotation, column, hold flag) — see [Human Gameplay](human.md).
2. At AI startup, `imitation_pretrain()` (`tetris/ai/imitation.py`) replays
   each game on a reconstructed board, enumerates the candidate placements
   the AI would consider, and applies a softmax cross-entropy ranking loss
   so `V(human-chosen board)` outranks all alternatives.
3. The pretrainer uses the same `get_candidate_states` enumerator as live
   play, so reachability matches exactly. Un-replayable moves are skipped;
   a missing log is a no-op; failures never crash AI startup.

The effect: the V-network starts already preferring human-shaped placements,
so early RL episodes explore from a stronger prior instead of noise.

### Learning Mode vs Playing Mode

| Aspect | Learning Mode | Playing Mode |
|--------|---------------|--------------|
| ε-greedy | Yes (decay from 1.0 → ε_end) | No (ε=0, greedy) |
| ARE entry delay | Fast-forwarded (no delay, training speed preserved) | Full 100ms delay, IRS/IHS buffered |
| Replay buffer | Stores transitions | No storage |
| Learning | `learn_per_action` updates per piece | Skipped |
| Logging | `ai_training_log.json`, `ai_step_log.jsonl`, `ai_behavior_log.jsonl`, TensorBoard | `ai_playing_log.json`, `ai_playing_behavior_log.jsonl` |
| Model save | Every 50 episodes + on exit | Never |
| Curriculum | Active if enabled | Disabled |

**Playing-mode logging**: Separate files, mode implicit by filename — no `mode` field in entries. Training files never written by playing mode. `_on_exit()` saves model + flushes TB only in learning mode; playing mode flushes playing log only.

The ARE entry delay and its IRS/IHS buffering follow the shared rule in [game_rules.md §12](game_rules.md#12-are-appearance-delay-irs-ihs).

### Configurable Hyperparameters (in AI Submenu, persisted to `settings.json`)

| Parameter | Default | Range | Step |
|-----------|---------|-------|------|
| ε decay | 0.999 | 0.990–0.9999 | 0.0001 |
| ε end | 0.1 | 0.02–0.10 | 0.01 |
| Learning rate | 1e-3 | 1e-6–1e-2 | log |
| γ (discount) | 0.97 | 0.80–0.99 | 0.01 |
| Batch size | 64 | 8–256 | 2× |
| Buffer size | 50,000 | 1,000–200,000 | 2× |
| Curriculum | OFF | OFF/ON | — |
| Curriculum freq | 50 | 10–500 | 10 |
| Curriculum ε | boost | reset/boost/decay | — |
| Warm start | ON | OFF/ON | — |
| Learn per action | 2 | 1–8 | 1 |
| Look-ahead | ON | OFF/ON | — |
| Look-ahead depth | 1 | 1–3 | 1 |
| Speed | normal | normal/fast | — |
| Dueling | OFF | OFF/ON | — |
| Imitation | OFF | OFF/ON | — |

### Constructor-Only Parameters (for `verify_training` / programmatic use)

| Parameter | Default | Description |
|-----------|---------|-------------|
| `ai_mode` | "learning" | "learning" or "playing" |
| `lookahead_depth` | 1 | 1-3 (overrides menu) |
| `preview_count` | 1 | 0/1/3 (overrides menu) |
| `seed` | None | Reproducibility seed |

### Curriculum Learning

Order: O → I → L → J → T → S → Z (easy → hard). First piece of each game restricted to I, J, L, T (`FIRST_PIECE_TYPES`) to avoid forced overhangs on empty board.

Curriculum state (`curriculum_level`, `curriculum_episode_count`) lives in `DQNAgent`, persisted in checkpoint. `advance_curriculum(max_level, freq)` advances level every `freq` episodes. `_reset_episode` re-applies `set_allowed_types` on the new `PieceProvider`.

Order: O → I → L → J → T → S → Z (easy → hard). First piece of each game restricted to I, J, L, T (`FIRST_PIECE_TYPES`) to avoid forced overhangs on empty board.

### Seed Reproducibility

`_reset_episode` derives `_episode_seed = seed + episode` and re-seeds `random`, `np.random`, `torch.manual_seed`, and the `PieceProvider`. Given the same `seed`, the same episode number produces the same piece sequence AND exploration decisions.

## Integration with Architecture

### File Structure

```
tetris/ai/
├── agent.py        # DQNAgent — select_action, store, learn, save, load
├── network.py      # DQNetwork — 17→256→128→1 V-network MLP
├── candidates.py   # Placement generation + soft-drop BFS
├── hud.py          # AI training HUD rendering
├── rewards.py      # DT-20 features, PBRS reward, El-Tetris evaluation
```

### FSM Integration

`AIState` inherits all board, piece, stats, and rendering logic from `GameState`. Candidate generation and HUD rendering are extracted to `tetris/ai/candidates.py` and `tetris/ai/hud.py` as pure functions.

It overrides:
- `update()` — AI candidate selection and move-sequence execution
- `_reset_episode()` — re-seeds, re-applies handicap, curriculum, handicap
- `_on_episode_end()` — logs, learns, saves model (learning mode only)
- `draw()` — renders board + AI HUD overlay

### AI HUD (Learning Mode Only)

**Training parameters table**: ε, ε_decay, ε_end, lr, γ, batch, buffer, look-ahead, depth, curriculum, warm-start, learn/action, speed.

**Statistics table** (4 columns × 6 rows): Tetromino, Lines, Score, Level with Current / Best / Average / Trend.

**Trend row**: compares last 100 episodes' average vs previous 100 episodes' average (5% threshold). Shows ↑ (improving), ↓ (declining), → (stable). Requires 200+ episodes.

**Last 5 moves**: compact single-line display showing last 5 piece placements as `{piece} r{rotation} c{column} {H| }`, where `H` indicates hold was used. Cleared on episode reset.

**Cooking-state indicator** (health scoring, 4 signals):
1. Score trend (up=+1, down=-1)
2. TD error trend (50-ep window ratio: <0.9=+1 converging, >1.5=-1 diverging)
3. V-margin (last_v_margin > 0.01 = +1, network discriminates top-2 candidates)
4. ε (< 0.2 = +1, exploration winding down)

Health score range -1 to +3: ≤0 "Overcooked" (red), 1 "Undercooked" (blue), ≥2 "Well cooked" (green).

**Thermometer bar**: 12×20px vertical bar with fill proportional to training progress (`max(eps_progress, ep_maturity)` clamped 0..1).

### Learning Curve Graph

The AI submenu includes a **Graph** option that opens a full-screen score-vs-episode plot (matplotlib Agg backend → pygame.Surface, cached). Any key returns to the AI submenu.

## Observability Infrastructure (5 Tiers)

| Tier | Target | File | Format |
|------|--------|------|--------|
| 1 | Per-episode enriched log | `ai_training_log.json` | JSON (35 fields: 9 original + 26 observability) |
| 2 | Per-`learn()` call metrics | `ai_step_log.jsonl` | JSONL (rotates at 1M lines) |
| 3 | Per-episode behavioral analytics | `ai_behavior_log.jsonl` | JSONL (column/rotation histograms, placement success rate) |
| 4 | Reward decomposition | `compute_reward_components()` | 9 components (sum = total reward) |
| 5 | Live dashboards | `SummaryWriter` → `data/runs/` | TensorBoard scalars |

**Key APIs**: `DQNAgent.training_metrics()` snapshots dynamics; `DQNAgent.flush_logs()` flushes TB writer; `AIState._write_behavior_log()` writes behavioral JSONL; `compute_reward_components()` in `rewards.py` decomposes reward. All I/O is best-effort — training never crashes on log failures. Playing mode disables step log and TB writer.

## Rule Alignment: Human vs AI (All Fixed)

All divergences between human and AI game rules have been resolved. The AI now follows identical rules:

| Rule | Human | AI (Fixed) | Status |
|------|-------|------------|--------|
| SRS Wall Kicks | `board.try_rotate()` | `board.try_rotate()` (was direct `piece.rotate()`) | ✅ Fixed |
| Hold Mechanic | Available | Available (hold candidates enumerated) | ✅ Fixed |
| Handicap | Persists all episodes | Re-applied on episode reset | ✅ Fixed |
| Lock Delay | 500ms with 15 resets | Full lock delay in playing mode; fast-forwarded in learning mode (by design) | ✅ Aligned |
| Top-out | Spawn overlap / lock above visible | Same | ✅ Aligned |
| T-Spin Detection | `Board.is_tspin()` | Same via `Board` | ✅ Aligned |
| Back-to-Back | `GameStats.b2b` + `ScoreEngine.b2b_bonus()` | Same | ✅ Aligned |
| Line Clear Scoring | `ScoreEngine` | Same | ✅ Aligned |

Duplicated game-rule code (collision, SRS kicks, hard drop, line clear, placement) was extracted to `tetris/game/rules.py` as grid-agnostic functions. Both `Board` (list-of-lists) and AI simulation (numpy arrays) now call the same rule functions.

## Training Validation

Run headless validation:
```bash
SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy python -m tetris.verify_training
```

**Success criteria**: best_score > 10,000, avg_score > 1,000. Duration and loss are reported as information only.

## Training Analysis

Standalone read-only script reads all AI logs and produces health report:
```bash
python scripts/analyze_training.py --charts
```
Outputs `[OK]`/`[ATTN]`/`[CRIT]` flags. Optional `--charts` saves PNGs to `data/analysis/` (score curve, column heatmap, dynamics 4-panel, reward decomposition). Replicates `_trend`, `_moving_average`, and `_cooking_status` logic from game code for consistency. TensorBoard loading disabled (event files too large; step log JSONL covers same metrics).

## MCTS Look-Ahead

`tetris/ai/mcts.py` adds an AlphaZero-style tree search over piece placements. The V-network evaluates leaf boards; the module does no random rollouts. The search works as follows:

1. The root uses the soft-drop candidate placements from `get_candidate_states`.
2. Root priors come from a softmax over the El-Tetris values (`pick_values`). This makes the priors scale-free.
3. Deeper levels use cheap hard-drop enumeration only. This is the same approximation as the greedy look-ahead.
4. The search selects children with the PUCT formula (`C_PUCT = 1.5`).
5. A terminal leaf (top-out) keeps the value `TERMINAL_VALUE = -1.0` forever.

Piece types beyond the preview queue are sampled from the injected `rng`. This keeps searches reproducible. Nodes are plain dicts, so `docs/class_diagram.md` stays untouched.

Enable it with the **MCTS** option in the AI hyperparameter menu (`ai_mcts` in `settings.json`). **MCTS iterations** sets the search budget (`ai_mcts_iterations`, 20 to 2000, default 200). When MCTS is on, the greedy look-ahead chain is off. This prevents the cost of two searches.

## Self-Play Tournament

`tetris/tournament.py` evolves the checkpoint weights without gradient descent. It runs from the CLI:

```bash
python -m tetris.tournament --generations 3 --episodes 2 --population 8 --sigma 0.02 --seed 7
```

The tournament works as follows:

1. It loads the checkpoint at `data/ai_model.pt`.
2. It builds a population from the base checkpoint plus Gaussian mutants (`sigma` = noise scale).
3. Each generation evaluates every checkpoint in headless playing-mode episodes. The episode score up to a piece cap is the fitness.
4. The top half of the population survives. Mutated survivors and uniform-crossover pairs refill the population.
5. It writes the report to `data/tournament/tournament_report.json` and the best weights to `data/tournament/tournament_best.pt`.


## Future Enhancements

- **Human Replay (Imitation Learning)** — pre-train on human game replays
- **Double DQN** — already implemented (V-network DQN)
- **Dueling Network** — separate value/advantage streams

## Summary

```
AI Player = V-network DQN + Soft-drop BFS + PBRS + PER + n-step + Look-ahead
            │
            ├── Learns autonomously at human cadence (~12 actions/sec)
            ├── Same game rules as human (SRS, hold, lock delay, T-spin, B2B)
            ├── 5-tier observability (logs, step log, behavior, reward decomp, TB)
            ├── Curriculum learning (piece introduction order)
            ├── Seed reproducibility (deterministic episodes)
            └── Separate learning/playing modes with isolated artifacts
```