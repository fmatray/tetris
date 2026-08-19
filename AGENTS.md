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
- `tetris/audio/` — procedural SFX synthesis + MIDI-based polyphonic music
- `tetris/storage/` — JSON persistence (leaderboard, human stats)
- `tetris/states/` — FSM states binding input → game logic → rendering
- `tetris/ai/` — V-network DQN agent, DT-20 features, PBRS reward shaping, PER, n-step returns, soft-drop BFS, training log

### State Machine Tree

```
MenuState (root, owns settings)
├── GameRulesMenuState (generator, preview, handicap)
├── HumanMenuState → { KeybindState, HumanStatsState }
├── AIMenuState → { TrainingMenuState → { HyperparamMenuState, PlaceholderState }, StatsState }
├── AudioMenuState
├── GameState   (abstract base: board, pieces, gravity, lock delay)
│   ├── HumanState (human gameplay: keyboard, DAS, pause)
│   └── AIState   (AI gameplay, inherits GameState)
├── LeaderboardState
└── Quit
```

`MenuState` is the settings owner: loads/saves `data/settings.json` via `_load_settings()`/`save_settings()`. Child menu states hold a reference to `MenuState` and mutate its attributes directly, then trigger `save_settings()`.


## Key Directories

| Directory | Purpose |
|---|---|
| `tetris/game/` | Pure domain: `Board`, `Tetromino`, `PieceProvider` facade + `PieceGenerator` hierarchy (`RandomGenerator`, `BagGenerator`→`SevenBagGenerator`/`ThirtyFiveBagGenerator`, `WeightedGenerator`, `ReplayGenerator`), `ScoreEngine`, `GameStats`, `rules` (grid-agnostic game-rule functions) |
| `tetris/states/` | FSM states (`State` base + 15 concrete states) |
| `tetris/ai/` | V-network DQN: `DQNetwork` (V-function), `DQNAgent` (per-candidate eval), `PrioritizedReplayBuffer`, DT-20 features + PBRS reward, `TrainingLog`, `candidates.py` (placement generation), `hud.py` (AI HUD rendering). Game-rule functions (SRS kicks, soft-drop BFS) extracted to `tetris/game/rules.py` |
| `tetris/visuals/` | `Renderer`, `ParticleSystem`, leaderboard/graph views |
| `tetris/audio/` | `AudioManager` — NumPy SFX synthesis + MIDI parsing for polyphonic music; `midi_gen` generates `.mid` files |
| `tetris/storage/` | JSON load/save for leaderboard and human game history |
| `tetris/logger.py` | Central logging module — `configure_logging()`, `get_logger()` |
| `tests/` | Pytest suite for game logic and AI components |
| `docs/` | Technical documentation (AI design, Architecture, etc.) |
| `data/` | All runtime-generated files (gitignored) |

## Development Commands

```bash
# Install
pip install -r requirements.txt

# Run the game
python main.py

# Lint and fix (ruff 0.16.3 available)
ruff check --fix .

# Type checker (zuban available)
zuban check .

# Headless / smoke test (no display)
SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy python3 -c "import tetris; ..."

# AI training validation (headless, runs N episodes)
python -m tetris.verify_training
```

**Runtime:** Python 3.14.5rc1, pygame-ce 2.5.x, macOS arm64.

**Test suite**: `tests/` directory with pytest tests for rewards, agent (n-step, PER), board, tetromino, scoring, stats, piece provider, curriculum, trainer, keybind, game-over, visuals, menus, AI states. Run with `SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy python -m pytest tests/ -q`. Coverage: `SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy python -m pytest tests/ --cov=tetris --cov-report=term-missing -q`.

## Code Conventions & Common Patterns

- **FSM states**: Subclass `State`, override `handle_event`/`update`/`draw`. Transitions return a new `State` or `None`. Import concrete states lazily inside methods (cycle avoidance).
- **Keybind flow**: `MenuState.keybinds` (dict: action→pygame keycode) → `HumanState._setup_keybinds()` builds the active `input_map`. Modified by `KeybindState`.
- **Path constants**: All data paths centralized in `tetris/settings.py` — never hardcode `"data/..."` in consumer modules; import from `settings`.
- **Data directory**: `DATA_DIR = "data"`; callers create it via `os.makedirs(DATA_DIR, exist_ok=True)` (done in `TetrisApp.__init__` and `verify_training.py`).
- **AI exclusion from human stats**: `save_human_game()` is only called in `GameOverState._handle_name_event()`. `AIState` has its own `_on_episode_end()` and never creates `GameOverState` — architectural guarantee that AI games never pollute human stats.
- **AI gameplay**: `AIState` inherits `GameState`, replaces keyboard input with per-candidate V-function evaluation. Candidate generation: soft-drop BFS (with SRS wall kicks) or hard-drop; configurable look-ahead depth (`ai_lookahead_depth` 1–3) simulates best next-piece placement. Hold candidates enumerated alongside placement candidates (AI can hold once per lock, same rule as human). `DQNAgent.select_action(candidate_states)` evaluates V per valid placement, picks max. AI uses SRS wall kicks via `board.try_rotate()` (same as human), respects lock delay (`LOCK_DELAY_MS`) for soft-dropped pieces, and re-applies handicap on episode reset. Learning mode fast-forwards lock delay (piece already positioned, `_prev_action` blocks re-selection) and does `learn_per_action` (default 2) gradient updates per locked piece; playing mode respects full lock delay, sets epsilon=0 (greedy), skips transition storage/learning/episode logging.
- **Tetris Guideline gameplay**: Board is 22 rows (20 visible + 2 hidden buffer, `HIDDEN_ROWS` constant). SRS wall kicks via `Board.try_rotate()` using `SRS_KICKS_JLSTZ`/`SRS_KICKS_I` from `settings.py`. All 7 pieces have 4 rotation states (except O). Lock delay (`LOCK_DELAY_MS`=500ms) with reset on move/rotate (max `LOCK_DELAY_RESETS`=15). Non-locking soft drop (accelerated gravity, piece locks only via lock delay). DAS auto-shift (`DAS_DELAY_MS`=170ms initial, `DAS_REPEAT_MS`=50ms repeat). Hold piece via `_hold()` — swap current with held, once per lock. Top-out on spawn overlap or lock entirely above visible field. T-Spin detection via 3-corner T rule (`Board.is_tspin()`), scored via `ScoreEngine.tspin_points()`. Back-to-Back chains (Tetris or T-Spin) tracked in `GameStats.b2b`, ×1.5 bonus via `ScoreEngine.b2b_bonus()`. Piece preview: `next_piece` + `preview_pieces` (2 additional).
- **Rendering**: `Renderer` is pure presentation — takes game state, draws to surface. `ParticleSystem` handles physics-based effects. Fonts are proportional (Arial), so use explicit pixel-positioned columns, not format-string alignment (`f"{x:<10}"` won't align).
- **Music**: MIDI files in `media/` are generated by `tetris/audio/midi_gen.py` (`ensure_midi_files()` called at `AudioManager.__init__`). `AudioManager._parse_midi()` reads `.mid` files and synthesizes polyphonic audio via NumPy. Tempo scaling regenerates the buffer at `1/_music_speed` duration. SFX remain procedural NumPy synthesis (separate channel).
- **Logging**: Use `from tetris.logger import get_logger` and `logger = get_logger(__name__)` at module level. `logger.debug()` calls are no-ops when debug is OFF (level=WARNING); they write to `data/debug.log` when debug is ON (level=DEBUG). `logger.error()` always writes. Never use `print()` in game modules — only in CLI scripts (`verify_training.py`).
- **Debug mode**: Toggled via the "Débogage" menu option (index 3 in `MenuState._OPTIONS`). When ON, `configure_logging(True)` sets DEBUG level and `GameState.debug=True` enables 7-bag visualization in the renderer. The `debug` flag is read at construction time, not live from menu.
- **Naming**: `PascalCase` classes, `snake_case` functions/variables, `UPPER_CASE` constants in `settings.py`.

## Important Files

| File | Role |
|---|---|
| `main.py` | Entry point → `tetris.run()` |
| `tetris/app.py` | `TetrisApp` — main loop, pygame init, state dispatch |
| `tetris/settings.py` | All constants, path constants, `DEFAULT_KEYBINDS`, `KEYBIND_LABELS`, `HIDDEN_ROWS`, `GENERATOR_LABELS` (pure constants — no functions) |
| `tetris/states/base.py` | `State` base class contract |
| `tetris/states/menu.py` | Root menu, settings load/save, navigation hub |
| `tetris/states/audio_menu.py` | Audio sub-menu: sound/music volume, song selection |
| `tetris/states/game_rules_menu.py` | Game rules sub-menu: generator, preview count, handicap |
| `tetris/states/game.py` | `GameState` abstract base: board, pieces, gravity, lock delay, movement primitives |
| `tetris/states/human.py` | `HumanState` — human gameplay: keyboard, DAS, pause, keybind setup |
| `tetris/states/keybind.py` | Keybinding state, `key_name()` (moved from settings.py) |
| `tetris/states/ai.py` | AI gameplay state + RL training integration (candidate generation and HUD rendering extracted to `tetris/ai/candidates.py` and `tetris/ai/hud.py`) |
| `tetris/ai/agent.py` | `DQNAgent` — `select_action`, `store`, `learn`, `save`, `load` |
| `tetris/ai/candidates.py` | Candidate placement generation — `iter_column_positions`, `best_next_placement`, `gen_placements`, `get_candidate_states`. Pure functions, no instance state |
| `tetris/ai/hud.py` | AI training HUD rendering — training params table, stats table, last-5-moves. Pure presentation |
| `tetris/game/rules.py` | Grid-agnostic pure game-rule functions (`shape_fits`, `try_rotation`, `hard_drop_y`, `soft_drop_placements`, `place_cells`, `find_full_rows`) — shared by `Board` (list grid) and AI simulation (numpy grid) |
| `tetris/game/piece_provider.py` | `PieceProvider` facade + `PieceGenerator` hierarchy (`RandomGenerator`, `BagGenerator`→`SevenBagGenerator`/`ThirtyFiveBagGenerator`, `WeightedGenerator`, `ReplayGenerator`) — tetromino spawning with record/replay, curriculum, first-piece safety |
| `tetris/ai/network.py` | `DQNetwork` — 17→128→64→1 V-network MLP |
| `tetris/verify_training.py` | Headless training validation script |
| `data/settings.json` | Persisted menu settings + keybinds |
| `tetris/logger.py` | Central logging — `configure_logging(debug)`, `get_logger(name)` |
| `tetris/audio/midi_gen.py` | MIDI file generation — `ensure_midi_files()`, Korobeiniki/Kalinka note data |
| `requirements.txt` | Dependencies: pygame>=2.5.0, numpy>=1.24.0, torch>=2.0, matplotlib>=3.7.0, mido>=1.3.0 |

## Runtime/Tooling Preferences

- **Python 3.14.5rc1** (any 3.9+ works; uses `dict[str, int]` generics)
- **pygame-ce** (pygame Community Edition) 2.5.x — not stock pygame
- **PyTorch** for the DQN
- **No package manager** — plain `pip install -r requirements.txt`
- **No pyproject.toml** — project uses `requirements.txt` only
- **ruff** for linting (`ruff check .`); pre-existing I001/DTZ005/PLR0402 diagnostics are known and not our concern
- **Headless testing** requires `SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy`
- **Vision model unavailable for image files** — use pixel-level analysis via `screen.get_at()` instead

## UI Layout Rules

When rendering text, tables, or HUD overlays:
- **No overlap**: text and tables must not overlap other text, tables, the game board, or pieces. Use explicit pixel positions from `HUD_POSITIONS` and layout constants in `settings.py`.
- **No window overflow**: all rendered elements must stay within `SCREEN_WIDTH` × `SCREEN_HEIGHT` (1500×800). Verify text surface width + x position ≤ `SCREEN_WIDTH`, and y + surface height ≤ `SCREEN_HEIGHT`.
- **Always leave margin**: maintain visible padding between elements and screen edges. No text flush against borders.

## Testing & QA

Verification patterns:

```bash
# Lint
ruff check .

# Type check
zuban check .


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

**Always run `zuban check .` and `ruff check .` before commits — fix all errors.**

## Performance Analysis Tools

All four profilers are installed and available:

| Tool | Purpose | Usage |
|------|---------|-------|
| **cProfile** | Deterministic call-graph profiling | `python -m cProfile -o profile.out -s cumulative script.py` |
| **line_profiler** | Line-level timing on hot functions | Decorate with `@profile`, run `kernprof -lv script.py` |
| **py-spy** | Native sampling profiler (low overhead, flamegraph) | `py-spy record --duration 30 --rate 100 --output flame.svg --pid <PID>` |
| **memory_profiler** | Memory usage tracking | `python -m memory_profiler script.py` |

### Profiling the AI training loop

```bash
# cProfile — 500 training frames
SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy python3 -c "
import cProfile, pstats, io, pygame
pygame.init()
screen = pygame.Surface((800, 600))
font = pygame.font.Font(None, 20)
from tetris.audio import AudioManager
from tetris.states.ai import AIState
from tetris.game.piece_provider import PieceProvider
from tetris.visuals.particles import ParticleSystem
audio = AudioManager(sound_volume=0, music_volume=0)
particles = ParticleSystem()
state = AIState(screen=screen, font=font, audio=audio, handicap=0,
    sound_volume=0, music_volume=0,
    piece_provider=PieceProvider(generator='7bag'),
    speed='fast', ai_mode='learning', lookahead=True, lookahead_depth=1,
    soft_drop=True, preview_count=1, warm_start=True, learn_per_action=2)
dt = 1/60
pr = cProfile.Profile()
pr.enable()
for _ in range(500):
    ns = state.update(dt, particles)
    if ns is not None: state = ns
pr.disable()
pstats.Stats(pr).sort_stats('cumulative').print_stats(20)
"

# py-spy — sample a running training process for 30s
SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy python3 -c "
import pygame, os, subprocess
pygame.init()
# ... setup AIState as above ...
pid = os.getpid()
proc = subprocess.Popen(['py-spy', 'record', '--duration', '30', '--rate', '100',
    '--output', '/tmp/tetris_pyspy.svg', '--pid', str(pid)])
# ... run training loop ...
"
```

See `docs/performance_review.md` for the full profiling report and optimization history.


## Workflow

- **Documentation**: Use the `code-documentation` skill for code documentation, global documentation reviews, and updates. Always update `README.md` and `docs/` when changing features or architecture.
- **Git**: Use the `version-control` skill for all git operations. Always commit and push after modifications with comprehensive messages.

## Data Files

All in `data/` (gitignored via blanket `data/` rule):

| File | Path constant | Format | Purpose |
|---|---|---|---|
| `settings.json` | `SETTINGS_PATH` | JSON | Menu prefs, AI hyperparams, keybinds, debug flag |
| `leaderboard.json` | `LEADERBOARD_PATH` | JSON | Top 10 scores (capped) |
| `human_stats.json` | `HUMAN_STATS_PATH` | JSON | Unbounded human game history |
| `ai_model.pt` | `MODEL_PATH` | PyTorch | DQN weights + optimizer + epsilon |
| `ai_training_log.json` | `LOG_PATH` | JSON | Per-episode training metrics |
| `replay_pieces.json` | `REPLAY_PATH` | JSON | Stored piece sequences for Replay mode |
| `debug.log` | `DEBUG_LOG_PATH` | Text | Debug logging output (when debug ON) |

## Media Files

| File | Path constant | Format | Purpose |
|---|---|---|---|
| `media/korobeiniki.mid` | `MUSIC_SONG_PATHS["korobeiniki"]` | MIDI | Korobeiniki music (melody + bass) |
| `media/kalinka.mid` | `MUSIC_SONG_PATHS["kalinka"]` | MIDI | Kalinka music (melody + bass) |

**`settings.json` schema**: `player` ("Humain"/"IA"), `mode` ("Normal"/"Replay"), `handicap` (0-5), `sound` (int 0-3), `music` (int 0-3), `song` ("korobeiniki"/"kalinka"), `debug` (bool), `ghost_piece` (bool), `preview_count` (int 0/1/3), `piece_generator` ("random"/"7bag"/"35bag"/"weighted"), `ai_speed` ("normal"/"fast"), `ai_epsilon_decay` (float), `ai_epsilon_end` (float), `ai_lr` (float), `ai_gamma` (float), `ai_batch_size` (int), `ai_buffer_size` (int), `ai_mode` ("learning"/"playing"), `ai_curriculum` (bool), `ai_curriculum_freq` (int), `ai_curriculum_epsilon` (str), `ai_warm_start` (bool), `ai_learn_per_action` (int), `ai_lookahead` (bool), `ai_lookahead_depth` (int 1-3), `ai_soft_drop` (bool), `keybinds` (dict: action→pygame keycode, includes `mute` and `hold`)

## DQN AI Specifics

- **Network**: `DQNetwork` — Input(17, normalized) → Dense(128, ReLU) → Dense(64, ReLU) → Output(1, Linear). V-function evaluates board quality per candidate placement.
- **State vector** (`extract_features`, 17-dim DT-20, normalized via `(x - mean) / std`): `[lines_cleared, holes, aggregate_height, bumpiness, max_height, row_transitions, column_transitions, wells, hole_depth, rows_with_holes, *next_piece_one_hot(7)]`.
- **Hyperparameters**: lr=1e-3, gamma=0.97, epsilon 1.0→0.10 (decay 0.999/episode, configurable), batch=64, Polyak τ=0.005 (soft target update every step), buffer capacity=50,000 (PrioritizedReplayBuffer, α=0.6, β=0.4→1.0). N-step returns (N=3, per-transition `gamma^n` discount). V-function Bellman, SmoothL1Loss (IS-weighted), grad clipping at 1.0. `seed` param (default `None`) for reproducible init; `device` param (default `auto` → CUDA if available else CPU). Checkpoint loading uses `weights_only=True`.
- **Candidate generation**: soft-drop BFS (`soft_drop_placements` in `tetris/game/rules.py`) with SRS wall kicks (`SRS_KICKS_JLSTZ`, `SRS_KICKS_I`) — enumerates all reachable placements including overhangs. Hold candidates: when `_can_hold` is True, the AI also enumerates placements for the held piece (or next piece if hold is empty), doubling the candidate space. Look-ahead depth configurable (`ai_lookahead_depth` 1–3): simulates best next-piece placement (Dellacherie-optimal) for N upcoming pieces. Hard-drop fallback when soft-drop is OFF (uses `_iter_column_positions` helper shared by hard-drop and look-ahead paths). All game-rule functions are grid-agnostic in `tetris/game/rules.py`, shared between `Board` (list grid) and AI simulation (numpy grid).
- **Modes**: `ai_mode="learning"` (epsilon-greedy + training updates + logging, fast-forwards lock delay) vs `"playing"` (greedy, epsilon=0, no learning, full lock delay). Set in `AIState.__init__` after `agent.load(MODEL_PATH)`. Training uses `lookahead_depth=1` + `preview_count=1` in `verify_training.py` for speed (6.9× faster); playing uses `lookahead_depth=3` + `preview_count=3` for best move quality. `online_net.eval()` during `select_action`, `online_net.train()` during `learn` (future-proofs for dropout/BN).
