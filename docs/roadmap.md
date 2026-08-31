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

## Completed Milestones

- **v1** — Human player with basic Tetris rules
- **v2** — Menu system, settings persistence, keybinds
- **v3** — AI player (DQN), El-Tetris bot (descended from the Dellacherie feature family), MCP integration
- **v3.1** — Full Guideline compliance (22-row board, SRS, hold, lock delay, T-spin, B2B, DAS, 3+ preview)
- **v3.2** — Rule engine centralization (`tetris/game/rules.py`), human/AI alignment
- **v3.3** — El-Tetris adoption, BFS path replay fix (survival bug), AI network widening

---

## Near-Term Priorities

### 1. Documentation Consolidation (In Progress)
- [x] Consolidate 10 docs → 11 domain files (one domain = one file)
- [x] Clean `docs/studies/` — archive implemented studies (6 moved to `archived/`)
- [ ] Write `README.md` (English) + `README-fr.md` (French)
- [ ] Add Documentation Rules to `AGENTS.md`
- [ ] Verify all Mermaid diagrams with `mmdc`
- [ ] Verify documentation duplication < 1% with `jscpd`

### 2. AI Model Retraining
The current `data/ai_model.pt` was trained on buggy features (pre-BFS-fix). Retrain using:
```bash
python -m tetris.verify_training
```
Expected: best_score > 10k, avg_score > 1k, avg_duration > 30s.

### 3. Performance Re-profiling
Re-run cProfile/py-spy benchmarks with:
- Widened network (17→256→128→1)
- El-Tetris evaluation in warm-start
- BFS path recording overhead
- Look-ahead depth 3 (playing mode)

---

## Medium-Term Enhancements

| Area | Idea | Effort |
|------|------|--------|
| **AI — MCTS** | Combine DQN value with Monte Carlo Tree Search for deeper look-ahead | High |
| **AI — Self-Play Tournament** | Population of agents competing, evolutionary selection | High |
| **AI — Imitation Learning** | Pre-train on human replays from `human_stats.json` | Medium |
| **AI — Double DQN** | Already implemented (V-network DQN) | Done |
| **AI — Dueling Network** | Separate value/advantage streams | Medium |
| **Replay System** | Full game replay viewer with scrubbing | Medium |
| **Statistics Dashboard** | Web-based training analytics (TensorBoard already available) | Low |

---

## Long-Term Vision

- **Multi-agent training** — Multiple AI agents learning simultaneously
- **Human-AI co-op** — Human and AI playing together (e.g., AI suggests moves)
- **Custom rule sets** — Configurable guideline subsets for variants
- **Network play** — Multiplayer over LAN/Internet via MCP

---

## Technical Debt

| Item | Location | Priority |
|------|----------|----------|
| Pre-existing test failures | `test_mcp_states.py`, `test_menus.py`, `test_player_cycle_includes_bot` | Low (unrelated to core logic) |
| `zuban` errors in `mcp_server.py` | `tetris/mcp_server.py` | Low (type hints only) |
| French UI strings hardcoded in states | Various `draw()` methods | Low (UI labels intentionally French) |
| No automated visual regression tests | N/A | Medium |

---

## Versioning

This project uses a simple versioning scheme:
- `main` branch — stable
- `v3` branch — current development (contains all fixes)
- Tags: `v1.0`, `v2.0`, `v3.0`, `v3.1`, `v3.2`, `v3.3`

No formal release process — `main` is always deployable.