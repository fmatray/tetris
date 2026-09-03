# Class Diagram

Exhaustive Mermaid.js class diagram of the Tetris codebase: every class, every method, every attribute, every relationship with label and cardinality.

Module-level functions (non-class) are listed in `%% Module-level functions` comments within each namespace.

```mermaid
classDiagram
    %% ====================================================================
    %%  App
    %% ====================================================================
    namespace App {
        class TetrisApp {
            +screen: pygame.Surface
            +clock: pygame.time.Clock
            +font: pygame.font.Font
            +audio: AudioManager
            +particles: ParticleSystem
            +state: State
            +__init__() None
            +run() None
            - _frame() None
        }
    }

    %% ====================================================================
    %%  States
    %% ====================================================================
    namespace States {
        class State {
            +handle_event(event: pygame.event.Event) State | None
            +update(dt: float, particles: ParticleSystem) State | None
            +draw(screen: pygame.Surface, particles: ParticleSystem | None) None
        }

        class MenuBase {
            # _OPTIONS: tuple~str, ...~ ClassVar
            # _title: str ClassVar
            # _toggle_indices: frozenset~int~ ClassVar
            # _title_y: int ClassVar
            # _options_y: int ClassVar
            # _item_spacing: int ClassVar
            # _instructions: str ClassVar
            # _disabled_color: tuple~int, int, int~ ClassVar
            +screen: pygame.Surface
            +font: pygame.font.Font
            +audio: AudioManager
            +selection: int
            +bg_anim: MenuBackgroundAnimation
            +__init__(screen, font, audio) None
            +update(dt: float, particles: ParticleSystem) State | None
            - _prev_enabled(current: int) int
            - _next_enabled(current: int) int
            +handle_event(event: pygame.event.Event) State | None
            +draw(screen: pygame.Surface, particles: ParticleSystem | None) None
            # _value_label(i: int) str
            # _toggle(direction: int) None
            # _on_select() State | None
            # _is_disabled(i: int) bool
            # _on_back() State | None
            # _on_navigate() None
            # _save() None
            # _option_text(i: int, is_sel: bool) str
            # _option_color(i: int, is_sel: bool, disabled: bool) tuple~int, int, int~
        }

        class MenuState {
            # _OPTIONS: tuple~str, ...~ ClassVar
            # _GENERATOR_CYCLE: tuple~str, ...~ ClassVar
            # _toggle_indices: frozenset~int~ ClassVar
            # _title: str ClassVar
            # _SETTINGS_MAP: ClassVar~dict~str, str~~ ClassVar
            +handicap: int
            +sound_volume: int
            +music_volume: int
            +music_song: str
            +player: str
            +mode: str
            +piece_generator: str
            +ghost_piece: bool
            +preview_count: int
            +debug: bool
            +ai_speed: str
            +ai_epsilon_decay: float
            +ai_epsilon_end: float
            +ai_lr: float
            +ai_gamma: float
            +ai_batch_size: int
            +ai_buffer_size: int
            +ai_mode: str
            +ai_curriculum: bool
            +ai_curriculum_freq: int
            +ai_curriculum_epsilon: str
            +ai_warm_start: bool
            +ai_learn_per_action: int
            +ai_lookahead: bool
            +ai_lookahead_depth: int
            +ai_dueling: bool
            +ai_imitation: bool
            +mcp_port: int
            +bot_lookahead: str
            +speed_mode: str
            +language: str
            +are: bool
            +__init__(screen, font, audio) None
            - _load_settings() None
            +save_settings() None
            # _value_label(i: int) str
            # _is_disabled(i: int) bool
            # _toggle(direction: int) None
            # _save() None
            # _on_back() State | None
            # _on_select() State | None
            - _build_ai_state() State
            - _build_mcp_state() State
            - _build_eltetris_state() State
            - _game_config() GameConfig
            +training_in_progress() bool
            +holes_overhangs_help: str
        }

        class LanguageMenuState {
            # _OPTIONS: tuple~str, ...~ ClassVar
            # _LANG_CODES: tuple~str, ...~ ClassVar
            # _title: str ClassVar
            +menu: MenuState
            +selection: int
            +__init__(screen, font, audio, menu) None
            +handle_event(event: pygame.event.Event) State | None
            +draw(screen: pygame.Surface, particles: ParticleSystem | None) None
            # _value_label(i: int) str
            # _toggle(direction: int) None
            # _on_select() State | None
            # _on_back() State | None
            # _on_navigate() None
            # _save() None
        }

        class NullAudio {
            +__getattr__(_name: str) Any
        }

        class SimulationError {
        }

        class _PreviewProvider {
            - _known: list~str~
            - _queue: list~str~
            - _generator_name: str
            +__init__(known_types: list~str~, generator_name: str) None
            +next_type() str
            +reset() None
            +save() None
        }

        class HumanMenuState {
            # _OPTIONS: tuple~str, ...~ ClassVar
            # _toggle_indices: frozenset~int~ ClassVar
            # _title: str ClassVar
            +menu: MenuState
            +__init__(screen, font, audio, menu) None
            # _value_label(i: int) str
            # _toggle(direction: int) None
            # _save() None
            # _on_back() State | None
            # _on_select() State | None
        }

        class AIMenuState {
            # _OPTIONS: tuple~str, ...~ ClassVar
            # _toggle_indices: frozenset~int~ ClassVar
            # _title: str ClassVar
            +menu: MenuState
            - _confirm_reset: bool
            +__init__(screen, font, audio, menu) None
            # _value_label(i: int) str
            # _is_disabled(i: int) bool
            # _toggle(direction: int) None
            # _save() None
            # _on_navigate() None
            # _on_back() State | None
            # _on_select() State | None
            # _option_text(i: int, is_sel: bool) str
            # _option_color(i: int, is_sel: bool, disabled: bool) tuple~int, int, int~
            - _reset_ai() None
        }

        class HyperparamMenuState {
            # _OPTIONS: tuple~str, ...~ ClassVar
            # _header_indices: frozenset~int~ ClassVar
            # _toggle_indices: frozenset~int~ ClassVar
            # _title: str ClassVar
            # _PARAM_META: ClassVar~tuple~ ClassVar
            # _DEFAULTS: ClassVar~dict~str, float | int | bool | str~~ ClassVar
            # _VALUE_SPECS: ClassVar~list~tuple~str, Any | None~~~ ClassVar
            +ai_menu: AIMenuState
            +menu: MenuState
            +__init__(screen, font, audio, ai_menu) None
            # _value_label(i: int) str
            # _is_disabled(i: int) bool
            # _toggle(direction: int) None
            # _save() None
            # _on_back() State | None
            # _on_select() State | None
            +draw(screen: pygame.Surface, particles: ParticleSystem | None) None
        }

        class AudioMenuState {
            # _OPTIONS: tuple~str, ...~ ClassVar
            # _toggle_indices: frozenset~int~ ClassVar
            # _title: str ClassVar
            +menu: MenuState
            +__init__(screen, font, audio, menu) None
            # _value_label(i: int) str
            # _toggle(direction: int) None
            # _save() None
            # _on_back() State | None
            # _on_select() State | None
        }

        class MCPMenuState {
            # _OPTIONS: tuple~str, ...~ ClassVar
            # _toggle_indices: frozenset~int~ ClassVar
            # _title: str ClassVar
            # _PORTS: list~int~ ClassVar
            +menu: MenuState
            +mcp_port: int
            +__init__(screen, font, audio, menu) None
            # _value_label(i: int) str
            # _toggle(direction: int) None
            # _save() None
            # _on_back() State | None
            # _on_select() State | None
        }

        class GameRulesMenuState {
            # _OPTIONS: tuple~str, ...~ ClassVar
            # _toggle_indices: frozenset~int~ ClassVar
            # _title: str ClassVar
            +menu: MenuState
            +__init__(screen, font, audio, menu) None
            # _value_label(i: int) str
            # _toggle(direction: int) None
            # _save() None
            # _on_back() State | None
            # _on_select() State | None
        }

        class KeybindState {
            +screen: pygame.Surface
            +font: pygame.font.Font
            +audio: AudioManager
            +human_menu: HumanMenuState
            +selection: int
            - _listening: bool
            - _conflict_msg: str
            +menu: MenuState
            +__init__(screen, font, audio, human_menu) None
            - _keybinds() dict~str, int~
            +handle_event(event: pygame.event.Event) State | None
            - _reset_defaults() None
            - _handle_listening(event: pygame.event.Event) State | None
            +draw(screen: pygame.Surface, particles: ParticleSystem | None) None
        }
        %% Module-level function: key_name(key: int) -> str

        class SeedEntryState {
            +screen: pygame.Surface
            +font: pygame.font.Font
            +audio: AudioManager
            +menu: MenuState
            +text: str
            +__init__(screen, font, audio, menu) None
            +handle_event(event: pygame.event.Event) State | None
            +update(dt: float, particles: ParticleSystem) State | None
            +draw(screen: pygame.Surface, particles: ParticleSystem | None) None
        }

        class HumanStatsState {
            +screen: pygame.Surface
            +font: pygame.font.Font
            +audio: AudioManager
            +human_menu: HumanMenuState
            - _games: list~dict~
            +__init__(screen, font, audio, human_menu) None
            - _load() None
            - _aggregate() list~tuple~str, int, int, float~~
            +draw(screen: pygame.Surface, particles: ParticleSystem | None) None
            - _draw_instructions(screen: pygame.Surface) None
            +handle_event(event: pygame.event.Event) State | None
        }

        class AIStatsState {
            +screen: pygame.Surface
            +font: pygame.font.Font
            +audio: AudioManager
            +ai_menu: AIMenuState
            - _surface: pygame.Surface | None
            - _episode_count: int
            - _stats: TrainingLog
            +__init__(screen, font, audio, ai_menu) None
            - _stat_values() list~str~
            - _build_surface() None
            +draw(screen: pygame.Surface, particles: ParticleSystem | None) None
            +handle_event(event: pygame.event.Event) State | None
        }
        class GameConfig {
            +handicap: int
            +sound_volume: int
            +music_volume: int
            +music_song: str
            +debug: bool
            +ghost_piece: bool
            +preview_count: int
            +speed_mode: str
            +holes_overhangs_help: str
            +seed: int | None
        }
        class PlacementsLog {
            +path: str
            - _fh: IO~str~ | None
            +__init__(path: str) None
            +__enter__() PlacementsLog
            +__exit__(exc_type, exc, tb) None
            - _write(entry: dict) None
            +start_game(seed: int | None, handicap: int) None
            +record(piece: str, rot: int, x: int, hold: bool) None
            +close() None
        }
        class GameState {
            +screen: pygame.Surface
            +font: pygame.font.Font
            +audio: AudioManager
            - _last_level: int
            - _pending_level_up: bool
            +menu: MenuState | None
            +debug: bool
            +ghost_piece: bool
            +preview_count: int
            +are: bool
            +speed_mode: str
            +renderer: Renderer
            +board: Board
            +pieces: PieceProvider
            +seed: int | None
            +current_piece: Tetromino
            +next_piece: Tetromino
            +preview_pieces: list~Tetromino~
            +drop_time: int
            +stats: GameStats
            +current_speed: float
            +game_over: bool
            +paused: bool
            +down_pressed: bool
            +hold_piece: Tetromino | None
            - _can_hold: bool
            - _lock_timer: float
            - _lock_resets: int
            - _grounded: bool
            - _are_timer: float
            - _irs_pending: int
            - _ihs_pending: bool
            - _mute_key: int
            - _placement_recorder: PlacementsLog | None
            - _used_hold_since_lock: bool
            +player_type: str
            +__init__(screen, font, audio, config, piece_provider, menu) None
            - _move_left() None
            - _move_right() None
            - _rotate_cw() None
            - _rotate_ccw() None
            - _soft_drop() None
            - _hard_drop() None
            - _hold() None
            - _advance_piece_pipeline() None
            - _lock_and_spawn(hard_drop: bool) tuple~int, list~  %% records placement if _placement_recorder set
            - _finalize_spawn() None
            - are_active: bool <<property>>
            - _on_piece_moved() None
            - _do_game_over() State
            - _return_to_menu() State
            - _on_exit() None
            +handle_event(event: pygame.event.Event) State | None
            +update(dt: float, particles: ParticleSystem) State | None
            - _emit_line_particles(particles: ParticleSystem, rows_data) None
            +draw(screen: pygame.Surface, particles: ParticleSystem | None) None
            +holes_overhangs_help: str
            - _execute_actions(actions: list~str~) list~str~
        }
        %% Module-level functions: _drop_interval(level: int, drop_step: float) -> float
        %% Module-level functions: _music_speed_for_level(level: int) -> float

        class HumanState {
            - _das_held: dict~int, float~
            +input_map: dict~int, Callable~
            - _pause_key: int
            - _soft_drop_key: int
            - _left_key: int
            - _right_key: int
            - _hold_key: int
            - _placement_recorder: PlacementsLog | None
            +__init__(screen, font, audio, config, piece_provider, menu) None
            - _setup_keybinds(menu) None
            +handle_event(event: pygame.event.Event) State | None
            +update(dt: float, particles: ParticleSystem) State | None
            - _on_exit() None
        }
        %% Module-level functions: _drop_interval(level: int, drop_step: float) -> float
        %% Module-level functions: _music_speed_for_level(level: int) -> float

        class PendingTransition {
            +state: np.ndarray
            +reward: float
            +done: bool
        }

        class MoveRecord {
            +piece: str
            +rot: int
            +col: int
            +hold: bool
        }
        class AIConfig {
            +epsilon_decay: float
            +epsilon_end: float
            +lr: float
            +gamma: float
            +batch_size: int
            +buffer_size: int
            +ai_mode: str
            +curriculum: bool
            +curriculum_freq: int
            +curriculum_epsilon: str
            +warm_start: bool
            +learn_per_action: int
            +lookahead: bool
            +lookahead_depth: int
            +dueling: bool
            +imitation: bool
        }

        class BotMovesMixin {
            - _get_candidate_states() tuple~np.ndarray, list~int~, np.ndarray~
            - _execute_move_sequence(action: int) None
        }
        class AIState {
            +ghost_piece: bool
            +agent: DQNAgent
            +log: TrainingLog
            - _behavior_log_path: str
            +episode: int
            +speed: str
            +ai_mode: str
            +learn_per_action: int
            +lookahead: bool
            +lookahead_depth: int
            - _candidate_placements: list~Placement~
            - _handicap: int
            +seed: int | None
            - _episode_seed: int
            +episode_steps: int
            +episode_start_grid: np.ndarray
            - _pending: PendingTransition | None
            - _last_moves: list~MoveRecord~
            - _prev_action: int | None
            - _action_timer: float
            +curriculum: bool
            +warm_start: bool
            +curriculum_freq: int
            +curriculum_epsilon: str
            - _curriculum_types: list~str~ | None
            +__init__(screen, font, audio, config, ai_config, piece_provider, speed, menu, seed, device) None
            - _lock_and_spawn(hard_drop: bool) tuple~int, list~
            +update(dt: float, particles: ParticleSystem) State | None
            - _on_episode_end() State | None
            - _ep_avg(values: list~float~) float
            - _log_and_learn() None
            - _log_playing() None
            - _write_behavior_log() None
            - _reset_episode() None
            - _apply_epsilon_policy() None
            +draw(screen: pygame.Surface, particles: ParticleSystem | None) None
            - _on_exit() None
        }
        %% Module-level function: iter_column_positions(piece_type: str) -> Iterator
        %% Module-level function: best_next_placement(grid: np.ndarray, piece_type: str) -> np.ndarray
        %% Module-level function: gen_placements(base_grid: np.ndarray, piece_type: str) -> Iterator
        %% Module-level function: hard_drop_y_batch(grid: np.ndarray, shapes: list, x_positions: list) -> np.ndarray
        %% Module-level function: soft_drop_placements(grid, piece_type: str) -> list[Placement]
        %% Module-level function: get_candidate_states(...) -> tuple
        %% Module-level function: draw_ai_hud(ai_state) -> None
        %% Module-level function: _hud_table_rows(log, stats, episode_steps: int) -> list
        %% Module-level function: _cooking_status(ai_state) -> tuple[str, tuple[int, int, int], float]

        class BotConfig {
            +lookahead: bool
            +lookahead_depth: int
        }

        class BotMenuState {
            +menu: MenuState
            +__init__(screen, font, audio, menu) None
            - _value_label(i: int) str
            - _toggle(direction: int) None
            - _save() None
            - _on_back() State | None
            - _on_select() State | None
        }

        class ElTetrisState {
            +lookahead: bool
            +lookahead_depth: int
            +player_type: str
            - _handicap: int
            - _candidate_placements: list~Placement~
            +_lock_and_spawn(hard_drop: bool) LineClearResult
            - _action_timer: float
            +episode_steps: int
            +__init__(screen, font, audio, config, piece_provider, menu, bot_config) None
            +update(dt: float, particles: ParticleSystem) State | None
        }

        class GameOverState {
            +screen: pygame.Surface
            +font: pygame.font.Font
            +audio: AudioManager
            +game: GameState
            +menu: MenuState | None
            +renderer: Renderer
            +name: str
            +step: str
            - _scores: list~dict~
            - _highlight_index: int | None
            +__init__(screen, font, audio, game, menu) None
            - _score_qualifies() bool
            +update(dt: float, particles) State | None
            +handle_event(event: pygame.event.Event) State | None
            - _handle_name_event(event: pygame.event.Event) State | None
            +draw(screen: pygame.Surface, particles: ParticleSystem | None) None
            - _draw_name_entry(screen: pygame.Surface) None
        }

        class LeaderboardState {
            +screen: pygame.Surface
            +font: pygame.font.Font
            +audio: AudioManager
            +menu: MenuState | None
            - _scores: list~dict~
            +__init__(screen, font, audio, menu) None
            - _load() None
            +handle_event(event: pygame.event.Event) State | None
            +draw(screen: pygame.Surface, particles: ParticleSystem | None) None
        }

        class MCPConfig {
            +port: int
        }

        class MCPState {
            +player_type: str
            +mcp_config: MCPConfig
            - _action_queue: Queue~MCPRequest~
            - _server: TetrisMCPServer | None
            - _last_tool_call: dict | None
            - _last_snapshot: dict | None
            - _handicap: int
            +seed: int | None
            # _ACTIONS: dict~str, str~ ClassVar
            +__init__(screen, font, audio, config, mcp_config, piece_provider, menu, start_server) None
            - _start_server() None
            - _stop_server() None
            - _execute_actions(actions: list~str~) list~str~
            - _board_snapshot(action_results: list~str~ | None) dict
            +update(dt: float, particles: ParticleSystem) State | None
            - _do_game_over() State | None
            - _reset_game(seed: int | None) None
            +draw(screen: pygame.Surface, particles: ParticleSystem | None) None
        }

        class MCPRequest {
            +actions: list~str~
            +frames: int
            +result_queue: Queue
            +simulate: bool
            +depth: int
            +hold: bool
            +seed: int | None
        }
        %% Module-level function: draw_mcp_hud(screen, font, state: MCPState) -> None
    }

    %% ====================================================================
    %%  MCP Server
    %% ====================================================================
    namespace MCPServer {
        class TetrisMCPServer {
            - _action_queue: Queue
            - _port: int
            - _thread: Thread | None
            - _mcp: FastMCP | None
            +__init__(action_queue, port) None
            - _setup_mcp() None
            - _run_command(actions: list~str~, frames: int, simulate: bool, depth: int, hold: bool, seed: int | None, error_fallback: dict) dict
            +start() None
            +stop() None
            +attach(action_queue) None
            +detach() None
        }
    }

    %% ====================================================================
    %%  Game
    %% ====================================================================
    namespace Game {
        class ClearedRow {
            +row_index: int
            +cell_colors: list
        }

        class LineClearResult {
            +lines_cleared: int
            +cleared_rows: list~ClearedRow~
        }

        class Board {
            +grid: list~list~tuple~int, int, int~ | None~~
            +__init__() None
            +is_valid_move(tetromino: Tetromino, dx: int, dy: int, rotation: int | None) bool
            +try_rotate(tetromino: Tetromino, direction: int) bool
            +is_tspin(tetromino: Tetromino) bool
            +lock_tetromino(tetromino: Tetromino) tuple~int, list~
            +hard_drop(tetromino: Tetromino) int
            +apply_handicap(level: int, rng: random.Random | None) None
            +clear_lines() tuple~int, list~
            +find_holes() set~tuple~int, int~~
            +find_overhangs() set~tuple~int, int~~
        }


        %% rules.py — grid-agnostic game-rule functions (module-level, not a class):
        %% shape_fits, try_rotation, hard_drop_y, place_cells, find_full_rows
        %% Shared between Board (list grid) and AI simulation (numpy grid)
        class Tetromino {
            +type: str
            +color: tuple~int, int, int~
            +rotation: int
            +x: int
            +y: int
            +shape: list~tuple~int, int~~
            +__init__(piece_type: str | None) None
            +get_current_shape() list~tuple~int, int~~
            +rotate(direction: int) None
            +move(dx: int, dy: int) None
            +get_blocks() list~tuple~int, int~~
        }

        class PieceGenerator {
            <<abstract>>
            +next(pool: list~str~, is_first: bool) str | None
            +reset() None
            +bag_remaining: list~str~
        }

        class RandomGenerator {
            - _rng: random.Random | random
            +__init__(seed: int | None) None
            +next(pool: list~str~, is_first: bool) str
            +reset() None
            +bag_remaining: list~str~
        }

        class BagGenerator {
            - _copies: int
            - _bag: list~str~
            - _rng: random.Random | random
            +__init__(copies: int, seed: int | None) None
            +next(pool: list~str~, is_first: bool) str
            +reset() None
            +bag_remaining: list~str~
        }
        class SevenBagGenerator {
            +__init__(seed: int | None) None
        }

        class ThirtyFiveBagGenerator {
            +__init__(seed: int | None) None
        }

        class WeightedGenerator {
            - _weights: dict~str, float~
            - _rng: random.Random | random
            +__init__(seed: int | None) None
            +next(pool: list~str~, is_first: bool) str
            +reset() None
            +bag_remaining: list~str~
            +weights: dict~str, float~
            - _rebalance(piece: str) None
        }

        class ReplayGenerator {
            - _queue: list~str~
            - _idx: int
            +__init__(path: Path | str) None
            +next(pool: list~str~, is_first: bool) str | None
            +reset() None
            +bag_remaining: list~str~
            %% static
            - _load(path: Path | str) list~str~
        }

        class PieceProvider {
            +mode: str
            +path: Path
            +allowed_types: list~str~ | None
            +generator: str
            - _generator_name: str
            - _seed: int | None
            - _recorded: list~str~
            - _first_piece: bool
            - _all_types: list~str~
            - _fallback: PieceGenerator
            - _generator: PieceGenerator
            +bag_remaining: list~str~
            +__init__(mode: str, path: str | Path, allowed_types: list~str~ | None, generator: str, seed: int | None) None
            +seed: int | None
            +weights: dict~str, float~
            +reset() None
            +next_type() str
            +set_allowed_types(types: list~str~) None
            +save() None
        }
        %% Module-level function: _make_generator(name: str, seed: int | None) -> PieceGenerator

        class ScoreEngine {
            %% static
            +line_clear_points(lines_cleared: int, level: int) int
            %% static
            +combo_points(combo_count: int, level: int) int
            %% static
            +soft_drop_points(cells: int) int
            %% static
            +hard_drop_points(cells: int) int
            %% static
            +tspin_points(lines_cleared: int, level: int) int
            %% static
            +b2b_bonus(base_points: int) int
        }

        class ClearCounts {
            +single: int
            +double: int
            +triple: int
            +tetris: int
            +total: int
            +add(lines_cleared: int) None
        }
        class GameStats {
            +score: int
            +total_lines: int
            +level: int
            +piece_count: int
            +combo: int
            +b2b: bool
            +clear_counts: ClearCounts
            +on_piece_locked(lines_cleared: int, tspin: bool) None
            +add_soft_drop(cells: int) None
            +add_hard_drop(cells: int) None
        }
    }

    %% ====================================================================
    %%  AI
    %% ====================================================================
    namespace AI {
        class NStepTransition {
            +state: np.ndarray
            +action: int
            +reward: float
            +next_state: np.ndarray
            +done: bool
        }

        class Placement {
            +piece_type: str
            +rot: int
            +px: int
            +py: int
            +hold: bool
            +moves: list~str~
            +shape: list~tuple~ [property]
        }

        class DQNAgent {
            +state_size: int
            +gamma: float
            +epsilon: float
            +epsilon_end: float
            +epsilon_decay: float
            +batch_size: int
            +target_sync_freq: int
            +device: torch.device
            +seed: int | None
            +online_net: DQNetwork
            +target_net: DQNetwork
            +optimizer: optim.Adam
            +loss_fn: nn.SmoothL1Loss
            +buffer: PrioritizedReplayBuffer
            - _n_step_buffer: deque
            +steps: int
            +last_loss: float
            +scheduler: optim.lr_scheduler.ReduceLROnPlateau
            +curriculum_level: int
            +curriculum_episode_count: int
            +step_log_path: str | None
            - _tb_writer: SummaryWriter | None
            +last_td_error_mean: float
            +last_td_error_max: float
            +last_grad_norm: float
            +target_syncs: int
            +last_v_spread: float
            +last_v_margin: float
            +last_action_was_random: bool
            +__init__(state_size, lr, gamma, epsilon_start, epsilon_end, epsilon_decay, batch_size, buffer_size, device, seed, step_log_path, tb_log_dir) None
            +select_action(candidate_states: np.ndarray, prior_values: np.ndarray | None) int
            +store(state: np.ndarray, action: int, reward: float, next_state: np.ndarray, done: bool) None
            - _push_n_step() None
            +flush_n_step() None
            +decay_epsilon() None
            +learn() float | None
            - _sync_target() None
            +advance_curriculum(max_level: int, freq: int) bool
            +save(path: str) None
            +load(path: str) None
            +training_metrics() dict
            - _write_step_log() None
            +flush_logs() None
        }
        %% Module-level function: _softmax(x: np.ndarray) -> np.ndarray
        %% Module-level constants: WARM_START_TEMP, N_STEP
        class DQNetwork {
            +dueling: bool
            +net: nn.Sequential
            +trunk: nn.Sequential
            +value_head: nn.Linear
            +advantage_head: nn.Linear
            +__init__(state_size: int, dueling: bool) None
            +forward(x: torch.Tensor) torch.Tensor
        }

        class Transition {
            +state: np.ndarray
            +action: int
            +reward: float
            +next_state: np.ndarray
            +done: bool
            +n: int
        }

        class PrioritizedReplayBuffer {
            +capacity: int
            +alpha: float
            +beta: float
            +beta_increment: float
            +buffer: deque
            +priorities: deque
            +__init__(capacity: int, alpha: float, beta: float, beta_increment: float) None
            +push(state: np.ndarray, action: int, reward: float, next_state: np.ndarray, done: bool, n: int) None
            +sample(batch_size: int) tuple~list, np.ndarray, np.ndarray~
            +update_priorities(indices: np.ndarray, td_errors: np.ndarray) None
            +__len__() int
        }

        class EpisodeRecord {
            +episode: int
            +score: int
            +lines: int
            +level: int
            +steps: int
            +epsilon: float
            +loss: float
            +timestamp: str
            +seed: int
        }
        class TrainingLog {
            # _SAVE_INTERVAL: int ClassVar
            +path: str
            +episodes: list~dict~
            +total_episodes: int
            +avg_score: float
            +best_score: int
            +total_lines: int
            +total_steps: int
            +avg_level: float
            +best_level: int
            +total_score: int
            +best_lines: int
            +avg_lines: float
            +best_steps: int
            +avg_steps: float
            +last_100_avg: float
            +last_100_avg_lines: float
            +last_100_avg_level: float
            +last_100_avg_steps: float
            +__init__(path: str) None
            - _load() None
            - _safe_sum(key: str) int
            - _safe_max(key: str) int
            - _safe_avg(key: str) float
            - _last_n_avg(key: str, n: int) float
            +record(episode: int, score: int, lines: int, level: int, steps: int, epsilon: float, loss: float, seed: int) None
            +flush() None
            - _save() None
            - _trend(key: str) str
        }
    }

    %% ====================================================================
    %%  Visuals
    %% ====================================================================
    namespace Visuals {
        class Renderer {
            # _GLITCH_COLORS: tuple ClassVar
            +screen: pygame.Surface
            +font: pygame.font.Font
            +__init__(screen: pygame.Surface, font: pygame.font.Font) None
            +render_frame(game: GameState, particles: ParticleSystem) None
            - _draw_text(text: str, pos: tuple~int, int~) None
            - _draw_debug_bag(game: GameState) None
            %% static
            +_cell_rect(x: int, y: int, ox: int, oy: int) pygame.Rect
            %% static
            +_panel_rect(x: int, y: int, ox: int, oy: int) pygame.Rect
            - _draw_debug_weights(game: GameState) None
            %% static
            +_normalized_blocks(tetromino: Tetromino) list~tuple~int, int~~
            +draw_grid(board: Board) None
            +draw_ghost(tetromino: Tetromino, board: Board) None
            +draw_tetromino(tetromino: Tetromino) None
            +draw_panel_pieces(pieces: list~Tetromino~, ox: int, oy: int, spacing: int, dim: bool | list~bool~) None
            - _render_glitch_board(game: GameState, shake_x: int, shake_y: int, glitch: float) pygame.Surface
            - _render_game_over_text(elapsed: int) None
            +play_game_over_animation(game: GameState, audio) None
            - _draw_hole_overhang_markers(game: GameState) None
            - _draw_cell_letter(letter: str, rect: pygame.Rect, color) None
            - _draw_hole_overhang_debug(game: GameState) None
        }

        class Particle {
            __slots__: color, decay, life, size, vx, vy, x, y
            +x: float
            +y: float
            +color: tuple~int, int, int~
            +vx: float
            +vy: float
            +life: float
            +decay: float
            +size: int
            +__init__(x: float, y: float, color: tuple~int, int, int~) None
            +update() None
            +draw(screen: pygame.Surface) None
        }

        class ParticleSystem {
            +particles: list~Particle~
            +__init__() None
            +emit(x: float, y: float, color: tuple~int, int, int~, count: int) None
            +update() None
            +draw(screen: pygame.Surface) None
        }

        class MenuBackgroundAnimation {
            - _pieces: list~_FallingPiece~
            - _spawn_timer: float
            +__init__() None
            +update(dt: float, particles: ParticleSystem) None
            - _explode(particles: ParticleSystem, piece: _FallingPiece) None
            +draw(screen: pygame.Surface) None
        }

        class _FallingPiece {
            __slots__: age, blocks, color, explode_delay, rot_index, rot_timer, shape_key, x, y
            +shape_key: str
            +blocks: list~list~tuple~int, int~~
            +color: tuple~int, int, int~
            +x: float
            +y: float
            +rot_index: int
            +rot_timer: float
            +age: float
            +explode_delay: float
            +cells: list~tuple~int, int~~
            +__init__(shape_key: str) None
            +rotate(direction: int) None
            +max_row() int
            +update(dt: float) None
            +should_explode() bool
            +is_offscreen() bool
            +fade_alpha() float
            +draw(screen: pygame.Surface) None
        }

        class ColumnDef {
            +label: str
            +width: int
            +align: str
        }
    }
    %% Module-level functions: draw_leaderboard(screen, font, scores, highlight_index) -> None
    %% Module-level functions: render_score_graph(episodes, scores) -> pygame.Surface
    %% Module-level functions: get_large_font() -> pygame.font.Font
    %% Module-level functions: get_small_font() -> pygame.font.Font

    %% ====================================================================
    %%  Audio
    %% ====================================================================
    namespace Audio {
        class AudioManager {
            # _SAMPLE_RATE: int ClassVar
            +sound_volume: int
            +music_volume: int
            +song: str
            +muted: bool
            - _music_speed: float
            - _music_start_tick: int
            - _music_pos_sec: float
            +sounds: dict~str, pygame.mixer.Sound~
            - _music_channel: pygame.mixer.Channel
            - _sfx_channel: pygame.mixer.Channel
            - _xfade_channel: pygame.mixer.Channel
            - _music_buffer: np.ndarray | None
            - _music_duration: float
            - _music_sound: pygame.mixer.Sound | None
            +__init__(sound_volume: int, music_volume: int, song: str) None
            - _init_sounds() None
            %% static
            +_parse_midi(path: str) list~MidiNote~
            %% static
            +_apply_envelope(n: int, attack_max: int, release_max: int) np.ndarray
            - _generate_music() None
            - _build_music_sound(from_pos: float, fade_in_ms: int) None
            +generate_melody(notes: list~tuple~float, float~~) pygame.mixer.Sound
            +play(key: str) bool
            - _get_music_pos() float
            +start_music() None
            +stop_music() None
            +set_music_speed(speed: float) None
            +toggle_mute() None
            +apply_settings(sound_volume: int, music_volume: int, song: str) None
        }

        class MidiNote {
            +start: float
            +duration: float
            +note: int
        }
    }
    %% Module-level functions: ensure_midi_files() -> None
    %% Module-level functions: _note(name, octave) -> int
    %% Module-level functions: _build_track(notes, ticks_per_beat) -> mido.MidiTrack
    %% Module-level functions: _generate_midi(song_name, path) -> None

    %% ====================================================================
    %%  Storage (module-level functions only, no classes)
    %% ====================================================================
    %% load_leaderboard() -> list[dict]
    %% save_score(name, score, level, lines, generator, mode) -> None
    %% load_human_games() -> list[dict]
    %% save_human_game(name, score, level, lines, tetrominos) -> None

    %% ====================================================================
    %%  External
    %% ====================================================================
    namespace External {
        class nn_Module {
            %% Placeholder for torch.nn.Module
        }
    }

    %% ====================================================================
    %%  Relationships — Inheritance
    %% ====================================================================
    State <|-- MenuBase
    State <|-- GameState
    State <|-- GameOverState
    State <|-- LeaderboardState
    State <|-- KeybindState
    State <|-- HumanStatsState
    State <|-- AIStatsState
    State <|-- SeedEntryState

    MenuBase <|-- MenuState
    MenuBase <|-- HumanMenuState
    MenuBase <|-- AIMenuState
    MenuBase <|-- HyperparamMenuState
    MenuBase <|-- AudioMenuState
    MenuBase <|-- GameRulesMenuState
    MenuBase <|-- MCPMenuState

    GameState <|-- HumanState
    GameState <|-- AIState
    GameState <|-- MCPState

    nn_Module <|-- DQNetwork
    PieceGenerator <|-- RandomGenerator
    PieceGenerator <|-- BagGenerator
    GameState <|-- ElTetrisState
    BotMovesMixin <|-- AIState
    BotMovesMixin <|-- ElTetrisState
    MenuBase <|-- BotMenuState
    MenuBase <|-- LanguageMenuState

    PieceGenerator <|-- ReplayGenerator
    PieceGenerator <|-- WeightedGenerator
    BagGenerator <|-- SevenBagGenerator
    BagGenerator <|-- ThirtyFiveBagGenerator

    %% ====================================================================
    %%  Relationships — Composition
    %% ====================================================================
    TetrisApp "1" *-- "1" AudioManager : owns
    TetrisApp "1" *-- "1" ParticleSystem : owns
    TetrisApp "1" *-- "1" State : manages

    MenuBase "1" *-- "1" MenuBackgroundAnimation : owns

    PieceProvider "1" *-- "1" PieceGenerator : delegates
    GameState "1" *-- "1" Board : owns
    GameState "1" *-- "1" PieceProvider : owns
    GameState "1" *-- "1" GameStats : owns
    GameStats "1" *-- "1" ClearCounts : owns
    GameState "1" *-- "1" GameConfig : owns

    AIState "1" *-- "1" DQNAgent : owns
    AIState "1" *-- "1" TrainingLog : owns
    AIState "1" *-- "1" AIConfig : owns

    MCPState "1" *-- "1" MCPConfig : owns
    MCPState "1" *-- "0..1" TetrisMCPServer : owns

    DQNAgent "1" *-- "1" DQNetwork : online_net
    DQNAgent "1" *-- "1" DQNetwork : target_net
    DQNAgent "1" *-- "1" PrioritizedReplayBuffer : owns

    GameOverState "1" *-- "1" Renderer : owns

    ParticleSystem "1" *-- "many" Particle : contains

    %% ====================================================================
    %%  Relationships — Association
    %% ====================================================================
    GameState "1" --> "1" ScoreEngine : uses
    GameState "1" --> "1" AudioManager : uses
    GameState "1" --> "1" Tetromino : current_piece
    GameState "1" --> "1" Tetromino : next_piece
    GameState "1" --> "0..1" MenuState : references

    AIState "1" --> "1" ScoreEngine : uses
    AIState "1" --> "1" AudioManager : uses
    AIState "1" --> "0..1" MenuState : references

    MCPState "1" --> "1" ScoreEngine : uses
    MCPState "1" --> "1" AudioManager : uses
    MCPState "1" --> "0..1" MenuState : references

    GameOverState "1" --> "1" GameState : references
    GameOverState "1" --> "0..1" MenuState : returns_to

    MenuBackgroundAnimation "1" --> "many" _FallingPiece : manages
    MenuBackgroundAnimation "1" --> "1" ParticleSystem : uses

    Renderer "1" --> "1" Board : reads
    Renderer "1" --> "1" Tetromino : reads

    AIStatsState "1" --> "1" TrainingLog : reads

    GameStats "1" --> "1" ScoreEngine : uses

    %% ====================================================================
    %%  Relationships — Navigation (FSM transitions)
    %% ====================================================================
    MenuState "1" --> "0..1" GameRulesMenuState : navigates
    MenuState "1" --> "0..1" AudioMenuState : navigates
    MenuState "1" --> "0..1" HumanMenuState : navigates
    MenuState "1" --> "0..1" AIMenuState : navigates
    MenuState "1" --> "0..1" HumanState : navigates
    MenuState "1" --> "0..1" AIState : navigates
    MenuState "1" --> "0..1" LeaderboardState : navigates

    MenuState "1" --> "0..1" MCPMenuState : navigates
    MenuState "1" --> "0..1" MCPState : navigates
    MCPMenuState "1" --> "0..1" MCPState : navigates
    MCPMenuState "1" --> "1" MenuState : returns_to

    HumanMenuState "1" --> "0..1" KeybindState : navigates
    HumanMenuState "1" --> "0..1" HumanStatsState : navigates

    AIMenuState "1" --> "0..1" HyperparamMenuState : navigates
    AIMenuState "1" --> "0..1" AIStatsState : navigates

    KeybindState "1" --> "1" HumanMenuState : returns_to
    GameRulesMenuState "1" --> "1" MenuState : returns_to
    HumanStatsState "1" --> "1" HumanMenuState : returns_to
    AIStatsState "1" --> "1" AIMenuState : returns_to
    LeaderboardState "1" --> "0..1" MenuState : returns_to
```