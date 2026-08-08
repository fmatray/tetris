"""Game constants and configuration."""

# Screen dimensions
SCREEN_WIDTH = 1440
SCREEN_HEIGHT = 800
BLOCK_SIZE = 30

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
    "J": (0, 0, 255),  # Blue
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

# Line-clear bonus by number of lines cleared (base = lines * 100)
LINE_BONUS = {1: 0, 2: 20, 3: 50, 4: 100}

# Drop speed: base seconds, exponential decay per level
DROP_BASE = 0.5
DROP_DECAY = 0.98
SOFT_DROP_FACTOR = 0.1  # soft drop speed = DROP_BASE * SOFT_DROP_FACTOR

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
    "lines": (20, 60),
    "level": (20, 100),
    "next": (570, 50),
    "ai_stats": (570, 180), 
}

# Game-over animation
GAME_OVER_DURATION_MS = 4000
GAME_OVER_PARTICLE_COUNT = 400

# Leaderboard
LEADERBOARD_SIZE = 10
MAX_NAME_LENGTH = 15
LEADERBOARD_PATH = "leaderboard.json"
