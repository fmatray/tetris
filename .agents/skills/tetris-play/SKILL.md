---
name: tetris-play
description: Play the Tetris game through its MCP server using the play and start_game tools. Use when the user asks to play Tetris, drive the board via MCP, or run the MCP player.
metadata:
  origin: repo
---

# Tetris MCP Player

Drive the game through the harness MCP tools `xd://mcp__tetris_start_game` and
`xd://mcp__tetris_play`. The server is assumed already running. The game
advances only when you send `play`; it stays frozen between calls.

## Limits

- **No reading** game source, scripts, or any repo code (including shape/kick
  data files).
- **No writing or executing** any code/scripts — no solvers, bots, or local
  simulation with game classes.
  using **only** the MCP tools (`start_game`, `play`, `simulate`, `enumerate_drops`) and the
  snapshot. Each move is a deliberate decision, never an automated loop: think
  of candidates, preview with `simulate`, commit with `play`.

## Tools

- **start_game** `{}` — reset board/score/lines; spawn fresh pieces.
- **simulate** `{ "actions": [...] }` — run the action list on a throwaway copy
  and return a snapshot, **without mutating** the real board or piece queue. Use
  it to preview a placement before committing. The horizon is bounded to known
  pieces (current + next + previews); requesting more drops than known returns
  `{"error": "horizon exceeded: ..."}`.
- **enumerate_drops** `{}` — compute every final board from rotating/shifting/hard-dropping
  the current piece, **without mutating** the real game. Returns
  `{"piece_type": ..., "boards": [ { ...simulate keys..., "actions": [...] } ]}`, each board
  de-duplicated and ranked by (1) most `lines_cleared`, (2) fewest `holes`,
  (3) fewest `overhangs`, (4) flattest/lowest stack. Use it as the **Plan** step: read the
  ranked list, pick `boards[0]` (or any entry), and commit its `actions` with `play`.
  Only the current falling piece is enumerated — `next_piece`/`preview_pieces` are never
  used to choose placements (soft_drop/hold fallbacks are out of scope for this tool).
- **play** `{ "actions": [...], "frames"?: int }` — run the action list, then
  advance `frames` (~16 ms) of gravity, return a snapshot. `frames` defaults to
  0. Actions: `left`, `right`, `rotate_cw`, `rotate_ccw`, `soft_drop`,
  `hard_drop`, `hold`, `start_game`, `quit`. `hard_drop` drops to the floor
  and locks immediately; later actions in the same call apply to the
  next piece. Send one piece's moves per call, then read the snapshot.

## Resources

- `tetris://shapes` — MCP resource with the full piece geometry (all rotation
  states) and SRS wall-kick tables. Read it once at session start for exact
  shape/kick data if needed. It is game data, not repo code, so reading it does
  not violate the Limits above. If you prefer, skip it and learn shapes from the
  snapshot + `simulate` instead.

## Snapshot

Both tools return a snapshot dict (the harness wraps it as JSON; parse the text
field). Key fields:

    board:          22 rows x 10 cols  (0 empty, 1 filled, "X" hole, "O" overhang)
    current_piece:  "I"|"O"|"T"|"S"|"Z"|"J"|"L"
    next_piece:     str
    preview_pieces: list[str]
    hold_piece:     str | None
    can_hold:       bool
    score, lines, level: int       # lines = cumulative total cleared (only increments on actual clears)
    game_over:      bool
    holes:          int   # "X" cells (empty, covered, no top path)
    overhangs:      int   # "O" cells (reachable covered empty — fillable now)
    action_results: list[str]   # "ok"|"blocked"|"unknown:<action>" (play only)
    lines_cleared:  int | None   # lines removed by this call (play, simulate, enumerate)

## Board & pieces

- Rows `y=0..21` (0 top, 21 bottom; 2 hidden buffer rows at top). Cols
  `x=0..9`. `1` = filled, `0` = empty, `"X"` = hole (empty, covered, currently
  unreachable — gap under filled cells with no path from top), `"O"` = overhang
  (empty, covered, reachable now — can be filled by soft-dropping into it). **A
  row clears only when all 10 cells are `1` (filled); `X` and `O` are empty-gap
  annotations, not obstacles.**
- A piece spawns at rotation `0`, `x = 3`, `y = 0`. `left`/`right` shift x;
  `rotate_cw`/`rotate_ccw` change rotation (SRS kicks may nudge x by 0/±1 —
  rotate while high, then shift). `hold` swaps once per piece (`can_hold` →
  False until next lock).
- Line clears and scoring are automatic on lock. A `handicap` may pre-fill
  bottom rows — treat as normal filled cells.

## Play loop

1. **Start** — call `start_game` once.
2. **Read** — get the snapshot. If `game_over`, stop (call `start_game` for a
   new game; never restart before game over).
3. **Plan** — call `enumerate_drops()` once to get every final board from
   rotating/shifting/hard-dropping the current piece, already ranked by
   (1) most `lines_cleared`, (2) fewest `holes`, (3) fewest `overhangs`,
   (4) flattest/lowest stack. Each entry carries its `actions` list — pick the
   best and commit it directly with `play`. Most placements drop straight with
   `hard_drop`; use `soft_drop` to lower to a specific row, then shift, only
   when you must tuck under an overhang or fill a mid-height gap. Also consider
   a `hold` swap when the piece fits nowhere cleanly and a preview piece fits
   better. Use `preview_pieces` to leave a notch for the next piece; building
   one edge well for vertical `I`s sustains long games. Completing a line beats
   saving height.
4. **Preview** — for each candidate call `simulate([...])` and read the board,
   `holes`, `overhangs`, `lines_cleared`. `simulate` never changes the real game,
   so preview as many as you can. Never auto-reject a line-clearing placement
   just because it adds a hole/overhang — score and compare instead (soft
   penalties, no hard filters).
5. **Choose** — rank by: (1) most `lines_cleared`, (2) fewest `holes`,
   (3) fewest `overhangs`, (4) flattest/lowest stack. Holes outrank overhangs:
   an `X` cell is currently unreachable (needs cells above cleared first); an
   `O` cell is reachable now and fillable. Holes are harder to recover, so they
   rank worse.
6. **Commit** — call `play([...], 0)` with the chosen actions; read the new
   snapshot and repeat from step 2.

### Example

`current_piece = "O"` spawns at `x=3`; target columns 4-5:
`play(["right", "hard_drop"], 0)`. The O locks at the bottom of cols 4-5; the
next snapshot shows the new piece and updated board.

## Notes

- `play` is deterministic with `frames=0` (no gravity): `hard_drop` to commit to
  the floor, or `soft_drop` + shift to tuck at a chosen height, then `hard_drop`.
- `action_results` reports rejected actions (`unknown:<action>`); the valid
  rotation is `rotate_cw`, not `rotate`.
- Pieces are random and not seeded — re-plan from each snapshot; never assume a
  sequence.
- On `game_over` the server stays alive (frozen); `start_game` resets in place,
  `quit` leaves MCP.
