# MCP Integration

## Overview

The MCP (Model Context Protocol) integration allows external AI agents to play Tetris via HTTP tool calls. The server exposes gameplay actions, board snapshots, and game rules as MCP tools and resources.

**Key Features:**
- **FastMCP** server on a daemon thread (streamable-http transport)
- **Process-wide singleton** — created once, stays bound for process lifetime
- **Queue-based communication** — tools enqueue requests; main thread processes in `MCPState.update()`
- **Game frozen between calls** — gravity only advances when `frames > 0` in a request
- **Simulation mode** — preview moves without mutating game state
- **Look-ahead enumeration** — `enumerate_drops` tool for planning

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    External AI Agent                          │
│  (any MCP client: Claude, custom script, etc.)               │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  HTTP (streamable-http)                                     │
│  127.0.0.1:PORT  (default from settings.MCP_SERVER_PORT)    │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  TetrisMCPServer (daemon thread, FastMCP)                   │
│  ┌─────────────┐  ┌──────────────┐  ┌────────────────────┐  │
│  │ play tool   │  │ start_game   │  │ board://state      │  │
│  │ simulate    │  │ quit         │  │ tetris://rules     │  │
│  │ enumerate_  │  └──────────────┘  │ tetris://shapes    │  │
│  │ drops       │                    └────────────────────┘  │
│  └─────────────┘                            ▲                │
└─────────────────────────────────────────────│────────────────┘
                              │               │
                              ▼               │
┌─────────────────────────────────────────────┘
│  queue.Queue[MCPRequest] (shared)           │
└─────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  MCPState.update() — Main thread (60 FPS loop)             │
│  - Polls queue for pending requests                         │
│  - Executes actions on real board (play) or copy (simulate)│
│  - Advances gravity for requested frames                    │
│  - Returns board snapshot via result_queue                  │
└─────────────────────────────────────────────────────────────┘
```

---

## Server Lifecycle

### Singleton Pattern

```python
from tetris.mcp_server import get_server

server = get_server(port=8765)  # Creates on first call, returns same instance
```

- Created once per process (avoids `Errno 48` "address already in use" on re-entry)
- Daemon thread started on first `attach()`
- Stays bound until process exit (no clean uvicorn shutdown for streamable-http)
- `MCPState` attaches/detaches its action queue on entry/exit

### Server Methods

| Method | Purpose |
|--------|---------|
| `attach(action_queue)` | Bind active game's queue; starts server if not running |
| `detach()` | Unbind queue (server keeps running) |
| `start()` | Launch daemon thread (idempotent) |
| `stop()` | Detach only (persistent server design) |

---

## Tools

### `play(actions: list[str], frames: int = 0) -> dict`

Execute actions on the real board, advance `frames` gravity ticks, return snapshot.

**Actions:**
| Action | Description |
|--------|-------------|
| `left` | Move piece left |
| `right` | Move piece right |
| `rotate_cw` | Rotate clockwise (SRS wall kicks) |
| `rotate_ccw` | Rotate counter-clockwise |
| `soft_drop` | Accelerated gravity for one frame |
| `hard_drop` | Instant drop to lock position |
| `hold` | Swap with hold piece (once per lock) |
| `start_game` | Reset board (also a tool below) |
| `quit` | Leave MCP mode, return to menu |

**Response Keys:**
```json
{
  "board": [["0", "1", "X", "O", ...]],  // 0=empty, 1=filled, X=hole, O=overhang
  "holes": 3,
  "overhangs": 1,
  "current_piece": "T",
  "next_piece": "I",
  "preview_pieces": ["J", "L"],
  "hold_piece": "S",
  "can_hold": true,
  "score": 12500,
  "lines": 42,
  "level": 4,
  "game_over": false,
  "aggregate_height": 145,
  "bumpiness": 12,
  "max_height": 18,
  "hole_depth": 2,
  "merit": 38500.4,
  "are_ms": 0.0,
  "action_results": ["moved", "rotated", "locked"],
  "lines_cleared": 1
```

`are_ms` — remaining entry delay in milliseconds (0.0 when no ARE is active). Actions received during ARE are buffered or gated per the rule in [game_rules.md §12](game_rules.md#12-are-appearance-delay-irs-ihs).

---

### `simulate(actions: list[str], frames: int = 0) -> dict`

Identical to `play` but runs on a **throwaway copy** of the board. Real game state unchanged.

**Constraints:**
- Bounded to known pieces (current + next + preview)
- Once known pieces exhausted, `next_piece: null`
- Requesting more drops than known → `{"error": "horizon exceeded: ..."}`
- `quit` ignored (simulation never leaves MCP)

---

### `enumerate_drops(depth: int = 1, hold: bool = true) -> dict`

Enumerate every final board from hard-dropping the current piece (and optionally hold piece).

**Parameters:**
| Param | Default | Description |
|-------|---------|-------------|
| `depth` | 1 | Look-ahead depth: 1 = current piece only, 2 = current + next, 3 = current + next + 1 preview |
| `hold` | true | If hold available, also enumerate hold-piece placements (prefixed with `["hold"]`) |

**Response:**
```json
{
  "piece_type": "T",
  "boards": [
    {
      "actions": ["rotate_cw", "right", "hard_drop"],
      "board": [...],
      "holes": 2,
      "overhangs": 0,
      "current_piece": "I",
      "next_piece": "J",
      "preview_pieces": ["L"],
      "hold_piece": "S",
      "can_hold": true,
      "score": 12500,
      "lines": 42,
      "level": 4,
      "game_over": false,
      "aggregate_height": 142,
      "bumpiness": 10,
      "max_height": 17,
      "hole_depth": 2,
      "merit": 38650.2,
      "locked_pieces": ["T"]
    }
  ]
}
```

- Boards are **de-duplicated** (identical final grids collapsed)
- Ranked by **merit** descending: `lines×1000 − holes×120 − overhangs×10 − aggregate_height×0.8 − bumpiness×1.5`
- Deeper placements evaluate best subsequent hard-drop(s); `merit` reflects look-ahead, but board shows depth-1 result
- `locked_pieces` lists piece types locked during simulation (simulate only)

---

### `start_game(seed: int | null = null) -> dict`

Reset the board and start a fresh game. Returns initial board snapshot.

**Parameters:**
- `seed`: Random seed for reproducible piece sequence. `null` = random.

---

### `quit() -> dict`

Stop the MCP session and return to the main menu.

---

## Resources

### `board://state` → Current board snapshot (0 actions, 0 frames)

Returns the same structure as `play` but without advancing the game.

### `tetris://rules` → Game rules summary

```json
{
  "actions": ["left", "right", "rotate_cw", "rotate_ccw", "soft_drop", "hard_drop", "hold", "start_game", "quit"],
  "board_size": "10x20 visible (22 with hidden buffer)",
  "pieces": ["I", "J", "L", "O", "S", "T", "Z"],
  "scoring": "standard Tetris guideline",
  "board_markers": "filled=1, empty=0, hole='X' (unreachable covered), overhang='O' (reachable covered)",
  "shapes_resource": "tetris://shapes"
}
```

### `tetris://shapes` → Full shape/kick geometry

Complete rotation data, SRS kick tables, spawn positions, board geometry.

```json
{
  "shapes": { "I": [[[...]], [[...]], [[...]], [[...]]], ... },
  "kicks": {
    "JLSTZ": { "0>>1": [[0,0], [-1,0], [-1,1], [0,-2], [-1,-2]], ... },
    "I": { "0>>1": [[0,0], [-2,0], [1,0], [-2,-1], [1,2]], ... }
  },
  "spawn": { "x": 3, "y": 0 },
  "board": { "width": 10, "height": 22, "visible_height": 20, "hidden_rows": 2 }
}
```

---

## MCPState Implementation

### Class: `MCPState` (inherits `GameState`)

Located in `tetris/states/mcp.py`.

**Key Attributes:**
- `_action_queue: queue.Queue[MCPRequest]` — inbound tool calls
- `_server: TetrisMCPServer | None` — attached server instance
- `_last_tool_call: dict | None` — for HUD display
- `_last_snapshot: dict | None` — for HUD display
- `player_type = "MCP"` — identifies player type
- `seed: int | None` — current game seed

**Key Methods:**

| Method | Purpose |
|--------|---------|
| `_start_server()` | Get singleton server, attach queue |
| `_stop_server()` | Detach queue (server persists) |
| `_reset_game(seed)` | Full game reset (called by `start_game` tool) |
| `_board_snapshot()` | Build snapshot dict for responses |
| `_execute_actions(actions)` | Apply action sequence to board |
| `update(dt, particles)` | Poll queue, process all pending requests |
| `draw(screen, particles)` | Render board + MCP HUD (if debug) |

**Update Loop:**
```python
def update(self, dt: float, particles: ParticleSystem) -> State | None:
    quit_requested = False
    while True:
        try:
            req = self._action_queue.get_nowait()
        except queue.Empty:
            break
        
        if req.simulate:
            # Run on copy, don't mutate
            snapshot = simulate_actions(...) or enumerate_drops(...)
        elif "start_game" in req.actions:
            self._reset_game(req.seed)
            snapshot = self._board_snapshot(["ok"])
        elif "quit" in req.actions:
            quit_requested = True
            snapshot = self._board_snapshot()
        else:
            # Execute on real board
            action_results = self._execute_actions(req.actions)
            for _ in range(req.frames):
                if self.game_over: break
                super().update(dt, particles)  # gravity + lock delay
            snapshot = self._board_snapshot(action_results, lines_cleared)
        
        result_queue.put(snapshot)
    
    if quit_requested:
        return self._do_game_over()  # returns MenuState
    return None
```

**Game Over Handling:**
- Top-out does **not** leave MCP — snapshot reports `game_over: true`
- Client calls `start_game` to reset
- Only explicit `quit` action returns to menu

---

## Simulator Module (`tetris/states/simulator.py`)

Pure, side-effect-free simulation logic used by `simulate` tool and `enumerate_drops`.

### Key Functions

| Function | Purpose |
|----------|---------|
| `simulate_actions(state, actions, frames, dt)` | Run actions on copy of state; return snapshot |
| `enumerate_drops(state, dt, depth, hold)` | Enumerate all hard-drop outcomes with look-ahead |
| `enumerate_hard_drop_actions(board, piece)` | All replayable action lists for hard drop |
| `build_board_repr(board)` | Convert Board → grid with hole/overhang markers |
| `_merit(lines, holes, overhangs, agg, bump)` | Weighted board quality score |
| `_lookahead_merit(grid, piece_types, depth)` | Recursive best merit after N hard drops |

### Simulation Rules

- Uses `NullAudio` (no SFX side effects)
- `_PreviewProvider` drains known pieces (current + next + preview)
- Raises `SimulationError` if action needs piece beyond known horizon
- SRS wall kicks applied via `Board.try_rotate()` / `shape_fits()`
- Lock delay respected during `frames` advancement
- Hole/overhang detection: "X" = unreachable covered empty, "O" = reachable covered empty

### Merit Formula

```
merit = lines_cleared × 1000
        − holes × 120
        − overhangs × 10
        − aggregate_height × 0.8
        − bumpiness × 1.5
```

Higher = better. Line clears dominate in normal play.

---

## Configuration

### Settings (from `tetris/settings.py`)

| Constant | Default | Description |
|----------|---------|-------------|
| `MCP_SERVER_PORT` | 8765 | Default port for MCP server |
| `MCPState.port` | from menu | Configurable via MCPMenuState |

### MCPMenuState

Located in `tetris/states/mcp_menu.py`. Allows user to:
- Set server port
- Return to main menu

Persisted in `settings.json` under `mcp_port`.

---

## Usage Examples

### Start Server from Menu
1. Navigate to **MCP** in main menu
2. Set port (default 8765)
3. Select **Retour** — server starts on daemon thread

### External Client (Python)

```python
import httpx
import json

# Base URL from server output
base = "http://127.0.0.1:8765"

# Start a new game with seed
resp = httpx.post(f"{base}/mcp/call", json={
    "method": "start_game",
    "params": {"seed": 42}
})
game = resp.json()["result"]

# Play a move sequence
resp = httpx.post(f"{base}/mcp/call", json={
    "method": "play",
    "params": {
        "actions": ["right", "rotate_cw", "hard_drop"],
        "frames": 30  # advance ~0.5s gravity
    }
})
snapshot = resp.json()["result"]

# Check board
print(f"Score: {snapshot['score']}, Lines: {snapshot['lines']}")

# Enumerate all placements for current piece
resp = httpx.post(f"{base}/mcp/call", json={
    "method": "enumerate_drops",
    "params": {"depth": 2, "hold": True}
})
placements = resp.json()["result"]["boards"]
```

### Get Board State (Resource)

```python
resp = httpx.get("http://127.0.0.1:8765/mcp/resources/read", params={
    "uri": "board://state"
})
snapshot = json.loads(resp.json()["result"])
```

---

## Debugging

### MCP HUD (Debug Mode)
When debug mode is ON (`d` key or menu), `MCPState.draw()` renders:
- Server status (Actif/Arrêté)
- Port
- Last tool call (actions, frames, results)
- Last snapshot (score, lines, level, game_over, or error)

### Logging
```python
from tetris.logger import get_logger
_logger = get_logger("mcp")
_logger.debug("MCP server attached on port %d", port)
```

### Common Issues

| Issue | Cause | Fix |
|-------|-------|-----|
| `error: no active MCP game` | Server running but no MCPState attached | Enter MCP mode from menu |
| `horizon exceeded` | Simulation needs piece beyond known | Reduce `frames` or `depth` |
| `Errno 48 address already in use` | Old design recreated server | Fixed: singleton `get_server()` |
| Tool hangs | Main thread not processing queue | Ensure game loop runs (`TetrisApp.run()`) |

---

## Design Notes

### Why Queue-Based?
- MCP tools run on server thread; game runs on main thread
- Thread-safe queue decouples HTTP request handling from game loop
- `result_queue.get()` blocks tool call until main thread processes it
- No locks needed on shared game state

### Why Persistent Server?
- Avoids bind errors when quitting/re-entering MCP mode
- Server thread + socket live for process lifetime
- Daemon thread exits cleanly on process termination

### Why Frozen Game Between Calls?
- External agents may need arbitrary think time
- Gravity only advances when client requests `frames > 0`
- Client controls game speed precisely

### Board Representation
- 22 rows (20 visible + 2 hidden buffer)
- `"X"` = hole (covered empty, unreachable from top)
- `"O"` = overhang (covered empty, reachable from side)
- `0` = empty, `1` = filled
- Exposed for external agent feature extraction

---

## Future Extensions

| Feature | Effort |
|---------|--------|
| WebSocket transport | Medium |
| Authentication/authorization | Medium |
| Multi-game sessions (named games) | High |
| Replay export via MCP | Low |
| Tournament mode (multiple agents) | High |