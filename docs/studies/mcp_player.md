# MCP Player — Implementation Study

> Status: **study only**. No implementation, no code change. This document
> captures the design decisions reached through investigation for a future
> implementation pass.

## Goal

Add a third player type — **"MCP"** — alongside Humain and IA. An LLM connected
via an MCP server plays Tetris at the **human input level**: it sees the board
and issues primitive movements (left, right, rotate, drop, hold), exactly like
a human pressing keys. No candidate enumeration, no DQN, no macro-actions.

## Architecture

```
TetrisApp (main loop, 60 FPS, single thread)
  └─ FSM
       └─ MCPState(GameState)           ← inherits GameState, NOT AIState
            ├─ _action_queue: queue.Queue[str]
            ├─ update(): drain queue → execute actions on main thread
            ├─ MCP server (side thread)
            │    ├─ @tool play(actions, frames)  → enqueue + advance
            │    ├─ @resource board://state      → JSON snapshot
            │    └─ @resource tetris://rules     → mechanics + coordinate system
            └─ _on_episode_end() → GameOverState (human flow, not AI auto-restart)
```

`MCPState` inherits `GameState` directly — not `AIState`. It overrides only:
- `update()` — paces the game based on queued LLM actions
- `handle_event()` — ignore keyboard (or allow ESC to quit)
- `_do_game_over()` — human game-over flow (GameOverState), not AI auto-restart

No candidate generation. No DQN. No reward shaping. No feature vectors.

## The primitive action surface

`GameState` already exposes 7 movement handlers via `input_map`:

| Action key      | Handler             | Effect                                          |
|-----------------|---------------------|-------------------------------------------------|
| `move_left`     | `_move_left()`      | `piece.move(-1, 0)` if valid                    |
| `move_right`    | `_move_right()`     | `piece.move(1, 0)` if valid                     |
| `rotate_cw`     | `_rotate_cw()`      | SRS rotation + wall kicks via `try_rotate(+1)`  |
| `rotate_ccw`    | `_rotate_ccw()`     | SRS rotation + wall kicks via `try_rotate(-1)`  |
| `soft_drop`     | `_toggle_down_true()`| Sets `down_pressed = True` — gravity accelerates|
| `hard_drop`     | `_hard_drop()`      | Instant drop + lock + spawn next piece           |
| `hold`          | `_hold()`           | Swap current with held (once per lock)           |

Plus `pause` (toggles `self.paused`). These are the exact primitives the MCP
server exposes — the same surface a human player has.

## Tool design: single batch tool

One tool, not seven:

```python
@mcp.tool()
def play(actions: list[str], frames: int = 0) -> dict:
    """Execute a sequence of actions, then advance the simulation.

    Actions execute in order, instantaneously (no time passes during
    movement/rotation). Invalid actions (e.g., move into a wall) are
    silently skipped — exactly like the game ignores a key press that
    can't move the piece.

    After all actions execute, the simulation advances by `frames` ticks
    (each tick = 16ms = 1/60s). Advancing applies gravity, soft drop,
    and lock delay.

    "hard_drop" locks the piece immediately (calls _lock_and_spawn
    directly), regardless of `frames`. All other actions just
    move/rotate the active piece.

    Actions:
        "move_left", "move_right", "rotate_cw", "rotate_ccw",
        "soft_drop", "hard_drop", "hold", "pause"

    Returns:
        Board state snapshot + which actions executed + whether a
        piece locked during this call.
    """
```

### Why a batch tool, not one tool per move

| Per-move tools                | Batch tool                     |
|-------------------------------|--------------------------------|
| 3–5 API calls per piece       | 1 API call per piece           |
| 6–10s per piece (at 2s/call)  | ~2s per piece                   |
| LLM reacts step-by-step       | LLM plans full trajectory       |
| 7 tools in the schema         | 1 tool in the schema            |

The batch forces the LLM to plan: "T-piece, rotate_cw, move_right ×3,
hard_drop." Higher reasoning load, better experiment, 3–5× faster gameplay.

### The `frames` parameter

Movement handlers are **instantaneous** — they mutate piece position/rotation
but don't advance gravity, lock delay, or line clears. Those only advance inside
`GameState.update(dt, particles)`:

| What               | Advanced by            | Without `frames`           |
|--------------------|------------------------|----------------------------|
| Gravity            | `update()` ticking `drop_time` | Piece floats at spawn forever |
| Soft drop          | `update()` reads `down_pressed` | `soft_drop` flag never read   |
| Lock delay (500ms) | `update()` ticks `_lock_timer`   | Piece rests but never locks   |
| Line clears        | `update()` → `_lock_and_spawn`   | Lines fill but never clear    |

Execution order:
1. Execute all `actions` (instantaneous, no time passes)
2. Advance `frames` ticks of `update(dt=16ms, particles)`

`hard_drop` is the exception — it calls `_lock_and_spawn()` directly, so
`play(["hard_drop"])` works with `frames=0`. This is the fast path; the LLM
can play a full game with only `hard_drop`. The `frames` parameter is the
upgrade path for finer control:

| Scenario                     | Call                                              |
|------------------------------|---------------------------------------------------|
| Position then hard-drop      | `play(["rotate_cw", "move_right", "hard_drop"])`  |
| Position then let gravity settle | `play(["move_right"], frames=120)`            |
| Soft drop into a gap         | `play(["soft_drop"], frames=30)`                  |
| Just read the board          | `play([], frames=0)`                             |

### SRS wall-kick caveat

With a batch, the LLM commits blind. If a wall kick shifts the piece left
during rotation, the subsequent `move_right ×3` overshoots. The LLM can do
two-phase: `play(["rotate_cw", "move_right"])` → see state → `play(["move_right",
"hard_drop"])`. Batch when confident, two-step when cautious.

## Board representation

### `board://state` resource

The full piece pipeline the LLM sees — same information a human player has
on screen:

```json
{
  "grid": [[0,0,0,...], ...],
  "piece_queue": {
    "current": {"type": "T", "rotation": 0, "x": 3, "y": 0, "shape": [[1,0],[1,1],[1,2]]},
    "next":    {"type": "I"},
    "preview": [{"type": "S"}, {"type": "Z"}],
    "hold":    {"type": "O"},
    "can_hold": true
  },
  "stats": {"score": 1200, "lines": 15, "level": 2},
  "game_over": false,
  "paused": false
}
```

| Field            | Source in `GameState`                  | Notes                              |
|------------------|----------------------------------------|------------------------------------|
| `grid`           | `board_to_grid(self.board)` → 22×10   | 0 = empty, 1 = filled              |
| `current`        | `self.current_piece`                   | Active piece on the board          |
| `next`           | `self.next_piece`                      | Immediate next piece               |
| `preview`        | `self.preview_pieces`                  | Upcoming pieces (`preview_count-1`)|
| `hold`           | `self.hold_piece`                      | Held piece or `null`               |
| `can_hold`       | `self._can_hold`                        | `false` after hold, reset on lock  |
| `stats`          | `self.stats` (score, lines, level)     | From `GameStats`                   |
| `game_over`      | `self.game_over`                        |                                    |
| `paused`         | `self.paused`                           |                                    |

`preview_count` (0, 1, or 3 in `settings.json`) controls how many pieces are
visible — the resource reflects whatever the player configured.

`board_to_grid()` already exists in `tetris/ai/rewards.py` — converts
`Board.grid` (list of `(r,g,b)|None`) to a 0/1 numpy array. Reusable as-is.

### `tetris://rules` resource

Mechanics the LLM must know to play legally. Read once at session start:

- **Coordinate system**: row 0 = top, column 0 = left. `shape` cells are
  `(dx, dy)` offsets from the piece's `(x, y)` position.
- **Hidden rows**: rows 0–1 are a buffer zone. Pieces spawn there. Locking
  entirely above row 2 = game over (top-out).
- **Tool semantics**:
  - `soft_drop` sets a gravity flag — needs `frames > 0` to take effect.
  - `hard_drop` instantly drops to bottom, locks, spawns next piece.
  - `hold` is once per lock — `can_hold` must be `true`.
- **Line clears**: a complete row disappears, everything above shifts down.
- **Scoring**: more lines at once = more points (single < double < triple < Tetris).
- **Levels**: speed increases with level, level rises every 10 lines.
- **SRS**: rotation auto-kicks off walls — `rotate_cw` may shift position.
- **Lock delay**: 500ms when grounded, reset on move/rotate (max 15 resets).

### Strategy prompt (optional)

An `@mcp.prompt("play_tetris")` carrying strategy guidance (minimize holes,
keep stack flat, save I-piece for Tetris, avoid wells). Injected by the host
as system prompt when the LLM starts a session. Not required for legal play.

## Concurrency model

### Problem

The pygame main loop is single-threaded, 60 FPS, CPU-bound, GIL-bound (confirmed
by `docs/threading_study.md`). pygame is not thread-safe — all Surface/event/draw
calls must be on the main thread. The MCP server runs on a side thread (asyncio
for HTTP transport). Tools must never touch pygame state directly.

### Solution: in-process queue

```
MCP server thread                 Main thread (pygame loop)
─────────────────                 ─────────────────────────
play(actions, frames)              MCPState.update(dt, particles):
  → push actions to queue            while queue not empty:
  → push frames to queue                action = queue.get()
  → block until result ready            self.input_map[action]()  # safe, main thread
                                     for _ in range(frames):
                                        super().update(16ms, particles)
                                     → return board snapshot via result queue
```

- Tools enqueue actions + frame counts.
- `update()` dequeues and executes on the main thread — pygame calls stay safe.
- The `play()` tool blocks until the main thread processes the batch and returns
  the resulting board state via a response queue.

### Transport

| Transport          | How                          | Verdict                          |
|--------------------|------------------------------|----------------------------------|
| `streamable-http`  | Game starts MCP server on side thread, LLM host connects to `http://localhost:PORT/mcp` | **Recommended.** Game owns the process, server is a side thread. |
| `stdio`            | MCP host launches game as subprocess, speaks over stdin/stdout | `mcp.run()` blocks on stdin — pygame loop must move to a side thread. More complex. |

## Integration points

### `tetris/settings.py`

No new constants needed for the core design. If using HTTP transport, an
`MCP_SERVER_PORT` constant (e.g. 8765) would live here.

### `tetris/states/menu.py`

| Change | Detail |
|--------|--------|
| `_toggle` case 1 | Cycle `Humain → IA → MCP → Humain` |
| `_on_select` case 0 | `if self.player == "MCP": return self._build_mcp_state()` |
| `_build_mcp_state()` | New method, mirrors `_build_ai_state()` but constructs `MCPState` with `GameState`-level params |

### `tetris/states/mcp.py` (new file, ~100 lines)

```python
class MCPState(GameState):
    """LLM-controlled player via MCP server.
    
    Inherits all game mechanics from GameState. Overrides update()
    to drain an action queue filled by MCP tool calls. The MCP server
    runs on a side thread; tools push to the queue, update() executes
    on the main thread.
    """
    _action_queue: queue.Queue
    _result_queue: queue.Queue
    _mcp_server: MCPServer  # side thread
    
    def update(self, dt, particles) -> State | None:
        # Drain queue, execute actions, advance frames
        ...
    
    def _on_episode_end(self) -> State | None:
        # Human flow: GameOverState, not AI auto-restart
        ...
```

### `tetris/mcp_server.py` (new file, ~150 lines)

```python
mcp = MCPServer("Tetris")

@mcp.tool()
def play(actions: list[str], frames: int = 0) -> dict:
    """..."""
    # Push to queue, block on result
    
@mcp.resource("board://state")
def board_state() -> str:
    """Current board + piece queue snapshot as JSON."""
    
@mcp.resource("tetris://rules")
def rules() -> str:
    """Coordinate system, piece shapes, mechanics, scoring."""
```

### `requirements.txt`

Add `mcp[cli]>=1.28,<2`. Adds `anyio`, `pydantic`, `starlette`, `uvicorn`
(for HTTP transport). Python 3.10+ required — project is 3.14, so compatible.

## What gets reused (no duplication)

| Component                     | Source                              | Reused by MCP player |
|-------------------------------|-------------------------------------|----------------------|
| All 7 movement handlers       | `GameState._move_left` etc.        | ✅ inherited          |
| Board + collision + SRS       | `tetris/game/board.py`             | ✅ inherited          |
| Board→grid conversion         | `board_to_grid()` in `rewards.py`  | ✅ importable         |
| Piece provider + generation   | `PieceProvider`                    | ✅ same as human      |
| Rendering                     | `GameState.draw` → `Renderer`      | ✅ inherited          |
| Lock delay, gravity, DAS      | `GameState.update`                 | ✅ inherited          |
| Stats + scoring               | `GameStats`, `ScoreEngine`         | ✅ inherited          |
| Game-over flow                | `GameState._do_game_over`          | ✅ human flow         |
| Piece queue (current/next/preview/hold) | `GameState` fields        | ✅ inherited          |

## What changes behaviorally

| Aspect              | Human              | AI                       | MCP                     |
|---------------------|--------------------|--------------------------|-------------------------|
| Decision source     | Keyboard events    | DQNAgent.select_action    | LLM via MCP tool call   |
| Action granularity  | Per key press      | Macro-action (place)     | Batch of primitives     |
| Episode end         | GameOverState      | Auto-restart (training)  | GameOverState (human)   |
| Stats persistence    | save_human_game()  | TrainingLog only          | save_human_game()? (TBD)|
| Speed               | Real-time (60 FPS) | Fast (learning) / normal  | Frozen between calls    |

### Stats question (open)

`MCPState` inherits from `GameState`, so `GameOverState` would call
`save_human_game()` — polluting human stats with LLM games. Two options:
1. Override `_do_game_over()` to skip `save_human_game()` (like AI does by
   never creating `GameOverState`).
2. Let it save — treat MCP games as human games (simplest, but misleading).

Decision deferred to implementation.

## Risks

| Risk                          | Impact | Mitigation |
|-------------------------------|--------|------------|
| LLM can't reason about 22×10 grid | Poor play, but legal | Strategy prompt resource; this is the experiment's point |
| Latency: 2s per `play()` call | Slow gameplay (30 pieces/min) | Acceptable for a demo; not real-time |
| SRS wall-kick overshoot in batches | Misplaced pieces | Two-phase play (batch without hard_drop, check, batch again) |
| `soft_drop` + `frames` ambiguity | LLM confused | Rich docstring; `tetris://rules` resource explains the flag model |
| Cost: ~150 API calls per 5-min game | $1–3/game (Sonnet), $0.10 (mini) | Use cheaper model for experimentation |
| pygame thread safety | Crash if tools touch pygame directly | Queue pattern — tools never touch pygame, only enqueue |
| GIL contention | Server thread starved by main loop | MCP server is I/O-bound (waiting on queue), not CPU-bound — no contention |

## File inventory (for implementation)

| File                          | Action  | Est. lines |
|-------------------------------|---------|------------|
| `tetris/states/mcp.py`        | New     | ~100       |
| `tetris/mcp_server.py`        | New     | ~150       |
| `tetris/states/menu.py`       | Modify  | ~15        |
| `tetris/settings.py`          | Modify  | ~3         |
| `requirements.txt`            | Modify  | ~1         |
| **Total new code**            |         | ~250       |

## Verdict

Green light. The MCP player is a thin adapter over `GameState`'s existing
input handlers + a board snapshot serializer. No AI code involved. Fully
additive — behind a new `player == "MCP"` branch. Existing human and AI
players untouched. The single batch `play(actions, frames)` tool is the
entire LLM interface; everything else is resources (board state, rules).