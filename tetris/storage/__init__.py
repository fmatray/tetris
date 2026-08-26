"""Leaderboard persistence (JSON file storage)."""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from tetris.logger import get_logger
from tetris.settings import HUMAN_STATS_PATH, LEADERBOARD_PATH, LEADERBOARD_SIZE


def load_leaderboard() -> list[dict[str, Any]]:
    """Load and normalize the leaderboard.

    Tolerates missing file, corrupt JSON, and legacy list/tuple entries
    (converted to dict form). Returns an empty list on any error.
    """
    path = Path(LEADERBOARD_PATH)
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text())
        return [
            d
            if isinstance(d, dict)
            else {
                "name": d[0],
                "score": d[1],
                "level": 0,
                "lines": 0,
                "generator": "-",
                "mode": "-",
                "speed_mode": "normal",
                "date": "Unknown",
            }
            for d in data
        ]
    except (OSError, json.JSONDecodeError):
        return []


def save_score(
    name: str,
    score: int,
    level: int,
    lines: int,
    generator: str = "",
    mode: str = "",
    speed_mode: str = "",
    seed: int | None = None,
) -> None:
    """Append a score, sort descending, and persist the top entries."""
    scores = load_leaderboard()
    scores.append(
        {
            "name": name,
            "score": score,
            "level": level,
            "lines": lines,
            "generator": generator,
            "mode": mode,
            "speed_mode": speed_mode,
            "seed": seed,
            "date": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M"),
        }
    )
    scores.sort(key=lambda x: x["score"], reverse=True)
    try:
        Path(LEADERBOARD_PATH).write_text(json.dumps(scores[:LEADERBOARD_SIZE], indent=4))
    except OSError as e:
        get_logger("storage").error("Save error: %s", e)


def load_human_games() -> list[dict[str, Any]]:
    """Load all recorded human games. Returns an empty list on any error."""
    path = Path(HUMAN_STATS_PATH)
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text())
        return data if isinstance(data, list) else []
    except (OSError, json.JSONDecodeError):
        return []


def save_human_game(name: str, score: int, level: int, lines: int, tetrominos: int, seed: int | None = None) -> None:
    """Append a human game record to the stats log (unbounded)."""
    games = load_human_games()
    games.append(
        {
            "name": name,
            "score": score,
            "level": level,
            "lines": lines,
            "tetrominos": tetrominos,
            "seed": seed,
            "date": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M"),
        }
    )
    try:
        Path(HUMAN_STATS_PATH).write_text(json.dumps(games, indent=4))
    except OSError as e:
        get_logger("storage").error("Human stats save error: %s", e)
