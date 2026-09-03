"""Human placement recorder for imitation warm-start (roadmap #5).

Writes one JSONL record per locked piece during human gameplay:
``{type: "game", seed, handicap, ts}`` at game start, then
``{type: "move", piece, rot, x, hold}`` per lock. The AI pretrainer
(``tetris.ai.imitation``) replays these games to pre-train the V-network
before RL. Only ``HumanState`` attaches a recorder — AI, El-Tetris, and
MCP states never do (same architectural guarantee as human stats).
"""

from __future__ import annotations

import json
import os
import time
from typing import IO

from tetris.logger import get_logger
from tetris.settings import PLACEMENTS_PATH
from typing_extensions import Self

_logger = get_logger("imitation")


class PlacementsLog:
    """JSONL append-only log of human piece placements.

    One instance per human game. Call :meth:`start_game` once, then
    :meth:`record` after each locked piece. File errors are best-effort:
    they never crash gameplay.
    """

    def __init__(self, path: str = PLACEMENTS_PATH) -> None:
        self.path = path
        self._fh: IO[str] | None = None

    def start_game(self, seed: int | None, handicap: int) -> None:
        """Append the game header record (seed, handicap, timestamp)."""
        self._write({"type": "game", "seed": seed, "handicap": handicap, "ts": int(time.time())})

    def record(self, piece: str, rot: int, x: int, hold: bool) -> None:
        """Append one locked-piece record."""
        self._write({"type": "move", "piece": piece, "rot": rot, "x": x, "hold": hold})

    def _write(self, record: dict) -> None:
        """Append one JSON line, opening the file lazily. Best-effort."""
        try:
            if self._fh is None:
                os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
                self._fh = open(self.path, "a", encoding="utf-8")  # noqa: SIM115 — append-only log, handle kept open per game
            self._fh.write(json.dumps(record) + "\n")
            self._fh.flush()
        except OSError as exc:
            _logger.error("PlacementsLog write failed: %s", exc)
            self._fh = None

    def close(self) -> None:
        """Close the file handle (called on state exit)."""
        if self._fh is not None:
            try:
                self._fh.close()
            except OSError:
                pass
            self._fh = None

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()


def read_placements(path: str = PLACEMENTS_PATH) -> list[dict]:
    """Read all records from a placements JSONL file.

    Returns ``[]`` if the file is missing or unreadable. Malformed lines
    are skipped (best-effort, matching the best-effort write contract).
    """
    records: list[dict] = []
    try:
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    except OSError:
        return []
    return records
