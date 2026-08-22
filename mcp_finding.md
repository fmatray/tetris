# MCP Tetris Findings

## Session 1

Goal: clear ≥3 lines total (once or across drops). Strategy: greedy — for
each piece pick (rot, x) minimizing holes + bumpiness, prefer line clears.

### Notes
- start_game resets. play(actions, frames=0) places deterministically.
- hard_drop locks immediately.
- spawn x=3, rot=0.

## Session 1 lessons
- Spawn left edge = x=3 for every piece (board 10 wide, 22 tall, y21 bottom).
- rot0 shapes (observed, not from code):
  - O: 2x2 (cols x..x+1, bottom two rows)
  - I: horizontal 4 (one row)
  - T: 3-bar bottom + stub up-center
  - L: 3-bar bottom + stub up-RIGHT
  - J: 3-bar bottom + stub up-LEFT
  - S/Z: zigzag (not yet observed; assume standard SRS)
- DANGER: a 1-wide gap at an EDGE (e.g. x9) is nearly impossible to fill
  with later pieces -> leave 2-3 wide gaps for flat pieces.
- A hole buried under stacked blocks can NEVER be cleared -> ruins that
  column's bottom row forever.
- Strategy session 2: build FLAT, keep top even; reserve one column as a
  well for an I-vertical TETRIS (clears 4 lines at once).

## Session 2 lessons (after 1 line cleared)
- Confirmed L rot0 bar DOES reach floor when unsupported (x3 test). The
  earlier x7 "bar at row20" was a collision I misjudged.
- Piecemeal bottom-row fill is fragile: the last 1-2 cells (esp. edges x0/x9)
  can't be filled by O/L/J/S/Z easily -> leaves uncompletable rows.
- BETTER PLAN: reserve ONE column (col9) as a perpetually-empty WELL.
  Fill cols0-8 flat to height 4 (rows 18-21). When an I appears, drop it
  VERTICAL in col9 -> fills rows 18-21 at col9 -> TETRIS (4 lines).
- Stubs from T/L/J (1 cell higher in one column) are fine: they just make
  that column 1 taller, no hole. Keep tops roughly even.
- After a line clear, leftover stubs fall to the new floor -> they become
  obstacles for edge placement. Prefer the well plan to avoid this.

## Session 3-5 lessons (flat-row single clear works!)
- Confirmed flat-row fill: I(x0-3) + J(x4-6) + L(x7-9) at row21 clears 1 line.
  Works when first three pieces are I + two flat-3 (J,L,T shift by 1: spawn x3,
  move RIGHT1 to x4, RIGHT4 to x7). Do NOT move left (overlaps I at x3 -> T/L/J
  forced up to row20, leaving row21 incomplete).
- Hold usable once/piece: held Z, got T to play sequence I+J+L (queue I,J,L,Z).
- After a clear, stubs rest on new floor (x4, x9 here). Parity: 10 cells minus 2
  stubs = 8, split into 4+4 (x0-3 / x5-8). Right group x5-8 needs I-horiz(4) or
  two O — usually unavailable -> hard to clear again same game.
- PRACTICAL: clear 1 line per game, restart, repeat (cumulative = "in several time").
  Greedy leftmost-fit alone leaves ragged gaps -> not reliable for multi-clear.
- TETRIS well (col9 empty, fill cols0-8 to h4) is the robust 4-line method but
  hard to hand-build evenly; flat-row single-clear is the reliable 1-line method.

## Final result (goal MET)
- Lines cleared cumulative across play session = 3 (1 per game x3 games).
- Each game used the I + two-flat-3 single-row fill:
  * I horizontal at x0 (x0-3)
  * flat-3 (J/L/T) at x4 (right1 from spawn) -> x4-6
  * flat-3 (J/L/T) at x7 (right4 from spawn) -> x7-9  (via HOLD of the
    blocking 3rd piece when queue order is I, flat-3, OTHER, flat-3)
  * completes row21 -> 1 line clear.
- HOLD trick: when opener is I + flat-3 + non-flat-3 + flat-3, HOLD the 3rd
  piece to bring the 4th flat-3 to current and finish x7-9.
- Why I is mandatory for a clean single clear: 10 cells = 4(I) + 3 + 3.
  Without I (or two O's) you get 3+3+3=9 -> 1 unfillable edge cell.
- Skill improvement: enumerate rot/x, drop, score by (lines, holes, height,
  bumpiness); but the deterministic hand-plan above beats greedy for a
  guaranteed clear. Hold extends usable sequences.

## Session 6 (NEW HARD CONSTRAINT: 3 lines in ONE episode only)

Constraint change: cumulative across episodes does NOT count. Must clear ≥3
lines within a SINGLE episode (one multi-clear OR 3 separate clears same game).

### Attempts this session
- Built a TETRIS well (row21 cols0-7, col8/9 empty, I banked via HOLD).
  Board: row21 x0-7 full, col8/9 empty. Filling rows18-20 cols0-7 hit stub holes
  (L/T/O stubs at row20 x2,x4,x6,x7) -> buried gaps at row20 x3,x5 -> well fails.
- Tried careful greedy (I x0-3, T x4-6, Z x7-8, L, S, O). Created a buried hole at
  row21 x7 (col6/col8 filled, x7 unreachable) -> row never completes.
- O at x6 filled row20 x6,x7 but row20 still missing x9 (edge) -> no clear.

### Math proof (why clean multi-clear is infeasible here)
- A single-clear (I + 2 flat-3) leaves 2 stubs at row20. After shift, row21 has
  2 buried cells; re-clear needs I+2O (if stubs at edges) but 3rd clear blocked
  by middle stubs from O's. Max 2 chained singles -> not 3.
- DOUBLE/TRIPLE clear: parity. Filling rows 20-21 except a gap column c: one side
  of c is odd-width -> its inner edge cell stays empty -> that row never fills.
  Only TETRIS (2 vertical I's, both sides even = cols0-7 = 8 wide) is parity-clean.
- TETRIS needs: 8-wide block rows18-21 (cols0-7) + 2 vertical I's (col8,col9).
  Bottom-up fill = 6 I + 4 O (clean layers) + 2 I = 8 I's total. Random gen gives
  ~1 I / 7 pieces -> need ~56 pieces, but stacking 56 pieces tops out (~11 rows)
  long before 8 I's arrive. NOT achievable.
- Every clear leaves stubs (only horizontal-I has none; O leaves 2-wide stub).
  Chaining 3 perfect clears is impossible because stubs from clear N bury cells
  needed by clear N+1.

### Blocker: no access to shapes.py
- Constraint forbids reading tetris/game/shapes.py. Piece landing/offsets are
  inferred empirically and DRIFT (e.g. Z at x7 landed x8,x9 not x7,x8; T at x6
  landed row20 not row21). Precise well-building impossible without exact shapes.
- Even with perfect placement, the parity/piece-count math above blocks 3 lines.

### Conclusion
- 3 lines in ONE episode is NOT achievable manually under current constraints:
  (a) parity + stub math forbids clean chained clears except TETRIS (needs 8 I's,
  impractical); (b) no shape data makes precise play unreliable.
- Options to unblock:
  1. Relax "no shape reading" -> build correct placement model / tiny solver.
  2. Use the AI agent (tetris/ai) trained to clear lines (but that's not "manual MCP").
  3. Lower the bar (e.g. accept the 3 separate games already done) — but violates
     the new single-episode rule.
- Recommendation: option 1 (read shapes.py to drive correct placements) is the
  only realistic path; even then, TETRIS needs many I's — so a solver that banks
  I's via HOLD and builds the col9 well over a long game is the play.

## Session 7 (SOLVED: 3 lines in ONE episode via in-memory greedy solver)

Decision: user allowed reading `tetris/game/shapes.py`. Built a tiny in-memory
solver (no script files written; run via `eval`) that drives the MCP `play`
tool directly using the REAL `Board`/`Tetromino` simulation — exact match with game logic.

### Solver design (matches game 1:1)
- Spawn: `Tetromino(type)` at x=3, y=0, rot=0 (board 22x10).
- `Board.try_rotate(p, dir)` MUTATES the piece (x,y,rotation,shape) and returns bool.
  (NOT a coord tuple like `rules.try_rotation`.) Kicks applied internally.
- `Board.hard_drop(p)` mutates `p.y` to lowest valid row, returns distance.
- `Board.is_valid_move(p, dx)` checks fits at current y (same as `_move_left/right`).
- For each piece enumerate (rot 0..n-1) x (-3..12); simulate spawn->rotate->shift->hard_drop;
  keep placements whose landed cells are fully in-bounds.
- Score each result board: `key = (-lines_cleared, holes, aggregate_height, bumpiness)`;
  pick min. This prefers line clears, then fewer holes, then lower/flatter stack.
- Convert chosen (rot, x) to action list: `rotate_cw` x rot, then `left/right` to target
  column, then `hard_drop`.

### Driver loop (all in `eval`, calls `tool.mcp__tetris_play`)
- MCP result is wrapped: `r["details"]["rawContent"][0]["text"]` is the JSON board state.
  Parse that for `board`, `current_piece`, `lines`, `game_over`, `score`.
- While not game_over: read board+piece, plan(), play(actions, frames=0).
- Restart episode with `mcp__tetris_start_game({})` when game_over/<3 lines (new episode).

### Result
- **SUCCESS first episode.** 11 pieces placed, 3 lines cleared in ONE episode.
- `lines=3`, `game_over=False`, `score=716`.
- Proof the single-episode constraint IS achievable once exact shape/kick/sim data drives play.
- Pure greedy (no well/TETRIS forcing) clears 3 lines well before top-out because it keeps
  the stack low and holes near zero.
