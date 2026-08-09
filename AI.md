# AI Player Mode — Design Document

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
| Algorithm | Double DQN | Reduces overestimation bias; online net selects, target net evaluates |
| Experience Replay | Yes (buffer size 50,000) | Stabilizes training by breaking correlation |
| Target Network | Yes (sync every 500 steps) | Reduces moving-target instability |
| Exploration | ε-greedy, decay 1.0 → ε_end (configurable) | Balances exploration vs exploitation |

### 1.2 Alternative: NEAT (Future)

If DQN proves too heavy, a fallback approach using **NEAT** (Neural
Evolution of Augmenting Topologies) can evolve a population of neural
networks over many games. This is lighter on memory and easier to visualize.

---

## 2. State Representation

The AI perceives the board as a **feature vector**, not raw pixels. This
keeps the input dimensionality low and training fast.

### 2.1 Board Encoding

The board is a `BOARD_HEIGHT × BOARD_WIDTH` grid (20×10). Each cell is:

- `0` — empty
- `1` — occupied

Flattened into a 1D tensor of size **200**.

### 2.2 Current Piece

One-hot encoded vector of size **7** (I, O, T, S, Z, J, L).

### 2.3 Next Piece

One-hot encoded vector of size **7** (enables planning ahead).

### 2.4 Piece Orientation

One-hot encoded vector of size **4** (0°, 90°, 180°, 270°).

### 2.5 Full State Vector

```
State = [board_with_piece(200), current_piece(7), next_piece(7), orientation(4), piece_x_norm(1), piece_y_norm(1)]
Total = 220 floats
```

---

## 3. Action Space

The AI uses **macro-actions**: one decision per piece, specifying the
target column and rotation. The game then automatically rotates and
moves the piece to the target column, then **BFS soft-drop** to the
best reachable position — allowing placement under overhangs.

| Action ID | Rotation | Column |
| ----------- | -------- | ------ |
| 0–9 | 0 | 0–9 |
| 10–19 | 1 | 0–9 |
| 20–29 | 2 | 0–9 |
| 30–39 | 3 | 0–9 |

Action ID = `rotation × 10 + column`. Invalid placements (piece
doesn't fit at that column/rotation) are masked during action
selection. Pieces with fewer rotations (e.g., O: 1, I/S/Z: 2) have
fewer valid actions.

### 3.1 BFS Placement (Soft-Drop with Hole Minimization)

After the piece is rotated and moved to the target column, a BFS
explores all reachable terminal positions (down, left, right from
the current position). A position is terminal when the piece cannot
move down further. Among all terminals, the BFS selects the one that
**minimizes holes** after placement, with **depth as tie-breaker**
(deepest first). This enables:

```
reward = (
    +50.0  × lines_cleared
    +5.0   × lines_cleared²           # bonus for multi-line clears
    -5.0   × holes_created             # delta: NEW holes only
    -0.1   × new_holes                 # residual absolute holes penalty
    -0.05  × aggregate_height           # stack height penalty
    -0.1   × bumpiness                  # surface unevenness penalty
    -10.0  if game_over                 # terminal penalty
    +1.0   per piece placed             # survival incentive
)
```

The hole penalty is **delta-based** (`new_holes - old_holes`): the
agent learns which actions create holes rather than inheriting a
constant penalty for pre-existing holes. A small residual on absolute
holes keeps the agent motivated to clear existing holes over time.

### 4.1 Feature Definitions

| Feature | Formula |
| --------- | --------- |
| `lines_cleared` | Number of rows completed this placement |
| `holes_created` | `max(0, new_holes - old_holes)` — new holes this placement |
| `new_holes` | Empty cells with at least one filled cell above them |
| `aggregate_height` | Sum of heights of all columns |
| `bumpiness` | Σ ` | height[i] - height[i+1] | ` for adjacent columns |
---

## 5. Neural Network Architecture

```
Input  (220)
  ↓
Dense (256, ReLU)
  ↓
Dense (128, ReLU)
  ↓
Dense (64, ReLU)
  ↓
Output (40, Linear) → Q-values per macro-action (column × rotation)
```

- **Optimizer**: Adam, learning rate 1e-4 (with gradient clipping at 1.0)
- **Loss**: SmoothL1Loss (Huber) — Double DQN target
- **Batch size**: 64
- **Discount factor (γ)**: 0.97

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

These are configurable in the **AI submenu** and persisted to
`settings.json`.

### 6.3 Episode = One Game

An episode runs from game start to game over. One macro-action per piece:

1. Observe state `s` (board + current/next piece)
2. Select action `a` via ε-greedy with action masking
3. Execute `a`: rotate + move to target column, BFS soft-drop
4. Observe reward `r` (delta holes + line bonus + board quality) and next state `s'`
5. Store `(s, a, r, s', done)` in replay buffer
6. Run 2 Double DQN gradient updates via mini-batch sampling
7. Periodically sync target network (every 500 steps)
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
│   ├── agent.py          # DQNAgent (ε-greedy, Double DQN, replay, target net)
│   ├── network.py        # DQNetwork (220→256→128→64→40)
│   ├── replay_buffer.py  # Experience replay buffer (50,000)
│   ├── rewards.py        # Reward function & board feature extraction
│   └── trainer.py        # TrainingLog (per-episode JSON persistence)
├── states/
│   ├── ai.py             # AIState (subclass of GameState)
│   ├── ai_menu.py         # AI submenu (speed, ε decay, ε end, graph, reset)
│   ├── graph.py           # GraphState (score-vs-episode matplotlib view)
│   └── menu.py           # MenuState (settings.json persistence)
```

### 7.2 FSM Architecture

```
MenuState (Joueur: IA)
    ↓
AIState (subclass of GameState)
    ↓
  AI agent selects macro-action (column + rotation)
  AIState executes action:
    - Rotate piece to target rotation
    - Move to target column
    - BFS soft-drop to best reachable position
    - Lock piece → compute reward → store transition → learn
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
| **Average Q-value** | Network confidence over time |

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
| **Sparse rewards** (few lines cleared early) | Shape reward with height/bumpiness penalties |
| **Catastrophic forgetting** | Experience replay + target network |
| **Slow training** | Macro-actions + frame skipping |
| **Overfitting to one piece sequence** | Randomized piece generator (already in `tetris/game/tetromino.py`) |
| **Memory growth** | Cap replay buffer; LRU eviction |

---

## 10. Future Enhancements

- ~~**Double DQN**~~ — ✅ Implemented. Online net selects best action, target net evaluates it.
- **Prioritized Experience Replay (PER)** — sample important transitions more.
- **Curriculum Learning** — start with only I and O pieces, gradually
  add harder pieces.
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
- [ ] **Step 17**: Compare DQN vs NEAT approaches

## 12. Dependencies

```
# requirements-ai.txt (optional)
torch>=2.0
matplotlib>=3.7.0
```

Install with:

```bash
pip install -r requirements-ai.txt
```

The base game remains playable without PyTorch. If the user selects
**Joueur : IA** without PyTorch installed, display a message:

> *"IA nécessite PyTorch. Installez avec `pip install torch`."*

---

## Summary

```
Human selects "Joueur : IA"
        ↓
AIState launched (subclass of GameState)
        ↓
AI agent observes board state (220 features)
        ↓
ε-greedy selects macro-action (column × rotation)
        ↓
Action executed: rotate → move → BFS soft-drop
        ↓
Reward computed (delta holes, lines, height, bumpiness)
        ↓
Experience stored in replay buffer
        ↓
Double DQN updates Q-network from mini-batch
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
