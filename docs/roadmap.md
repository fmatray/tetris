# Roadmap

## Current Status (as of 2026-08-31)

All core features are **implemented and functional**:

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
| 1 | **Sprint (40 Lines)** | Low | Race to clear 40 lines with a live timer. Reuses `GameStats.lines` + existing `GameState`; adds win condition + timer HUD only. Standard modern mode. |
| 2 | **Blitz (2-minute Ultra)** | Low | Max score in 120 s. Reuses `ScoreEngine`; adds countdown + end condition. Same skeleton as Sprint — build both together. |
| 3 | **VS AI with garbage** | High | Local versus: human vs El-Tetris bot; garbage rows per clear with combo + B2B bonuses (Guideline). New `GarbageQueue` domain class in `tetris/game/`; bot side reuses `ElTetrisState`. |
| 4 | **Replay viewer** | Medium | Scrub recorded human games. `ReplayGenerator` + `replay_pieces.json` already store piece sequences — extend to render board states per frame. |
| 5 | **Per-mode leaderboards** | Low | Separate top-10 tables for Marathon/Sprint/Blitz in `leaderboard.json` (new `mode` field, backward-compatible read). |
| 6 | **Efficiency stats (PPS, finesse)** | Low | Post-game PPS + finesse-error count (Galactoid-style feedback) in `human_stats.json` and stats screen. Pure accounting, no gameplay change. |
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
| 3 | **Vectorized simulation** | Medium | Numpy/bitboard board ops for candidate evaluation (arXiv 2603.26765 reports ~53× faster engines). Cuts wall-clock per episode; same placements, same rewards. |
| 4 | **Dueling network head** | Medium | Split V into value + advantage streams over DT-20 features (Rainbow-family). Architecture flag; current V-network stays default until the dueling model beats baseline in `verify_training`. |
| 5 | **Imitation warm-start** | Medium | Pre-train V-network on placements from `human_stats.json` before RL. Addresses cold-start; gated behind existing `ai_warm_start` setting. |
| 6 | **Visual regression harness** | Medium | Headless `SDL_VIDEODRIVER=dummy` screenshot-diff of menus/HUD states. Catches layout regressions like the FR/ES HUD overflow (fixed d33393f) before they ship. |
| 7 | **CI pipeline** | Low | ✅ **Done (v3.5)** — GitHub Actions `.github/workflows/ci.yml`: `ruff check`, `zuban check`, headless pytest (`ubuntu-latest`, Python 3.14, pip cache) on every push/PR. Mirrors the pre-commit ritual from AGENTS.md. |
| 8 | **Fix pre-existing test debt** | Low | ✅ **Done (v3.4)** — Root-caused and fixed: (1) `MenuState.__init__` no longer mutates global i18n state (persisted language now applied once at app boot in `TetrisApp.__init__`), fixing 6 order-dependent failures in `test_i18n.py`/`test_keybind.py`; (2) stale `_toggle_indices` updated for the Language entry insertion (Debug now index 9), fixing debug event-toggle; (3) `_draw_hole_overhang_markers` call restored in `render_frame` (dropped in i18n refactor). All previously failing tests now pass; `mcp_server.py` zuban clean (was stale entry). |
| 9 | **MCTS look-ahead** | High | Combine DQN value with Monte Carlo Tree Search for deeper-than-3 search at play time. Optional mode; greedy V-eval stays default. |
| 10 | **Self-play tournament** | High | Population of agents competing, evolutionary selection. Reuses `verify_training` harness; new experiment, no change to shipped agent. |

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

---

## Near-Term Priorities

### Documentation Consolidation
- [x] Consolidate 10 docs → 11 domain files (one domain = one file)
- [x] Clean `docs/studies/` — archive implemented studies (6 moved to `archived/`)
- [x] Write `README.md` (English) + `README-fr.md` (French)
- [x] Add Documentation Rules to `AGENTS.md`
- [ ] Verify all Mermaid diagrams with `mmdc`
- [ ] Verify documentation duplication < 1% with `jscpd`

AI model retraining and performance re-profiling are tracked as TOP 10 Technical items #1–2.

---

## Technical Debt

| Item | Location | Priority |
|------|----------|----------|
| French UI strings hardcoded in states | Various `draw()` methods | Low (UI labels intentionally French) |
| No automated visual regression tests | N/A | Medium |

---

## Versioning

This project uses a simple versioning scheme:
- `main` branch — stable
- `v3` branch — current development (contains all fixes)
- Tags: `v1.0`, `v2.0`, `v3.0`, `v3.1`, `v3.2`, `v3.3`

No formal release process — `main` is always deployable.