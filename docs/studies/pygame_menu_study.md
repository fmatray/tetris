# pygame-menu Adoption Study

**Date:** 2026-08-14
**Library:** [pygame-menu](https://pygame-menu.readthedocs.io/en/latest/) v4.5.2 (stock) / [pygame-menu-ce](https://github.com/ppizarror/pygame-menu/tree/pygame-ce) v4.5.4 (CE fork)
**Scope:** Evaluate replacing the custom menu rendering in `tetris/states/menu_base.py` and its 6 subclasses with pygame-menu.

---

## 1. Executive Summary

**Recommendation: Do not adopt.**

pygame-menu is a mature, well-documented widget toolkit for pygame. It offers buttons, selectors, toggle switches, range sliders, text inputs, and submenu navigation — all of which map conceptually to the current `MenuBase` template-method pattern. However, three fundamental incompatibilities make adoption net-negative:

1. **pygame/pygame-ce conflict**: pygame-menu depends on stock `pygame`; the project uses `pygame-ce`. Having both installed simultaneously breaks `Surface.blit()` at the C level. A `pygame-menu-ce` fork exists (v4.5.4) but is a separate package with lower maintenance velocity and limited community usage.

2. **Custom rendering pipeline**: The current menus render over a live `MenuBackgroundAnimation` (falling tetrominos + particle explosions), use a specific font/colour scheme (Arial bold/large, BLACK/WHITE/GRAY), and follow a precise pixel layout (`TITLE_Y=50`, `CONTENT_Y=120`, `INSTRUCTIONS_Y=SCREEN_HEIGHT-50`). pygame-menu's `Theme` system can approximate this but produces a visually different result (menubar, widget padding, selection effects, scrollbars). Matching the current look would require fighting the theme system rather than using it.

3. **FSM integration friction**: pygame-menu manages its own event loop (`mainloop`) or operates in an "external loop" mode (`menu.update(events)` / `menu.draw(surface)`). The external mode is compatible with the current `State` contract, but the submenu navigation model (persistent `Menu` objects with `_current` pointer) conflicts with the disposable-state pattern (new `MenuState` per transition, lazy imports for cycle avoidance). Bridging the two would add a translation layer that eliminates the simplicity gain.

The genuine wins — mouse support, scrollbar for long lists, pre-built widgets — are not needed: the menus are keyboard-only, fit on one screen, and the template-method already handles toggles/selectors/buttons in ~15 lines per subclass.

---

## 2. Current Menu Architecture

### 2.1 MenuBase Template Method

```python
# tetris/states/menu_base.py
class MenuBase(State):
    _OPTIONS: tuple[str, ...] = ()
    _toggle_indices: frozenset[int] = frozenset()
    _title: str = ""

    def handle_event(self, event) -> State | None:
        # UP/DOWN: navigate (skip disabled)
        # LEFT/RIGHT: toggle value if in _toggle_indices
        # ENTER: _on_select() -> State | None
        # ESC: _on_back() -> State | None

    def draw(self, screen, *, particles=None) -> None:
        screen.fill(BLACK)
        self.bg_anim.draw(screen)        # falling tetrominos
        if particles: particles.draw(screen)
        # title (large font, centered)
        # options (small font, centered, "> " prefix for selected)
        # instructions (bottom, gray)
```

Subclasses override 7 hooks: `_value_label`, `_toggle`, `_on_select`, `_is_disabled`, `_on_back`, `_on_navigate`, `_save`. The entire navigation logic lives in `MenuBase.handle_event()` (30 lines). Each subclass is ~40-80 lines defining options and hook overrides.

### 2.2 Menu State Tree (7 menu classes + 3 non-menu states)

```
State
├── MenuBase (template)
│   ├── HumanMenuState     (5 options: mode, ghost, keys, stats, back)
│   ├── AIMenuState        (6 options: mode, speed, learning, stats, reset, back)
│   ├── AudioMenuState     (4 options: sound, music, song, back)
│   ├── GameRulesMenuState (4 options: generator, preview, handicap, back)
├── KeybindState           (interactive rebinding, not a MenuBase subclass)
├── StatsState             (AI stats table + matplotlib graph, any-key return)
├── HumanStatsState        (human stats table, any-key return)
├── LeaderboardState       (top-10 display, any-key return)
├── GameOverState          (animation → name entry → leaderboard → menu)
├── GameState              (gameplay)
│   └── AIState            (AI gameplay)
```

**Non-menu states** (KeybindState, StatsState, HumanStatsState, LeaderboardState, GameOverState) have custom rendering that pygame-menu cannot replace: interactive key capture, matplotlib graph surfaces, multi-column stat tables, particle-driven game-over animation.

### 2.3 Menu Transition Map

```
MenuState ──ENTER──→ AudioMenuState ──ESC/Retour──→ MenuState (stored ref)
MenuState ──ENTER──→ GameRulesMenuState ──ESC/Retour──→ MenuState (stored ref)
MenuState ──ENTER──→ HumanMenuState ──ESC/Retour──→ MenuState (stored ref)
MenuState ──ENTER──→ AIMenuState ──ESC/Retour──→ MenuState (stored ref)
MenuState ──ENTER──→ GameState / AIState ──ESC──→ MenuState (NEW instance, reloads settings)
MenuState ──ENTER──→ LeaderboardState ──any key──→ MenuState (stored ref or new)
MenuState ──ENTER──→ Quit (sys.exit)
MenuState ──ESC──→ Quit (sys.exit)

HumanMenuState ──ENTER──→ KeybindState ──ESC──→ HumanMenuState (stored ref)
HumanMenuState ──ENTER──→ HumanStatsState ──any key──→ HumanMenuState (stored ref)
AIMenuState ──ENTER──→ HyperparamMenuState ──ESC/Retour──→ AIMenuState (stored ref)
AIMenuState ──ENTER──→ StatsState ──any key──→ AIMenuState (stored ref)
```

**Key pattern**: Submenus return a stored `self.menu` reference (preserves settings). `GameState` ESC creates a new `MenuState` (reloads settings from disk). This is a known inconsistency documented in AGENTS.md.

### 2.4 Settings Flow

`MenuState` is the single source of truth. Submenus hold a `self.menu` reference and mutate `MenuState` attributes directly, then call `self.menu.save_settings()`. Child states never read settings from disk — they read from the parent `MenuState` reference. This is a clean, simple pattern with no serialization layer.

### 2.5 Visual Identity

- **Background**: `MenuBackgroundAnimation` — up to N tetrominos falling from the top, randomly rotating, exploding into particles, fading near the bottom. Each menu state owns its own animation instance, resetting on every transition.
- **Fonts**: Arial 32px bold (titles), Arial 24px normal (body). Proportional, so all positioning is explicit pixel coordinates.
- **Colours**: BLACK background, WHITE selected text, GRAY unselected, dark gray disabled, RED for confirmation prompts.
- **Selection indicator**: `"> "` prefix before selected option text.
- **Layout**: Title at `TITLE_Y=50`, options at `CONTENT_Y=120` with `LINE_HEIGHT_SMALL=32` spacing, instructions at `SCREEN_HEIGHT-50`.

---

## 3. Library Analysis (pygame-menu v4.5.2)

### 3.1 Core API

```python
import pygame_menu

menu = pygame_menu.Menu(title, width, height, theme=...)
menu.add.button(label, action_or_submenu, *args)
menu.add.selector(label, items, onchange=callback)
menu.add.toggle_switch(label, onchange=callback)
menu.add.range_slider(label, default, range_values, increment, onchange=callback)
menu.add.text_input(label, default=...)
menu.add.label(text)

# External event loop mode (compatible with State pattern):
events = pygame.event.get()
menu.update(events)    # process events, returns list of update modes
menu.draw(surface)     # render to screen
menu.is_enabled()      # check if menu is active
menu.enable() / menu.disable()
```

### 3.2 Submenu Navigation

pygame-menu handles submenus via `menu.add.button('Label', submenu_menu_object)`. Pressing ENTER on the button opens the submenu. The library maintains a `_current` pointer and supports `BACK` (go to previous), `RESET` (go to first), `CLOSE`, and `EXIT` events. This is a persistent-menu model — all `Menu` objects are created upfront and reused.

### 3.3 Theme System

`Theme` objects control: background colour/image, title bar style (7 styles), font family/size, widget selection effect (5 types: Highlight, LeftArrow, RightArrow, None, Simple), widget padding/margins, colours. Pre-built themes: `THEME_DEFAULT`, `THEME_BLUE`, `THEME_DARK`, `THEME_GREEN`, `THEME_ORANGE`, `THEME_SOLARIZED`.

Custom themes can be created from scratch or copied from a preset. This could approximate the current BLACK/WHITE/GRAY aesthetic, but the menubar, selection effects, and widget padding produce a fundamentally different visual.

### 3.4 Widget Inventory

| Widget | Current equivalent | Fit |
|--------|-------------------|-----|
| `Button` | `_on_select()` for non-toggle options | Good — direct mapping |
| `Selector` | `_toggle(direction)` for cycling values | Good — `onchange` callback |
| `ToggleSwitch` | `_toggle()` for boolean toggles | Good — ON/OFF display |
| `RangeSlider` | HyperparamMenuState numeric params | Good — slider for floats/ints |
| `TextInput` | GameOverState name entry | Good — but GameOverState is not a menu |
| `Label` | `_value_label()` display | Partial — labels are static, not inline |
| `DropSelect` | Not currently used | N/A |
| `Table` | HyperparamMenuState custom table | Partial — but current table has explanations |
| `Frame` | Not used | N/A |
| `SurfaceWidget` | StatsState matplotlib graph | Partial — could embed graph surface |

### 3.5 External Event Loop Integration

The library supports an "external loop" mode compatible with the current `State` contract:

```python
# Current State contract:
def handle_event(self, event) -> State | None
def update(self, dt, particles) -> State | None
def draw(self, screen, *, particles=None) -> None

# pygame-menu external mode:
events = pygame.event.get()
menu.update(events)  # replaces handle_event
menu.draw(surface)   # replaces draw
# No update(dt) equivalent — menu has no per-frame animation
```

The `Menu.update(events)` method processes a list of pygame events. `Menu.draw(surface)` renders to the screen. This maps to the current `handle_event` / `draw` hooks. The `update(dt, particles)` hook (for the background animation) would need to run separately — pygame-menu has no per-frame update concept.

### 3.6 Sound Support

pygame-menu has a built-in `Sound` engine (`menu.get_sound()`) with methods like `play_event_button_click()`, `play_event_widget_selection()`. This could replace the manual `self.audio.play_nav()` calls in `MenuBase`, but the project already has a sophisticated `AudioManager` with procedural SFX synthesis. The library's sound system would be redundant.

---

## 4. Compatibility Analysis

### 4.1 Blocking Issue: pygame/pygame-ce Conflict

**The project uses pygame-ce 2.5.x** (per AGENTS.md: "pygame-ce (pygame Community Edition) 2.5.x — not stock pygame"). **pygame-menu 4.5.2 depends on stock `pygame`** (declared in its `Requires` metadata). Installing pygame-menu pulls in stock pygame, which conflicts with pygame-ce at the C extension level.

**Observed failure**: With both `pygame==2.6.1` and `pygame-ce==2.5.8` installed, `Surface.blit()` raises `pygame.error: Parameter 'surface' is invalid` — even for basic operations like rendering text onto a surface. This is a hard incompatibility: the two packages share the `pygame` namespace but have incompatible C extensions.

**Mitigation**: `pygame-menu-ce` (v4.5.4) is a fork on the `pygame-ce` branch of the same repository. It depends on `pygame-ce` instead of `pygame`. However:
- It is a separate PyPI package (`pip install pygame-menu-ce`).
- Latest version: 4.5.4 (vs 4.5.2 for stock — the CE fork is ahead).
- Only 5 versions published (vs 90+ for stock) — lower community adoption.
- The project would need to switch from `pygame-menu` to `pygame-menu-ce` in requirements.
- The API is identical (same codebase, different dependency).

**Severity**: Blocking for stock pygame-menu. Solvable with pygame-menu-ce, but introduces a less-established dependency.

### 4.2 Mismatch: Persistent Menus vs Disposable States

**Current**: Each menu transition creates a new `State` instance. Submenus store a reference to the parent `MenuState` and return it on ESC. This is idiomatic to the State Pattern — each state is self-contained, garbage-collected on transition.

**pygame-menu**: All `Menu` objects are created upfront and persisted. Submenu navigation uses a `_current` pointer — the same `Menu` instance is reused. `menu.disable()` hides it; `menu.enable()` shows it. `menu.full_reset()` returns to the root menu.

**Conflict**: The current "new `MenuState` on ESC from game" pattern (reloads settings from disk) is intentional — it picks up any external changes. pygame-menu's persistent model would require manually resetting widget values when re-entering a menu, adding complexity.

**Impact**: Medium. Would need a translation layer between the FSM's disposable states and pygame-menu's persistent menus. The FSM would create a `State` wrapper that enables/disables the appropriate `Menu` object, rather than creating/destroying it.

### 4.3 Mismatch: Background Animation

**Current**: `MenuBackgroundAnimation` is a per-state instance with its own spawn/update/draw cycle. It spawns falling tetrominos, updates positions, triggers explosions into the `ParticleSystem`, and draws everything. This runs in `MenuBase.update(dt, particles)` and `MenuBase.draw()`.

**pygame-menu**: The menu draws its own background (theme `background_color` or `BaseImage`). A `bgfun` callback can be passed to `mainloop()` for custom background drawing, but this is only used in the `mainloop` mode, not the external `draw()` mode. In external mode, the application must draw the background before calling `menu.draw(surface)`.

**Fit**: The background animation would need to run outside pygame-menu's draw cycle. The `State` wrapper would call `bg_anim.update(dt)` in `update()`, then `bg_anim.draw(screen)` before `menu.draw(screen)` in `draw()`. This is workable but means the background animation code stays — pygame-menu doesn't replace it.

**Impact**: Low. The animation is already decoupled. But it means pygame-menu only replaces the text rendering, not the full visual pipeline.

### 4.4 Mismatch: Custom Rendering (HyperparamMenuState)

`HyperparamMenuState` overrides `draw()` entirely to render a multi-column table: `(param_name, current_value, min, max, step, explanation)`. This is not a standard menu — it's a data table with inline toggles. pygame-menu's `Table` widget could display the data, but the current implementation interleaves toggle behaviour (LEFT/RIGHT changes values) with table display. A pygame-menu `Table` is read-only display; toggling would require separate `RangeSlider` or `Selector` widgets alongside the table, changing the layout.

**Impact**: High for this one state. Either keep `HyperparamMenuState` as a custom `State` (mixed approach) or redesign the UI to use pygame-menu widgets (losing the table-with-explanations layout).

### 4.5 Mismatch: Non-Menu States (5 classes)

`KeybindState`, `StatsState`, `HumanStatsState`, `LeaderboardState`, `GameOverState` have custom rendering that pygame-menu cannot replace:

- **KeybindState**: Interactive key capture — listens for the next key press to rebind. Requires custom event handling that pygame-menu's `TextInput` cannot replicate (it captures text, not raw keycodes).
- **StatsState**: Embeds a matplotlib graph surface alongside a stats table. Could use `SurfaceWidget` for the graph, but the table layout is custom.
- **GameOverState**: Three-phase flow (animation → name entry → leaderboard) with particle effects. Not a menu at all.

**Impact**: These states would remain as custom `State` subclasses regardless. pygame-menu adoption would be partial — only the 6 `MenuBase` subclasses.

### 4.6 Mismatch: Selection Indicator

**Current**: `"> "` text prefix before the selected option. Simple, zero visual overhead.

**pygame-menu**: 5 selection effect classes (HighlightSelection, LeftArrowSelection, RightArrowSelection, NoneSelection, SimpleSelection). `SimpleSelection` (font colour change) or `NoneSelection` + custom font colour could approximate the current look, but the library's widget rendering (padding, margins, font handling) will differ from the current `font.render()` + `screen.blit()` approach.

**Impact**: Low. Cosmetic, but the visual identity would change.

### 4.7 Mismatch: Lazy Import Pattern

**Current**: Concrete states are imported lazily inside methods (e.g., `from tetris.states.audio_menu import AudioMenuState` inside `MenuState._on_select()`) to avoid import cycles. This is an architectural decision documented in `base.py`.

**pygame-menu**: Submenu `Menu` objects must be created before being passed to `menu.add.button('Label', submenu)`. If all menus are created upfront (persistent model), all state classes and their dependencies must be importable at module load time, reintroducing the import cycle problem.

**Mitigation**: Create `Menu` objects lazily on first access, or use callable actions that create submenus on demand. But this fights the library's persistent-menu design.

**Impact**: Medium. Would need careful restructuring of imports.

### 4.8 What pygame-menu Would Improve

| Feature | Current state | With pygame-menu |
|---------|--------------|-----------------|
| Mouse support | Not implemented | Built-in |
| Scrollbar for long lists | Not needed (all menus fit) | Built-in if needed |
| Widget reusability | Each subclass reimplements | Library handles |
| Visual polish | Minimal (text + prefix) | Themes, selection effects, shadows |
| Text input for name entry | Custom in GameOverState | `TextInput` widget |
| Range slider for hyperparams | Custom toggle with step | `RangeSlider` widget |
| Accessibility | None | Mouse, touchscreen, joystick support |

### 4.9 What Would Be Lost

| Feature | Current state | With pygame-menu |
|---------|--------------|-----------------|
| Falling tetromino background | Custom animation | Must run outside menu |
| Particle explosion effects | Integrated with menu | Must run outside menu |
| Exact pixel layout control | Explicit coordinates | Theme/widget system overrides |
| MenuBase template simplicity | 30-line handler, 7 hooks | Library API + callbacks |
| Zero new dependencies | No menu library | +1 dependency (pygame-menu-ce) |
| Visual consistency with gameplay | Same fonts, colours | Different rendering pipeline |
| HyperparamMenuState table | Custom multi-column with explanations | No direct equivalent |

---

## 5. Migration Plan (If Adopted)

### Phase 0: Dependency Resolution (0.5 day)

1. Uninstall stock `pygame` and `pygame-menu`.
2. Install `pygame-menu-ce` (v4.5.4) — depends on `pygame-ce`.
3. Add `pygame-menu-ce>=4.5.4` to `requirements.txt`.
4. Verify all 144 tests pass with the new dependency.
5. **Gate**: If any test fails due to pygame-ce/pygame-menu-ce incompatibility, stop.

### Phase 1: Theme Design (1 day)

1. Create a custom `Theme` matching the current visual identity:
   - `background_color=(0, 0, 0)` (BLACK) or transparent (to show animation behind)
   - `title_font=pygame.font.SysFont("Arial", 32, bold=True)`
   - `widget_font=pygame.font.SysFont("Arial", 24)`
   - `title_background_color=(0, 0, 0)` or `MENUBAR_STYLE_NONE`
   - `widget_selection_effect=SimpleSelection()` (font colour change)
   - `widget_selection_color=(255, 255, 255)` (WHITE)
   - `widget_font_color=(128, 128, 128)` (GRAY for unselected)
   - Disable menubar if possible (`MENUBAR_STYLE_NONE`)
2. Create a test menu and compare visually with the current menu.
3. **Gate**: If the visual result is unacceptable, stop.

### Phase 2: MenuState Wrapper (1.5 days)

1. Create a `PygameMenuState(State)` wrapper that:
   - Holds a `pygame_menu.Menu` instance.
   - Calls `menu.update(events)` in `handle_event()`.
   - Calls `bg_anim.update(dt)` + `bg_anim.draw(screen)` + `menu.draw(screen)` in `draw()`.
   - Translates menu events (BACK, EXIT) into `State` transitions.
2. Build the root `Menu` with all 9 options as widgets:
   - `ToggleSwitch` for Joueur (Humain/IA), Débogage (ON/OFF).
   - `Button` for Audio, Règles du jeu, Humain, IA submenus.
   - `Button` for Démarrer le jeu, Leaderboard, Quitter.
3. Wire callbacks to mutate `MenuState` settings and trigger transitions.
4. **Gate**: If the FSM integration is too awkward, stop.

### Phase 3: Submenu Migration (2 days)

Migrate each `MenuBase` subclass to a `pygame_menu.Menu`:

| Submenu | Widgets needed | Complexity |
|---------|---------------|------------|
| AudioMenuState | 3 `Selector` + 1 `Button` (Retour) | Low |
| GameRulesMenuState | 2 `Selector` + 1 `RangeSlider` + 1 `Button` | Low |
| HumanMenuState | 1 `Selector` + 1 `ToggleSwitch` + 3 `Button` | Medium |
| AIMenuState | 1 `ToggleSwitch` + 1 `Selector` + 3 `Button` + confirmation | Medium |
| HyperparamMenuState | 13 `RangeSlider`/`Selector`/`ToggleSwitch` + 1 `Button` | High |
| MenuState | 2 `ToggleSwitch` + 6 `Button` + 1 `Selector` | Medium |

### Phase 4: Non-Menu States (1 day)

Decide for each non-menu state whether to keep as custom `State` or attempt pygame-menu integration:

| State | Decision | Reason |
|-------|----------|--------|
| KeybindState | Keep custom | Interactive key capture not supported |
| StatsState | Keep custom | Matplotlib graph + custom table |
| HumanStatsState | Keep custom | Custom stat aggregation table |
| LeaderboardState | Keep custom | Custom leaderboard view |
| GameOverState | Keep custom | Animation + particle effects |

### Phase 5: Test Update (1 day)

1. Update `tests/test_game_state.py` and any menu-related tests.
2. Tests that assert `type(result).__name__ == "GameOverState"` should still work (transitions return `State` objects).
3. Add visual smoke test for each menu.

### Phase 6: Cleanup (0.5 day)

1. Remove `MenuBase`, `menu_animation.py` (if animation moves to wrapper), `fonts.py` layout constants (if no longer used).
2. Update `docs/class_diagram.md` + `tests/test_class_diagram.py`.
3. Update `AGENTS.md` architecture section.

**Total estimated effort: 7.5 days** (vs 6.5 days for python-statemachine — more effort for less architectural gain, since only 7 of 16 states would be affected).

---

## 6. Alternatives

### Option A: Selective Widget Adoption (Low cost, high value)

Use pygame-menu only for `HyperparamMenuState`, which has the most complex widget needs (13 parameters with min/max/step). Replace the custom table draw with `RangeSlider` and `ToggleSwitch` widgets. Keep all other menus as-is.

**Cost**: ~1 day (only one state, only if pygame-ce conflict is resolved).
**Benefit**: Better UX for hyperparameter tuning (sliders instead of left/right toggles).
**Risk**: Mixed rendering pipelines (pygame-menu for one screen, custom for others).

### Option B: Custom Widget Components (Medium cost, medium value)

Extract reusable widget classes from the current `MenuBase` pattern: `ToggleOption`, `SelectorOption`, `ButtonOption` — each handling its own event dispatch and rendering. This formalizes what `MenuBase` already does via hooks, without any external dependency.

**Cost**: ~2 days.
**Benefit**: Cleaner subclass code, no new dependency, preserves visual identity.
**Risk**: Adds abstraction layers for minimal gain over the current template method.

### Option C: Do Nothing (Zero cost, zero risk)

The current menu system works. 144 tests pass. The `MenuBase` template method is 30 lines of navigation logic. Each subclass is 40-80 lines. The total menu code is ~500 lines across 7 files — not enough to justify a library dependency.

**Cost**: 0.
**Benefit**: No risk, no new dependency, no visual regression.
**Risk**: None.

---

## 7. Conclusion

| Criterion | Current (MenuBase) | pygame-menu-ce |
|-----------|-------------------|----------------|
| Dependencies | 0 new | +1 (pygame-menu-ce) |
| Lines of code | ~500 (7 files) | ~300 (estimated, but + library) |
| Visual identity | Custom, matches game | Theme approximation |
| Background animation | Integrated | External workaround |
| FSM compatibility | Native | Translation layer needed |
| pygame-ce compatible | Yes | Yes (via pygame-menu-ce) |
| Mouse/touch support | No | Yes |
| Test impact | None | Requires test updates |
| Migration effort | 0 | 7.5 days |
| Risk | None | Medium (visual, structural) |

The current `MenuBase` template method is a clean, minimal solution that handles all menu needs in ~500 lines. pygame-menu would replace those 500 lines with ~300 lines of menu-building code plus a 4,000+ line library dependency, a theme-fighting exercise, a persistent-vs-disposable state translation layer, and a visual identity shift. The only real gains — mouse support and sliders for hyperparameters — are not requirements and can be achieved selectively (Option A) if ever needed.

**Final recommendation**: Do not adopt pygame-menu. The current menu system is proportionate to the problem. If mouse support or slider widgets are ever requested, pursue Option A (selective adoption for `HyperparamMenuState` only) after resolving the pygame-ce dependency with `pygame-menu-ce`.