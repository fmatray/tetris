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
| Algorithm | Deep Q-Network (DQN) | Discrete action space, well-suited for board games |
| Experience Replay | Yes (buffer size 50,000) | Stabilizes training by breaking correlation |
| Target Network | Yes (sync every 500 steps) | Reduces moving-target instability |
| Exploration | ε-greedy, decay 1.0 → 0.10 (0.999/episode) | Balances exploration vs exploitation |

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

---

## 3. Action Space

The AI uses **macro-actions**: one decision per piece, specifying the
target column and rotation. The game then automatically rotates and
moves the piece to the target position and hard-drops it.

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

```
MacroAction = (column: int, rotation: int)
```

---

## 4. Reward Function

The reward shapes the AI's behavior. Every time a piece locks, the AI
receives a reward:

```
reward = (
    +50.0  × lines_cleared
    +5.0   × lines_cleared²          # bonus for multi-line clears
    -0.5   × holes                   # absolute board holes penalty
    -0.05  × aggregate_height        # absolute stack height penalty
    -0.1   × bumpiness               # absolute surface unevenness penalty
    -10.0  if game_over               # terminal penalty
    +1.0   per piece placed           # strong survival incentive
)
```

### 4.1 Feature Definitions

| Feature | Formula |
| --------- | --------- |
| `lines_cleared` | Number of rows completed this placement |
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
│  Play       │     │  (ε decay)   │     │  (ε = 0.05)  │
└─────────────┘     └──────────────┘     └──────────────┘
```

1. **Random Play** — ε = 1.0, pure exploration. Fills replay buffer
   with diverse experiences. (~10,000 steps)
2. **Training** — ε decays from 1.0 to 0.05. Network learns Q-values
   from replay buffer samples. (~500,000 steps)
3. **Exploit** — ε = 0.05, mostly greedy. AI plays near-optimally.
   Continue learning but slowly.

### 6.2 Episode = One Game

An episode runs from game start to game over. One macro-action per piece:

1. Observe state `s` (board + current/next piece)
2. Select action `a` via ε-greedy with action masking
3. Execute `a`: rotate + move to target column, hard-drop
4. Observe reward `r` (absolute board quality + line bonus) and next state `s'`
5. Store `(s, a, r, s', done)` in replay buffer
6. Run 2 Double DQN gradient updates via mini-batch sampling
7. Periodically sync target network (every 500 steps)
8. Decay ε once per episode

| File | Purpose |
| ------ | --------- |
| `ai_model.pt` | Trained Q-network weights |
| `ai_replay_buffer.pkl` | Saved experience replay (for resuming training) |
| `ai_training_log.json` | Per-episode stats (score, lines, epsilon) |

---

## 7. Integration with Existing Architecture

### 7.1 New Files

```
tetris/
├── ai/
│   ├── __init__.py
│   ├── agent.py          # DQN agent (select action, learn)
│   ├── network.py        # PyTorch model definition
│   ├── replay_buffer.py  # Experience replay buffer
│   ├── rewards.py        # Reward function & board features
│   └── trainer.py        # Training loop orchestration
├── ai_model.pt           # Trained weights (generated)
└── tetris/
    └── states/
        └── game.py       # Modified to support AI mode
```

### 7.2 FSM Changes

```
MenuState (Joueur: IA)
    ↓
GameState (human_input=False)
    ↓
  AI agent replaces keyboard input
  AI calls state.board methods directly:
    - board.move(dx)
    - board.rotate(clockwise)
    - board.drop()
    - board.lock_piece()

### 7.3 GameState Modifications

`GameState` (in `tetris/states/game.py`) needs a flag `self.is_ai`:

```python
class GameState(State):
    def __init__(self, screen, font, audio, handicap, is_ai=False):
        ...
        self.is_ai = is_ai
        self.agent = AIAgent() if is_ai else None
```

In `GameState.update()`:

```python
if self.is_ai and self.agent:
    action = self.agent.select_action(self.get_state_vector())
    self.execute_ai_action(action)
else:
    # normal human timing logic
```

### 7.4 Rendering AI Games

- Run AI games at **accelerated speed** (skip frame delays).
- Display "AI MODE" overlay on screen.
- Show current ε (epsilon) and episode count in HUD.
- Allow `ESC` to return to menu during AI play.
- Optional: render only every Nth frame for speed during training.

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

- **Double DQN** — reduces overestimation bias in Q-values.
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
- [ ] **Step 10**: Compare DQN vs NEAT approaches
---

## 12. Dependencies

```
# requirements-ai.txt (optional)
torch>=2.0
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
GameState launched with is_ai=True
        ↓
AI agent observes board state (220 features)
        ↓
ε-greedy selects action (move/rotate/drop)
        ↓
Action executed in game engine
        ↓
Reward computed (lines, holes, height, bumpiness)
        ↓
Experience stored in replay buffer
        ↓
Q-network updated from mini-batch
        ↓
Repeat until game over
        ↓
Model saved, episode logged
        ↓
Next episode begins (faster, smarter)
```

The AI starts knowing nothing. Through thousands of games, it discovers
that clearing lines is good, creating holes is bad, and keeping the
surface flat leads to higher scores. The result is an agent that plays
Tetris as well as — or better than — a skilled human.
