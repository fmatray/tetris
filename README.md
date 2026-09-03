# Tetris Python

A complete Tetris game built in Python with Pygame, featuring an embedded Deep Q-Network (DQN) AI agent, an El-Tetris heuristic bot, and Model Context Protocol (MCP) integration for external agents.

## Features

### Gameplay
- ✅ **Tetris Guideline compliant** — 22-row board (20 visible + 2 hidden), SRS wall kicks, hold piece, lock delay with reset limit, T-Spin detection (3-corner rule), Back-to-Back chaining, combo scoring
- ✅ **Four player types** — Human, DQN AI, El-Tetris bot, MCP external agent
- ✅ **Multiple piece generators** — Random, 7-bag, 35-bag, weighted, replay
- ✅ **Configurable rules** — Ghost piece, preview count (0/1/3), handicap (0–5), speed modes (none/insane)
- ✅ **Reproducible seeds** — Numeric seed entry for deterministic piece sequences
- ✅ **ARE entry delay** — 100ms appearance delay with IRS/IHS input buffering (configurable)

### AI Player (DQN)
- ✅ **V-network DQN** — 17→256→128→1 MLP evaluating board quality per candidate placement
- ✅ **DT-20 features** — 17-dimensional normalized state vector (holes, height, bumpiness, wells, transitions, next piece one-hot)
- ✅ **PBRS reward shaping** — Potential-based reward shaping preserves optimal policy
- ✅ **Prioritized Experience Replay** — Beta annealing 0.4→1.0 over 10K learn steps
- ✅ **N-step returns** — Configurable n-step TD targets
- ✅ **Soft-drop BFS** — Full SRS wall-kick enumeration for all reachable placements including overhangs
- ✅ **Look-ahead** — Simulates best next-piece placement (depth 1–3, El-Tetris-optimal)
- ✅ **Hold candidates** — AI can hold once per lock, same rules as human
- ✅ **Curriculum learning** — Progressive piece-set restriction with epsilon reset
- ✅ **Two modes** — Learning (epsilon-greedy, training updates, fast-forward lock) vs Playing (greedy, full lock delay)
- ✅ **5-tier observability** — Per-episode JSON, per-step JSONL, behavioral JSONL, reward decomposition, TensorBoard

### El-Tetris Bot
- ✅ **El-Tetris evaluation** — 6 heuristics (landing height, eroded cells, row transitions, column transitions, holes, well sums) with weighted sum
- ✅ **Soft-drop BFS** — Same candidate enumeration as AI, exact path replay via BFS move sequences
- ✅ **Look-ahead** — Configurable depth (none / preview)
- ✅ **Shared bot library** — `BotMovesMixin` reused by AI and bot states

### MCP Integration
- ✅ **FastMCP HTTP server** — Streamable-http transport, daemon thread
- ✅ **Tools** — `play(moves)`, `start_game(config)`
- ✅ **Resources** — `board://state` (live board snapshot), `tetris://rules` (rule reference)
- ✅ **Queue architecture** — Thread-safe communication between MCP server and `MCPState`

### Audio
- ✅ **Procedural SFX** — NumPy-synthesized sine waves with envelopes (move, rotate, lock, line clear, level up, game over)
- ✅ **Polyphonic MIDI music** — Korobeiniki and Kalinka parsed from `.mid` files, synthesized via NumPy
- ✅ **Music speed adaptation** — Tempo scaling regenerates audio buffer at `1/speed` duration
- ✅ **Crossfade** — Smooth transitions between tracks
- ✅ **Volume controls** — Independent sound/music volumes (0–3)

### Visuals
- ✅ **Renderer** — Pure presentation layer (board, preview, hold, ghost, stats, leaderboard)
- ✅ **Particle system** — Physics-based effects (gravity, friction) on line clears (80 particles/line)
- ✅ **Debug overlay** — 7-bag visualization, speed info, hole/overhang debug (toggle with `d` key)

### Persistence & Logging
- ✅ **Settings** — `data/settings.json` (all menu prefs, keybinds, AI hyperparams)
- ✅ **Leaderboard** — Top 10 scores (`data/leaderboard.json`)
- ✅ **Human stats** — Unbounded game history (`data/human_stats.json`)
- ✅ **AI model** — PyTorch checkpoint (`data/ai_model.pt`: weights, optimizer, epsilon, curriculum state)
- ✅ **Training logs** — 5-tier observability (see AI Player section)
- ✅ **Centralized logging** — `tetris.logger` module, debug mode writes to `data/debug.log`

## Installation

### Prerequisites
- Python 3.9+
- pygame-ce 2.5.x (not stock pygame)
- PyTorch 2.0+
- NumPy 1.24+
- matplotlib 3.7+
- mido 1.3+

### Install
```bash
pip install -r requirements.txt
```

### Run
```bash
python main.py
```

### Headless / Smoke Test (No Display)
```bash
SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy python3 -c "
import pygame
from tetris.states.menu import MenuState
pygame.init()
screen = pygame.Surface((1500, 800))
font = pygame.font.Font(None, 20)
from tetris.audio import AudioManager
audio = AudioManager(sound_volume=0, music_volume=0)
state = MenuState(screen, font, audio)
# Drive states with synthetic events...
"
```

### AI Training Validation (Headless)
```bash
python -m tetris.verify_training
```
Success criteria: best_score > 10000, avg_score > 1000. Duration and loss are reported as information.

## Controls

Keys are configurable via the menu (**Human > Keys**). Default bindings:

| Key | Game | Menu |
|-----|------|------|
| `←` / `→` | Move left/right | Navigate |
| `↑` | Rotate CW | Navigate / Change value |
| `↓` | Soft drop | Navigate / Change value |
| `Space` | Hard drop | Select |
| `C` / `Shift` | Hold piece | — |
| `P` / `Escape` | Pause | Back |
| `M` | Mute audio | — |
| `D` | Toggle debug overlay | — |
| `Return` | — | Select |
| `Backspace` | — | Back |

## Documentation

Technical documentation is in the `docs/` directory:

| Document | Description |
|----------|-------------|
| `architecture.md` | System architecture, FSM state diagram, class diagram |
| `ai.md` | DQN AI design, V-network, DT-20 features, PBRS, training pipeline |
| `bot.md` | El-Tetris bot, El-Tetris evaluation, shared bot library |
| `game_rules.md` | Tetris Guideline compliance, rule engine, human/AI alignment |
| `menus.md` | Menu hierarchy, keybinds, settings persistence |
| `human.md` | Human gameplay, DAS, keybind customization, seed/replay |
| `music_and_sound.md` | SFX synthesis, MIDI parsing, music speed adaptation |
| `mcp.md` | MCP server, tools, resources, simulation |
| `performance.md` | Profiling methodology, optimizations, benchmarks |
| `development.md` | Commands, conventions, testing, data files, DQN summary |
| `roadmap.md` | Milestones, priorities, enhancements, technical debt |

## Project Structure

```
tetris/
├── ai/              # DQN agent, network, rewards, candidates, HUD
├── audio/           # AudioManager, SFX synthesis, MIDI parsing
├── bots/            # Shared bot library (BotMovesMixin)
├── game/            # Pure domain: Board, Tetromino, shapes, scoring, stats, piece providers, rules
├── logger.py        # Central logging
├── mcp_server.py    # FastMCP HTTP server
├── settings.py      # All constants, path constants
├── states/          # FSM states (16 classes)
├── storage/         # JSON persistence
└── visuals/         # Renderer, ParticleSystem
```

## Development

```bash
# Lint
ruff check .

# Type check
zuban check .

# Tests (headless)
SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy python -m pytest tests/ -q

# Coverage
SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy python -m pytest tests/ --cov=tetris --cov-report=term-missing -q
```

## Credits

Developed by Frédéric Matray.
Music and sound effects generated procedurally with NumPy.
Tetris® is a trademark of The Tetris Company.

## License

MIT License — Free to use and modify.

## References

- [Tetris Wiki](https://tetris.wiki) — Comprehensive guide to mechanics, SRS, and game history.
- [Tetris Guideline](https://tetris.wiki/Tetris_Guideline) — Official specification for Tetris implementations.