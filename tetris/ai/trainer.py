"""Training log: per-episode statistics persisted as JSON.

Tracks learning progress across episodes and sessions. The log is
loaded on startup so the AI resumes from where it left off, and
updated after every episode.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from tetris.logger import get_logger
from tetris.settings import LOG_PATH


class TrainingLog:
    """Append-only per-episode log with rolling summary stats.

    The full JSON file is rewritten every ``_SAVE_INTERVAL`` episodes
    (default 10) for efficiency. ``flush()`` forces a save on exit.
    Summary stats (avg/best score, best episode, line clears) are
    derived from the log entries.
    """

    _SAVE_INTERVAL = 10

    def __init__(self, path: str = LOG_PATH) -> None:
        self.path = path
        self.episodes: list[dict] = []
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
        self.episodes.append(
            {
                "episode": episode,
                "score": score,
                "lines": lines,
                "level": level,
                "steps": steps,
                "epsilon": epsilon,
                "loss": loss,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        )
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

    # --- Summary stats ---------------------------------------------------

    @property
    def total_episodes(self) -> int:
        return len(self.episodes)

    @property
    def avg_score(self) -> float:
        if not self.episodes:
            return 0.0
        return sum(e["score"] for e in self.episodes) / len(self.episodes)

    @property
    def best_score(self) -> int:
        if not self.episodes:
            return 0
        return max(e["score"] for e in self.episodes)

    @property
    def total_lines(self) -> int:
        return sum(e["lines"] for e in self.episodes)

    @property
    def total_steps(self) -> int:
        return sum(e["steps"] for e in self.episodes)

    @property
    def avg_level(self) -> float:
        if not self.episodes:
            return 0.0
        return sum(e["level"] for e in self.episodes) / len(self.episodes)

    @property
    def best_level(self) -> int:
        if not self.episodes:
            return 0
        return max(e["level"] for e in self.episodes)

    @property
    def total_score(self) -> int:
        return sum(e["score"] for e in self.episodes)

    @property
    def best_lines(self) -> int:
        if not self.episodes:
            return 0
        return max(e["lines"] for e in self.episodes)

    @property
    def avg_lines(self) -> float:
        if not self.episodes:
            return 0.0
        return sum(e["lines"] for e in self.episodes) / len(self.episodes)

    @property
    def best_steps(self) -> int:
        if not self.episodes:
            return 0
        return max(e["steps"] for e in self.episodes)

    @property
    def avg_steps(self) -> float:
        if not self.episodes:
            return 0.0
        return sum(e["steps"] for e in self.episodes) / len(self.episodes)

    @property
    def last_100_avg(self) -> float:
        """Average score over the last 100 episodes (recent performance)."""
        recent = self.episodes[-100:]
        if not recent:
            return 0.0
        return sum(e["score"] for e in recent) / len(recent)

    @property
    def last_100_avg_lines(self) -> float:
        recent = self.episodes[-100:]
        if not recent:
            return 0.0
        return sum(e["lines"] for e in recent) / len(recent)

    @property
    def last_100_avg_level(self) -> float:
        recent = self.episodes[-100:]
        if not recent:
            return 0.0
        return sum(e["level"] for e in recent) / len(recent)

    @property
    def last_100_avg_steps(self) -> float:
        recent = self.episodes[-100:]
        if not recent:
            return 0.0
        return sum(e["steps"] for e in recent) / len(recent)

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