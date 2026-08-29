# AI Player Mode — Design Document

_(Updated: 2026-08-26)_


## Overview

When the player selects **Joueur : IA** in the start menu, the game launches
and an autonomous agent plays Tetris instead of a human. The AI is not
hard-coded with heuristics — it **learns by itself** through trial and error
using **Reinforcement Learning (RL)**. The objective is simple: achieve the
highest score possible.

---

## 1. Learning Algorithm

### 1.1 Approach: Deep Q-Learning (DQN)

| Component | Choice | Reason |
| ----------- | -------- | -------- |
| Algorithm | V-network DQN | Per-candidate board value evaluation; picks max-V placement |
| Experience Replay | Yes (buffer size 50,000) | Stabilizes training by breaking correlation |
| Target Network | Yes (hard sync every 500 learn steps) | Reduces moving-target instability |
| Exploration | ε-greedy, decay 1.0 → ε_end (configurable) | Balances exploration vs exploitation |
| Reward Shaping | PBRS (Dellacherie potential) | Speeds convergence without reward hacking (Ng et al. 1999) |

### 1.2 Alternative: NEAT (Future)

If DQN proves too heavy, a fallback approach using **NEAT** (Neural
Evolution of Augmenting Topologies) can evolve a population of neural
networks over many games. This is lighter on memory and easier to visualize.

---
## 2. State Representation

The AI perceives the board as a **DT-20 feature vector** (10 board
features + 7-dim next-piece one-hot = **17 dimensions**). Engineered
features provide inductive bias, keeping the network small and
training fast.

### 2.1 Feature Vector

```
State = [lines_cleared, holes, aggregate_height, bumpiness, max_height,
         row_transitions, column_transitions, wells, hole_depth,
         rows_with_holes, *one_hot_piece(next_piece_type)]
Total = 17 floats (normalized: (x - mean) / std before network input)
```

### 2.2 Feature Definitions

| Feature | Formula |
| --------- | --------- |
| `lines_cleared` | Number of rows completed this placement |
| `holes` | Empty cells with at least one filled cell above them |
| `aggregate_height` | Sum of heights of all columns |
| `bumpiness` | Σ ` | height[i] - height[i+1] | ` for adjacent columns |
| `max_height` | Height of the tallest column |
| `row_transitions` | Horizontal filled↔empty transitions per row (walls = filled) |
| `column_transitions` | Vertical filled↔empty transitions per column (floor = filled) |
| `wells` | Σ `depth*(depth+1)//2` per column lower than both neighbors |
| `hole_depth` | Max holes in any single column below the first filled cell |
| `rows_with_holes` | Count of rows containing ≥1 hole cell |
| `next_piece_one_hot` | 7-dim one-hot encoding of next piece type (I, O, T, S, Z, J, L) |

---

## 3. Action Space

The AI uses **per-candidate evaluation**: for each valid placement,
the agent simulates the placement, computes the resulting board
features, and evaluates V(resulting_board) via the V-network. The
candidate with the highest V-value is selected.

### 3.1 Candidate Generation

**Soft-drop BFS** (always on): BFS over (x, y, rotation) states —
move left/right, soft-drop, rotate with SRS wall kicks. Enumerates
ALL reachable landing positions, including placements under
overhangs that hard-drop cannot reach. Uses SRS wall kick tables
(`SRS_KICKS_JLSTZ`, `SRS_KICKS_I`) for rotation around obstacles.

Each placement records its **move sequence** — the list of atomic
actions (`left`, `right`, `soft_drop`, `rot_cw`, `rot_ccw`) that
leads from spawn to the landing position. The `Placement` NamedTuple
carries a `moves: list[str]` field, and `_execute_move_sequence()`
replays these actions atom-by-atom using `Board.is_valid_move` /
`Board.try_rotate`. This guarantees the piece reaches the exact
`(px, py, rot)` the BFS evaluated — no execution mismatch.

**2-piece look-ahead** (when enabled): after simulating the current
piece placement, simulate the best placement of the NEXT piece on
the resulting board (El-Tetris-optimal, argmax — the same evaluation
the Dellacherie bot selects with). The V-network evaluates the board
after both pieces are placed. Look-ahead uses hard-drop internally
for speed (board-quality evaluation only, not executed).

For each candidate:
1. Simulate placement via soft-drop BFS (records move sequence)
2. Simulate line clears on the resulting board
3. If look-ahead: simulate best next-piece placement
4. Extract 17-dim DT-20 features from the resulting board

The V-network evaluates each candidate: `V = network(features)`.
The agent picks `argmax(V)` (greedy) or random (exploration).

---

## 4. Reward Function

### 4.1 Base Reward

```
reward = (
    +50.0  × lines_cleared
    +5.0   × lines_cleared²           # bonus for multi-line clears
    -5.0   × holes_created             # delta: NEW holes only
    -0.1   × new_holes                 # residual absolute holes penalty
    -0.5   × aggregate_height           # stack height penalty (10× stronger)
    -0.3   × bumpiness                  # surface unevenness penalty (3× stronger)
    -0.5   × wells                      # deep well penalty
    -50.0  if game_over                 # terminal penalty (5× stronger)
    +1.0   per piece placed             # survival incentive
)
```

The hole penalty is **delta-based** (`new_holes - old_holes`): the
agent learns which actions create holes rather than inheriting a
constant penalty for pre-existing holes.

### 4.2 PBRS (Potential-Based Reward Shaping)

The base reward is augmented with a PBRS term using the Dellacherie
board value as the potential function Φ:

```
shaped_reward = base_reward + PBRS_SCALE × (γ × Φ(new_grid) - Φ(prev_grid))
```

Where Φ uses Dellacherie weights:

| Feature | Weight |
| --------- | --------- |
| `row_transitions` | -3.418893 |
| `column_transitions` | -9.336683 |
| `holes` | -7.899265 |
| `wells` | -3.385597 |
| `hole_depth` | -0.192486 |
| `rows_with_holes` | -0.106548 |

PBRS is **policy-preserving** (Ng et al. 1999): it speeds convergence
without changing the optimal policy. For empty grids Φ=0 so PBRS=0.
Excludes landing_height/eroded_cells (placement-specific, not board-state).

Selection values (bot pick + the AI warm-start exploration prior) are a
**separate El-Tetris evaluation** (`el_tetris_value_batch`) that adds the
two placement-specific terms `landing_height` and `rows_eliminated`;
the PBRS potential (`DELLACHERIE_WEIGHTS`) is unchanged.

`PBRS_SCALE = 0.1` caps the PBRS contribution to ±20, keeping it
meaningful without dominating the base reward (±130).

## 5. Neural Network Architecture

```
Input  (17, normalized)
  ↓
Dense (256, ReLU)
  ↓
Dense (128, ReLU)
  ↓
Output (1, Linear) → V(board) = board value
```

- **Optimizer**: Adam, learning rate 1e-3 (with gradient clipping at 1.0)
- **Loss**: SmoothL1Loss (Huber) — V-function Bellman target
- **Batch size**: 64
- **Discount factor (γ)**: 0.97
- **Target sync**: hard sync every 500 learn steps (`target_sync_freq=500`). Target network weights copied from online network at the sync boundary.
- **LR scheduler**: `ReduceLROnPlateau(optimizer, mode="min", factor=0.5, patience=50, min_lr=1e-6)` — called after each `learn()` step with `self.last_loss`. Halves the learning rate when loss plateaus for 50 steps, down to 1e-6.
- **Device**: `auto` (CUDA if available, else CPU). No MPS — transfer overhead negates gains on this small network.
- **Seed**: `None` by default (random). Set `seed=N` for reproducible weight init + sampling + piece generation + handicap. Per-episode seed derived as `seed + episode` for varied but reproducible training. Logged in `TrainingLog`.
- **Mode toggling**: `online_net.eval()` during inference, `online_net.train()` during learning.

The V-network evaluates board quality. Per-candidate action selection:
evaluate V(resulting_board) for each valid placement, pick max. No
action dimension — the network outputs a single scalar board value.

### 5.1 Framework Choice

| Framework | Pros | Cons |
| ----------- | ------ | ------ |
| **PyTorch** | Pythonic, easy debugging | Heavier install |
| **TensorFlow/Keras** | High-level API | Less intuitive for RL |
| **Custom NumPy** | Zero new deps | Reimplementing backprop |

**Recommendation**: PyTorch, since `numpy` is already a dependency and
PyTorch integrates cleanly. Add `torch` to `requirements.txt` as an
optional dependency.

---

## 6. Training Pipeline

### 6.1 Phases

```
┌─────────────┐     ┌──────────────┐     ┌──────────────┐
│  Phase 1    │────▶│   Phase 2    │────▶│   Phase 3    │
│  Random     │     │  Training    │     │  Exploit     │
│  Play       │     │  (ε decay)   │     │  (ε = ε_end) │
└─────────────┘     └──────────────┘     └──────────────┘
```

1. **Random Play** — ε = 1.0, pure exploration. Fills replay buffer
   with diverse experiences.
2. **Training** — ε decays from 1.0 to ε_end. Network learns Q-values
   from replay buffer samples.
3. **Exploit** — ε = ε_end, mostly greedy. AI plays near-optimally.
   Continue learning but slowly.

### 6.2 Configurable Hyperparameters

| Parameter | Default | Range | Step |
| --------- | ------- | ----- | ---- |
| `epsilon_decay` | 0.999 | 0.990–0.9999 | 0.0001 |
| `epsilon_end` | 0.10 | 0.02–0.10 | 0.01 |
| `ai_lr` | 1e-3 | 1e-6–1e-2 | ×10 |
| `ai_gamma` | 0.97 | 0.80–0.99 | 0.01 |
| `ai_batch_size` | 64 | 8–256 | 8 |
| `ai_buffer_size` | 50,000 | 1,000–200,000 | 5,000 |
| `ai_curriculum` | OFF | ON/OFF | toggle |
| `ai_curriculum_freq` | 50 | 10–500 | 10 |
| `ai_curriculum_epsilon` | reset | reset/boost/decay | cycle |

Constructor-only parameters (not in menu, for `verify_training` / programmatic use):

| Parameter | Default | Description |
| --------- | ------- | ----------- |
| `seed` | `None` | Random seed for reproducible training (torch + numpy + random + piece generation + handicap). Per-episode seed = `seed + episode` |
| `device` | `auto` | Torch device: `auto` (CUDA if available), `cpu`, or `cuda` |
| `target_sync_freq` | 500 | Hard target network sync interval (learn steps) |

These are configurable in the **AI submenu** and persisted to
`settings.json`.

### 6.3 Episode = One Game

An episode runs from game start to game over. One placement per piece:

1. Generate candidate states: soft-drop BFS enumerates all reachable placements, records move sequence for each, extracts DT-20 features
2. Select candidate via ε-greedy: random or `argmax(V(candidate_states))`
3. Execute placement: replay move sequence (`_execute_move_sequence`) — atomic actions validated via `Board.is_valid_move` / `Board.try_rotate`, then lock via lock delay
4. Observe reward `r` (delta holes + line bonus + board quality + PBRS shaping)
5. Store `(s, 0, r, s', done)` in n-step buffer → PER (delayed: s = board after prev placement, s' = board after this placement)
6. Run `learn_per_action` V-function Bellman gradient updates via prioritized mini-batch (IS-weighted)
7. LR scheduler step: `scheduler.step(last_loss)` — reduces LR on plateau (patience=50)
8. Hard target sync every `target_sync_freq` learn steps
9. Decay ε once per episode
10. Advance curriculum if enabled (`agent.advance_curriculum`)

### 6.4 Curriculum Learning

Curriculum state (`curriculum_level`, `curriculum_episode_count`)
lives in `DQNAgent`, not `AIState`. The agent's `advance_curriculum(max_level, freq)`
method increments the level after `freq` episodes, up to `max_level`.
Both fields are persisted in the checkpoint, so resuming training
restores curriculum progress. `AIState` applies the piece-type
restriction (`pieces.set_allowed_types`) based on the agent's level
— re-applied in `_reset_episode` after creating a fresh `PieceProvider`.

### 6.5 Seed Reproducibility

`_reset_episode` derives `_episode_seed = seed + episode` and re-seeds
`random`, `np.random`, `torch.manual_seed`, and the `PieceProvider`.
Given the same `seed`, the same episode number produces the same piece
sequence AND the same exploration decisions.

| File | Purpose |
| ------ | --------- |
| `data/ai_model.pt` | Trained weights + optimizer + scheduler + ε + curriculum level + PER β |
| `data/ai_training_log.json` | Per-episode stats (score, lines, level, steps, ε, loss) |
| `data/settings.json` | Menu options + AI hyperparameters (ε decay, ε end, speed) |

---

## 7. Integration with Existing Architecture

### 7.1 File Structure

```
tetris/
├── ai/
│   ├── __init__.py
│   ├── network.py        # DQNetwork (17→256→128→1 V-network)
│   ├── replay_buffer.py  # Experience replay buffer (50,000)
│   ├── rewards.py        # DT-20 features, Dellacherie value, PBRS reward, simulation helpers
│   ├── candidates.py     # Candidate placement generation (pure functions)
│   ├── hud.py            # AI training HUD rendering (pure presentation)
│   └── trainer.py        # TrainingLog (per-episode JSON persistence)
├── states/
│   ├── ai.py             # AIState (subclass of GameState)
│   ├── ai_menu.py         # AI submenu (speed, ε decay, ε end, graph, reset)
│   └── menu.py           # MenuState (settings.json persistence)
```

### 7.2 FSM Architecture

```
MenuState (Joueur: IA)
    ↓
AIState (subclass of GameState)
    ↓
  AI generates candidate states (soft-drop BFS, records move sequences)
  AI evaluates V(candidate_states) per-candidate, picks max
  AIState executes action:
    - Replay move sequence (_execute_move_sequence)
    - Lock piece → compute reward (PBRS) → store transition → learn
```

`AIState` inherits all board, piece, stats, and rendering logic from
`GameState`. Candidate generation and HUD rendering are extracted to
`tetris/ai/candidates.py` and `tetris/ai/hud.py` as pure functions.
It overrides:

- `update()` — AI candidate selection and move-sequence execution
- `_lock_and_spawn()` — intercepts piece locking for reward + transition
- `draw()` — delegates AI HUD overlay to `tetris.ai.hud.draw_ai_hud`
- `_on_episode_end()` — logs episode, saves model, auto-restarts

### 7.3 AI HUD

The HUD overlay has two sections:

**Training:**
- Speed (Rapide/Normal)
- Episode number
- Epsilon (current exploration rate)
- Epsilon decay (configurable)
- Epsilon end (configurable)
- Loss (last training loss)

**Statistics table** (4 columns × 6 rows):

| | Tetromino | Lines | Score | Level |
|---|---|---|---|---|
| Current | pieces in current episode | lines in episode | episode score | episode level |
| Total | cumulative pieces | cumulative lines | cumulative score | — |
| Best | best episode pieces | best episode lines | best episode score | best episode level |
| Average | avg pieces/episode | avg lines/episode | avg score/episode | avg level/episode |
| Last 100 | avg of last 100 | avg of last 100 | avg of last 100 | avg of last 100 |
| Trend | ↑/↓/→ | ↑/↓/→ | ↑/↓/→ | ↑/↓/→ |

The **Trend** row compares the last 100 episodes' average vs the
previous 100 episodes' average (5% threshold). Shows ↑ (improving),
↓ (declining), or → (stable). Requires 200+ episodes.

**Last 5 moves** — a compact single-line display below the board showing
the last 5 piece placements as `{piece} r{rotation} c{column} {H| }`,
where `H` indicates hold was used. Cleared on episode reset.

### 7.4 Learning Curve Graph

The AI submenu includes a **Graphique** option that opens a full-screen
score-vs-episode plot:

- X axis: episode number
- Y axis: episode score
- Cyan line: raw score per episode
- Yellow line: 20-episode moving average (learning trend)

Rendered with matplotlib (Agg backend) to a `pygame.Surface`, cached on
first draw. Any key returns to the AI submenu.

- Two speeds: **Rapide** (no delay, fast training) and **Normal** (~80ms
  per action, human-like).

---

## 8. Evaluation & Metrics

### 8.1 Tracking

| Metric | Description |
| -------- | ------------- |
| **Score** | Final game score |
| **Lines cleared** | Total lines per episode |
| **Level reached** | Highest level achieved |
| **Pieces placed** | Total tetrominoes placed |
| **Survival time** | Steps before game over |
| **Average V-value** | Network confidence over time |
| **TD error** | Mean/max temporal-difference error per learn step |
| **Grad norm** | Gradient magnitude after clipping |
| **LR** | Current learning rate (scheduler-adjusted) |
| **Buffer fill** | Replay buffer occupancy |
| **V-value spread/margin** | Difference between best and worst candidate V-values |
| **Random/greedy ratio** | Actual exploration rate (n_random / n_greedy per episode) |
| **Hold rate** | Fraction of placements using the hold slot |
| **Reward components** | Per-component averages (lines, holes, overhangs, height, bumpiness, wells, survival, PBRS, game_over) |

### 8.2 Milestones

| Milestone | Expected Performance |
| ----------- | --------------------- |
| 10k episodes | Clears lines consistently, survives ~30 pieces |
| 50k episodes | Reaches level 5+, multi-line clears |
| 100k episodes | Near-optimal play, survives 200+ pieces |
| 500k episodes | Human-competitive or superhuman scores |

---

## 9. Challenges & Mitigations

| Challenge | Mitigation |
| ----------- | ------------ |
| **Sparse rewards** (few lines cleared early) | Shape reward with height/bumpiness penalties + PBRS (Dellacherie potential) |
| **Catastrophic forgetting** | Experience replay + target network |
| **Overhang execution mismatch** | Move-sequence planner: BFS records full atomic action path; `_execute_move_sequence` replays it exactly, guaranteeing the piece reaches the evaluated position |
| **Training plateau** | Wider network (256→128), hard target sync (500 steps), LR scheduler (ReduceLROnPlateau, patience=50) |
| **PER beta never reaches 1.0** | Beta annealed over fixed 10K samples (not buffer_size-based) |

---

## 9a. Observability Infrastructure

Five-tier instrumentation for training diagnostics:

| Tier | Target | File | Format |
| ---- | ------ | ---- | ----- |
| **1. Enriched episode log** | Per-episode | `data/ai_training_log.json` | JSON (35 fields: 9 original + 26 observability) |
| **2. Step log** | Per-`learn()` call | `data/ai_step_log.jsonl` | JSONL (rotates at 100K lines, ~20MB max) |
| **3. Behavioral log** | Per-episode | `data/ai_behavior_log.jsonl` | JSONL (column histogram 10 bins, rotation histogram 4 bins, placement success rate) |
| **4. Reward decomposition** | Per-episode | `data/ai_training_log.json` | `compute_reward_components()` returns 9 named components; sum equals `compute_reward()` |
| **5. TensorBoard** | Per-`learn()` call | `data/runs/` | TensorBoard event files (`tensorboard --logdir data/runs`) |

**Key APIs**: `DQNAgent.training_metrics()` snapshots dynamics; `DQNAgent.flush_logs()` flushes TB writer; `AIState._write_behavior_log()` writes behavioral JSONL; `compute_reward_components()` in `rewards.py` decomposes reward. All I/O is best-effort — training never crashes on log failures. Playing mode disables step log and TB writer.

---

## 10. Future Enhancements
- ~~**Double DQN**~~ — ✅ Implemented (now V-network DQN).
- ✅ **Per-candidate evaluation** — V-network evaluates V(resulting_board) per valid placement.
- ✅ **DT-20 features** — 17-dim engineered features replace 220-dim raw board.
- ✅ **PBRS** — Potential-based reward shaping with Dellacherie board value.
- ✅ **Prioritized Experience Replay (PER)** — Proportional PER with IS weights (Schaul et al. 2015).
- ✅ ~~**Hard target sync**~~ — Implemented (every 500 learn steps, replaces Polyak averaging).
- ✅ ~~**LR scheduling**~~ — Implemented (ReduceLROnPlateau, factor 0.5, patience 50).
- ✅ ~~**Curriculum Learning**~~ — Implemented (O → I → L → J → T → S → Z). State lives in `DQNAgent`, persisted in checkpoint.
- ✅ ~~**Move-sequence planner**~~ — Implemented (Option D: BFS records atomic action path, `_execute_move_sequence` replays it).
- ✅ **N-step returns** — 3-step Bellman targets for faster credit assignment.
- ✅ **Soft-drop BFS** — SRS wall kicks + BFS candidate generation with move-sequence recording (overhangs, T-Spins).
- ✅ **2-piece look-ahead** — Simulate best next-piece placement before evaluation.
- ✅ **Feature normalization** — Standardize DT-20 features (mean/std) before network input.
- ✅ **Observability infrastructure** — 5-tier instrumentation: enriched episode log (26 new fields), JSONL step log with rotation, behavioral JSONL, reward decomposition (`compute_reward_components`), TensorBoard integration.
- ✅ **Playing-mode logging** — Mode Jeu writes to separate log files (`PLAYING_LOG_PATH` / `PLAYING_BEHAVIOR_LOG_PATH`) to avoid polluting training artifacts. Training files (`ai_training_log.json`, `ai_behavior_log.jsonl`, `ai_model.pt`, `ai_step_log.jsonl`, `runs/`) are never written in playing mode. `AIStatsState` reads training logs only; playing stats shown in-game HUD only.
- ✅ **Cooking-state indicator** — HUD indicator (apprentissage mode only) uses 4-signal health scoring: (1) score trend, (2) TD error trend (50-ep window ratio), (3) V-margin discrimination, (4) epsilon decay. Maps health score (-1 to +3) to undercooked (blue) / good (green) / overcooked (red). Includes a thermometer bar showing training progress (epsilon decay + episode maturity).
- ✅ **Training analysis script** — `scripts/analyze_training.py`: standalone read-only tool that reads all AI logs and produces a health report with `[OK]`/`[ATTN]`/`[CRIT]` flags. Optional `--charts` generates PNGs to `data/analysis/`. Replicates game logic (`_trend`, `_moving_average`, `_cooking_status`) for consistency.
- **Self-Play Tournament** — run multiple AI agents in parallel, keep the
  best-performing model.
- **Human Replay** — let a human play, record the session, and pre-train
  the AI on human demonstrations (imitation learning bootstrapping).
- **Monte Carlo Tree Search (MCTS)** — for look-ahead planning on top of
  the learned value function.

---

## 11. Implementation Roadmap

- [x] **Step 1**: Add hard drop action to `GameState` and `Board`
- [x] **Step 2**: Create `ai/` package with network, replay buffer, agent
- [x] **Step 3**: Implement reward function and board feature extraction
- [x] **Step 4**: Wire `AIState` (subclass of `GameState`) into FSM
- [x] **Step 5**: Implement training loop with ε-greedy exploration
- [x] **Step 6**: Add model save/load and training resume
- [x] **Step 7**: Add AI HUD overlay (epsilon, episode, score)
- [x] **Step 8**: Evaluate on 1,000 games, tune hyperparameters
- [x] **Step 9**: Introduce macro-actions for training speedup
- [x] **Step 10**: Implement Double DQN (online selects, target evaluates)
- [x] **Step 11**: BFS soft-drop with hole minimization (overhang access)
- [x] **Step 12**: Delta-based hole penalty in reward function
- [x] **Step 13**: Configurable ε decay/end in AI submenu
- [x] **Step 14**: AI HUD statistics table with trend row
- [x] **Step 15**: Settings persistence (`settings.json`)
- [x] **Step 16**: Score-vs-episode graph in AI submenu (matplotlib)
- [x] **Step 17**: Per-candidate V-function evaluation (rotation + column + hard-drop)
- [x] **Step 18**: DT-20 feature set (17-dim engineered features replace 220-dim raw board)
- [x] **Step 19**: PBRS with Dellacherie board value potential
- [ ] **Step 20**: Compare DQN vs NEAT approaches
---

## Summary

```
Human selects "Joueur : IA"
        ↓
AIState launched (subclass of GameState)
        ↓
AI agent generates candidate states (17 DT-20 features each)
        ↓
ε-greedy evaluates V per candidate, picks max
        ↓
Action executed: replay move sequence (soft-drop BFS path)
        ↓
Reward computed (delta holes, lines, height, bumpiness + PBRS)
        ↓
Experience stored in replay buffer (delayed: s + s' from consecutive placements)
        ↓
V-network Bellman updates from mini-batch
        ↓
Repeat until game over
        ↓
Model + settings saved, episode logged
        ↓
Next episode begins (faster, smarter)

The AI starts knowing nothing. Through thousands of games, it discovers
that clearing lines is good, creating holes is bad, and keeping the
surface flat leads to higher scores. The result is an agent that plays
Tetris as well as — or better than — a skilled human.

---

## Limitations de l'IA

L'IA utilise un espace d'actions basé sur le **soft-drop BFS avec planification de séquence de mouvements** : pour chaque pièce, elle énumère toutes les positions atteignables via BFS (déplacement latéral, chute douce, rotation avec SRS wall kicks), enregistre la séquence de mouvements atomiques pour chaque placement, simule le placement, et évalue le plateau résultant via la V-function. La séquence est ensuite rejouée par `_execute_move_sequence` pour garantir que la pièce atteint la position évaluée. Cette approche couvre les surplombs et les T-Spins.

### Surplombs et placements en glissé

✅ **Implémenté** — Le soft-drop BFS énumère les placements sous les surplombs. La pièce peut glisser horizontalement pendant la descente pour se loger sous une structure.

### T-Spins

✅ **Partiellement implémenté** — Les wall kicks SRS sont intégrés dans le simulateur (`SRS_KICKS_JLSTZ`, `SRS_KICKS_I`), permettant les rotations dans des espaces restreints. La détection explicite de T-Spin (3 coins occupés) et le bonus de score ne sont pas implémentés.

### Wall kicks (SRS)

✅ **Implémenté** — Les tables de wall kicks SRS sont utilisées dans le BFS de candidate generation.
