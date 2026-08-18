# AI Player Mode — Design Document

(Updated: 2026-08-10)


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
| Target Network | Yes (Polyak averaging τ=0.005, every step) | Reduces moving-target instability |
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

Two modes:

**Hard-drop** (default when soft-drop is OFF): for each valid
(rotation, column) combination, simulate hard-drop + line clear.

**Soft-drop BFS** (default when soft-drop is ON): BFS over
(x, y, rotation) states — move left/right, soft-drop, rotate with
SRS wall kicks. Enumerates ALL reachable landing positions, including
placements under overhangs that hard-drop cannot reach. Uses SRS
wall kick tables (`SRS_KICKS_JLSTZ`, `SRS_KICKS_I`) for rotation
around obstacles.

**2-piece look-ahead** (when enabled): after simulating the current
piece placement, simulate the best placement of the NEXT piece on
the resulting board (Dellacherie-optimal). The V-network evaluates
the board after both pieces are placed.

For each candidate:
1. Simulate placement (hard-drop or soft-drop BFS)
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

`PBRS_SCALE = 0.1` caps the PBRS contribution to ±20, keeping it
meaningful without dominating the base reward (±130).

## 5. Neural Network Architecture

```
Input  (17, normalized)
  ↓
Dense (128, ReLU)
  ↓
Dense (64, ReLU)
  ↓
Output (1, Linear) → V(board) = board value
```

- **Optimizer**: Adam, learning rate 1e-3 (with gradient clipping at 1.0)
- **Loss**: SmoothL1Loss (Huber) — V-function Bellman target
- **Batch size**: 64
- **Discount factor (γ)**: 0.97
- **Polyak τ**: 0.005 (soft target update every step)
- **Device**: `auto` (CUDA if available, else CPU). No MPS — transfer overhead negates gains on this small network.
- **Seed**: `None` by default (non-deterministic). Set `seed=N` for reproducible weight init + sampling.
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
| `ai_soft_drop` | ON | ON/OFF | toggle |

Constructor-only parameters (not in menu, for `verify_training` / programmatic use):

| Parameter | Default | Description |
| --------- | ------- | ----------- |
| `seed` | `None` | Random seed for reproducible training (`torch` + `numpy` + `random`) |
| `device` | `auto` | Torch device: `auto` (CUDA if available), `cpu`, or `cuda` |


These are configurable in the **AI submenu** and persisted to
`settings.json`.

### 6.3 Episode = One Game

An episode runs from game start to game over. One macro-action per piece:

1. Generate candidate states: enumerate valid (rotation, column) placements, simulate hard-drop + line clear, extract DT-20 features
2. Select candidate via ε-greedy: random or `argmax(V(candidate_states))`
3. Execute placement: rotate → move to column → hard-drop → lock
4. Observe reward `r` (delta holes + line bonus + board quality + PBRS shaping)
5. Store `(s, 0, r, s', done)` in n-step buffer → PER (delayed: s = board after prev placement, s' = board after this placement)
6. Run `learn_per_action` V-function Bellman gradient updates via prioritized mini-batch (IS-weighted)
7. Polyak soft target update (τ=0.005, every step)
8. Decay ε once per episode

| File | Purpose |
| ------ | --------- |
| `data/ai_model.pt` | Trained Q-network weights + optimizer state + ε |
| `data/ai_training_log.json` | Per-episode stats (score, lines, level, steps, ε, loss) |
| `data/settings.json` | Menu options + AI hyperparameters (ε decay, ε end, speed) |

---

## 7. Integration with Existing Architecture

### 7.1 File Structure

```
tetris/
├── ai/
│   ├── __init__.py
│   ├── network.py        # DQNetwork (17→128→64→1 V-network)
│   ├── replay_buffer.py  # Experience replay buffer (50,000)
│   ├── rewards.py        # DT-20 features, Dellacherie value, PBRS reward, simulation helpers
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
  AI generates candidate states (rotation + column + hard-drop simulation)
  AI evaluates V(candidate_states) per-candidate, picks max
  AIState executes action:
    - Rotate piece to target rotation
    - Move to target column
    - Hard-drop to lowest position
    - Lock piece → compute reward (PBRS) → store transition → learn
```

`AIState` inherits all board, piece, stats, and rendering logic from
`GameState`. It overrides:

- `update()` — AI macro-action selection and execution
- `_lock_and_spawn()` — intercepts piece locking for reward + transition
- `render()` — draws AI HUD overlay (training + statistics table)
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
| **Slow training** | Macro-actions + DT-20 features (17-dim vs 220-dim) + frame skipping |
| **Reward hacking** | PBRS (policy-preserving, Ng et al. 1999) — cannot change optimal policy |
| **Overfitting to one piece sequence** | Randomized piece generator (already in `tetris/game/tetromino.py`) |
| **Memory growth** | Cap replay buffer; LRU eviction |

---

## 10. Future Enhancements
- ~~**Double DQN**~~ — ✅ Implemented (now V-network DQN).
- ✅ **Per-candidate evaluation** — V-network evaluates V(resulting_board) per valid placement.
- ✅ **DT-20 features** — 17-dim engineered features replace 220-dim raw board.
- ✅ **PBRS** — Potential-based reward shaping with Dellacherie board value.
- ✅ **Prioritized Experience Replay (PER)** — Proportional PER with IS weights (Schaul et al. 2015).
- ✅ ~~**Soft target update (Polyak averaging)**~~ — Implemented (τ=0.005, every step).
- ✅ ~~**Heuristic warm-start**~~ — Implemented (Dellacherie-weighted softmax exploration).
- ✅ ~~**Curriculum Learning**~~ — Implemented (O → I → L → J → T → S → Z).
- ✅ **N-step returns** — 3-step Bellman targets for faster credit assignment.
- ✅ **Soft-drop BFS** — SRS wall kicks + BFS candidate generation (overhangs, T-Spins).
- ✅ **2-piece look-ahead** — Simulate best next-piece placement before evaluation.
- ✅ **Feature normalization** — Standardize DT-20 features (mean/std) before network input.
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
Action executed: rotate → move → hard-drop
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

L'IA utilise un espace d'actions basé sur le **soft-drop BFS** : pour chaque pièce, elle énumère toutes les positions atteignables via BFS (déplacement latéral, chute douce, rotation avec SRS wall kicks), simule le placement, et évalue le plateau résultant via la V-function. Cette approche couvre les surplombs et les T-Spins.

### Surplombs et placements en glissé

✅ **Implémenté** — Le soft-drop BFS énumère les placements sous les surplombs. La pièce peut glisser horizontalement pendant la descente pour se loger sous une structure.

### T-Spins

✅ **Partiellement implémenté** — Les wall kicks SRS sont intégrés dans le simulateur (`SRS_KICKS_JLSTZ`, `SRS_KICKS_I`), permettant les rotations dans des espaces restreints. La détection explicite de T-Spin (3 coins occupés) et le bonus de score ne sont pas implémentés.

### Wall kicks (SRS)

✅ **Implémenté** — Les tables de wall kicks SRS sont utilisées dans le BFS de candidate generation.
