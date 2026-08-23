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

# Piece generator labels (French UI)
GENERATOR_LABELS = {
    "random": "Aléatoire",
    "7bag": "7-bag",
    "35bag": "35-bag",
    "weighted": "Pondéré",
}

# --- Board geometry ----------------------------------------------------
BOARD_WIDTH = 10
BOARD_HEIGHT = 22  # total rows (2 hidden buffer + 20 visible)
VISIBLE_ROWS = 20  # rows rendered on screen (rows 0-1 are hidden)
HIDDEN_ROWS = BOARD_HEIGHT - VISIBLE_ROWS  # 2 buffer rows above the visible field

# Board rendering offset (top-left pixel of playfield)
BOARD_OFFSET_X = 250
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

# --- Gameplay timing ---------------------------------------------------
LOCK_DELAY_MS = 500  # ms before a grounded piece locks
LOCK_DELAY_RESETS = 15  # max move/rotate resets before forced lock
DAS_DELAY_MS = 170  # initial auto-shift delay (ms)
DAS_REPEAT_MS = 50  # auto-shift repeat interval (ms)

# Drop speed: Tetris Guideline formula (seconds per row at given level).
# Super-exponential: (DROP_BASE - level×DROP_STEP)^level.
# Level 0 → 1.0s, level 10 → 0.04s, level 20 → 0.001s.
DROP_BASE = 0.8  # Tetris Guideline gravity base
DROP_MIN_INTERVAL = 0.001  # minimum seconds per row (cap)
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
    "none": "Aucune",
    "easy": "Facile",
    "normal": "Normal",
    "medium": "Moyen",
    "hard": "Difficile",
    "crazy": "Fou",
    "insane": "Infernal",
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
    "speed": (20, 180),
    "hold": (20, 220),  # "HOLD:" label
    "hold_panel": (20, 250),  # hold piece drawing position
    "debug_holes_overhang": (20, 340),  # hole/overhang debug count readout
    "next": (570, 50),  # "NEXT:" label
    "next_panel": (570, 80),  # next pieces drawing (30px below label)
    "ai_stats": (570, 350),
    "mode": (20, 680),
    "generator": (20, 720),
    "speed_mode": (20, 760),
    "ai_moves": (800, 100),
    "debug_bag": (800, 50),  # bag/weights debug panel
    "mcp_hud": (570, 450),
}

# --- Game-over animation -----------------------------------------------
GAME_OVER_DURATION_MS = 4000
GAME_OVER_PARTICLE_COUNT = 400

# --- AI ----------------------------------------------------------------
AI_ACTION_DELAY_MS = 80  # normal-mode reaction delay
AI_MODEL_SAVE_INTERVAL = 50  # save model every N episodes
LEARN_PER_ACTION = 2  # gradient updates per locked piece

# Curriculum learning: piece introduction order (easy → hard)
CURRICULUM_ORDER: list[str] = ["O", "I", "L", "J", "T", "S", "Z"]
# First piece of each game must be from this set (avoids forced overhang
# on an empty board: S/Z/O create awkward gaps right from the start).
FIRST_PIECE_TYPES: list[str] = ["I", "J", "L", "T"]

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
VOLUME_LABELS = ["Off", "Bas", "Moyen", "Max"]

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

# Display labels for each action (French).
KEYBIND_LABELS: dict[str, str] = {
    "move_left": "Gauche",
    "move_right": "Droite",
    "rotate_cw": "Rotation horaire",
    "rotate_ccw": "Rotation anti-horaire",
    "soft_drop": "Chute douce",
    "hard_drop": "Chute rapide",
    "hold": "Réserve",
    "pause": "Pause",
    "mute": "Muet",
}

# --- File paths --------------------------------------------------------
LEADERBOARD_SIZE = 10
MAX_NAME_LENGTH = 15
LEADERBOARD_PATH = os.path.join(DATA_DIR, "leaderboard.json")
HUMAN_STATS_PATH = os.path.join(DATA_DIR, "human_stats.json")
SETTINGS_PATH = os.path.join(DATA_DIR, "settings.json")
MODEL_PATH = os.path.join(DATA_DIR, "ai_model.pt")
LOG_PATH = os.path.join(DATA_DIR, "ai_training_log.json")
REPLAY_PATH = os.path.join(DATA_DIR, "replay_pieces.json")
DEBUG_LOG_PATH = os.path.join(DATA_DIR, "debug.log")

# --- MCP ---------------------------------------------------------------
MCP_SERVER_PORT = 8765
