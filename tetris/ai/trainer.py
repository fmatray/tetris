"""Training log: per-episode statistics persisted as JSON.

Tracks learning progress across episodes and sessions. The log is
loaded on startup so the AI resumes from where it left off, and
updated after every episode.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, TypedDict

from tetris.logger import get_logger
from tetris.settings import LOG_PATH


class EpisodeRecord(TypedDict):
    """A single episode's training metrics for the log."""

    episode: int
    score: int
    lines: int
    level: int
    steps: int
    epsilon: float
    loss: float
    timestamp: str


class TrainingLog:
    """Append-only per-episode log with rolling summary stats.

    The full JSON file is rewritten every ``_SAVE_INTERVAL`` episodes
    (default 10) for efficiency. ``flush()`` forces a save on exit.
    Summary stats (avg/best score, best episode, line clears) are
    derived from the log entries.
    """

    _SAVE_INTERVAL = 10

    def __init__(self, path: str = LOG_PATH) -> None:
        """Load the training log from disk (or start empty if missing)."""
        self.path = path
        self.episodes: list[dict[str, Any]] = []
        self._load()

    def _load(self) -> None:
        path = Path(self.path)
        if path.exists():
            try:
                self.episodes = json.loads(path.read_text())
            except (OSError, json.JSONDecodeError):
                self.episodes = []

    def record(
        self,
        episode: int,
        score: int,
        lines: int,
        level: int,
        steps: int,
        epsilon: float,
        loss: float,
    ) -> None:
        """Append an episode record and persist to disk."""
        entry: EpisodeRecord = {
            "episode": episode,
            "score": score,
            "lines": lines,
            "level": level,
            "steps": steps,
            "epsilon": epsilon,
            "loss": loss,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self.episodes.append(dict(entry))
        if len(self.episodes) % self._SAVE_INTERVAL == 0:
            self._save()

    def flush(self) -> None:
        """Force-save the log (call on exit)."""
        self._save()

    def _save(self) -> None:
        try:
            Path(self.path).write_text(json.dumps(self.episodes, indent=2))
        except OSError as e:
            get_logger("trainer").error("Training log save error: %s", e)

    def _safe_sum(self, key: str) -> int:
        """Sum of a metric across all episodes (0 if empty)."""
        return sum(e[key] for e in self.episodes)

    def _safe_max(self, key: str) -> int:
        """Max of a metric across all episodes (0 if empty)."""
        return max((e[key] for e in self.episodes), default=0)

    def _safe_avg(self, key: str) -> float:
        """Mean of a metric across all episodes (0.0 if empty)."""
        if not self.episodes:
            return 0.0
        return sum(e[key] for e in self.episodes) / len(self.episodes)

    def _last_n_avg(self, key: str, n: int = 100) -> float:
        """Mean of a metric over the last *n* episodes (0.0 if empty)."""
        recent = self.episodes[-n:]
        if not recent:
            return 0.0
        return sum(e[key] for e in recent) / len(recent)

    @property
    def total_episodes(self) -> int:
        """Total number of logged episodes."""
        return len(self.episodes)

    @property
    def avg_score(self) -> float:
        """Mean score across all episodes (0 if empty)."""
        return self._safe_avg("score")

    @property
    def best_score(self) -> int:
        """Highest single-episode score (0 if empty)."""
        return self._safe_max("score")

    @property
    def total_lines(self) -> int:
        """Sum of lines cleared across all episodes."""
        return self._safe_sum("lines")

    @property
    def total_steps(self) -> int:
        """Sum of piece-placements across all episodes."""
        return self._safe_sum("steps")

    @property
    def avg_level(self) -> float:
        """Mean final level across all episodes (0 if empty)."""
        return self._safe_avg("level")

    @property
    def best_level(self) -> int:
        """Highest final level reached (0 if empty)."""
        return self._safe_max("level")

    @property
    def total_score(self) -> int:
        """Sum of scores across all episodes."""
        return self._safe_sum("score")

    @property
    def best_lines(self) -> int:
        """Most lines cleared in a single episode (0 if empty)."""
        return self._safe_max("lines")

    @property
    def avg_lines(self) -> float:
        """Mean lines cleared per episode (0 if empty)."""
        return self._safe_avg("lines")

    @property
    def best_steps(self) -> int:
        """Most piece-placements in a single episode (0 if empty)."""
        return self._safe_max("steps")

    @property
    def avg_steps(self) -> float:
        """Mean piece-placements per episode (0 if empty)."""
        return self._safe_avg("steps")

    @property
    def last_100_avg(self) -> float:
        """Average score over the last 100 episodes (recent performance)."""
        return self._last_n_avg("score")

    @property
    def last_100_avg_lines(self) -> float:
        """Mean lines cleared over the last 100 episodes (0 if empty)."""
        return self._last_n_avg("lines")

    @property
    def last_100_avg_level(self) -> float:
        """Mean final level over the last 100 episodes (0 if empty)."""
        return self._last_n_avg("level")

    @property
    def last_100_avg_steps(self) -> float:
        """Mean piece-placements over the last 100 episodes (0 if empty)."""
        return self._last_n_avg("steps")

    def _trend(self, key: str) -> str:
        """Compare last-100 avg vs previous-100 avg for a metric.

        Returns 'up', 'down', or 'stable' based on whether the recent
        average improved, declined, or stayed within 5% of the previous.
        Needs at least 200 episodes for a meaningful comparison.
        """
        if len(self.episodes) < 200:
            return "stable"
        recent = self.episodes[-100:]
        previous = self.episodes[-200:-100]
        recent_avg = sum(e[key] for e in recent) / len(recent)
        prev_avg = sum(e[key] for e in previous) / len(previous)
        if prev_avg == 0:
            return "up" if recent_avg > 0 else "stable"
        ratio = recent_avg / prev_avg
        if ratio > 1.05:
            return "up"
        if ratio < 0.95:
            return "down"
        return "stable"
