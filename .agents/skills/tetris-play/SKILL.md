---
name: tetris-play
description: Play the Tetris game through its MCP server using the play and start_game tools. Use when the user asks to play Tetris, drive the board via MCP, or run the MCP player.
metadata:
  origin: repo
---

# Tetris MCP Player

Play the game via the harness MCP tools `xd://mcp__tetris_start_game` and
`xd://mcp__tetris_play`. The MCP server is assumed already running and
connected (see Connection). The game is fully under your control: it
advances only when you send `play` with `frames > 0`; otherwise it stays
frozen between calls.

## Response format (harness)

The harness MCP tools (`xd://mcp__tetris_play`, `xd://mcp__tetris_start_game`)
return a wrapper, not the raw snapshot dict:

```json
{ "text": "<str>", "details": { "rawContent": [ { "type": "text", "text": "<json>" } ] } }
```

Parse `details.rawContent[0].text` as the snapshot dict. External HTTP clients
(direct FastMCP streamable-http) receive the dict directly.

## When to activate

- User asks to "play Tetris", "drive the board via MCP", "use the tetris MCP
  tools", or run the MCP player.

## Tools

### start_game

Reset the board, score/lines/level to 0, spawn fresh pieces.

- Args: `{}` (none)
- Returns: board snapshot (see below).

### play

Execute a list of actions, optionally advance `frames` (~16 ms each) of
gravity/lock delay, return a board snapshot.

- Args: `{ "actions": string[], "frames"?: int }` (frames default 0)
- Actions: `left`, `right`, `rotate_cw`, `rotate_ccw`, `soft_drop`,
      `hard_drop`, `hold`, `start_game` (reset), `quit` (leave MCP).
      `start_game`/`quit` may also be sent inside a `play` action list.
- All actions in one call run sequentially, then `frames` ticks of gravity
  happen, then the snapshot is returned. `hard_drop` drops the piece to the
  floor and locks it immediately — so `play(["hard_drop"], 0)` places the
  current piece and spawns the next one.
- Actions after `hard_drop` in the same call apply to the NEXT spawned piece
  (the current one already locked). Send one piece's moves per `play` call,
  then read the snapshot to plan the next one.
- Returns: board snapshot.

### simulate

Preview the result of a move **without** touching the real game. Same
arguments and return schema as `play`, but it runs on a throwaway copy, so the
board, score, and piece queue are unchanged — use it to test a sequence before
committing it with `play`.

- Args: `{ "actions": string[], "frames"?: int }` (frames default 0)
- Returns: same snapshot dict as `play` (board 0/1/"X"/"O", holes, overhangs,
  current_piece, next_piece, preview_pieces, hold_piece, can_hold, score, lines,
  level, game_over, action_results, lines_cleared).
- **Non-mutating**: the real board only changes on `play`. A `simulate` call
  leaves the current piece and queue exactly as they were.
- **Horizon**: the simulation is bounded to the pieces the game already knows
  (current falling piece + `next_piece` + previews). A sequence that would need
  a piece beyond that horizon returns `{"error": "horizon exceeded: ..."}`
  rather than inventing future pieces. `quit` is ignored (simulate never leaves
  MCP).

### Board snapshot (both tools)

```text
board:            list[22] of list[10] of (int|"X"|"O")   # 1 = filled, 0 = empty, "X" = hole (unreachable covered), "O" = overhang (reachable covered)
current_piece:    str   # "I","O","T","S","Z","J","L"
next_piece:       str
preview_pieces:   list[str]                  # extra lookahead (count = preview_count-1)
hold_piece:       str | None
can_hold:         bool   # hold available for this piece
score:            int
lines:            int
level:            int
game_over:        bool
holes:            int                         # count of unreachable covered empty cells ("X")
overhangs:        int                        # count of reachable covered empty cells ("O")
action_results:   list[str]                  # "ok" / "blocked" (hold unavailable) / "unknown:<action>" per action (play only)
lines_cleared:    int | None                  # lines removed by this call's actions (play only)
error:            str | None                  # present only when processing raised; also game_over/board
```

## Resources

### tetris://shapes

Full shape/kick geometry as JSON (read the resource; harness: `mcp://tetris://shapes`):

- `shapes`: `SHAPES` — `dict[piece_type, list[rotation_cells]]`, each rotation a
  list of `(col,row)` cell offsets in the 4×4 piece box.
- `srs_kicks`: `{"JLSTZ": ..., "I": ...}` — SRS wall-kick offset tables.
- `spawn`: `{"x": 3, "y": 0}` (BOARD_WIDTH//2 - 2).
- `board`: `{"width":10, "height":22, "hidden_rows":2, "visible_rows":20}`.
- `coordinate_convention`: cells are `(col,row)` in the piece box; absolute =
  `(piece.x+col, piece.y+row)`; board `y=0` top, `y` increases downward.

Read it once at session start; no need to open `tetris/game/shapes.py`.

## Board representation

- `board[y][x]`: `y=0` is the **top** (2 hidden buffer rows at y=0,1),
  `y=21` is the bottom. `x=0` is the left wall. `1` = occupied, `0` = empty,
  `"X"` = hole (empty with a filled cell above and no path from the top),
  `"O"` = overhang (empty with a filled cell above but still reachable from
  the top through a side gap). `holes`/`overhangs` count them.
- Height of column `x` = `22 - (index of first filled row from the top)`.
- Line clears and scoring (standard Tetris Guideline) happen automatically
  on lock.
- A `handicap` (settings) may pre-fill bottom rows with gray blocks at game
  start — treat them as normal filled cells.

## Piece model (for planning moves)

- A new piece **spawns** at rotation `0`, `x = BOARD_WIDTH//2 - 2 = 3`,
  `y = 0` (top). Its cells are `SHAPES[type][rotation]` offsets added to
  `(x, y)`.
- The snapshot does **not** include the falling piece's coordinates — you
  must track them yourself:
  - `left` → x -= 1, `right` → x += 1.
  - `rotate_cw` / `rotate_ccw` → advance rotation; SRS wall kicks *may*
    shift x (usually by 0 or ±1). Rotate while the piece is high (near
    spawn) where there is room, then move horizontally — kicks rarely fire
    there.
  - `hold` swaps with `hold_piece` (once per piece; `can_hold` becomes
    `False` until the next lock).
- Exact cell offsets, SRS kick tables, spawn, and board geometry are exposed
  by the `tetris://shapes` resource (read it once at session start).
- For exact placement you can simulate locally with
  `tetris.game.board.Board` + `tetris.game.tetromino.Tetromino`:
  `Board.try_rotate(piece, dir)` **mutates** the piece (x/y/rotation/shape)
  and returns a `bool`; `Board.hard_drop(piece)` mutates `piece.y` to the
  lowest valid row; `Board.is_valid_move(piece, dx)` checks fit at the current
  y. `frames=0` + `hard_drop` is fully deterministic — plan offline, then send
  `[rotate_cw]*n + [left|right]*m + [hard_drop]`.

## Play loop (greedy heuristic)

1. Call `start_game` once to begin.
2. Read the snapshot. Note `game_over`; stop if `True`.
3. Decide the placement for `current_piece`:
   - Using `SHAPES`, enumerate every `(rotation, x)` where the piece fits
     (no overlap with `board`, within `0..9`).
   - For each candidate, drop it onto the stack (lowest valid y), place,
     clear full lines, and score the resulting board: prefer more lines
     cleared, fewer holes, lower and less bumpy aggregate height.
   - Pick the best `(rotation, x)`.
4. Build one `play` action list: first the needed `rotate_cw`/`rotate_ccw`
   (from spawn rotation `0` to target), then `left`/`right` to reach target
   `x` from spawn `x=3` (account for any kick shift if you rotated), then
   `hard_drop`.
   - `frames = 0` (no gravity during placement).
5. Send the `play` call, read the new snapshot, repeat from step 2.

### Worked example

After `start_game`, suppose `current_piece = "O"` (rotations irrelevant;
2x2). Spawn `x=3`. Target column: `x=4`. Actions:
`["right", "hard_drop"]`, `frames=0`. The O locks at the bottom of columns
4-5. The next snapshot shows the new `current_piece` and updated
`board`/`score`.

### Worked example — vertical I (well fill)

`current_piece = "I"` spawns horizontal (rotation 0) at `x=3`. To drop a
vertical I into the right well (column 8): rotate once, then move right 3:
`["rotate_cw", "right", "right", "right", "hard_drop"]`, `frames=0`. After
`rotate_cw` the I occupies a single column; the three `right`s shift that
column to `x=8`; `hard_drop` locks it at the bottom.

## Caveats

- `simulate` is non-mutating — preview a move with it, then commit with `play`.
  The real board only changes on `play`. A sequence past the known piece horizon
  (current + next + previews) returns `{"error": "horizon exceeded: ..."}`.

- The game does not run on its own — gravity only advances when you pass
- On `game_over` the server stays ALIVE — the snapshot reports
  `game_over: true` and play is frozen. Call `start_game` to reset within the
  same MCP session (no menu transition). To leave MCP entirely, send the
  `quit` action/tool — it stops the server and returns to the menu.
- Pieces are random (not 7-bag) and NOT seeded — episodes are not
  reproducible. Re-plan from each snapshot; do not assume a fixed sequence.
- Issuing `play` with no movement and `hard_drop` drops straight from the
  current position (spawn column by default).
- `action_results` tells you if any action name was rejected
  (`unknown:<name>`).
- Respect `can_hold`: `hold` is unavailable after you have already held this
  piece (until the next lock).
- On `game_over`, the server stops and returns to the menu; call
  `start_game` for a new game.
