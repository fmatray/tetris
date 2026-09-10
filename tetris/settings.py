"""Game constants and configuration."""

import os

import pygame

# --- Data directory ----------------------------------------------------
# All generated runtime data (settings, leaderboard, stats, AI model,
# training log, replay sequences) lives under this directory so the repo
# root stays clean. Callers create it via ``os.makedirs(DATA_DIR, exist_ok=True)``.
DATA_DIR = "data"

# --- Display -----------------------------------------------------------
SCREEN_WIDTH = 1500
SCREEN_HEIGHT = 800
BLOCK_SIZE = 30
GHOST_OUTLINE_WIDTH = 2  # pixel width of ghost piece outline

# UI colors
BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
GRAY = (128, 128, 128)
RED = (255, 0, 0)
GREEN = (0, 200, 0)
ORANGE = (255, 165, 0)

# Piece generator labels (English; translated at render time).
GENERATOR_LABELS = {
    "random": "Random",
    "7bag": "7-bag",
    "35bag": "35-bag",
    "weighted": "Weighted",
}

# --- Board geometry ----------------------------------------------------
BOARD_WIDTH = 10
BOARD_HEIGHT = 22  # total rows (2 hidden buffer + 20 visible)
VISIBLE_ROWS = 20  # rows rendered on screen (rows 0-1 are hidden)
HIDDEN_ROWS = BOARD_HEIGHT - VISIBLE_ROWS  # 2 buffer rows above the visible field

# Board rendering offset (top-left pixel of playfield)
BOARD_OFFSET_X = 290
BOARD_OFFSET_Y = 50

# --- Tetrominos --------------------------------------------------------
# Tetromino colors
SHAPES_COLORS = {
    "I": (0, 255, 255),  # Cyan
    "O": (255, 255, 0),  # Yellow
    "T": (160, 32, 240),  # Purple
    "S": (0, 255, 0),  # Green
    "Z": (255, 0, 0),  # Red
    "J": (71, 71, 255),  # Blue
    "L": (255, 165, 0),  # Orange
}


# --- Scoring -----------------------------------------------------------
# Line-clear base points (× level at clear time)
LINE_CLEAR_POINTS = {1: 100, 2: 300, 3: 500, 4: 800}

# T-Spin base points (× level at clear time). 0 lines = T-Spin Mini.
TSPIN_POINTS = {0: 100, 1: 200, 2: 400, 3: 800, 4: 1200}

# Back-to-Back: consecutive T-Spin or Tetris (4-line clear) gets ×1.5
B2B_MULTIPLIER = 1.5

# Lines required to advance one level
LINES_PER_LEVEL = 10

# Level cap: ends the game when the player's level reaches the cap.
# OFF (None) disables the rule; otherwise a value from LEVEL_CAP_VALUES.
# Applies to Human / Bot / AI playing mode only (never AI training).
DEFAULT_LEVEL_CAP = 1000
LEVEL_CAP_VALUES = tuple(range(500, 20_001, 500))
LEVEL_CAP_OFF = None

# --- Gameplay timing ---------------------------------------------------
LOCK_DELAY_MS = 500  # ms before a grounded piece locks
LOCK_DELAY_RESETS = 15  # max move/rotate resets before forced lock
DAS_DELAY_MS = 170  # initial auto-shift delay (ms)
DAS_REPEAT_MS = 50  # auto-shift repeat interval (ms)
ARE_MS = 100  # Appearance (entry) delay between lock and next piece

# Drop speed: Tetris Guideline formula (seconds per row at given level).
# Super-exponential: (DROP_BASE - level×DROP_STEP)^level.
# Level 0 → 1.0s, level 10 → 0.04s, level 20 → 0.001s.
DROP_BASE = 0.8  # Tetris Guideline gravity base
DROP_MIN_INTERVAL = 0.0001  # minimum seconds per row (cap)
SOFT_DROP_FACTOR = 0.1  # soft drop speed = gravity × SOFT_DROP_FACTOR

# Speed modes: maps mode key → DROP_STEP value (per-level gravity decrement).
# "normal" matches the original DROP_STEP (0.007). Higher = faster acceleration.
SPEED_MODES: dict[str, float] = {
    "none": 0.0,  # no speedup — constant 0.8s/row
    "easy": 0.003,
    "normal": 0.007,  # default, original value
    "medium": 0.012,
    "hard": 0.020,
    "crazy": 0.035,
    "insane": 0.060,
}
SPEED_MODE_LABELS: dict[str, str] = {
    "none": "None",
    "easy": "Easy",
    "normal": "Normal",
    "medium": "Medium",
    "hard": "Hard",
    "crazy": "Crazy",
    "insane": "Insane",
}
SPEED_MODE_ORDER: list[str] = list(SPEED_MODES.keys())  # ["none", "easy", ...]
DEFAULT_SPEED_MODE = "normal"

# --- Layout / HUD positions --------------------------------------------
# All in-game text and panel positions as (x, y) pixel coordinates.
HUD_POSITIONS = {
    "score": (20, 20),
    "tetrominos": (20, 60),
    "lines": (20, 100),
    "level": (20, 140),
    "clear_single": (20, 180),
    "clear_double": (20, 220),
    "clear_triple": (20, 260),
    "clear_tetris": (20, 300),
    "combo": (20, 340),
    "speed": (20, 380),
    "hold": (20, 420),  # "HOLD:" label
    "hold_panel": (20, 450),  # hold piece drawing position
    "debug_holes_overhang": (20, 540),  # hole/overhang debug count readout
    "next": (610, 50),  # "NEXT:" label
    "next_panel": (610, 80),  # next pieces drawing (30px below label)
    "ai_stats": (610, 350),
    "mode": (20, 680),
    "generator": (20, 720),
    "speed_mode": (20, 760),
    "ai_moves": (840, 120),
    "debug_bag": (840, 50),  # bag/weights debug panel
    "mcp_hud": (610, 450),
    "pause": (400, 350),
    "timer": (840, 20),  # Sprint/Blitz timer (elapsed or remaining)
}


# --- Special modes -------------------------------------------------------
SPRINT_TARGET_LINES = 40  # Sprint: clear this many lines to win
BLITZ_DURATION_MS = 120_000  # Blitz: game ends after this many ms
LEADERBOARD_MODES = ("marathon", "sprint", "blitz")  # leaderboard tabs

# --- Game-over animation -----------------------------------------------
GAME_OVER_DURATION_MS = 4000
GAME_OVER_PARTICLE_COUNT = 400

# --- AI ----------------------------------------------------------------
AI_ACTION_DELAY_MS = 80  # normal-mode reaction delay
AI_MODEL_SAVE_INTERVAL = 50  # save model every N episodes
LEARN_PER_ACTION = 2  # gradient updates per locked piece
BOT_IMITATION_TOP_N = 10  # best bot games (tetris, triple, score) used for warm-start

# Curriculum learning: piece introduction order (easy → hard)
CURRICULUM_ORDER: list[str] = ["O", "I", "L", "J", "T", "S", "Z"]
# First piece of each game must be from this set (avoids forced overhang
# on an empty board: S/Z/O create awkward gaps right from the start).
FIRST_PIECE_TYPES: list[str] = ["I", "J", "L", "T"]

# --- Player skill levels (Bot + AI playing mode; never training) ------
PLAYER_LEVELS = ("noob", "good", "advanced", "champion", "god")
PLAYER_LEVEL_LABELS = {
    "noob": "Noob",
    "good": "Good",
    "advanced": "Advanced",
    "champion": "Champion",
    "god": "God",
}
# Per-level playing-skill profile:
#   misstep:     probability of NOT taking the argmax placement
#   temp:        softmax temperature over z-normalized values (higher = more random)
#   delay_mult:  decision-delay multiplier (1.0 = current speed)
#   lookahead_cap: max lookahead depth (0 = lookahead off)
# "god" = no reduction = exactly the pre-level behavior.
PLAYER_LEVEL_PROFILES = {
    "noob": {"misstep": 0.60, "temp": 1.5, "delay_mult": 4.0, "lookahead_cap": 0},
    "good": {"misstep": 0.30, "temp": 1.0, "delay_mult": 2.0, "lookahead_cap": 1},
    "advanced": {"misstep": 0.15, "temp": 0.6, "delay_mult": 1.5, "lookahead_cap": 2},
    "champion": {"misstep": 0.05, "temp": 0.4, "delay_mult": 1.0, "lookahead_cap": 3},
    "god": {"misstep": 0.0, "temp": 1.0, "delay_mult": 1.0, "lookahead_cap": 3},
}
DEFAULT_PLAYER_LEVEL = "god"

# --- Bot column reservation (El-Tetris) ----------------------------------
# The bot commits to one column for I-pieces so it can score tetrises.
# The column is chosen from board state (cleanest, most tetris-ready)
# and re-chosen only when it becomes dirty; no clean column -> off.
# Non-I placements whose filled cells touch the reserved column get a
# pick-value penalty; I-pieces are exempt (they are the payoff). This is
# a placement-level rule applied on the bot-only path (BotMovesMixin),
# never on AI training. Penalty must stay in [-80, -40]: <= -100 tops out
# early (68 pieces), -80 already degrades one seed.
RESERVE_COLUMN_PENALTY = -60.0

# --- Menu background animation -----------------------------------------
MENU_ANIM_MAX_PIECES = 35  # max simultaneously falling tetrominos
MENU_ANIM_BLOCK_SIZE = 15  # block size for falling tetrominos (px)
MENU_ANIM_FALL_SPEED = 45  # vertical fall speed (px/s)
MENU_ANIM_MIN_SPAWN_INTERVAL = 0.2  # min seconds between spawns
MENU_ANIM_MAX_SPAWN_INTERVAL = 3.0  # max seconds between spawns
MENU_ANIM_ROT_INTERVAL = (1.5, 4.0)  # seconds between random rotations
MENU_ANIM_ROT_CHANCE = 0.5  # probability rotation is CW vs CCW
MENU_ANIM_EXPLODE_DELAY = (10.0, 16.0)  # seconds before explosion check
MENU_ANIM_EXPLODE_CHANCE = 0.01  # per-frame probability after delay
MENU_ANIM_EXPLODE_PARTICLES = 80  # particles per explosion
MENU_ANIM_FADE_DISTANCE = 100  # px from bottom where fade-out begins

# --- Audio -------------------------------------------------------------
# Volume levels and labels shared by sound and music (4 steps: Off → Max).
VOLUME_LEVELS = [0.0, 0.25, 0.5, 1.0]
VOLUME_LABELS = ["Off", "Low", "Medium", "Max"]

MUSIC_SONGS = ["korobeiniki", "kalinka"]
MUSIC_SONG_LABELS = {"korobeiniki": "Korobeiniki", "kalinka": "Kalinka"}
MUSIC_MIDI_DIR = "media"
MUSIC_SONG_PATHS = {
    "korobeiniki": os.path.join(MUSIC_MIDI_DIR, "korobeiniki.mid"),
    "kalinka": os.path.join(MUSIC_MIDI_DIR, "kalinka.mid"),
}
MUSIC_BASE_SPEED = 1.0
MUSIC_SPEED_PER_LEVEL = 0.05  # +5% speed per level
MUSIC_MAX_SPEED = 2.0  # cap at 2x

# --- Keybindings -------------------------------------------------------
# Human player keybindings: action name → pygame key constant.
# Stored in settings.json as integer key codes.
DEFAULT_KEYBINDS: dict[str, int] = {
    "move_left": pygame.K_LEFT,
    "move_right": pygame.K_RIGHT,
    "rotate_cw": pygame.K_UP,
    "rotate_ccw": pygame.K_s,
    "soft_drop": pygame.K_DOWN,
    "hard_drop": pygame.K_SPACE,
    "hold": pygame.K_c,
    "pause": pygame.K_p,
    "mute": pygame.K_m,
}

# Display labels for each action (English; translated at render time).
KEYBIND_LABELS: dict[str, str] = {
    "move_left": "Left",
    "move_right": "Right",
    "rotate_cw": "Rotate clockwise",
    "rotate_ccw": "Rotate counter-clockwise",
    "soft_drop": "Soft drop",
    "hard_drop": "Hard drop",
    "hold": "Hold",
    "pause": "Pause",
    "mute": "Mute",
}

# --- File paths --------------------------------------------------------
LEADERBOARD_SIZE = 10
MAX_NAME_LENGTH = 15
LEADERBOARD_PATH = os.path.join(DATA_DIR, "leaderboard.json")
HUMAN_STATS_PATH = os.path.join(DATA_DIR, "human_stats.json")
SETTINGS_PATH = os.path.join(DATA_DIR, "settings.json")
MODEL_PATH = os.path.join(DATA_DIR, "ai_model.pt")
PRE_TOURNAMENT_PATH = os.path.join(DATA_DIR, "ai_model.pre_tournament.pt")
TOURNAMENT_LOOPS_PATH = os.path.join(DATA_DIR, "tournament", "loops.json")
LOG_PATH = os.path.join(DATA_DIR, "ai_training_log.json")
REPLAY_PATH = os.path.join(DATA_DIR, "replay_pieces.json")
HUMAN_PLACEMENTS_DIR = os.path.join(DATA_DIR, "human")
BOT_PLACEMENTS_DIR = os.path.join(DATA_DIR, "bot")
PLACEMENTS_PATH = os.path.join(HUMAN_PLACEMENTS_DIR, "game_XXXXXX.jsonl")
BOT_PLACEMENTS_PATH = os.path.join(BOT_PLACEMENTS_DIR, "game_XXXXXX.jsonl")
DEBUG_LOG_PATH = os.path.join(DATA_DIR, "debug.log")
STEP_LOG_PATH = os.path.join(DATA_DIR, "ai_step_log.jsonl")
BEHAVIOR_LOG_PATH = os.path.join(DATA_DIR, "ai_behavior_log.jsonl")
PLAYING_LOG_PATH = os.path.join(DATA_DIR, "ai_playing_log.json")
PLAYING_BEHAVIOR_LOG_PATH = os.path.join(DATA_DIR, "ai_playing_behavior_log.jsonl")
STEP_LOG_MAX_LINES = 1_000_000  # rotate ai_step_log.jsonl at this many lines
TB_LOG_DIR = os.path.join(DATA_DIR, "runs")

# --- MCP ---------------------------------------------------------------
MCP_SERVER_PORT = 8765
