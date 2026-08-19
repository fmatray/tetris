# python-statemachine Adoption Study

**Date:** 2026-08-14
**Library:** [python-statemachine](https://python-statemachine.readthedocs.io/en/latest/) v3.2.0
**Scope:** Evaluate replacing the custom FSM in `tetris/states/` with python-statemachine.

---

## 1. Executive Summary

**Recommendation: Do not adopt.**

The library is mature and well-designed, but it solves a different problem than what this codebase has. The current "FSM" is a **State Pattern** (GoF) with per-frame `update(dt)` / `draw(screen)` hooks — not an event-driven state machine. python-statemachine would replace the ~5% of each State class that handles transitions, while demanding a rearchitecture of the other 95% (game loop, heavy state objects, template-method menus, Open/Closed inheritance).

The one genuine win — declarative transition graph with automatic diagrams and invalid-transition prevention — can be achieved more cheaply with a standalone diagram or a transition-validation test.

---

## 2. Current FSM Architecture

### 2.1 Base Contract

```python
# tetris/states/base.py
class State:
    def handle_event(self, event: pygame.event.Event) -> State | None: ...
    def update(self, dt: float, particles: ParticleSystem) -> State | None: ...
    def draw(self, screen: pygame.Surface, *, particles: ParticleSystem | None = None) -> None: ...
```

Transitions: return a new `State` from `handle_event` or `update`; `None` = stay.

### 2.2 Main Loop

```python
# tetris/app.py — TetrisApp._frame()
dt = clock.tick(60)
for event in pygame.event.get():
    new_state = self.state.handle_event(event)
    if new_state:
        self.state = new_state     # transition
new_state = self.state.update(dt, particles)
if new_state:
    self.state = new_state         # transition
self.state.draw(screen, particles)  # render
```

Three-phase per frame: **event → update → draw**, at 60 FPS.

### 2.3 State Tree (16 classes)

```
State (base)
├── MenuBase (abstract template)
│   ├── MenuState          (root, settings owner)
│   ├── HumanMenuState
│   ├── AIMenuState
│   ├── AudioMenuState
│   ├── GameRulesMenuState
│   └── HyperparamMenuState
├── GameState              (human gameplay)
│   └── AIState            (AI gameplay, inherits GameState)
├── GameOverState
├── KeybindState
├── StatsState
├── HumanStatsState
└── LeaderboardState
```

### 2.4 Transition Map (~25 edges)

| Source | Trigger | Target | Pattern |
|--------|---------|--------|---------|
| MenuState | select 1 | AudioMenuState | new instance |
| MenuState | select 2 | GameRulesMenuState | new instance |
| MenuState | select 4 | HumanMenuState | new instance |
| MenuState | select 5 | AIMenuState | new instance |
| MenuState | select 6 (Human) | GameState | new instance |
| MenuState | select 6 (IA) | AIState | new instance |
| MenuState | select 7 | LeaderboardState | new instance |
| MenuState | select 8 / ESC | Quit | `sys.exit()` |
| HumanMenuState | select 2 | KeybindState | new instance |
| HumanMenuState | select 3 | HumanStatsState | new instance |
| HumanMenuState | select 4 / back | MenuState | stored ref |
| AIMenuState | select 2 | HyperparamMenuState | new instance |
| AIMenuState | select 3 | StatsState | new instance |
| AIMenuState | back | MenuState | stored ref |
| AudioMenuState | back | MenuState | stored ref |
| GameRulesMenuState | back | MenuState | stored ref |
| HyperparamMenuState | back | AIMenuState | stored ref |
| GameState | ESC | MenuState | **new** MenuState (reloads settings) |
| GameState | update → game_over | GameOverState | new instance |
| AIState | ESC | MenuState | **new** MenuState |
| AIState | update → game_over (playing) | AIState | new instance (self-loop, restart) |
| AIState | update → game_over (learning) | (in-place reset) | no transition |
| GameOverState | ESC after name | MenuState | new instance |
| StatsState | any key | AIMenuState | stored ref |
| HumanStatsState | any key | HumanMenuState | stored ref |
| KeybindState | ESC | HumanMenuState | stored ref |
| LeaderboardState | any key | MenuState | new or stored ref |

**Two transition patterns coexist:**
- **New instance**: creates fresh state (e.g., `GameState(...)` — new board, new pieces).
- **Stored reference**: returns the parent menu passed at construction (e.g., `return self.menu`).

**Inconsistency**: `GameState` ESC creates a *new* `MenuState` (reloads settings from disk), while `AudioMenuState` back returns the *stored* `MenuState` (preserves in-memory state). This is a known design wart, not a bug.

### 2.5 Key Characteristics

| Characteristic | Current Design |
|---|---|
| **State lifecycle** | Disposable objects; transitions construct new instances |
| **State data** | Heavy: each state owns board, renderer, timers, pygame surfaces |
| **Pygame coupling** | States hold `screen`, `font`, `audio` references |
| **Per-frame hooks** | `update(dt)` + `draw(screen)` every frame (60 FPS) |
| **Input model** | Raw `pygame.event.Event` objects |
| **Menu pattern** | Template Method (`MenuBase.handle_event` dispatches to 7 hooks) |
| **Inheritance** | `AIState(GameState)` — Open/Closed, shared gameplay logic |
| **Import cycles** | Avoided via lazy imports inside methods |
| **Settings** | `MenuState` is the single source of truth; child states hold references |

---

## 3. python-statemachine Library Analysis (v3.2.0)

### 3.1 Core API

```python
from statemachine import StateChart, State

class TetrisSM(StateChart):
    menu = State(initial=True)
    playing = State()
    game_over = State()

    start_game = menu.to(playing)
    die = playing.to(game_over, cond="is_game_over")
    restart = game_over.to(menu)

    def on_enter_playing(self):
        ...  # setup board, spawn piece
    def on_exit_playing(self):
        ...  # cleanup
```

- **States**: declarative class attributes (not instances)
- **Transitions**: `source.to(target)` assigned to event-named attributes
- **Guards**: `cond="method_name"` or `unless=`
- **Actions**: `on_enter_<state>`, `on_exit_<state>`, `on_<event>`, `before_<event>`, `after_<event>`
- **Dependency injection**: callback signatures auto-inspected
- **Single instance**: one StateChart persists across all transitions; state is stored on `model`

### 3.2 Features Relevant to Tetris

| Feature | Fit |
|---|---|
| **Declarative transitions** | Good — makes transition graph explicit |
| **Guards (`cond=`)** | Good — replaces if/else in `_on_select()` |
| **Invalid transition prevention** | Good — `TransitionNotAllowed` catches bugs |
| **Automatic diagram generation** | Good — `sm._graph().write_png()` |
| **Compound states** | Partial — menu hierarchy could nest, but current design doesn't need it |
| **History states** | Unused — no pause/resume feature exists |
| **Eventless transitions** | Partial — could model `game_over` auto-detection |
| **Domain models** | Good — game state could live on a model object |
| **Async support** | Irrelevant — pygame is synchronous |
| **Parallel states** | Irrelevant — no concurrent game modes |

---

## 4. Compatibility Analysis

### 4.1 Fundamental Mismatches

#### Mismatch 1: Event-driven vs. frame-driven

python-statemachine is **event-driven**: `sm.send("event_name")` triggers a transition. The current FSM is **frame-driven**: `handle_event` + `update(dt)` + `draw` run every frame at 60 FPS.

Only `handle_event` maps to `sm.send()`. The `update(dt)` hook (gravity, DAS, lock delay, AI decisions, background animations) and `draw(screen)` hook (rendering) have **no equivalent** in the library. They would need to live outside the StateChart, in the app loop, dispatching to the current state somehow.

**Impact**: The library replaces the transition mechanism but not the game loop. You'd end up with a hybrid: StateChart for transitions + a separate dispatcher for update/draw. This adds a layer without removing one.

#### Mismatch 2: State as heavy object vs. declarative attribute

Current states are **heavy objects** carrying substantial instance data:

```python
# GameState carries: board, piece, next_piece, preview_pieces, hold_piece,
#   stats, renderer, piece_provider, lock_timer, lock_resets, _grounded,
#   _das_held, drop_timer, game_over, score, level, lines, combo, ...
# AIState adds: agent, training_log, episode, epsilon, steps, best_score,
#   avg_score, loss, decision_timer, candidate_states, ...
```

python-statemachine's `State` is a **declarative class attribute** — it carries no instance data. All game state would need to move to the `model` object or the StateChart instance.

**Impact**: Complete reorganization of where game state lives. Every attribute access changes from `self.board` to `self.model.board` or `self.board` (on the StateChart). This touches every line of every state.

#### Mismatch 3: Disposable states vs. persistent instance

Current transitions **construct new state objects**:

```python
# Current: new game = new GameState with fresh board
return GameState(self.screen, self.font, self.audio, ...)
```

python-statemachine uses a **single persistent instance**; transitions change which state is active:

```python
# Library: same instance, state changes
sm.send("start_game")  # sm.current_state_value == "playing"
```

**Impact**: The "new game = new GameState" pattern is idiomatic in the current design. With the library, starting a new game would mean resetting the model's attributes rather than constructing a fresh object. This changes initialization, testing, and the mental model.

#### Mismatch 4: Template Method for menus

`MenuBase` uses a **Template Method pattern** with 7 overridable hooks:

```python
class MenuBase(State):
    def handle_event(self, event) -> State | None:
        # Template: dispatches to hooks
        if event.key == K_UP:    self._navigate(-1)
        elif event.key == K_DOWN:  self._navigate(1)
        elif event.key == K_LEFT:  self._toggle(-1); self._save()
        elif event.key == K_RIGHT: self._toggle(1);  self._save()
        elif event.key == K_RETURN: return self._on_select()
        elif event.key == K_ESCAPE: return self._on_back()

    # Hooks (subclasses override):
    def _value_label(self, i) -> str: ...
    def _toggle(self, direction) -> None: ...
    def _on_select(self) -> State | None: ...
    def _is_disabled(self, i) -> bool: ...
    def _on_back(self) -> State | None: ...
    def _on_navigate(self) -> None: ...
    def _save(self) -> None: ...
```

This is a **UI list navigation pattern**, not a state machine pattern. It handles arrow-key navigation within a menu (up/down moves selection, left/right toggles values). python-statemachine's `on_enter_<state>` / `on_<event>` callbacks don't replace this — they'd coexist awkwardly.

**Impact**: MenuBase's template method would survive the migration as a separate concern, adding complexity instead of replacing it.

#### Mismatch 5: Open/Closed inheritance

`AIState(GameState)` inherits and overrides:

```python
class AIState(GameState):
    # Inherits: board, stats, renderer, update, _lock_and_spawn, _on_piece_moved
    # Overrides: handle_event (ESC only), update (AI decisions), draw (HUD overlay)
    # Adds: agent, training_log, _select_action, _get_candidate_states, _reset_episode
```

python-statemachine has no inheritance mechanism for states. `human_playing` and `ai_playing` would be **sibling states** with shared callbacks, or a **compound state** with internal transitions. The shared gameplay logic (`update`, `_lock_and_spawn`, `_on_piece_moved`) would need to be extracted to standalone functions or mixed into the model.

**Impact**: The clean Open/Closed inheritance is lost. Shared logic moves from inheritance to composition or free functions.

#### Mismatch 6: Lazy import cycle avoidance

Current states import each other **lazily inside methods**:

```python
def _on_select(self) -> State | None:
    from tetris.states.game import GameState  # lazy import
    return GameState(...)
```

python-statemachine declares all states and transitions **at class level**:

```python
class TetrisSM(StateChart):
    menu = State(initial=True)
    playing = State()
    # All states referenced here — no lazy imports possible
```

**Impact**: All 16 states must be visible at class definition time. With 16 states in separate modules, this means either one large file or a registry/forward-reference pattern. Import cycles become a real risk.

### 4.2 What the Library Would Improve

| Improvement | Value | Alternatives |
|---|---|---|
| Declarative transition graph | Medium — makes ~25 edges visible in one place | A standalone transition table/doc |
| Guard conditions | Low — replaces simple if/else | Keep if/else (already clear) |
| Invalid transition prevention | Medium — `TransitionNotAllowed` catches bugs | A test asserting valid transitions |
| Automatic diagrams | Medium — documentation artifact | Manual Mermaid diagram |
| Compound states for menus | Low — current flat hierarchy works | Keep flat |

### 4.3 What the Library Would Cost

| Cost | Severity |
|---|---|
| Rewrite all 15 state files (~1000 lines) | High |
| Restructure game state from per-state to model | High |
| Add hybrid update/draw dispatcher outside StateChart | High |
| Lose AIState(GameState) Open/Closed inheritance | Medium |
| Resolve import cycles for declarative states | Medium |
| Rework all state-related tests (144 tests) | High |
| New dependency in requirements.txt | Low |
| Learning curve for contributors | Low-Medium |

---

## 5. Migration Plan (if pursued)

Despite the recommendation against, here is the plan for completeness.

### Phase 1: Prototype (1 day)

Create a minimal StateChart covering only menu navigation (MenuState ↔ AudioMenuState ↔ GameRulesMenuState). Validate that:
- Event dispatch works with pygame events
- The hybrid loop (StateChart + external update/draw dispatcher) is viable
- State data can live on a model object

**Gate**: If the prototype feels like fighting the library, stop here.

### Phase 2: Game state model extraction (1 day)

Extract all game state from `GameState`/`AIState` into a `GameModel` class:
- `board`, `piece`, `next_piece`, `preview_pieces`, `hold_piece`, `stats`
- `renderer`, `piece_provider`
- Timers: `drop_timer`, `lock_timer`, `lock_resets`, `_grounded`, `_das_held`
- `game_over`, `score`, `level`, `lines`, `combo`

This model would be passed to the StateChart as `model=`.

### Phase 3: State declaration (1 day)

Define all 16 states and ~25 transitions declaratively:

```python
class TetrisSM(StateChart):
    # Top-level
    menu = State(initial=True)
    playing = State()
    game_over = State()

    # Menu sub-states (could be compound)
    human_menu = State()
    ai_menu = State()
    audio_menu = State()
    game_rules_menu = State()
    # ... etc

    # Transitions
    start_human_game = menu.to(playing, cond="is_human")
    start_ai_game = menu.to(playing, cond="is_ai")
    open_human_menu = menu.to(human_menu)
    back_to_menu = human_menu.to(menu) | ai_menu.to(menu) | ...
    die = playing.to(game_over, cond="is_game_over")
    # ...
```

### Phase 4: Callback migration (2 days)

Move all logic from `handle_event`/`update`/`draw` into:
- `on_enter_<state>` / `on_exit_<state>` for setup/teardown
- `on_<event>` for transition actions
- A separate `update(dt)` / `draw(screen)` dispatcher keyed on `sm.current_state_value`

The dispatcher would be:

```python
# tetris/app.py
UPDATE_HANDLERS = {
    "menu": menu_update,
    "playing": game_update,
    "game_over": game_over_update,
    ...
}
DRAW_HANDLERS = {
    "menu": menu_draw,
    "playing": game_draw,
    ...
}
```

### Phase 5: MenuBase template method (1 day)

Keep `MenuBase`'s template method as a standalone helper, not a State subclass. Each menu state's `handle_event` callback delegates to this helper.

### Phase 6: Test rework (1 day)

Update all 144 tests. State construction changes from `GameState(screen, font, audio, ...)` to `TetrisSM(model=GameModel(...))` + `sm.send("start_game")`. Tests that assert `type(result).__name__ == "GameOverState"` change to `sm.current_state_value == "game_over"`.

### Phase 7: Diagram generation + docs (0.5 day)

```python
sm = TetrisSM()
sm._graph().write_png("docs/state_diagram.png")
```

### Total estimated effort: 6.5 days

---

## 6. Alternative: Lightweight Transition Validation

If the goal is to gain the library's main benefits (explicit transition graph, invalid transition prevention) without the rewrite cost:

### Option A: Transition table test (2 hours)

```python
# tests/test_transitions.py
VALID_TRANSITIONS = {
    "MenuState": {"AudioMenuState", "GameRulesMenuState", "HumanMenuState",
                  "AIMenuState", "GameState", "AIState", "LeaderboardState", "Quit"},
    "GameState": {"GameOverState", "MenuState"},
    "AIState": {"AIState", "MenuState"},
    "GameOverState": {"MenuState"},
    # ... etc
}

def test_all_transitions_valid():
    # Grep all `return XState(` calls, assert they're in VALID_TRANSITIONS
    ...
```

### Option B: Mermaid state diagram (1 hour)

Add a Mermaid `stateDiagram-v2` to `docs/` documenting the transition graph. Already partially done in `docs/class_diagram.md`.

### Option C: Transition registry (4 hours)

Add a `TRANSITIONS: dict[type[State], set[type[State]]]` registry in `tetris/states/base.py`. Each state declares its valid targets. `TetrisApp._frame()` asserts the returned state is in the registry. This gives invalid-transition prevention without a library.

---

## 7. Conclusion

| Criterion | python-statemachine | Current custom FSM |
|---|---|---|
| Transition expressiveness | Better (declarative, guarded) | Adequate (imperative) |
| Game loop integration | Poor (no update/draw) | Native (per-frame hooks) |
| State data management | Requires model extraction | Natural (per-state fields) |
| Menu pattern | Awkward coexistence | Template Method (clean) |
| AI inheritance | Lost (sibling states) | Open/Closed (clean) |
| Import cycle handling | Problematic (class-level) | Solved (lazy imports) |
| Diagram generation | Free (automatic) | Manual |
| Migration cost | 6.5 days, full rewrite | — |
| Risk | High (touches everything) | — |

The library is excellent for **event-driven workflows** (order processing, approval pipelines, protocol handlers). It is a poor fit for **real-time game loops** where the state machine is a small part of a larger frame-driven architecture. The current State Pattern is the right tool for this job.

**Final recommendation**: Do not adopt python-statemachine. If transition graph visibility is desired, implement Option A (transition table test) or Option B (Mermaid diagram) — 90% of the benefit at 1% of the cost.