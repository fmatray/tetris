# El-Tetris Bot

A deterministic rule-based player. It evaluates every reachable placement
of the current piece with the El-Tetris heuristic and plays the best
one. No learning, no model, no persistence — a watch and benchmark player.

El-Tetris (Yiyuan Lee, 2009) is an improvement on Pierre Dellacherie's
classic algorithm; this bot descends from that feature family and uses
the full published El-Tetris evaluation.

## Player type

`player = "Bot"` in `data/settings.json` (menu: Joueur → Bot).
Its sub-menu ("Bot El-Tetris") has two settings:

| Option | Values | Meaning |
|---|---|---|
| Level | Noob / Good / Advanced / Champion / God | The skill level of the bot. It controls how often the bot makes a bad move, how long it waits between decisions, and how many preview pieces it plans with. See [Player levels](#player-levels). |
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
3. **Reserve a column** — `BotMovesMixin._get_candidate_states` applies a
   placement-level penalty: any non-I placement whose filled cells touch
   the committed column gets `RESERVE_COLUMN_PENALTY = -60` added to its
   pick value. I-pieces are exempt. This keeps the column open for
   I-pieces so the bot scores tetrises and triples. The committed column
   is chosen from board state (`ElTetrisState._update_reserved_column`):
   among clean columns (no filled cell), the one where a vertical I would
   clear the most lines right now, highest index on ties (a flat empty
   board therefore picks column 9). The bot commits to that column and
   re-chooses only when it becomes dirty; if no column is clean the
   reservation turns off until a line clear opens one. Board-level
   evaluation terms cannot do this: within one decision all candidates
   share the same pre-clear board, so board features are constant across
   candidates and never flip the argmax. The reservation is a
   placement-level rule on the bot-only path — it never runs on AI
   training (see [ai.md](ai.md#warm-start-priors)).
4. **Pick** — `level_select(values, misstep, temperature, rng)` in
   `tetris/bots/moves.py`. At level God, `misstep` is 0 and the pick is
   `argmax` (ties resolve to the lowest index), so God is the exact
   previous behavior. At lower levels, the values are z-normalized and
   sampled through a softmax with probability `misstep`, so the bot
   sometimes picks a weaker placement.
5. **Execute** — the placement's recorded BFS move sequence is replayed
   atomically (`BotMovesMixin._execute_move_sequence`), so the piece
   lands exactly where the evaluation saw it. No execution mismatch.

With look-ahead enabled, `get_candidate_states` simulates each upcoming
preview piece with the same El-Tetris evaluation and keeps the best
continuation (argmax) per candidate — the same machinery the DQN's
look-ahead uses. The level caps the look-ahead depth: the effective
depth is `min(configured_depth, level_cap)`, and a cap of 0 disables
look-ahead entirely.

The bot plays at `AI_ACTION_DELAY_MS` (80ms) between decisions so a
human can watch; lower levels multiply this delay (up to 4x at Noob).
Lock delay runs normally (500ms).

The bot is subject to the ARE entry delay: its selection is deferred during ARE, and the `GameState` base class handles the delay. See [game_rules.md §12](game_rules.md#12-are-appearance-delay-irs-ihs).

## Player levels

The bot and the AI in playing mode share the same five skill levels.
The level profile has three numbers:

| Profile value | Meaning |
|---|---|
| `misstep` | The probability that the bot samples a placement through softmax instead of taking the best one. |
| `temperature` | The softmax temperature. A higher temperature makes the sampled placement more random. |
| `delay_mult` | The multiplier on the decision delay. A higher multiplier makes the bot play slower. |
| `lookahead_cap` | The maximum look-ahead depth. A cap of 0 disables look-ahead. |

| Level | `misstep` | `temperature` | `delay_mult` | `lookahead_cap` |
|---|---|---|---|---|
| Noob | 0.60 | 1.5 | 4.0 | 0 |
| Good | 0.30 | 1.0 | 2.0 | 1 |
| Advanced | 0.15 | 0.6 | 1.5 | 2 |
| Champion | 0.05 | 0.4 | 1.0 | 3 |
| God | 0.0 | 1.0 | 1.0 | 3 |

God is the default. Its `misstep` is 0, its delay multiplier is 1, and
its look-ahead cap is 3, so God plays exactly like the bot before
levels existed. The profiles live in `PLAYER_LEVEL_PROFILES` in
`tetris/settings.py`.

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

The column reservation (step 3 above) is what lets the bot score tetrises
and triples. Measured on 300-piece runs (seeds 42/7/123, God, look-ahead
depth 2): without reservation the bot scores 0 tetrises and ~0 triples;
with it, 1–4 tetrises and 6–13 triples per run, score +19–23%, and no
survival regression (both variants reach the 5000-piece frame cap on all
seeds). The penalty must stay in `[-80, -40]`: `-100` tops out early
(68 pieces) and `-80` already degrades one seed.

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