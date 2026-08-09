# Repository Guidelines

## Project Overview

A Python pygame Tetris game with an embedded Deep Q-Network (DQN) AI agent that learns to play. UI labels are in French. Runs as a desktop app at 60 FPS with a finite state machine (FSM) driving navigation between menus, gameplay, AI training, and stats views.

## Architecture & Data Flow

```
main.py → tetris.run() → TetrisApp.run()
                            │
                            └─ FSM loop (60 FPS):
                                 1. event.get() → state.handle_event(event) → Optional[State]
                                 2. state.update(dt, particles)            → Optional[State]
                                 3. state.draw(screen)
                                 4. display.flip() + particles.update()
```

Returning a new `State` from `handle_event`/`update` transitions the app; `None` stays. Concrete states are imported lazily inside methods to avoid import cycles (`tetris/states/base.py`).

**Layering** (domain → presentation → persistence):
- `tetris/game/` — pure game logic (board, tetromino, scoring, stats, piece provider)
- `tetris/visuals/` — rendering + particle effects (no game logic)
- `tetris/audio/` — procedural sound synthesis via NumPy
- `tetris/storage/` — JSON persistence (leaderboard, human stats)
- `tetris/states/` — FSM states binding input → game logic → rendering
- `tetris/ai/` — DQN agent, network, replay buffer, reward shaping, training log

### State Machine Tree

```
MenuState (root, owns settings)
├── HumanMenuState → { KeybindState, HumanStatsState }
├── AIMenuState → { TrainingMenuState → { HyperparamMenuState, PlaceholderState }, StatsState }
├── GameState   (human gameplay)
├── AIState     (AI gameplay, inherits GameState)
├── LeaderboardState
└── Quit
```

`MenuState` is the settings owner: loads/saves `data/settings.json` via `_load_settings()`/`save_settings()`. Child menu states hold a reference to `MenuState` and mutate its attributes directly, then trigger `save_settings()`.

**`GraphState`** (`tetris/states/graph.py`) is orphaned — `StatsState` replaced it. Safe to delete.

## Key Directories

| Directory | Purpose |
|---|---|
| `tetris/game/` | Pure domain: `Board`, `Tetromino`, `PieceProvider`, `ScoreEngine`, `GameStats` |
| `tetris/states/` | FSM states (`State` base + 15 concrete states) |
| `tetris/ai/` | DQN: `DQNetwork`, `DQNAgent`, `ReplayBuffer`, reward/feature extraction, `TrainingLog` |
| `tetris/visuals/` | `Renderer`, `ParticleSystem`, leaderboard/graph views |
| `tetris/audio/` | `AudioManager` — procedural NumPy sine-wave synthesis |
| `tetris/storage/` | JSON load/save for leaderboard and human game history |
| `data/` | All runtime-generated files (gitignored) |

## Development Commands

```bash
# Install
pip install -r requirements.txt

# Run the game
python main.py

# Lint (ruff 0.16.2 available)
ruff check .

# Headless / smoke test (no display)
SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy python3 -c "import tetris; ..."

# AI training validation (headless, runs N episodes)
python -m tetris.verify_training
```

**Runtime:** Python 3.14.5rc1, pygame-ce 2.5.x, macOS arm64.

**No test suite exists.** Verification is done via headless smoke tests with `SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy` and synthetic `pygame.event.Event(pygame.KEYDOWN, key=K_x)` events.

## Code Conventions & Common Patterns

- **FSM states**: Subclass `State`, override `handle_event`/`update`/`draw`. Transitions return a new `State` or `None`. Import concrete states lazily inside methods (cycle avoidance).
- **Settings flow**: `MenuState` is the single source of truth for runtime settings. Child states mutate `MenuState` attributes, then call `save_settings()`. Never read settings from disk in child states — read from the parent `MenuState` reference.
- **Keybind flow**: `MenuState.keybinds` (dict: action→pygame keycode) → `GameState._setup_keybinds()` builds the active `input_map`. Modified by `KeybindState`.
- **Path constants**: All data paths centralized in `tetris/settings.py` — never hardcode `"data/..."` in consumer modules; import from `settings`.
- **Data directory**: `DATA_DIR = "data"` with `os.makedirs(DATA_DIR, exist_ok=True)` at import time — directory always exists.
- **AI exclusion from human stats**: `save_human_game()` is only called in `GameOverState._handle_name_event()`. `AIState` has its own `_on_episode_end()` and never creates `GameOverState` — architectural guarantee that AI games never pollute human stats.
- **AI gameplay**: `AIState` inherits `GameState`, replaces keyboard input with `DQNAgent.select_action()` macro-actions (rotation + column + BFS drop to deepest reachable position). Learning mode does `LEARN_PER_ACTION = 2` gradient updates per locked piece; playing mode sets epsilon=0 (greedy), skips transition storage/learning/episode logging.
- **Rendering**: `Renderer` is pure presentation — takes game state, draws to surface. `ParticleSystem` handles physics-based effects. Fonts are proportional (Arial), so use explicit pixel-positioned columns, not format-string alignment (`f"{x:<10}"` won't align).
- **Naming**: `PascalCase` classes, `snake_case` functions/variables, `UPPER_CASE` constants in `settings.py`.

## Important Files

| File | Role |
|---|---|
| `main.py` | Entry point → `tetris.run()` |
| `tetris/app.py` | `TetrisApp` — main loop, pygame init, state dispatch |
| `tetris/settings.py` | All constants, path constants, `DEFAULT_KEYBINDS`, `KEYBIND_LABELS`, `key_name()` |
| `tetris/states/base.py` | `State` base class contract |
| `tetris/states/menu.py` | Root menu, settings load/save, navigation hub |
| `tetris/states/game.py` | Human gameplay loop, `_setup_keybinds()` |
| `tetris/states/ai.py` | AI gameplay + RL training integration |
| `tetris/ai/agent.py` | `DQNAgent` — `select_action`, `store`, `learn`, `save`, `load` |
| `tetris/ai/rewards.py` | `extract_state` (220-dim vector) + `compute_reward` |
| `tetris/ai/network.py` | `DQNetwork` — 220→256→128→64→40 MLP |
| `tetris/verify_training.py` | Headless training validation script |
| `data/settings.json` | Persisted menu settings + keybinds |
| `requirements.txt` | Dependencies: pygame>=2.5.0, numpy>=1.24.0, torch>=2.0, matplotlib>=3.7.0 |

## Runtime/Tooling Preferences

- **Python 3.14.5rc1** (any 3.9+ works; uses `dict[str, int]` generics)
- **pygame-ce** (pygame Community Edition) 2.5.x — not stock pygame
- **PyTorch** for the DQN
- **No package manager** — plain `pip install -r requirements.txt`
- **No pyproject.toml** — project uses `requirements.txt` only
- **ruff** for linting (`ruff check .`); pre-existing I001/DTZ005/PLR0402 diagnostics are known and not our concern
- **Headless testing** requires `SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy`
- **Vision model unavailable for image files** — use pixel-level analysis via `screen.get_at()` instead

## Testing & QA

No formal test framework. Verification patterns:

```bash
# Lint
ruff check .

# Headless smoke test pattern
SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy python3 -c "
import pygame
from tetris.states.menu import MenuState
# ... drive states with synthetic events ...
pygame.event.Event(pygame.KEYDOWN, key=pygame.K_x)
"

# AI training validation
python -m tetris.verify_training
# Success criteria: best_score > 10000, avg_score > 1000,
# avg_duration > 30s, max_loss < 1000
```

## Data Files

All in `data/` (gitignored via blanket `data/` rule):

| File | Path constant | Format | Purpose |
|---|---|---|---|
| `settings.json` | `SETTINGS_PATH` | JSON | Menu prefs, AI hyperparams, keybinds |
| `leaderboard.json` | `LEADERBOARD_PATH` | JSON | Top 10 scores (capped) |
| `human_stats.json` | `HUMAN_STATS_PATH` | JSON | Unbounded human game history |
| `ai_model.pt` | `MODEL_PATH` | PyTorch | DQN weights + optimizer + epsilon |
| `ai_training_log.json` | `LOG_PATH` | JSON | Per-episode training metrics |
| `replay_pieces.json` | `REPLAY_PATH` | JSON | Stored piece sequences for Replay mode |

**`settings.json` schema**: `player` ("Humain"/"IA"), `mode` ("Normal"/"Replay"), `handicap` (0-5), `sound` (bool), `ai_speed` ("normal"/"fast"), `ai_epsilon_decay` (float), `ai_epsilon_end` (float), `ai_mode` ("learning"/"playing"), `keybinds` (dict: action→pygame keycode).

## DQN AI Specifics

- **Network**: `DQNetwork` — Input(220) → Dense(256, ReLU) → Dense(128, ReLU) → Dense(64, ReLU) → Output(40, Linear). 40 macro-actions = (10 columns × 4 rotations).
- **State vector** (`extract_state`, 220-dim): board cells (200) + current piece one-hot (7) + next piece one-hot (7) + orientation one-hot (4) + normalized x (1) + normalized y (1).
- **Hyperparameters**: lr=1e-4, gamma=0.97, epsilon 1.0→0.10 (decay 0.999/episode, configurable), batch=64, target sync=500 steps, buffer capacity=50,000. Double DQN, SmoothL1Loss, grad clipping at 1.0.
- **Reward** (`compute_reward`): +50×lines + 5×lines², +1.0 survival, -10.0 game over, -5.0 per new hole, -0.1 per total hole, -0.05×height, -0.1×bumpiness.
- **Modes**: `ai_mode="learning"` (epsilon-greedy + training updates + logging) vs `"playing"` (greedy, epsilon=0, no learning). Set in `AIState.__init__` after `agent.load(MODEL_PATH)`.