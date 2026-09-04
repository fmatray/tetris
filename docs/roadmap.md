# Roadmap

## Current Status (as of 2026-09-04)

All core features are **implemented and functional**; the TOP 10 Technical
list is fully closed (items #1–#10 all verified done — see the table below).

| Feature | Status | Details |
|---------|--------|---------|
| Human Player | ✅ Complete | Keyboard input, DAS, pause, ghost piece, hold, configurable keybinds |
| AI Player (DQN) | ✅ Complete | V-network DQN, learning/playing modes, PER, n-step, look-ahead, curriculum |
| El-Tetris Bot | ✅ Complete | El-Tetris evaluation, soft-drop BFS, look-ahead, shared bot library |
| MCP Player | ✅ Complete | FastMCP HTTP server, play/start_game tools, board/rules resources |
| Game Rules (Guideline) | ✅ Complete | All 11 indispensable/recommended rules implemented |
| SRS Wall Kicks | ✅ Complete | Human + AI + Bot use same rule engine |
| T-Spin / B2B / Combo | ✅ Complete | Detection, scoring, chaining |
| Audio (SFX + MIDI Music) | ✅ Complete | Procedural SFX, polyphonic MIDI synthesis, 2 songs |
| Visuals (Renderer + Particles) | ✅ Complete | Board, preview, hold, ghost, particles, leaderboard |
| Settings Persistence | ✅ Complete | `data/settings.json` with all menu prefs |
| Logging / Debug | ✅ Complete | Centralized logging, debug overlay, 5-tier AI observability |

---

## TOP 10 Features

Ranked by player value ÷ effort. Every item is additive — no regression to
existing modes, tests, or behavior. Each ships behind its own menu entry.

| # | Feature | Effort | Why |
|---|---------|--------|-----|
| 1 | ~~**Sprint (40 Lines)**~~ **Done (v3.7)** | Low | Race to clear 40 lines with a live timer. Implemented inside `HumanState` (`game_mode`, `elapsed_ms`); timer HUD at `HUD_POSITIONS["timer"]`. |
| 2 | ~~**Blitz (2-minute Ultra)**~~ **Done (v3.7)** | Low | Max score in 120 s. Shares the Sprint skeleton: countdown HUD + end condition in `HumanState._check_mode_end`. |
| 3 | **VS AI with garbage** | High | Local versus: human vs El-Tetris bot; garbage rows per clear with combo + B2B bonuses (Guideline). New `GarbageQueue` domain class in `tetris/game/`; bot side reuses `ElTetrisState`. |
| 4 | **Replay viewer** | Medium | Scrub recorded human games. `ReplayGenerator` + `replay_pieces.json` already store piece sequences — extend to render board states per frame. |
| 5 | ~~**Per-mode leaderboards**~~ **Done (v3.7)** | Low | Single `leaderboard.json`, per-entry `game_mode` field (legacy entries read as marathon); top-10 per mode, sprint ranked by time. LEFT/RIGHT tabs in `LeaderboardState`. |
| 6 | ~~**Efficiency stats (PPS, finesse)**~~ **Done (v3.7)** | Low | Post-game PPS + finesse-fault count in `human_stats.json` (keyword-only fields, legacy-safe) and summary lines on the stats screen. |
| 7 | **Daily challenge** | Medium | Seeded run (date-derived seed) with one leaderboard entry per day. Seed machinery already exists (`SeedEntryState`). |
| 8 | **Human-AI co-op hints** | Medium | Optional overlay showing the DQN agent's best placement for the human's current piece. Read-only; uses existing candidate generation. |
| 9 | **Custom rule sets** | Medium | Configurable guideline subsets (starting garbage rows, inverted colors, gravity curves) via a rules menu entry persisted in `settings.json`. |
| 10 | **Network play via MCP** | High | Two-instance LAN play through the existing MCP HTTP server; garbage attacks reuse item 3's `GarbageQueue`. |

---

## TOP 10 Technical

Ranked by engineering value ÷ effort. Every item is additive or parallel —
current behavior stays the default until a replacement proves out.

| # | Improvement | Effort | Why |
|---|-------------|--------|-----|
| 1 | **Retrain AI model** | Low | ✅ **Done (v3.5)** — 164-episode background run from the existing checkpoint via `python -m tetris.verify_training`. New-window results: best_score 1.15B, avg_score 35.9M (criteria: best > 10k, avg > 1k). Info: avg duration 349 s/episode, max loss 86.8, epsilon 0.248 → 0.211. |
| 2 | **Performance re-profiling** | Low | ✅ **Done (v3.5)** — Round 4 baseline added to `docs/performance.md` (§Round 4 Baseline): 500-frame cProfile on the post-redesign architecture — 17.4 s (~28 FPS under profiler, ~69 FPS clean), 15.1 M calls (−38% vs Round 3). Look-ahead `best_next_placement` is the dominant cost (~60% of `update` cumulative time; ~2.2× FPS cost at depth 1); TensorBoard writer measured as noise. py-spy requires root on macOS, so cProfile + A/B runs used instead. |
| 3 | **Vectorized simulation** | Medium | ✅ **Done (v3.6)** — `best_next_placements_batch` in `tetris/ai/candidates.py`: cross-candidate batched look-ahead, one vectorized pass per depth level replaces the per-candidate scalar loop. Bit-identical outputs (tie-break preserved); 2.1× on the look-ahead stage (80.8 ms → 38.1 ms, N=200). Vectorized line-clear (`clear_lines_batch`) removes the Python row loop in `place_and_clear_batch`. Equivalence tests in `tests/test_rules_batch.py`. Details: `docs/performance.md` (§Round 5). |
| 4 | **Dueling network head** | Medium | ✅ **Done (v3.6)** — `DQNetwork(state_size, dueling)`: optional value + advantage streams over the shared 17→256→128 trunk, summed as `V(s) + A(s)` with no batch-mean centering (single-sample candidate evaluation stays batch-independent). Plumbed end-to-end: `AIConfig.dueling`, `ai_dueling` settings key, Training menu toggle (default OFF), checkpoint `dueling` flag with architecture-mismatch guard on load. Non-dueling layout keeps the legacy `net.0/2/4` state-dict keys, so existing checkpoints load unchanged. Tests: `tests/test_dueling.py` (10). Current V-network stays default until the dueling model beats baseline in `verify_training`. |
| 5 | **Imitation warm-start** | Medium | ✅ **Done (v3.6)** — Human placements recorded per locked piece to `data/human_placements.jsonl` (`PlacementsLog`, `tetris/game/imitation.py`; attached by `HumanState` only). With `ai_imitation` ON (new settings key, Training menu toggle, learning mode only), `imitation_pretrain()` (`tetris/ai/imitation.py`) runs at AI startup: replays each recorded game, re-enumerates candidates with the live `get_candidate_states` enumerator, and applies a softmax ranking loss so `V(human placement)` outranks alternatives. Missing log / un-replayable moves are skipped; failures never crash startup. Tests: `tests/test_imitation.py` (11). |
| 6 | **Visual regression harness** | Medium | ✅ **Done (v3.6)** — `tests/layout_harness.py`: invariant-based layout assertions instead of pixel goldens (font rasterization is cross-platform flaky). `RecordingFont` (Font subclass — the C type can't be monkeypatched) logs render metrics; `RecordingScreen` (Surface subclass) records each text blit's position/size; `assert_layout_in_bounds` + `assert_no_text_overlap` (same-position HUD re-renders tolerated). `tests/test_visual_regression.py` drives MenuState/HumanState/AIState (learning + playing HUD) through `draw()` in EN/FR/ES/SL, plus meta-tests proving the harness flags planted violations. Details: `docs/development.md` (§Layout Regression Harness). |
| 7 | **CI pipeline** | Low | ✅ **Done (v3.5)** — GitHub Actions `.github/workflows/ci.yml`: `ruff check`, `zuban check`, headless pytest (`ubuntu-latest`, Python 3.14, pip cache) on every push/PR. Mirrors the pre-commit ritual from AGENTS.md. |
| 8 | **Fix pre-existing test debt** | Low | ✅ **Done (v3.4)** — Root-caused and fixed: (1) `MenuState.__init__` no longer mutates global i18n state (persisted language now applied once at app boot in `TetrisApp.__init__`), fixing 6 order-dependent failures in `test_i18n.py`/`test_keybind.py`; (2) stale `_toggle_indices` updated for the Language entry insertion (Debug now index 9), fixing debug event-toggle; (3) `_draw_hole_overhang_markers` call restored in `render_frame` (dropped in i18n refactor). All previously failing tests now pass; `mcp_server.py` zuban clean (was stale entry). |
| 9 | **MCTS look-ahead** | High | ✅ **Done (v3.6)** — `tetris/ai/mcts.py`: AlphaZero-style PUCT tree search guided by the V-network (no rollouts; leaf = one hard-drop level deeper, evaluated in batch). Root priors = softmax over El-Tetris pick values; deeper piece types sampled from a per-episode `rng` for reproducibility. Nodes are plain dicts (class diagram untouched). Menu: **MCTS** toggle + **MCTS iterations** (20–2000, default 200) in the Training menu; `ai_mcts`/`ai_mcts_iterations` settings keys; FR/ES/SL labels. When MCTS is on, the greedy look-ahead chain is disabled (no double search). Tests: `tests/test_mcts.py` (5). |
| 10 | **Self-play tournament** | High | ✅ **Done (v3.6)** — `tetris/tournament.py`: evolutionary weight search from the shipped checkpoint. Gaussian mutants + uniform crossover, top-half survivor selection, headless playing-mode episodes as fitness (score to first game-over, capped at `piece_cap` pieces, default 400). Deterministic: same seed + weights → same score (board, pieces, and global RNG all seeded from the episode seed). Path-isolated: playing logs redirect to `data/tournament/`; never writes `data/ai_model.pt` or training logs. CLI: `python -m tetris.tournament --generations 3 --episodes 2 --population 8 --sigma 0.02`. Report: `data/tournament/tournament_report.json`; best weights: `tournament_best.pt`. Tests: `tests/test_tournament.py` (9). |

---

## Completed Milestones

- **v1** — Human player with basic Tetris rules
- **v2** — Menu system, settings persistence, keybinds
- **v3** — AI player (DQN), El-Tetris bot (descended from the Dellacherie feature family), MCP integration
- **v3.1** — Full Guideline compliance (22-row board, SRS, hold, lock delay, T-spin, B2B, DAS, 3+ preview)
- **v3.2** — Rule engine centralization (`tetris/game/rules.py`), human/AI alignment
- **v3.3** — El-Tetris adoption, BFS path replay fix (survival bug), AI network widening
- **v3.4** — Test debt repayment: i18n global-state leak fixed (language applied at app boot), debug toggle index repaired, hole/overhang markers render restored; ARE entry delay with IRS/IHS
- **v3.5** — CI pipeline (GitHub Actions: ruff + zuban + headless pytest), Round 4 performance re-profile, AI model retrained (164 background episodes, criteria passed), zuban baseline fully clean
- **v3.6** — Vectorized look-ahead simulation (`best_next_placements_batch`), dueling network head, imitation warm-start, visual layout regression harness, MCTS look-ahead (PUCT + V-network), self-play tournament (CLI + in-game loops), `q` quit-after-game-over key (AI/Bot/MCP)
- **v3.7** — Sprint (40 lines) and Blitz (2-minute) human modes with timer HUD, per-game-mode leaderboards (LEFT/RIGHT tabs, sprint ranked by time), efficiency stats (PPS + approximate finesse faults) on the stats screen

---

## Near-Term Priorities

### Documentation Consolidation
- [x] Consolidate 10 docs → 11 domain files (one domain = one file)
- [x] Clean `docs/studies/` — archive implemented studies (6 moved to `archived/`)
- [x] Write `README.md` (English) + `README-fr.md` (French)
- [x] Add Documentation Rules to `AGENTS.md`
- [x] Verify all Mermaid diagrams with `mmdc` (all `docs/*.md` + READMEs pass, 2026-09-04)
- [x] Verify documentation duplication < 1% with `jscpd` (0.33% across `docs/` + READMEs, 2026-09-04)

AI model retraining and performance re-profiling are tracked as TOP 10 Technical items #1–2.

---

## Technical Debt

| Item | Location | Priority |
|------|----------|----------|
| Legacy French settings values (`"Humain"`, `"Normal"`, `"Replay"`) persisted in `settings.json` and used as `player_type` identifiers | `tetris/states/menu.py`, `tetris/states/game.py` | Low (display-mapped via `FR_PLAYER_KEY` + `tr()`; format change would break saved settings) |

---

## Versioning

This project uses a simple versioning scheme:
- `main` branch — stable, all development lands here
- `v3` branch — alias of `main` (kept for history; not separately maintained)
- `old-main`, `AIv2` — historical branches, kept for reference
- Milestones (v1–v3.7) are documented above; no git tags are maintained

No formal release process — `main` is always deployable.