# Repository Guidelines

## Project Overview

A Python pygame Tetris game with an embedded Deep Q-Network (DQN) AI agent that learns to play. UI labels are internationalized (English default; French, Spanish, Slovenian available via on-the-fly language menu). Runs as a desktop app at 60 FPS with a finite state machine (FSM) driving navigation between menus, gameplay, AI training, and stats views.

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
- `tetris/bots/` — shared bot-algorithm library (`BotMovesMixin` candidate enumeration + BFS move replay), reused by `AIState` and `ElTetrisState`
- `tetris/ai/` — V-network DQN agent, DT-20 features, PBRS reward shaping, PER, n-step returns, soft-drop BFS, training log
- `tetris/mcp_server.py` — MCP HTTP server (FastMCP): exposes `play` + `start_game` tools and board/rules resources to external agents

### State Machine Tree

```
MenuState (root, owns settings)
├── GameRulesMenuState (generator, preview, handicap, speed, ghost piece)
├── HumanMenuState → { SeedEntryState, KeybindState, HumanStatsState }
├── AIMenuState → { TrainingMenuState → { HyperparamMenuState, PlaceholderState }, TournamentMenuState → { TournamentState, TournamentStatsState }, AIStatsState }
├── BotMenuState (El-Tetris lookahead)
├── MCPMenuState (port, retour)
├── AudioMenuState
├── GameState   (abstract base: board, pieces, gravity, lock delay)
│   ├── HumanState (human gameplay: keyboard, DAS, pause)
│   ├── AIState   (AI gameplay, inherits BotMovesMixin + GameState)
│   ├── ElTetrisState (El-Tetris bot, inherits BotMovesMixin + GameState)
│   └── MCPState  (MCP gameplay, inherits GameState — external agent via HTTP)
├── LeaderboardState
└── Quit
```

`MenuState` is the settings owner: loads/saves `data/settings.json` via `_load_settings()`/`save_settings()`. Child menu states hold a reference to `MenuState` and mutate its attributes directly, then trigger `save_settings()`.


## Key Directories

| Directory | Purpose |
|---|---|
| `tetris/game/` | Pure domain: `Board`, `Tetromino`, `shapes` (`SHAPES` rotation data + `SHAPES_TYPES` + helpers), `PieceProvider` facade + `PieceGenerator` hierarchy (`RandomGenerator`, `BagGenerator`→`SevenBagGenerator`/`ThirtyFiveBagGenerator`, `WeightedGenerator`, `ReplayGenerator`), `ScoreEngine`, `GameStats`, `rules` (grid-agnostic game-rule functions + SRS kick data) |
| `tetris/states/` | FSM states (`State` base + 18 concrete states) |
| `tetris/ai/` | V-network DQN: `DQNetwork` (V-function), `DQNAgent` (per-candidate eval), `PrioritizedReplayBuffer`, DT-20 features + PBRS reward, `TrainingLog`, `candidates.py` (placement generation + soft-drop BFS), `mcts.py` (PUCT tree search), `hud.py` (AI HUD rendering). Game-rule functions (SRS kicks) extracted to `tetris/game/rules.py` |
| `tetris/tournament.py` | Evolutionary self-play tournament: Gaussian mutants, uniform crossover, headless playing-mode fitness, in-game loop mode (`run_tournament_loops`), CLI entry point |
| `tetris/visuals/` | `Renderer`, `ParticleSystem`, leaderboard/graph views |
| `tetris/audio/` | `AudioManager` — NumPy SFX synthesis + MIDI parsing for polyphonic music; `midi_gen` generates `.mid` files |
| `tetris/storage/` | JSON load/save for leaderboard and human game history |
| `tetris/logger.py` | Central logging module — `configure_logging()`, `get_logger()` |
| `tests/` | Pytest suite for game logic and AI components |
| `docs/` | Technical documentation (AI design, Architecture, etc.) |
| `data/` | All runtime-generated files (gitignored) |
| `scripts/` | Standalone analysis utilities (`analyze_training.py` — read-only training health report from AI logs) |

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

**Test suite**: `tests/` directory with pytest tests for rewards, agent (n-step, PER), board, tetromino, scoring, stats, piece provider, curriculum, trainer, keybind, game-over, visuals, menus, AI states, dueling, imitation, layout regression (`tests/layout_harness.py` — `RecordingFont`/`RecordingScreen` assert in-bounds, non-overlapping text across EN/FR/ES/SL state draws). Run with `SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy python -m pytest tests/ -q`. Coverage: `SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy python -m pytest tests/ --cov=tetris --cov-report=term-missing -q`.

## Code Conventions & Common Patterns

- **FSM states**: Subclass `State`, override `handle_event`/`update`/`draw`. Transitions return a new `State` or `None`. Import concrete states lazily inside methods (cycle avoidance).
- **Keybind flow**: `MenuState.keybinds` (dict: action→pygame keycode) → `HumanState._setup_keybinds()` builds the active `input_map`. Modified by `KeybindState`.
- **Path constants**: All data paths centralized in `tetris/settings.py` — never hardcode `"data/..."` in consumer modules; import from `settings`.
- **Data directory**: `DATA_DIR = "data"`; callers create it via `os.makedirs(DATA_DIR, exist_ok=True)` (done in `TetrisApp.__init__` and `verify_training.py`).
- **AI exclusion from human stats**: `save_human_game()` is only called in `GameOverState._handle_name_event()`. `AIState` has its own `_on_episode_end()` and never creates `GameOverState` — architectural guarantee that AI games never pollute human stats.
- **AI gameplay**: `AIState` inherits `GameState`, replaces keyboard input with per-candidate V-function evaluation. Candidate generation: soft-drop BFS (with SRS wall kicks) or hard-drop; configurable look-ahead depth (`ai_lookahead_depth` 1–3) simulates best next-piece placement. Hold candidates enumerated alongside placement candidates (AI can hold once per lock, same rule as human). `DQNAgent.select_action(candidate_states)` evaluates V per valid placement, picks max. AI uses SRS wall kicks via `board.try_rotate()` (same as human), respects lock delay (`LOCK_DELAY_MS`) for soft-dropped pieces, and re-applies handicap on episode reset. Learning mode fast-forwards lock delay (piece already positioned, `_prev_action` blocks re-selection) and does `learn_per_action` (default 2) gradient updates per locked piece; playing mode respects full lock delay, sets epsilon=0 (greedy), skips transition storage/learning/episode logging.
- **Tetris Guideline gameplay**: Board is 22 rows (20 visible + 2 hidden buffer, `HIDDEN_ROWS` constant). SRS wall kicks via `Board.try_rotate()` using `SRS_KICKS_JLSTZ`/`SRS_KICKS_I` from `tetris/game/rules.py`. All 7 pieces have 4 rotation states (except O). Lock delay (`LOCK_DELAY_MS`=500ms) with reset on move/rotate (max `LOCK_DELAY_RESETS`=15). Non-locking soft drop (accelerated gravity, piece locks only via lock delay). DAS auto-shift (`DAS_DELAY_MS`=170ms initial, `DAS_REPEAT_MS`=50ms repeat). Hold piece via `_hold()` — swap current with held, once per lock. ARE entry delay (`ARE_MS`=100, toggleable, IRS/IHS buffered) between lock and next-piece activity; AI learning mode skips it. Top-out on spawn overlap or lock entirely above visible field. T-Spin detection via 3-corner T rule (`Board.is_tspin()`), scored via `ScoreEngine.tspin_points()`. Back-to-Back chains (Tetris or T-Spin) tracked in `GameStats.b2b`, ×1.5 bonus via `ScoreEngine.b2b_bonus()`. Clear-type tallies (single/double/triple/tetris) tracked in `GameStats.clear_counts` (`ClearCounts` dataclass), shown in left HUD, exposed in MCP `clear_counts` snapshot key. Piece preview: `next_piece` + `preview_pieces` (2 additional).
- **Rendering**: `Renderer` is pure presentation — takes game state, draws to surface. `ParticleSystem` handles physics-based effects. Fonts are proportional (Arial), so use explicit pixel-positioned columns, not format-string alignment (`f"{x:<10}"` won't align).
- **Music**: MIDI files in `media/` are generated by `tetris/audio/midi_gen.py` (`ensure_midi_files()` called at `AudioManager.__init__`). `AudioManager._parse_midi()` reads `.mid` files and synthesizes polyphonic audio via NumPy. Tempo scaling regenerates the buffer at `1/_music_speed` duration. SFX remain procedural NumPy synthesis (separate channel).
- **Logging**: Use `from tetris.logger import get_logger` and `logger = get_logger(__name__)` at module level. `logger.debug()` calls are no-ops when debug is OFF (level=WARNING); they write to `data/debug.log` when debug is ON (level=DEBUG). `logger.error()` always writes. Never use `print()` in game modules — only in CLI scripts (`verify_training.py`).
- **Debug mode**: Toggled via the "Débogage" menu option (index 8 in `MenuState._OPTIONS`). When ON, `configure_logging(True)` sets DEBUG level and `GameState.debug=True` enables 7-bag visualization in the renderer. During gameplay, pressing **`d`** toggles the visual debug overlay (7-bag visualization, speed info, hole/overhang debug) on all player types (Human, AI, MCP) — this flips `GameState.debug` live without changing the logging level. The `debug` flag is initially read at construction time from menu settings.
- **Naming**: `PascalCase` classes, `snake_case` functions/variables, `UPPER_CASE` constants (in `settings.py`, `tetris/game/shapes.py` for `SHAPES`/`SHAPES_TYPES`, `tetris/game/rules.py` for `SRS_KICKS_*`).

## Important Files

| File | Role |
|---|---|
| `main.py` | Entry point → `tetris.run()` |
| `tetris/app.py` | `TetrisApp` — main loop, pygame init, state dispatch |
| `tetris/settings.py` | All constants, path constants, `DEFAULT_KEYBINDS`, `KEYBIND_LABELS`, `HIDDEN_ROWS`, `GENERATOR_LABELS`, `SHAPES_COLORS`, `HUD_POSITIONS` (pure constants — no functions) |
| `tetris/states/base.py` | `State` base class contract |
| `tetris/states/menu.py` | Root menu, settings load/save, navigation hub |
| `tetris/states/audio_menu.py` | Audio sub-menu: sound/music volume, song selection |
| `tetris/states/game_rules_menu.py` | Game rules sub-menu: generator, preview count, handicap, speed mode, ghost piece |
| `tetris/states/game.py` | `GameState` abstract base: board, pieces, gravity, lock delay, movement primitives; `GameConfig` dataclass (shared gameplay settings) |
| `tetris/states/human.py` | `HumanState` — human gameplay: keyboard, DAS, pause, keybind setup |
| `tetris/states/ai.py` | AI gameplay state + RL training integration (candidate generation and HUD rendering extracted to `tetris/ai/candidates.py` and `tetris/ai/hud.py`); `AIConfig` dataclass (DQN hyperparameters) |
| `tetris/states/tournament_menu.py` | `TournamentMenuState` — tournament sub-menu: loop params, stats, restore checkpoint (two-press confirm), start |
| `tetris/states/tournament.py` | `TournamentState` — runs tournament loops in a daemon thread, draws live progress, Esc = coarse cancel (current generation finishes first) |
| `tetris/states/tournament_stats.py` | `TournamentStatsState` — tournament stats table + best-score-per-loop graph from `data/tournament/loops.json` |
| `tetris/states/seed_entry.py` | `SeedEntryState` — numeric text input for game seed (empty = random) |
| `tetris/states/bot_menu.py` | `BotMenuState` — El-Tetris bot sub-menu: lookahead toggle (Non / Comme aperçu) |
| `tetris/states/eltetris.py` | `ElTetrisState` — El-Tetris bot gameplay state (`BotMovesMixin` + `GameState`); `BotConfig` dataclass. No learning, no logs, game over returns to menu |
| `tetris/bots/moves.py` | `BotMovesMixin` — shared candidate enumeration (`_get_candidate_states`) + BFS move replay (`_execute_move_sequence`), reused by `AIState` and `ElTetrisState` |
| `tetris/states/mcp_menu.py` | `MCPMenuState` — MCP sub-menu: port selection, back |
| `tetris/mcp_server.py` | `TetrisMCPServer` — MCP HTTP server (FastMCP streamable-http): `play` + `start_game` tools, `board://state` + `tetris://rules` resources. Daemon thread, queue-based communication with `MCPState` |
| `tetris/ai/agent.py` | `DQNAgent` — `select_action`, `store`, `learn`, `save`, `load` |
| `tetris/ai/hud.py` | AI training HUD rendering — training params table, stats table, last-5-moves, cooking-state indicator (4-signal health scoring: score trend, TD error trend, V-margin, epsilon + thermometer bar). Pure presentation |
| `tetris/game/rules.py` | Grid-agnostic pure game-rule functions (`shape_fits`, `try_rotation`, `hard_drop_y`, `place_cells`, `find_full_rows`), SRS wall-kick data (`SRS_KICKS_JLSTZ`, `SRS_KICKS_I`) — shared by `Board` (list grid) and AI simulation (numpy grid) |
| `tetris/game/shapes.py` | Tetromino shape data (`SHAPES` dict — SRS rotation states), `SHAPES_TYPES` constant, shape-rotation helpers (`num_shape_rot`, `get_shape_rot`) |
| `tetris/game/tetromino.py` | `Tetromino` class — stateful piece model (type, color, rotation, position) |
| `tetris/game/stats.py` | `GameStats` (score, lines, level, combo, B2B, piece count) + `ClearCounts` (single/double/triple/tetris line-clear tallies) |
| `tetris/game/piece_provider.py` | `PieceProvider` facade + `PieceGenerator` hierarchy (`RandomGenerator`, `BagGenerator`→`SevenBagGenerator`/`ThirtyFiveBagGenerator`, `WeightedGenerator`, `ReplayGenerator`) — tetromino spawning with record/replay, curriculum, first-piece safety, seed support for reproducible sequences |
| `tetris/ai/network.py` | `DQNetwork` — 17→256→128→1 V-network MLP |
| `tetris/verify_training.py` | Headless training validation script |
| `scripts/analyze_training.py` | Standalone read-only training analysis — reads all AI logs, produces health report with `[OK]`/`[ATTN]`/`[CRIT]` flags + optional `--charts` PNG output to `data/analysis/` |
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
- **jscpd** for code duplication detection (`npx jscpd .` or jscpd MCP tools); target <1% duplication, configured via `.jscpd.json`

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
# Success criteria: best_score > 10000, avg_score > 1000
```

### Code Duplication (jscpd)

```bash
# Check duplication via CLI
npx jscpd .

# Or use the jscpd MCP tools (preferred):
#   get_statistics       — project-wide duplication stats
#   check_current_directory — rescan after edits
#   get_file_clones       — clones involving a specific file
#   check_duplication     — check a snippet against the project
```

Target: **<1% duplication rate**. Config in `.jscpd.json` (threshold, ignore patterns, min-tokens/lines). Mermaid diagrams in `docs/class_diagram.md` are excluded from scans. Before commits, run `get_statistics` via jscpd MCP; if >1%, use `check_current_directory` then `get_file_clones` to find top offenders and refactor.

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
from tetris.states.game import GameConfig
from tetris.states.ai import AIConfig
from tetris.game.piece_provider import PieceProvider
from tetris.visuals.particles import ParticleSystem
audio = AudioManager(sound_volume=0, music_volume=0)
particles = ParticleSystem()
config = GameConfig(handicap=0, sound_volume=0, music_volume=0, music_song='korobeiniki',
    debug=False, ghost_piece=True, preview_count=1, speed_mode='normal')
ai_config = AIConfig(epsilon_decay=0.999, epsilon_end=0.1, lr=1e-3, gamma=0.97,
    batch_size=64, buffer_size=50_000, ai_mode='learning', curriculum=False,
    curriculum_epsilon='boost', warm_start=True,
    learn_per_action=2, lookahead=True, lookahead_depth=1)
state = AIState(screen=screen, font=font, audio=audio, config=config, ai_config=ai_config,
    piece_provider=PieceProvider(generator='7bag'), speed='fast')
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
| `leaderboard.json` | `LEADERBOARD_PATH` | JSON | Top 10 scores per game mode (marathon/sprint/blitz; per-entry `game_mode` field, sprint entries carry `time_s`) |
| `human_stats.json` | `HUMAN_STATS_PATH` | JSON | Unbounded human game history (optional `time_s`/`pps`/`finesse_faults` fields on new records) |
| `ai_model.pt` | `MODEL_PATH` | PyTorch | DQN weights + optimizer + epsilon |
| `ai_training_log.json` | `LOG_PATH` | JSON | Per-episode training metrics (35 fields: 9 original + 26 observability) |
| `ai_step_log.jsonl` | `STEP_LOG_PATH` | JSONL | Per-`learn()`-call metrics (loss, TD error, grad norm, LR, buffer fill); rotates at 100K lines |
| `ai_behavior_log.jsonl` | `BEHAVIOR_LOG_PATH` | JSONL | Per-episode behavioral analytics (column/rotation histograms, placement success rate) |
| `ai_playing_log.json` | `PLAYING_LOG_PATH` | JSON | Per-episode playing-mode metrics (separate from training log; mode implicit by filename) |
| `ai_playing_behavior_log.jsonl` | `PLAYING_BEHAVIOR_LOG_PATH` | JSONL | Per-episode playing-mode behavioral analytics (separate from training behavior log) |
| `runs/` | `TB_LOG_DIR` | TensorBoard | TensorBoard event files for live dashboards (`tensorboard --logdir data/runs`) |
| `tournament/tournament_report.json` | — | JSON | Tournament generations report (best/mean scores) |
| `tournament/tournament_best.pt` | — | PyTorch | Best tournament weights per run |
| `tournament/playing_log.json` | — | JSON | Tournament-redirected playing log (never the real one) |
| `ai_model.pre_tournament.pt` | `PRE_TOURNAMENT_PATH` | PyTorch | Pre-tournament checkpoint of `ai_model.pt` (overwritten each run; restore via Tournament menu) |
| `tournament/loops.json` | `TOURNAMENT_LOOPS_PATH` | JSON | Per-loop tournament results (loop, seed, best, mean, elapsed_s, timestamp) |

| File | Path constant | Format | Purpose |
|---|---|---|---|
| `media/korobeiniki.mid` | `MUSIC_SONG_PATHS["korobeiniki"]` | MIDI | Korobeiniki music (melody + bass) |
| `media/kalinka.mid` | `MUSIC_SONG_PATHS["kalinka"]` | MIDI | Kalinka music (melody + bass) |

**`settings.json` schema**: `player` ("Humain"/"IA"/"Bot"/"MCP"), `mode` ("Normal"/"Replay"/"Sprint"/"Blitz"), `handicap` (0-5), `sound` (int 0-3), `music` (int 0-3), `song` ("korobeiniki"/"kalinka"), `debug` (bool), `ghost_piece` (bool), `preview_count` (int 0/1/3), `piece_generator` ("random"/"7bag"/"35bag"/"weighted"), `speed_mode` ("none"/"easy"/"normal"/"medium"/"hard"/"crazy"/"insane"), `are` (bool), `ai_speed` ("normal"/"fast"), `ai_epsilon_decay` (float), `ai_epsilon_end` (float), `ai_lr` (float), `ai_gamma` (float), `ai_batch_size` (int), `ai_buffer_size` (int), `ai_mode` ("learning"/"playing"), `ai_curriculum` (bool), `ai_curriculum_freq` (int), `ai_curriculum_epsilon` (str), `ai_warm_start` (bool), `ai_learn_per_action` (int), `ai_lookahead` (bool), `ai_lookahead_depth` (int 1-3), `ai_dueling` (bool), `ai_imitation` (bool), `ai_mcts` (bool), `ai_mcts_iterations` (int 20-2000), `mcp_port` (int), `bot_lookahead` ("none"/"preview"), `tournament_loops` (int 1-20), `tournament_generations` (int 1-20), `tournament_episodes` (int 1-5), `tournament_population` (int 2-12), `tournament_sigma` (float 0.005-0.10), `tournament_seed` (int), `seed` (int|null), `keybinds` (dict: action→pygame keycode, includes `mute` and `hold`)

## DQN AI Specifics

- **Network**: `DQNetwork` — Input(17, normalized) → Dense(256, ReLU) → Dense(128, ReLU) → Output(1, Linear). V-function evaluates board quality per candidate placement. Optional dueling head (`ai_dueling`, default OFF): output splits into value + advantage streams, summed as `V(s) + A(s)` with no batch-mean centering (single-sample candidate evaluation must stay batch-independent). Checkpoints store a `dueling` flag; mismatched load raises `ValueError("checkpoint architecture mismatch")`. Non-dueling layout keeps the original `net.0/2/4` state-dict keys, so legacy checkpoints load unchanged.
- **State vector** (`extract_features`, 17-dim DT-20, normalized via `(x - mean) / std`): `[lines_cleared, holes, aggregate_height, bumpiness, max_height, row_transitions, column_transitions, wells, hole_depth, rows_with_holes, *next_piece_one_hot(7)]`.
- **Candidate generation**: soft-drop BFS (`soft_drop_placements` in `tetris/ai/candidates.py`) with SRS wall kicks (`SRS_KICKS_JLSTZ`, `SRS_KICKS_I`) — enumerates all reachable placements including overhangs. Placements are `Placement` NamedTuples `(piece_type, rot, px, py, hold, moves)` — `shape` is derived from `get_shape_rot(piece_type, rot)` (see `tetris/game/shapes.py`); `moves` is the full path of atomic actions (`["left", "rot_cw", "soft_drop", ...]`) from BFS. Hold candidates: when `_can_hold` is True, the AI also enumerates placements for the held piece (or next piece if hold is empty), doubling the candidate space. Look-ahead depth configurable (`ai_lookahead_depth` 1–3): simulates best next-piece placement (El-Tetris-optimal) for N upcoming pieces. Look-ahead uses hard-drop (`best_next_placement`), independent of the main soft-drop BFS path.
- **Move execution**: `_execute_move_sequence` replays `p.moves` atomic actions using `Board.is_valid_move`/`try_rotate`, eliminating execution mismatch for overhang placements.
- **Target network sync**: Hard sync every 500 learn steps (`target_sync_freq=500`), replacing Polyak averaging.
- **LR scheduling**: `ReduceLROnPlateau(optimizer, mode="min", factor=0.5, patience=50, min_lr=1e-6)` — `learn()` calls `scheduler.step(last_loss)` after each gradient step.
- **PER beta annealing**: `beta` anneals from 0.4 → 1.0 over 10,000 learn steps (fixed, not buffer-size-based).
- **Curriculum**: Curriculum state (`curriculum_level`, `curriculum_episode_count`) lives in `DQNAgent`, persisted in checkpoint. `advance_curriculum(max_level, freq)` advances level every `freq` episodes. `_reset_episode` re-applies `set_allowed_types` on the new `PieceProvider`.
- **Seed reproducibility**: `_reset_episode` derives `_episode_seed = seed + episode` and re-seeds `random`, `np.random`, `torch.manual_seed`, and `PieceProvider` for reproducible training.
- **Modes**: `ai_mode="learning"` (epsilon-greedy + training updates + logging, fast-forwards lock delay) vs `"playing"` (greedy, epsilon=0, no learning, full lock delay). Set in `AIState.__init__` after `agent.load(MODEL_PATH)`. Training uses `lookahead_depth=1` + `preview_count=1` in `verify_training.py` for speed (6.9× faster); playing uses `lookahead_depth=3` + `preview_count=3` for best move quality. `online_net.eval()` during `select_action`, `online_net.train()` during `learn` (future-proofs for dropout/BN). **Playing-mode logging**: playing mode writes to `PLAYING_LOG_PATH` / `PLAYING_BEHAVIOR_LOG_PATH` (separate files, mode implicit by filename — no `mode` field in entries). Training files (`ai_training_log.json`, `ai_behavior_log.jsonl`, `ai_model.pt`, `ai_step_log.jsonl`, `runs/`) are never written by playing mode. `_on_exit()` saves model + flushes TB only in learning mode; playing mode flushes playing log only. `AIStatsState` reads from `LOG_PATH` (training) only; playing stats shown in-game HUD only. `_log_playing()` records episode metrics to the playing log via `_on_episode_end()`.
- **Observability** (5 tiers): Tier 1 enriches per-episode JSON log with 26 new fields (LR, TD errors, grad norm, buffer fill, target syncs, PER beta, V-value spread/margin, candidate count, random/greedy ratio, hold rate, move-sequence length, avg reward, curriculum level, 9 reward components). Tier 2 writes per-`learn()`-call JSONL to `STEP_LOG_PATH` (rotates at 100K lines). Tier 3 writes per-episode behavioral JSONL to `BEHAVIOR_LOG_PATH` (column histogram 10 bins, rotation histogram 4 bins, placement success rate). Tier 4 decomposes reward via `compute_reward_components()` in `rewards.py` (9 components: lines, holes_delta, overhangs, height, bumpiness, wells, survival, pbrs, game_over — sum equals `compute_reward()`). Tier 5 writes TensorBoard scalars via `SummaryWriter` in `DQNAgent.learn()` to `TB_LOG_DIR` (runtime-guarded by `ImportError`). `DQNAgent.training_metrics()` snapshots dynamics; `flush_logs()` flushes TB writer; `AIState._write_behavior_log()` writes behavioral JSONL. `last_action_was_random` flag tracks actual exploration rate. `target_syncs` persisted in checkpoint. All logs are best-effort (I/O errors never crash training). Playing mode disables step log and TB writer.
- **Cooking-state indicator** (`tetris/ai/hud.py`): `_cooking_status()` uses a 4-signal health scoring system: (1) score trend (`log._trend("score")`: up=+1, down=-1), (2) TD error trend (50-ep window ratio: <0.9=+1 converging, >1.5=-1 diverging), (3) V-margin (`agent.last_v_margin > 0.01` = +1, network discriminates top-2 candidates), (4) epsilon (`< 0.2` = +1, exploration winding down). Health score range -1 to +3: <=0 "Trop cuit" (red), 1 "Pas assez cuit" (blue `(100,180,255)`), >=2 "Bien cuit" (green). `_draw_thermometer()` renders a 12x20px vertical bar with fill proportional to training progress (`max(eps_progress, ep_maturity)` clamped 0..1). Shown in `draw_ai_hud()` only in learning mode. Color + label encode cooking health; thermometer level encodes training progress.
- **MCTS look-ahead** (`ai_mcts`, default OFF): `mcts_select()` in `tetris/ai/mcts.py` runs AlphaZero-style PUCT search over placements; V-network evaluates leaves, no rollouts. Root priors = softmax over El-Tetris pick values; deeper levels use hard-drop enumeration; deeper piece types sampled from a per-episode `rng`. `ai_mcts_iterations` (20–2000, default 200) sets the budget. When ON, the greedy look-ahead chain is disabled. Tests: `tests/test_mcts.py`.
- **Self-play tournament** (`tetris/tournament.py`): evolutionary weight search from the shipped checkpoint. CLI `python -m tetris.tournament --generations N --episodes N --population N --sigma F --piece-cap N`. Fitness = playing-mode episode score to first game-over, capped at `piece_cap` pieces. Deterministic (same seed + weights → same score); path-isolated in CLI mode (logs to `data/tournament/`, never writes `ai_model.pt`). Tests: `tests/test_tournament.py`.
- **In-game tournament loop**: menu path AI → Tournament (`TournamentMenuState` → `TournamentState`, background thread). Each loop re-seeds `ai_model.pt` with the winner; the base model is checkpointed to `data/ai_model.pre_tournament.pt` before loop 0; per-loop results append to `data/tournament/loops.json`. See [docs/menus.md](docs/menus.md) (menu surface) and [docs/ai.md](docs/ai.md) (loop semantics). Tests: `tests/test_tournament_menu.py`, `tests/test_tournament_loops.py`, `tests/test_tournament_stats.py`.

## Documentation Rules

**Source of truth**: All documentation follows the rules defined in this section. The `simple-english` skill (ASD-STE100 Simplified Technical English) MUST be used for all documentation writing and rewriting.

### Language
- **English only** in `docs/`, `README.md`, and code comments.
- **English default** for UI labels (in code); French, Spanish, Slovenian via i18n catalogs (`tetris/i18n.py`). `README-fr.md` is French translation of README.
- No mixing languages within a single file.

### Structure: One Domain = One File
Each domain has exactly one file in `docs/`:

| Domain | File |
|--------|------|
| Architecture | `architecture.md` |
| AI (DQN) | `ai.md` |
| Bot (El-Tetris) | `bot.md` |
| Game Rules (Guideline) | `game_rules.md` |
| Menus & Settings | `menus.md` |
| Human Gameplay | `human.md` |
| Audio & Music | `music_and_sound.md` |
| MCP Integration | `mcp.md` |
| Performance | `performance.md` |
| Development Guide | `development.md` |
| Roadmap | `roadmap.md` |

**No duplicate content** across files. Cross-reference with links instead of copying.

### `docs/studies/` — Analysis Only
- Contains **only** non-implemented features, rejected proposals, or exploratory analysis.
- **Implemented studies MUST be moved out** (to `docs/studies/archived/` or integrated into domain files).
- Current non-adopted studies kept: `python_statemachine_study.md`, `states_split_study.md`, `pygame_menu_study.md`, `AI_REQUIREMENTS.md` (requirements spec).

### Diagrams
- **All schematics MUST use Mermaid.js** (` ```mermaid ` blocks).
- Diagram types: `flowchart`, `graph`, `stateDiagram-v2`, `classDiagram`, `sequenceDiagram`, `erDiagram`, `gantt`, `timeline`, `pie`, `quadrantChart`, `requirementDiagram`, `gitgraph`, `mindmap`, `sankey`, `block`, `packet`, `journey`.
- **Verify with `mmdc`** before commit: `mmdc -i <file>.md -o /dev/null` (checks syntax only).
- No ASCII art diagrams in documentation.

### Code in Documentation
- **No executed or evaluated code** in documentation.
- Code snippets are illustrative only — show API shape, not runnable scripts.
- Runnable examples go in `scripts/` or tests, referenced from docs.

### Cleanup
- **Remove unused/outdated information** when consolidating.
- **Archive, don't delete** — move superseded content to `docs/studies/archived/` with a note.
- **No stale status markers** (e.g., "TODO", "WIP", "deprecated") in domain files.

### README Files
- `README.md` — English, primary entry point.
- `README-fr.md` — French translation, kept in sync.
- Both link to `docs/` for technical detail.

### Verification (Pre-Commit)
Run both checks before committing documentation changes:

```bash
# 1. Mermaid syntax validation (all .md files with mermaid blocks)
for f in docs/*.md README.md README-fr.md; do
  if grep -q '^```mermaid' "$f"; then
    mmdc -i "$f" -o /dev/null || exit 1
  fi
done

# 2. Documentation duplication < 1% (excludes class_diagram.md per .jscpd.json)
npx jscpd docs/ README.md README-fr.md
# Or via jscpd MCP: get_statistics with path "docs"
```

Target: **<1% duplication rate** across documentation files.
