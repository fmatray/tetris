"""Leaderboard persistence (JSON file storage)."""

import json
import os
from datetime import datetime
from typing import Any

from tetris.settings import LEADERBOARD_PATH, LEADERBOARD_SIZE


def load_leaderboard() -> list[dict[str, Any]]:
    """Load and normalize the leaderboard.

    Tolerates missing file, corrupt JSON, and legacy list/tuple entries
    (converted to dict form). Returns an empty list on any error.
    """
    if not os.path.exists(LEADERBOARD_PATH):
        return []
    try:
        with open(LEADERBOARD_PATH) as f:
            data = json.load(f)
            return [
                d
                if isinstance(d, dict)
                else {
                    "name": d[0],
                    "score": d[1],
                    "level": 0,
                    "lines": 0,
                    "date": "Unknown",
                }
                for d in data
            ]
    except (OSError, json.JSONDecodeError):
        return []


def save_score(name: str, score: int, level: int, lines: int) -> None:
    """Append a score, sort descending, and persist the top entries."""
    scores = load_leaderboard()
    scores.append(
        {
            "name": name,
            "score": score,
            "level": level,
            "lines": lines,
            "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
        }
    )
    scores.sort(key=lambda x: x["score"], reverse=True)
    try:
        with open(LEADERBOARD_PATH, "w") as f:
            json.dump(scores[:LEADERBOARD_SIZE], f, indent=4)
    except OSError as e:
        print(f"Save error: {e}")