# MCP Tetris Play — Findings

Goal: clear >=10 lines in a single episode (cumulative across episodes does NOT count).
Hard limits: no reading/writing code or scripts; only MCP tools + this file.

## Episode 1 (2026-08-24)

- **Result:** game_over at `lines=1`, score 584, holes 12, overhangs 20.
- **Strategy tried:** trust `enumerate_drops` `boards[0]` (ranked by lines, overhangs, holes, flatness) for every piece.
- **What went wrong:**
  - First pieces (L, T, Z) all landed on the RIGHT (cols 4–9). Cols 0–3 stayed empty top-to-bottom.
  - That one-sided pile created overhangs (`O`) and holes (`X`) that permanently block row clears on the right, while the empty left could never complete a row. Death spiral.
  - `enumerate_drops` `boards[0]` is NOT reliably the line-clearing move: with `I` and a near-full bottom row, the horizontal `I` on the far left DID clear a line (verified via `simulate`), but `boards[0]` had ranked a non-clearing vertical `I` first. So always verify line clears with `simulate` when a row is nearly full.
  - Z/S pieces inherently make overhangs on a flat floor (top cell hangs over the empty cell below).
- **Good finding:** a horizontal `I` dropped on the far left fills cols 0–3 of the bottom row; if the rest of that row is already solid, it clears a line. Reached line 1 this way.

## Lessons for Episode 2+
1. Spread placements across the board from move 1 — keep the stack FLAT and LOW, don't pile one side.
2. When a bottom row is missing only 1–2 cells, `simulate` a piece that fills that gap (esp. horizontal `I`) to clear, even if `boards[0]` doesn't suggest it.
3. Prefer placements with overhangs=0 and holes=0; avoid creating `O`/`X` cells.
4. Use the per-call multi-piece trick (repeat `hard_drop` sequences) only to end a lost episode fast — not for scoring.
5. `play` with a long action list places multiple pieces in one call (later actions apply to the next piece after each `hard_drop`).

## Episode 2 (2026-08-24, FINAL — game_over)

- **Result:** `lines=37`, `score=17128`, `holes=0`, `overhangs=8`, `game_over=true` at ~piece78 (S landed at rows1–3, topping the left stack). **Goal of ≥10 lines in a single episode ACHIEVED** (crossed 10 at piece36, finished at 37).
- **Strategy that worked — the "well" strategy:**
  - Spread flat left-to-right early (pieces 1–35) to build a flat floor with one open column (well).
  - Keep a single open `well` column (started col1, later moved to col0) and refill it with a **vertical I** (`rotate_cw×3` → vertical, `[left×3, hard_drop]`) to clear 2 lines at once.
  - Repeated Z drops (`[rotate_cw×3, left×3, hard_drop]`) cleared 2 lines each (Z49→15, Z50→17) the same way the well was on col1.
  - When the well has only 1 row left to fill, a **horizontal I** at `[left×3, hard_drop]` (or other piece that completes the open cells of the bottom row) clears 1 line.
  - "Fill the last gap" generalizes: whenever a bottom row is missing only the cells a piece can supply, drop to complete it → clear. Board oscillates sparse↔filled and stays low (rows19–21).
- **Enumerate_drops reliability — refined:**
  - `lines_cleared` is ALWAYS 0 (bug) — never trust it for clears.
  - The `lines` (total) field is correct **only when the piece can physically complete a row** (its cells fill the open cells of a row). It is a **FALSE POSITIVE** when the piece cannot complete any row (e.g. O46 claimed lines:13 but the O couldn't finish a row; actual play showed lines:11, no clear).
  - **Distinguishing rule:** before trusting a claimed clear, check whether the open cells of the target row actually match the piece's cells. If yes → clear is real (verify via `play`/`simulate`). If no → bogus, ignore the `lines` bump, still pick the placement by `overhangs:0`.
  - The J69 clear (`[left×3, hard_drop]` → lines:27) looked like a false positive in planning (I assumed J spawns at cols4–6, making `[left×3]` land cols1–3 and leave col0 open). Reality: **J spawns at cols3–5**, so `[left×3]` lands cols0–2, completing row20 → real clear. Lesson: verify spawn offsets; don't assume.
  - Enumerate ranking order is `lines_cleared` > `overhangs` > `holes` > flatness, but since `lines_cleared` is dead, **rank manually by `overhangs:0` + well-preservation + low `holes`.**
  - **Board display in enumerate is buggy** (mixes `"O"`/`"X"` strings with `1`s, sometimes marks wrong cells). Trust the `holes`/`overhangs`/`score` JSON fields, NOT the displayed grid.
- **Frames notes:** `frames:0` for plain drops; `frames:5` for pending line clears (advance the clear animation); `frames:1` can be a no-op — avoid.
- **Clearing actions that worked (post piece36):**
  - I36 `[rotate_cw,left×5,hard_drop]` → 10
  - I48 `[rotate_cw×3,left×3,hard_drop]` → 13 (col1 well)
  - Z49/Z50 `[rotate_cw×3,left×3,hard_drop]` → 15 / 17
  - I53 `[rotate_cw,left×2,hard_drop]` → 18 (col0 well)
  - T54 → 20 (2-line)
  - O56 `[left×2,hard_drop]` → 21 (also eliminated the persistent hole at col4-row21)
  - J57 `[rotate_cw,hard_drop]` → 22
  - I60/I66 `[left×3,hard_drop]` → 23 / 26 (horizontal I fills last gap)
  - Z62 `[rotate_cw,left,hard_drop]` → 24
  - L64 `[rotate_cw,right,hard_drop]` → 25
  - J69 `[left×3,hard_drop]` → 27
  - Z (score 16052, +1234) → 36 (2-line clear, confirmed via `play`)
  - J (`[rotate_cw×3,left×3,hard_drop]`, +432) → 37 (1-line clear, confirmed via `play`)
- **Late episode (27→37) — score-spike heuristic PROVEN UNRELIABLE:** Z (`+1234`) and J (`+432`) were real clears, but T (`+422`) was **NOT** a clear (lines stayed 37, `lines_cleared:0`). A score bump can mean a clear OR a good board position. **Only `play` `lines`/`lines_cleared` confirms a clear** — never the score delta alone.
- **Topout cause (game over at ~piece78):** the col0 well stayed open the whole time, but **no piece (incl. vertical I, blocked by the wall at `left×4`) could fill a 1-wide well**. So the side columns (cols3–4 left, cols8–9 right) kept growing until the S landed at rows1–3 → topout. **Stack height — not holes/overhangs (ov=8, holes=0 at death) — was the killer.** The well strategy stalls the stack: the open column can't be cleared, so the rest grows.
- **Honor "DO NOT RESTART":** finished the episode to `game_over`; only `start_game` after `game_over=true`.
- **Persistent hole** (X at col4-row21) was eliminated at piece56 (O clear); board has been hole-free since.

## Lessons for Episode 3+
1. **The 1-wide well is a TRAP** with `hard_drop`-only: no piece (incl. vertical I, blocked by the wall at `left×4`) can fill a 1-wide column, so it stays open forever while the side columns grow → topout. Keep the stack FLAT and fill every column; don't preserve a permanent well. Use a temporary gap only when an I/Z can clear it that turn.
2. Trust `enumerate_drops` only for `overhangs`/`holes`/flatness — NEVER for `lines_cleared`; verify clears by checking whether the piece's cells complete a row, then confirm with `play`. **Board display in enumerate is buggy — trust the `holes`/`overhangs`/`score` JSON fields.**
3. **Score-spike is NOT a clear signal:** Z (`+1234`) and J (`+432`) were real clears, but T (`+422`) was not. Only `play` `lines`/`lines_cleared` confirms a clear.
4. Horizontal I at the bottom (`[left×3,hard_drop]`) is the catch-all for "1 cell short" rows, but it needs a 4-cell-wide open span — the well strategy removes that option.
5. Verify piece spawn offsets before second-guessing a real clear (J spawns cols3–5, not 4–6).
6. **Stack HEIGHT is the real killer, not holes/overhangs**: Ep2 died at `ov=8, holes=0` with the left stack at row1. Prioritize keeping the tallest column low over marginal overhang reduction.
7. Strategy for Ep3: flat Tetris — spread pieces evenly, keep all columns within ~2 rows of each other, clear whenever a piece completes a row; avoid leaving any column open.

## Episode 3 (2026-08-24, IN PROGRESS — paused at piece 5)
- **Goal tested:** replace the well strategy with a flat left-to-right fill (every column kept roughly equal, no permanent well). Hypothesis: flatter stack avoids the height-topout of Ep2.
- **Result so far:** `lines=0`, `score=194`, `holes=1`, `overhangs=0` after 5 pieces (J,Z,S,L,I). **Hypothesis FAILED** — flat fill with `hard_drop`-only creates NOTCHES → buried holes, same dead-end as Ep2 but faster.
- **Piece log (Ep3):**
  - J `["left","left","left","hard_drop"]` → 40, ov0
  - Z `["left","left","left","hard_drop"]` → 78, ov0
  - S `["hard_drop"]` → 118, ov1
  - L `["right","right","right","hard_drop"]` → 158, **holes=1** (notch at col3/col6–7 → buried hole)
  - I `["rotate_cw","right","right","right","right","hard_drop"]` → 194, **no clear** (+36 only)
- **Critical corrections to earlier notes:**
  - **`I` DOES reach col9 vertically** via `rotate_cw` + `right×4` (earlier "max right = col7" claim in Ep2 notes was wrong). It filled col9 rows18–21.
  - **The `X` in board display marks the HOLE, not a filled cell.** After the I, row21 showed `[1,1,1,1,1,"X",1,1,1,1]` with `holes=1` — col5-row21 is the buried hole (empty, with col5-row20 filled above it). So row21 was NOT complete → no clear (score +36, not the +100s of a real clear). **Re-confirms `lines`/`lines_cleared` via `play` is the only clear signal; board display is unreliable.**
  - **Flat-fill creates buried holes:** with `hard_drop`-only you cannot tuck a piece under a notch, so every uneven landing leaves an empty cell with filled cells above → permanent hole. Ep2's early `holes=0` came from enumerate-per-piece discipline, NOT from the well itself.
- **Revised strategy for Ep3 restart:** enumerate-per-piece (pick `holes=0` + lowest flatness), keep columns within ~1–2 rows, clear whenever a piece completes a row. Do NOT use a permanent well (height trap) and do NOT free-flat-fill (buried-hole trap). The only reliable path is per-piece enumeration keeping the board flat AND hole-free, clearing lines before any column gets tall.
- **Status:** session ended mid-episode (buried hole already present at piece5). Ep3 to be continued (or restarted) next session with the corrected enumerate-per-piece-flat approach.

## Episode 3 (2026-08-24, CONTINUED — recovery, then L-mistake, then re-recovery attempt)

- **Enumerate-per-piece-flat RECOVERS from a buried hole** (revises earlier "flat-fill FAILED"): resumed with enumerate-per-piece discipline (pick `holes:0`+lowest `overhangs`); pieces S/J/T/Z/J/O/I/S/T/L cleared lines 1→5 on a clean (holes:0, ov:0) board. Blind `hard_drop` flat-fill makes notches→holes; enumerated flat picks the one `holes:0` placement per piece and stays clean. **Both true: blind flat-fill fails, enumerated flat works.**
- **Ep3 clears (recovery):** O→1, L→2, I→3, S→4, I(col9)→5. Vertical I at col8/9 seals the right edge; O/L/S gap-fill the left.
- **THE L-MISTAKE (key lesson):** at lines:5, rows19–20 missing only cols0,1, tried `L ["left×4","hard_drop"]` expecting a triple clear (L0 at col0 → rows19–21 + col1 row19 complete). **No clear.** `play` → `lines_cleared:0`, `holes:5`. The target cells show as `"X"` in the board — and `"X"` = OPEN, not filled. So those rows were never complete; `"X"` marks the piece's *unfilled* target (display artifact), not locked cells.
- **Root cause:** misapplied the "enumerate `lines`/`lines_cleared` unreliable (pre-clear)" rule to `holes`. The simulate HAD reported `holes:5` — that was REAL (5 buried holes under the row18 overhang at cols0,1 rows19–21). **The pre-clear-unreliable rule covers ONLY `lines`/`lines_cleared`, never `holes`.**
- **FINAL RULE:** before playing, read the simulate/enumerate `holes` field. **`holes>0` ⇒ the placement creates holes ⇒ DO NOT PLAY.** Only play `holes:0`. (`"X"` cells in the displayed grid confirm they are open/holes.)
- **Re-recovery path:** the 5 holes are buried under the row18 overhang (cols0–5 at row18). Row18 has a 2-cell gap at cols6,7. Fill cols6,7 at row18 → row18 completes → clears → overhang removed → cols0,1 rows19–21 become reachable from above → fillable. T cannot fill cols6,7; trying Z/L/I next.
- **Status:** board compromised (holes:5) but recoverable; episode continues to game_over per rules.
- **Enumerate `holes` count is UNRELIABLE (undercounts) when overhangs are present** — CRITICAL revision to "FINAL RULE" (line 91). S `["rotate_cw×3","left×3","hard_drop"]` enumerated as `holes:5, overhangs:8`, but the actual `play` returned `holes:8`: it buried col0 rows15–17 (a cell landed at col0 row14, sealing them under an overhang) — 3 new holes the enumerate MISSED. **The enumerate `holes` field undercounts whenever the placement spawns overhangs.** The `play` response `holes` is the SOLE source of truth; re-read it after every move. (Earlier matches — T `[hard_drop]` holes:5, L opt1 holes:5, I opt1 holes:5 — were all `ov:0` cases, so the counter was correct ONLY when `overhangs=0`.)
- **O-recovery attempt FAILED.** With the row18 gap at cols6,7, `O ["right","right","hard_drop"]` was played to fill it; `play` returned `lines_cleared:0, holes:8` — O filled only col6 (col7 still open), so row18 did NOT complete → no clear. Likely O spawn offset is not cols4–5 (so `right×2` did not reach cols6–7), or the displayed "O" is a misrendered single cell. A 2-cell gap is NOT trivially fillable with O via `right×2`.
- **Ep3 final (game_over):** fast-forwarded the compromised board to topout via repeated `hard_drop` (permitted to end a lost episode). Final `lines=5, score=1672, holes=8, overhangs=14, game_over=true`. Ep3 never recovered from the L-mistake/O-failure; 5 lines was its ceiling.
- **Goal status:** ≥10 lines in one episode ACHIEVED in Ep2 (lines:37). Ep3 (flat-fill + enumerate-per-piece recovery) reached only lines:5 — confirms `hard_drop`-only cannot sustain a clean board once a buried hole forms; enumerate-per-piece discipline recovers partial lines but a deep hole set is terminal. Strategies tried: (1) well (Ep2, 37 lines), (2) blind flat-fill (Ep3 early, failed), (3) enumerate-per-piece-flat (Ep3 recovery, 5 lines). Key learned bugs: enumerate `lines_cleared` dead; `lines` false-positive; enumerate `holes` undercounts under overhangs (read `play` `holes`); board display `X`/`O` strings unreliable.
- **Episode 4+:** after this real `game_over`, `start_game` is legitimate. A clean enumerate-per-piece run from piece 1 (trusting `play` `holes`, never enumerate `holes`) could target a 10+ line episode without the early buried-hole trap. Left for a future session.

## Reliability Audit (2026-08-25)

Full code investigation of all reported MCP tool issues. Two confirmed code bugs fixed, three non-bugs confirmed.

### Issue 1 — `lines_cleared` always 0 in simulate/enumerate: FIXED

**Root cause:** `simulate_actions` (simulator.py:141-142) captured `before = state.stats.total_lines` AFTER `_execute_actions`, which already incremented `total_lines` during lock. So `lines_cleared = total_lines - before = 0`.

**Fix:** Moved `before` capture to before `_execute_actions`, matching the play path (mcp.py:161-162). Now simulate/enumerate correctly report `lines_cleared`.

### Issue 2 — `lines` (total) false-positive: NOT A BUG

`GameStats.total_lines` only increments via `on_piece_locked(lines_cleared)` — never on score-only events (hard-drop points). The "false-positive" was a misattribution: the agent saw score increase and assumed lines increased. SKILL.md now documents `lines` as "cumulative total cleared (only increments on actual clears)".

### Issue 3 — Board display "X"/"O" strings: BY DESIGN — SKILL.md corrected

`build_board_repr` intentionally uses: `0`=empty, `1`=filled, `"X"`=hole (unreachable covered empty), `"O"`=overhang (reachable covered empty). The display is correct; SKILL.md described them wrong (called overhangs "filled-but-unsupported", called X/O "obstacles", said "overhangs outrank holes"). All SKILL.md errors corrected.

### Issue 4 — Enumerate holes undercounts under overhangs: NOT A BUG

Direct test: all 17 S-piece placements on an overhang board produce identical boards/holes/overhangs between enumerate and play. The reported discrepancy was a session-observation artifact.

### Issue 5 — `_dedup_and_rank` ranking: overhangs before holes: FIXED

**Root cause:** Sort key was `(-lines, overhangs, holes, ...)` — ranked fewer-overhangs ahead of fewer-holes. But holes (X = unreachable) are worse than overhangs (O = reachable, fillable).

**Fix:** Swapped to `(-lines, holes, overhangs, height, bumpiness)`. Now fewer-holes ranks higher, matching the strategic priority. SKILL.md and docstrings updated to match.

### Two hole definitions — by design

- `rules.find_holes` (flood-fill reachability): used by `build_board_repr` for X/O display annotation
- `rewards.count_holes` (column-based "filled above"): used by AI feature extraction (DT-20 index 1)

These serve different purposes and intentionally differ. Not a discrepancy.
