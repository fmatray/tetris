# El-Tetris Bot

A deterministic rule-based player. It evaluates every reachable placement
of the current piece with the El-Tetris heuristic and plays the best
one. No learning, no model, no persistence — a watch and benchmark player.

El-Tetris (Yiyuan Lee, 2009) is an improvement on Pierre Dellacherie's
classic algorithm; this bot descends from that feature family and uses
the full published El-Tetris evaluation.

## Player type

`player = "Bot"` in `data/settings.json` (menu: Joueur → Bot).
Its sub-menu ("Bot El-Tetris") has one setting:

| Option | Values | Meaning |
|---|---|---|
| Anticipation | Non / Comme aperçu | Whether the bot plans using the pieces shown in the preview. "Comme aperçu" uses the game menu's `preview_count` as look-ahead depth. |

## Selection algorithm

`ElTetrisState.update()` (tetris/states/eltetris.py):

1. **Enumerate candidates** — all reachable placements of the current
   piece via soft-drop BFS with SRS wall kicks, plus hold-swap
   candidates when hold is available (`tetris/ai/candidates.py`).
2. **Evaluate** — each candidate's resulting board is scored with the
   **El-Tetris evaluation** (`el_tetris_value_batch`, tetris/ai/rewards.py):
   the 4 shared board features (row/column transitions, holes, wells) plus
   the two placement-specific terms the DQN's PBRS weights exclude —
   `landing_height` (distance from the board floor to the piece centroid,
   weight −4.5) and `rows_eliminated` (weight +3.42), with the published
   PSO-tuned weights
   ([El-Tetris](https://imake.ninja/el-tetris-an-improvement-on-pierre-dellacheries-algorithm/)).
3. **Pick** — `int(np.argmax(values))`; ties resolve to the lowest index.
4. **Execute** — the placement's recorded BFS move sequence is replayed
   atomically (`BotMovesMixin._execute_move_sequence`), so the piece
   lands exactly where the evaluation saw it. No execution mismatch.

With look-ahead enabled, `get_candidate_states` simulates each upcoming
preview piece with the same El-Tetris evaluation and keeps the best
continuation (argmax) per candidate — the same machinery the DQN's
look-ahead uses.

The bot plays at fixed `AI_ACTION_DELAY_MS` (80ms) between decisions so
a human can watch; lock delay runs normally (500ms).

The bot is subject to the ARE entry delay: its selection is deferred during ARE, and the `GameState` base class handles the delay. See [game_rules.md §12](game_rules.md#12-are-appearance-delay-irs-ihs).

## BFS Path Replay Fix (Survival Bug Root Cause)

**Problem**: The bot (and AI) used soft-drop BFS to enumerate candidate placements from the spawn position (3, 0, rotation=0). However, during the decision throttle (`AI_ACTION_DELAY_MS`), the piece pre-falls due to gravity. When the recorded move sequence was replayed, it started from the wrong position — the piece had already fallen several rows, causing the replayed moves to land the piece incorrectly.

**Root Cause**: BFS paths are recorded from spawn, but execution happens after gravity has moved the piece. The board is unchanged since enumeration, so the path is valid at spawn — but not at the pre-fallen position.

**Fix** (committed `e9098d1`): In `BotMovesMixin._execute_move_sequence()` (`tetris/bots/moves.py`), re-anchor the piece to its spawn position (3, 0, rotation=0) **before** replaying the recorded moves. The board has not changed since candidate enumeration, so the path is valid at any gravity level. Removed the incorrect `y >= p.py` guard that assumed monotonic downward movement (SRS kicks can move pieces up).

**Verification**:
- 0/1831 mismatches on seed 99 (normal speed)
- Seed 99 reaches level 73 / 730 lines
- Insane speed seed 42: 120K frames (3731 pieces, 1490 lines)

The throttle cap (`AI_ACTION_DELAY_MS`) is kept as a visual nicety so humans can watch the bot play.

## El-Tetris evaluation

The bot uses the **El-Tetris evaluation** (`el_tetris_value_batch` in `tetris/ai/rewards.py`). El-Tetris adds two placement-specific terms to the base 4 board features:
- `landing_height` (weight −4.5) — distance from board floor to piece centroid
- `rows_eliminated` (weight +3.42) — lines cleared by this placement

with published PSO-tuned weights from the [El-Tetris paper](https://imake.ninja/el-tetris-an-improvement-on-pierre-dellacheries-algorithm/).

Literature benchmark: ~16M lines average (vs ~5M for classic Dellacherie). The bot serves as a score floor and oracle for debugging candidate generation.

## Shared Bot Library (`tetris/bots/`)

`ElTetrisState` and `AIState` are fully independent states — neither imports the other. Their shared machinery lives in `tetris/bots/`:

| Module | Contents |
|---|---|
| `tetris/bots/moves.py` | `BotMovesMixin` — `_get_candidate_states()` and `_execute_move_sequence()`, extracted verbatim from AIState. Hosts must provide the attributes listed in the mixin docstring (board, pieces, `_can_hold`, `lookahead`, `lookahead_depth`, `_hold()`). |

`AIState(BotMovesMixin, GameState)` refactored to inherit the mixin — same methods, same behavior, single implementation.

## Game over

The bot returns to the menu on game over. It never writes to the
leaderboard, human stats, AI training logs, or any `data/` file beyond
the piece provider's own record/replay path. Press `q` during play to
return to the menu after the current game ends.

## Benchmark expectations

El-Tetris clears ~16M lines on average in the literature's benchmark
(vs ~5M for classic Dellacherie in the same harness) — orders of
magnitude beyond the previous bot implementation. Expect the bot to
outperform the current trained DQN; it serves as a score floor and
as an oracle for debugging candidate generation.