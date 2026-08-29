# Dellacherie Bot

A deterministic rule-based player. It evaluates every reachable placement
of the current piece with the El-Tetris heuristic and plays the best
one. No learning, no model, no persistence — a watch and benchmark player.

## Player type

`player = "Bot"` in `data/settings.json` (menu: Joueur → Bot).
Its sub-menu ("Bot Dellacherie") has one setting:

| Option | Values | Meaning |
|---|---|---|
| Anticipation | Non / Comme aperçu | Whether the bot plans using the pieces shown in the preview. "Comme aperçu" uses the game menu's `preview_count` as look-ahead depth. |

## Selection algorithm

`DellacherieState.update()` (tetris/states/dellacherie.py):

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
3. **Pick** — `dellacherie_pick()` returns the argmax; ties resolve to
   the lowest index (tetris/bots/dellacherie.py).
4. **Execute** — the placement's recorded BFS move sequence is replayed
   atomically (`BotMovesMixin._execute_move_sequence`), so the piece
   lands exactly where the evaluation saw it. No execution mismatch.

With look-ahead enabled, `get_candidate_states` simulates each upcoming
preview piece with the same El-Tetris evaluation and keeps the best
continuation (argmax) per candidate — the same machinery the DQN's
look-ahead uses.

The bot plays at fixed `AI_ACTION_DELAY_MS` (80ms) between decisions so
a human can watch; lock delay runs normally (500ms).

## Shared bot library (`tetris/bots/`)

`DellacherieState` and `AIState` are fully independent states — neither
imports the other. Their shared machinery lives in `tetris/bots/`:

| Module | Contents |
|---|---|
| `tetris/bots/moves.py` | `BotMovesMixin` — `_get_candidate_states()` and `_execute_move_sequence()`, extracted verbatim from AIState. Hosts must provide the attributes listed in the mixin docstring (board, pieces, `_can_hold`, `lookahead`, `lookahead_depth`, `_hold()`). |
| `tetris/bots/dellacherie.py` | `dellacherie_pick(dellvals)` — pure argmax selection. |

`AIState(BotMovesMixin, GameState)` refactored to inherit the mixin —
same methods, same behavior, single implementation.

## Game over

The bot returns to the menu on game over. It never writes to the
leaderboard, human stats, AI training logs, or any `data/` file beyond
the piece provider's own record/replay path.

## Benchmark expectations

El-Tetris clears ~16M lines on average in the literature's benchmark
(vs ~5M for classic Dellacherie in the same harness) — orders of
magnitude beyond the previous bot implementation. Expect the bot to
outperform the current trained DQN; it serves as a score floor and
as an oracle for debugging candidate generation.