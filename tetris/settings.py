"""Game constants and configuration."""

import os

import pygame

# --- Data directory ----------------------------------------------------
# All generated runtime data (settings, leaderboard, stats, AI model,
# training log, replay sequences) lives under this directory so the repo
# root stays clean. Created on first use via ``ensure_data_dir()``.
DATA_DIR = "data"


def ensure_data_dir() -> None:
    """Create the data directory if it doesn't exist."""
    os.makedirs(DATA_DIR, exist_ok=True)


# Screen dimensions
SCREEN_WIDTH = 1500
SCREEN_HEIGHT = 800
BLOCK_SIZE = 30
GHOST_OUTLINE_WIDTH = 2  # pixel width of ghost piece outline

# Game board dimensions
BOARD_WIDTH = 10
BOARD_HEIGHT = 20

# Colors
BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
GRAY = (128, 128, 128)
RED = (255, 0, 0)

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

# Tetromino shapes
SHAPES = {
    "I": [[(0, 1), (1, 1), (2, 1), (3, 1)], [(2, 0), (2, 1), (2, 2), (2, 3)]],
    "O": [[(0, 0), (1, 0), (0, 1), (1, 1)]],
    "T": [
        [(1, 0), (0, 1), (1, 1), (2, 1)],
        [(1, 0), (1, 1), (2, 1), (1, 2)],
        [(0, 1), (1, 1), (2, 1), (1, 2)],
        [(0, 1), (1, 1), (1, 0), (1, 2)],
    ],
    "S": [[(1, 0), (2, 0), (0, 1), (1, 1)], [(1, 0), (1, 1), (2, 1), (2, 2)]],
    "Z": [[(0, 0), (1, 0), (1, 1), (2, 1)], [(2, 0), (2, 1), (1, 1), (1, 2)]],
    "J": [
        [(0, 0), (0, 1), (1, 1), (2, 1)],
        [(1, 0), (2, 0), (1, 1), (1, 2)],
        [(0, 1), (1, 1), (2, 1), (2, 2)],
        [(1, 0), (1, 1), (0, 2), (1, 2)],
    ],
    "L": [
        [(2, 0), (0, 1), (1, 1), (2, 1)],
        [(1, 0), (1, 1), (1, 2), (2, 2)],
        [(0, 1), (1, 1), (2, 1), (0, 2)],
        [(0, 0), (1, 0), (1, 1), (1, 2)],
    ],
}

# Line-clear base points (× level at clear time)
LINE_CLEAR_POINTS = {1: 100, 2: 300, 3: 500, 4: 800}

# Drop speed: Tetris Guideline formula (seconds per row at given level).
# Super-exponential: (0.8 - level×0.007)^level.
# Level 0 → 1.0s, level 10 → 0.04s, level 20 → 0.001s.
SOFT_DROP_FACTOR = 0.1  # soft drop speed = gravity × SOFT_DROP_FACTOR


def drop_interval(level: int) -> float:
    """Seconds per row at the given level (Tetris Guideline gravity)."""
    base = max(0.001, 0.8 - level * 0.007)
    return max(0.001, base ** level)

# Lines required to advance one level
LINES_PER_LEVEL = 10

# Board rendering offset (top-left pixel of playfield)
BOARD_OFFSET_X = 250
BOARD_OFFSET_Y = 50

# Next-piece panel position
NEXT_PANEL_X = 550
NEXT_PANEL_Y = 100

# HUD text positions
HUD_POSITIONS = {
    "score": (20, 20),
    "tetrominos": (20, 60),
    "lines": (20, 100),
    "level": (20, 140),
    "speed": (20, 180),
    "next": (570, 50),
    "ai_stats": (570, 180),
    "mode": (20, 700),
    "generator": (20, 740),
}

# Game-over animation
GAME_OVER_DURATION_MS = 4000
GAME_OVER_PARTICLE_COUNT = 400

# AI behavior
AI_ACTION_DELAY_MS = 80        # normal-mode reaction delay
AI_MODEL_SAVE_INTERVAL = 50    # save model every N episodes
LEARN_PER_ACTION = 2          # gradient updates per locked piece

# Curriculum learning: piece introduction order (easy → hard)
CURRICULUM_ORDER: list[str] = ["O", "I", "L", "J", "T", "S", "Z"]
# First piece of each game must be from this set (avoids forced overhang
# on an empty board: S/Z/O create awkward gaps right from the start).
FIRST_PIECE_TYPES: list[str] = ["I", "J", "L", "T"]
CURRICULUM_EPSILON_POLICIES: list[str] = ["reset", "boost", "decay"]

# Leaderboard
LEADERBOARD_SIZE = 10
MAX_NAME_LENGTH = 15
LEADERBOARD_PATH = os.path.join(DATA_DIR, "leaderboard.json")
HUMAN_STATS_PATH = os.path.join(DATA_DIR, "human_stats.json")
SETTINGS_PATH = os.path.join(DATA_DIR, "settings.json")
MODEL_PATH = os.path.join(DATA_DIR, "ai_model.pt")
LOG_PATH = os.path.join(DATA_DIR, "ai_training_log.json")
REPLAY_PATH = os.path.join(DATA_DIR, "replay_pieces.json")
DEBUG_LOG_PATH = os.path.join(DATA_DIR, "debug.log")
# --- Menu background animation ------------------------------------------
MENU_ANIM_MAX_PIECES = 35          # max simultaneously falling tetrominos
MENU_ANIM_BLOCK_SIZE = 15         # block size for falling tetrominos (px)
MENU_ANIM_FALL_SPEED = 45         # vertical fall speed (px/s)
MENU_ANIM_MIN_SPAWN_INTERVAL = 0.2  # min seconds between spawns
MENU_ANIM_MAX_SPAWN_INTERVAL = 3.0  # max seconds between spawns
MENU_ANIM_ROT_INTERVAL = (1.5, 4.0)  # seconds between random rotations
MENU_ANIM_ROT_CHANCE = 0.5        # probability rotation is CW vs CCW
MENU_ANIM_EXPLODE_DELAY = (10.0, 16.0)  # seconds before explosion check
MENU_ANIM_EXPLODE_CHANCE = 0.01  # per-frame probability after delay
MENU_ANIM_EXPLODE_PARTICLES = 80  # particles per explosion
MENU_ANIM_FADE_DISTANCE = 100     # px from bottom where fade-out begins

# --- Audio --------------------------------------------------------------
SOUND_VOLUME_LEVELS = [0.0, 0.25, 0.5, 1.0]  # Off, Low, Half, Full
SOUND_VOLUME_LABELS = ["Off", "Bas", "Moyen", "Max"]
MUSIC_VOLUME_LEVELS = [0.0, 0.25, 0.5, 1.0]
MUSIC_VOLUME_LABELS = ["Off", "Bas", "Moyen", "Max"]
MUSIC_SONGS = ["korobeiniki", "kalinka"]
MUSIC_SONG_LABELS = {"korobeiniki": "Korobeiniki", "kalinka": "Kalinka"}
MUSIC_MIDI_DIR = "media"
MUSIC_SONG_PATHS = {
    "korobeiniki": os.path.join(MUSIC_MIDI_DIR, "korobeiniki.mid"),
    "kalinka": os.path.join(MUSIC_MIDI_DIR, "kalinka.mid"),
}
MUSIC_BASE_SPEED = 1.0
MUSIC_SPEED_PER_LEVEL = 0.05  # +5% speed per level
MUSIC_MAX_SPEED = 2.0          # cap at 2x


def music_speed_for_level(level: int) -> float:
    """Music playback speed factor for the given level."""
    return min(MUSIC_BASE_SPEED + level * MUSIC_SPEED_PER_LEVEL, MUSIC_MAX_SPEED)

# --- Keybindings --------------------------------------------------------
# Human player keybindings: action name → pygame key constant.
# Stored in settings.json as integer key codes.
DEFAULT_KEYBINDS: dict[str, int] = {
    "move_left": pygame.K_LEFT,
    "move_right": pygame.K_RIGHT,
    "rotate_cw": pygame.K_UP,
    "rotate_ccw": pygame.K_s,
    "soft_drop": pygame.K_DOWN,
    "hard_drop": pygame.K_SPACE,
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
    "pause": "Pause",
    "mute": "Muet",
}


def key_name(key: int) -> str:
    """Human-readable name for a pygame key constant (French where ambiguous)."""
    _SPECIALS = {
        pygame.K_LEFT: "←",
        pygame.K_RIGHT: "→",
        pygame.K_UP: "↑",
        pygame.K_DOWN: "↓",
        pygame.K_SPACE: "Espace",
        pygame.K_RETURN: "Entrée",
        pygame.K_ESCAPE: "Échap",
        pygame.K_TAB: "Tab",
        pygame.K_BACKSPACE: "Retour",
        pygame.K_LSHIFT: "Maj G",
        pygame.K_RSHIFT: "Maj D",
        pygame.K_LCTRL: "Ctrl G",
        pygame.K_RCTRL: "Ctrl D",
        pygame.K_LALT: "Alt G",
        pygame.K_RALT: "Alt D",
    }
    if key in _SPECIALS:
        return _SPECIALS[key]
    name = pygame.key.name(key)
    if len(name) == 1:
        return name.upper()
    return name
