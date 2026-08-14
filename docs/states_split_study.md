# tetris/states/ Sub-Package Split Study

**Date:** 2026-08-14
**Scope:** Evaluate splitting the flat `tetris/states/` package (16 modules, 2 666 lines) into sub-packages grouped by concern (menu, game, ai, human, stats).

---

## 1. Executive Summary

**Recommendation: Do not split.**

The current flat package has 16 files averaging 167 lines. Every file is already a cohesive unit with a single class and a clear docstring. Sub-packaging would add directory nesting and import-path churn without addressing any real coupling problem — the modules are already decoupled. The actual complexity lives in two files (`ai.py` 651 lines, `game.py` 380 lines), and neither is reducible by moving them into a subdirectory.

Three factors make this net-negative:

1. **No coupling to reduce.** Module-level imports between states are minimal: `base.py` is imported by all, `menu_base.py` by 6 menus, `game.py` by 2 files. All cross-state transitions use lazy imports inside methods (7 lazy imports total). No state module imports another at top level except `ai.py → game.py` and `game_over.py → game.py` (both genuine inheritance/usage, not cycles).

2. **Import path churn across the codebase.** 22 `from tetris.states.X import Y` statements across 14 files would all need updating. The `tests/test_class_diagram.py` test AST-parses all of `tetris/` so it would survive, but `tests/test_curriculum.py`, `tests/test_game_state.py`, `tetris/app.py`, and `tetris/verify_training.py` all import specific state classes. Every lazy import inside `menu.py`, `human_menu.py`, `ai_menu.py`, `game.py`, `game_over.py`, `leaderboard.py` would need path updates.

3. **The grouping is ambiguous.** 4 of 16 files don't fit cleanly into any group. `GameOverState` is gameplay-adjacent (receives a `GameState`), but also menu-adjacent (returns to `MenuState`). `KeybindState` is human-player config but not a `MenuBase` subclass. `LeaderboardState` is neither gameplay nor menu nor AI. `HyperparamMenuState` is AI config but a `MenuBase` subclass. Any partition forces arbitrary assignments that mislead readers.

The one genuine win — locating the menu hierarchy in one place — is already achieved by the `menu_base.py` + 6 subclasses naming convention. `grep "MenuBase" tetris/states/` returns the full hierarchy in one command.

---

## 2. Current Package Inventory

### 2.1 File Sizes

| File | Lines | Class | Role |
|------|-------|-------|------|
| `base.py` | 41 | `State` | Base contract (handle_event/update/draw) |
| `menu_base.py` | 198 | `MenuBase` | Template method for menu navigation |
| `menu.py` | 235 | `MenuState` | Root menu, settings owner, navigation hub |
| `ai.py` | 651 | `AIState` | AI gameplay (inherits GameState) |
| `game.py` | 380 | `GameState` | Human gameplay |
| `hyperparam_menu.py` | 256 | `HyperparamMenuState` | DQN hyperparameter table |
| `keybind.py` | 207 | `KeybindState` | Interactive key rebinding |
| `human_stats.py` | 165 | `HumanStatsState` | Human stats aggregation table |
| `stats.py` | 120 | `StatsState` | AI stats + matplotlib graph |
| `game_over.py` | 108 | `GameOverState` | 3-phase game-over flow |
| `ai_menu.py` | 105 | `AIMenuState` | AI sub-menu |
| `human_menu.py` | 60 | `HumanMenuState` | Human sub-menu |
| `audio_menu.py` | 57 | `AudioMenuState` | Audio sub-menu |
| `game_rules_menu.py` | 51 | `GameRulesMenuState` | Game rules sub-menu |
| `leaderboard.py` | 32 | `LeaderboardState` | Top-10 display |
| `__init__.py` | 0 | — | Empty (docstring only) |
| **Total** | **2 666** | **16 classes** | |

### 2.2 Class Hierarchy

```
State (base.py)
├── MenuBase (menu_base.py)
│   ├── MenuState              (menu.py — root, settings owner)
│   ├── HumanMenuState         (human_menu.py)
│   ├── AIMenuState            (ai_menu.py)
│   ├── AudioMenuState         (audio_menu.py)
│   ├── GameRulesMenuState     (game_rules_menu.py)
│   └── HyperparamMenuState    (hyperparam_menu.py)
├── GameState                  (game.py — human gameplay)
│   └── AIState                (ai.py — AI gameplay)
├── GameOverState              (game_over.py)
├── KeybindState               (keybind.py)
├── StatsState                 (stats.py)
├── HumanStatsState            (human_stats.py)
└── LeaderboardState           (leaderboard.py)
```

### 2.3 Import Dependency Graph

**Top-level (module-load) imports between state files:**

```
base.py           ← imported by all 15 other state files
menu_base.py      ← imported by 6 menu subclasses (menu, human_menu, ai_menu,
                     audio_menu, game_rules_menu, hyperparam_menu)
game.py           ← imported by ai.py (AIState(GameState))
                   ← imported by game_over.py (GameOverState uses GameState)
```

**That's it.** Only 3 cross-state top-level import edges. No cycles exist — the lazy-import pattern handles all back-references.

**Lazy imports (inside methods, for transitions):**

| Source file | Lazy import target | Location |
|-------------|-------------------|----------|
| `menu.py` | `audio_menu.py` | `MenuState._on_select()` |
| `menu.py` | `game_rules_menu.py` | `MenuState._on_select()` |
| `menu.py` | `human_menu.py` | `MenuState._on_select()` |
| `menu.py` | `ai_menu.py` | `MenuState._on_select()` |
| `menu.py` | `game.py` | `MenuState._on_select()` |
| `menu.py` | `ai.py` | `MenuState._build_ai_state()` |
| `menu.py` | `leaderboard.py` | `MenuState._on_select()` |
| `ai_menu.py` | `hyperparam_menu.py` | `AIMenuState._on_select()` |
| `ai_menu.py` | `stats.py` | `AIMenuState._on_select()` |
| `human_menu.py` | `keybind.py` | `HumanMenuState._on_select()` |
| `human_menu.py` | `human_stats.py` | `HumanMenuState._on_select()` |
| `game.py` | `game_over.py` | `GameState._do_game_over()` |
| `game.py` | `menu.py` | `GameState._return_to_menu()` |
| `game_over.py` | `menu.py` | `GameOverState._handle_name_event()` |
| `leaderboard.py` | `menu.py` | `LeaderboardState.handle_event()` |

All 15 lazy imports are transition-creation: `return SomeState(screen, font, audio, ...)`. They exist to avoid import cycles (documented in `base.py` docstring). Sub-packaging does not eliminate any of these — the cycles are inherent to the state graph topology.

### 2.4 External Consumers (outside `tetris/states/`)

| File | Import | Usage |
|------|--------|-------|
| `tetris/app.py` | `from tetris.states.base import State` | Type annotation |
| `tetris/app.py` | `from tetris.states.menu import MenuState` | Initial state |
| `tetris/verify_training.py` | `from tetris.states.ai import AIState` | Training validation |
| `tetris/visuals/renderer.py` | `from tetris.states.game import GameState` (TYPE_CHECKING) | Type annotation |
| `tests/test_curriculum.py` | `from tetris.states.ai import AIState` | Test fixture |
| `tests/test_curriculum.py` | `from tetris.states.menu import MenuState` | Test fixture |
| `tests/test_game_state.py` | `from tetris.states.game import GameState` | Test fixture |
| `tests/test_class_diagram.py` | (AST-parses `tetris/` recursively) | Diagram sync test |

**8 import statements** across 6 external files. Sub-packaging would require updating every one.

### 2.5 Transition Map (25 edges)

```
MenuState ──select──→ AudioMenuState ──back──→ MenuState (stored ref)
MenuState ──select──→ GameRulesMenuState ──back──→ MenuState (stored ref)
MenuState ──select──→ HumanMenuState ──back──→ MenuState (stored ref)
MenuState ──select──→ AIMenuState ──back──→ MenuState (stored ref)
MenuState ──select──→ GameState ──ESC──→ MenuState (stored ref or new)
MenuState ──select──→ AIState ──ESC──→ MenuState (stored ref or new)
MenuState ──select──→ LeaderboardState ──any key──→ MenuState (stored ref or new)
MenuState ──ESC──→ Quit (sys.exit)

HumanMenuState ──select──→ KeybindState ──ESC──→ HumanMenuState (stored ref)
HumanMenuState ──select──→ HumanStatsState ──any key──→ HumanMenuState (stored ref)

AIMenuState ──select──→ HyperparamMenuState ──back──→ AIMenuState (stored ref)
AIMenuState ──select──→ StatsState ──any key──→ AIMenuState (stored ref)

GameState ──game over──→ GameOverState ──ESC/name──→ MenuState (new or stored ref)
```

The transition graph is the real coupling — it spans all groups. Splitting files into directories does not reduce edge count or change the graph.

---

## 3. Candidate Architectures

### 3.1 Option A: Five Sub-Packages (Domain Grouping)

```
tetris/states/
├── __init__.py
├── base.py
├── menu/
│   ├── __init__.py
│   ├── menu_base.py
│   ├── menu.py            (MenuState)
│   ├── audio_menu.py
│   ├── game_rules_menu.py
│   ├── human_menu.py
│   ├── ai_menu.py
│   └── hyperparam_menu.py
├── game/
│   ├── __init__.py
│   ├── game.py            (GameState)
│   └── game_over.py       (GameOverState)
├── ai/
│   ├── __init__.py
│   └── ai.py             (AIState)
└── stats/
    ├── __init__.py
    ├── stats.py           (StatsState)
    ├── human_stats.py     (HumanStatsState)
    └── leaderboard.py     (LeaderboardState)
```

**Plus**: `keybind.py` stays at top level (human config, not menu, not game).

**Import paths change:**
```python
# Before                              # After
from tetris.states.menu import MenuState          → from tetris.states.menu.menu import MenuState
from tetris.states.ai import AIState              → from tetris.states.ai.ai import AIState
from tetris.states.game import GameState          → from tetris.states.game.game import GameState
from tetris.states.hyperparam_menu import ...     → from tetris.states.menu.hyperparam_menu import ...
from tetris.states.stats import StatsState        → from tetris.states.stats.stats import StatsState
from tetris.states.leaderboard import ...         → from tetris.states.stats.leaderboard import ...
```

**Pros:**
- Menu hierarchy co-located (7 files in `menu/`).
- `game/` groups gameplay + game-over.
- `ai/` isolates the largest file.

**Cons:**
- `menu/menu.py`, `game/game.py`, `ai/ai.py`, `stats/stats.py` — stuttering names (package/file redundancy).
- `keybind.py` is orphaned at root (not in any group).
- `LeaderboardState` in `stats/` is misleading — it's a display state, not a statistics state.
- 5 new `__init__.py` files.
- 22 import paths change across 14 files.
- `ai/` package has 1 file — a package with a single module is a directory that adds navigation cost for zero grouping benefit.
- Ambiguity: `GameOverState` extends `State` but receives a `GameState` and returns a `MenuState`. Placing it in `game/` couples `game/` → `menu/` (for the transition). Placing it elsewhere loses the gameplay adjacency.

### 3.2 Option B: Three Sub-Packages (Coarser Grouping)

```
tetris/states/
├── __init__.py
├── base.py
├── menu/
│   ├── __init__.py
│   ├── menu_base.py
│   ├── menu.py
│   ├── audio_menu.py
│   ├── game_rules_menu.py
│   ├── human_menu.py
│   ├── ai_menu.py
│   └── hyperparam_menu.py
├── gameplay/
│   ├── __init__.py
│   ├── game.py
│   ├── ai.py
│   └── game_over.py
└── views/
    ├── __init__.py
    ├── keybind.py
    ├── stats.py
    ├── human_stats.py
    └── leaderboard.py
```

**Pros:**
- 3 packages, each with 3–7 files — reasonable sizes.
- `gameplay/` groups the gameplay loop + AI + game-over (genuine cohesion: all use `GameState`).
- `views/` groups the read-only display states (keybind, stats, leaderboard) — all "press any key to return" states.
- No stuttering names (no `menu/menu.py`).

**Cons:**
- `keybind.py` in `views/` is a stretch — it has interactive rebinding, not just display.
- `game_over.py` in `gameplay/` still couples to `menu/` for the return transition.
- 3 new `__init__.py` files.
- 22 import paths change.
- `menu_base.py` in `menu/` means `menu/` has 7 files — the same count as the current flat package. The grouping doesn't reduce the menu file count, just nests it.
- `views/` is a catch-all that mixes different concerns (keybind config vs. stats display vs. leaderboard display).

### 3.3 Option C: Two Sub-Packages (Menu vs. Everything Else)

```
tetris/states/
├── __init__.py
├── base.py
├── menu/
│   ├── __init__.py
│   ├── menu_base.py
│   ├── menu.py
│   ├── audio_menu.py
│   ├── game_rules_menu.py
│   ├── human_menu.py
│   ├── ai_menu.py
│   └── hyperparam_menu.py
├── game.py
├── ai.py
├── game_over.py
├── keybind.py
├── stats.py
├── human_stats.py
└── leaderboard.py
```

**Pros:**
- Only the menu hierarchy moves (7 files → `menu/`). This is the one group with genuine internal cohesion (all `MenuBase` subclasses).
- 9 files stay at root — no stuttering, no catch-all packages.
- Smallest diff: only menu-related import paths change (~12 of 22 imports).
- `menu/__init__.py` could re-export all menu states, so `from tetris.states.menu import MenuState` still works (backward-compatible).

**Cons:**
- Asymmetric — why does `menu/` get a sub-package but `gameplay` states don't?
- The root still has 9 files — only marginally flatter than the current 16.
- `menu/__init__.py` re-exports would add a new abstraction layer (the `__init__.py` as facade). If it doesn't re-export, all 12 menu import paths change.

### 3.4 Option D: Do Nothing (Status Quo)

**Pros:**
- 0 files moved, 0 imports changed, 0 tests broken.
- Flat package with 16 files is the norm for Python packages of this size. Django's `views/`, Flask's `views/`, many game frameworks — all have flat state/view directories with 10–20 files.
- Naming convention already provides grouping: `*_menu.py` = menu states, `game*.py` = gameplay, `ai*.py` = AI, `*_stats.py` = stats. `ls tetris/states/*.py` already shows the groups sorted.
- The `__init__.py` docstring documents the flat structure: "concrete states are imported lazily inside methods to avoid import cycles while keeping the package API flat."

**Cons:**
- 16 files in one directory is at the upper end of comfortable for some developers.
- No structural enforcement of grouping (naming convention only).

---

## 4. Compatibility Analysis

### 4.1 Import Cycle Risk

**Current**: No cycles. The lazy-import pattern (15 lazy imports inside methods) breaks all back-references. Top-level imports form a clean DAG: `base.py ← menu_base.py ← {6 menus}`, `base.py ← game.py ← ai.py`, `base.py ← {game_over, keybind, stats, human_stats, leaderboard}.py`.

**With sub-packages**: The same lazy imports would use longer paths (`from tetris.states.menu.menu import MenuState` instead of `from tetris.states.menu import MenuState`). No cycles are introduced or resolved — the topology is identical. Sub-packaging is orthogonal to the cycle-avoidance strategy.

**However**: If `__init__.py` files in sub-packages re-export their classes (to provide clean import paths), those `__init__.py` files import their submodules at load time. If `menu/__init__.py` does `from tetris.states.menu.menu import MenuState`, and `menu.py` does a lazy `from tetris.states.menu.audio_menu import AudioMenuState` inside `_on_select()`, there's no cycle. But if any submodule of `menu/` does a top-level `from tetris.states.menu import MenuState` (to avoid the longer path), that creates a cycle: `menu/__init__.py → menu.py → menu/__init__.py`. This is a new failure mode that doesn't exist in the flat package.

### 4.2 `test_class_diagram.py` Impact

The test AST-parses all `*.py` files under `tetris/` recursively (`SOURCE_ROOT.rglob("*.py")`). Sub-packages would still be parsed. The test checks class names, methods, attributes, inheritance edges — not file paths. **No test changes needed.**

### 4.3 External Import Impact

| External file | Current import | After split (Option A) |
|---------------|---------------|----------------------|
| `app.py` | `from tetris.states.menu import MenuState` | `from tetris.states.menu.menu import MenuState` |
| `app.py` | `from tetris.states.base import State` | `from tetris.states.base import State` (unchanged) |
| `verify_training.py` | `from tetris.states.ai import AIState` | `from tetris.states.ai.ai import AIState` |
| `renderer.py` | `from tetris.states.game import GameState` | `from tetris.states.game.game import GameState` |
| `test_curriculum.py` | `from tetris.states.ai import AIState` | `from tetris.states.ai.ai import AIState` |
| `test_curriculum.py` | `from tetris.states.menu import MenuState` | `from tetris.states.menu.menu import MenuState` |
| `test_game_state.py` | `from tetris.states.game import GameState` | `from tetris.states.game.game import GameState` |

With Option C (menu-only) + `menu/__init__.py` re-exports, only `verify_training.py`, `test_curriculum.py`, and `test_game_state.py` would need changes if they import non-menu states. Menu-state imports would remain backward-compatible via the `__init__.py` facade.

### 4.4 `settings.py` Constraint

`settings.py` must remain pure constants. Sub-packaging doesn't touch `settings.py`. **No impact.**

### 4.5 `docs/class_diagram.md` Impact

The class diagram documents classes, methods, attributes, and relationships — not file paths. Sub-packaging changes where classes live but not their API surface. The diagram itself wouldn't change, but the `test_class_diagram.py` test would need to pass (it does — see 4.2). **No diagram changes needed.**

### 4.6 Lazy Import Verbosity

Lazy imports become longer:

```python
# Before:
from tetris.states.audio_menu import AudioMenuState

# After (Option A):
from tetris.states.menu.audio_menu import AudioMenuState
```

15 lazy imports get longer. This is cosmetic but adds noise to the transition methods, which are already the densest code in the package.

---

## 5. Evaluation Matrix

| Criterion | Option A (5 pkgs) | Option B (3 pkgs) | Option C (menu only) | Option D (do nothing) |
|-----------|-------------------|-------------------|----------------------|----------------------|
| Files moved | 15 | 16 | 7 | 0 |
| New `__init__.py` | 5 | 3 | 1 | 0 |
| Import paths changed | 22 | 22 | 12 | 0 |
| External files touched | 6 | 6 | 3 | 0 |
| New cycle risk | Yes (if re-exports) | Yes (if re-exports) | Low (menu-only) | None |
| Grouping clarity | Medium (4 orphans) | Medium (1 stretch) | Good (menus only) | Naming convention |
| Stuttering names | Yes (4) | No | No | N/A |
| Navigation cost | High (5 dirs) | Medium (3 dirs) | Low (1 dir) | None |
| Diff size | Large | Large | Medium | Zero |
| Addresses real coupling? | No | No | Partially | N/A |

---

## 6. Migration Plan (If Adopted — Option C Only)

Option C is the only option with a reasonable cost/benefit ratio. If the team decides to proceed, this is the plan.

### Phase 1: Create `menu/` Sub-Package (0.5 day)

1. Create `tetris/states/menu/` directory.
2. Move 7 files: `menu_base.py`, `menu.py`, `audio_menu.py`, `game_rules_menu.py`, `human_menu.py`, `ai_menu.py`, `hyperparam_menu.py`.
3. Create `menu/__init__.py` with re-exports:
   ```python
   from tetris.states.menu.menu_base import MenuBase
   from tetris.states.menu.menu import MenuState
   from tetris.states.menu.audio_menu import AudioMenuState
   from tetris.states.menu.game_rules_menu import GameRulesMenuState
   from tetris.states.menu.human_menu import HumanMenuState
   from tetris.states.menu.ai_menu import AIMenuState
   from tetris.states.menu.hyperparam_menu import HyperparamMenuState
   ```
4. Update internal imports within moved files:
   - `menu.py`: `from tetris.states.menu_base import MenuBase` → `from tetris.states.menu.menu_base import MenuBase` (or relative: `from .menu_base import MenuBase`)
   - All 6 subclasses: same pattern.
5. Update lazy imports in `menu.py` (6 lazy imports → `from tetris.states.menu.X import Y`).
6. **Gate**: Run `ruff check .` and `pytest tests/ -q`. If any import fails, fix before proceeding.

### Phase 2: Update External Consumers (0.5 day)

1. `tetris/app.py`: `from tetris.states.menu import MenuState` — **unchanged** (re-export handles it).
2. `tests/test_curriculum.py` line 172: `from tetris.states.menu import MenuState` — **unchanged**.
3. `tetris/states/game.py` line 261: `from tetris.states.menu import MenuState` — **unchanged**.
4. `tetris/states/game_over.py` line 64: `from tetris.states.menu import MenuState` — **unchanged**.
5. `tetris/states/leaderboard.py` line 27: `from tetris.states.menu import MenuState` — **unchanged**.
6. Update `docs/class_diagram.md` if it references file paths (it doesn't — class-based only).
7. **Gate**: Full test suite passes, ruff clean.

### Phase 3: Verify and Document (0.25 day)

1. Run full test suite: `SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy python -m pytest tests/ -q` (144 tests).
2. Run ruff: `ruff check .` (expect 2 pre-existing issues only).
3. Run headless smoke test.
4. Update `AGENTS.md` state machine tree to reflect new structure.
5. Commit and push.

**Total estimated effort: 1.25 days.**

---

## 7. Alternatives (Lighter Touch)

### Alternative A: Keep Flat, Add `# region` Comments

Add `# region: Menu States` / `# endregion` comments to group files in IDEs that support folding. Zero structural change, zero import changes. Visual grouping in editors only.

### Alternative B: Keep Flat, Document the Grouping in `__init__.py`

Expand the `__init__.py` docstring to enumerate the groups:

```python
"""FSM states for the Tetris game loop.

Groups:
  - Menu states: menu_base, menu, audio_menu, game_rules_menu,
    human_menu, ai_menu, hyperparam_menu
  - Gameplay: game, ai, game_over
  - Display: keybind, stats, human_stats, leaderboard
"""
```

Zero structural change. `help(tetris.states)` shows the grouping.

### Alternative C: Keep Flat, Extract `ai.py` Internally

The one file that's genuinely too large is `ai.py` (651 lines). Instead of sub-packaging, split `AIState` into:
- `ai.py` — `AIState` class (gameplay + AI decision logic).
- Move candidate generation helpers into `tetris/ai/` (they're already partially there in `rewards.py`).

This addresses the real size problem without touching the package structure.

---

## 8. Conclusion

| Question | Answer |
|----------|--------|
| Is the package too large to navigate? | No — 16 files, `ls` shows them sorted by group via naming convention. |
| Are there import cycles to break? | No — the lazy-import pattern already handles all 15 back-references. |
| Are there ambiguous couplings? | No — only 3 top-level cross-state imports, all genuine (inheritance/usage). |
| Would sub-packages reduce any real complexity? | No — the complexity is in `ai.py` (651 lines) and the 25-edge transition graph, neither of which is affected by directory structure. |
| Would sub-packages introduce new risks? | Yes — new cycle risk if `__init__.py` re-exports, import path verbosity, stuttering names. |
| Is there a cheaper way to achieve grouping? | Yes — naming convention already provides it; `__init__.py` docstring can document it. |

**Final recommendation**: Do not split. The flat package is proportionate to the problem. The naming convention (`*_menu.py`, `game*.py`, `ai*.py`, `*_stats.py`) already provides the grouping that sub-packages would enforce. If `ai.py`'s size is a concern, extract its helper logic into `tetris/ai/` rather than reorganizing the states package.