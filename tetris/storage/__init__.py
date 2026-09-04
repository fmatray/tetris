"""Leaderboard persistence (JSON file storage)."""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from tetris.logger import get_logger
from tetris.settings import HUMAN_STATS_PATH, LEADERBOARD_PATH, LEADERBOARD_SIZE, LEADERBOARD_MODES


def load_leaderboard(mode: str | None = None) -> list[dict[str, Any]]:
    """Load and normalize the leaderboard.

    Tolerates missing file, corrupt JSON, and legacy list/tuple entries
    (converted to dict form). Returns an empty list on any error.
    ``mode`` (marathon/sprint/blitz) filters to that game mode; entries
    without a ``game_mode`` field count as marathon. ``None`` returns
    everything (legacy behavior).
    """
    path = Path(LEADERBOARD_PATH)
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text())
        entries = [
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
    if mode is None:
        return entries
    return [e for e in entries if e.get("game_mode", "marathon") == mode]


def _sort_leaderboard(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Sort per game mode: sprint by time ascending, others by score."""

    def key(e: dict[str, Any]) -> tuple:
        if e.get("game_mode") == "sprint":
            t = e.get("time_s")
            return (0, t if t is not None else float("inf"), -e["score"])
        return (1, 0.0, -e["score"])

    entries.sort(key=key)
    return entries


def save_score(
    name: str,
    score: int,
    level: int,
    lines: int,
    generator: str = "",
    mode: str = "",
    speed_mode: str = "",
    seed: int | None = None,
    game_mode: str = "marathon",
    time_s: float | None = None,
) -> None:
    """Append a score, keep the top entries per game mode, and persist."""
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
            "game_mode": game_mode,
            "time_s": time_s,
            "date": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M"),
        }
    )
    kept: list[dict[str, Any]] = []
    for gm in LEADERBOARD_MODES:
        group = [e for e in scores if e.get("game_mode", "marathon") == gm]
        kept.extend(_sort_leaderboard(group)[:LEADERBOARD_SIZE])
    try:
        Path(LEADERBOARD_PATH).write_text(json.dumps(kept, indent=4))
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


def save_human_game(
    name: str,
    score: int,
    level: int,
    lines: int,
    tetrominos: int,
    seed: int | None = None,
    time_s: float | None = None,
    pps: float | None = None,
    finesse_faults: int | None = None,
) -> None:
    """Append a human game record to the stats log (unbounded)."""
    games = load_human_games()
    entry: dict[str, Any] = {
        "name": name,
        "score": score,
        "level": level,
        "lines": lines,
        "tetrominos": tetrominos,
        "seed": seed,
        "date": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M"),
    }
    if time_s is not None:
        entry["time_s"] = round(time_s, 2)
    if pps is not None:
        entry["pps"] = round(pps, 2)
    if finesse_faults is not None:
        entry["finesse_faults"] = finesse_faults
    games.append(entry)
    try:
        Path(HUMAN_STATS_PATH).write_text(json.dumps(games, indent=4))
    except OSError as e:
        get_logger("storage").error("Human stats save error: %s", e)
