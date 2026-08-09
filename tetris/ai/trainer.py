"""Training log: per-episode statistics persisted as JSON.

Tracks learning progress across episodes and sessions. The log is
loaded on startup so the AI resumes from where it left off, and
updated after every episode.
"""

from __future__ import annotations

import json
import os
from datetime import datetime

from tetris.settings import LOG_PATH


class TrainingLog:
    """Append-only per-episode log with rolling summary stats.

    The full JSON file is rewritten each save (small data, ~hundreds of
    episodes). Summary stats (avg/best score, best episode, line clears)
    are derived from the log entries.
    """

    def __init__(self, path: str = LOG_PATH) -> None:
        self.path = path
        self.episodes: list[dict] = []
        self._load()

    def _load(self) -> None:
        if os.path.exists(self.path):
            try:
                with open(self.path) as f:
                    self.episodes = json.load(f)
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
                "timestamp": datetime.now().isoformat(),
            }
        )
        self._save()

    def _save(self) -> None:
        try:
            with open(self.path, "w") as f:
                json.dump(self.episodes, f, indent=2)
        except OSError as e:
            print(f"Training log save error: {e}")

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