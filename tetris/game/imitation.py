"""Placement recorder for imitation warm-start (roadmap #5).

Writes one JSONL record per locked piece during human or god-level
El-Tetris bot gameplay: ``{type: "game", seed, handicap, ts}`` at game
start, ``{type: "move", piece, rot, x, hold}`` per lock, and
``{type: "game_end", score, tetris, triple, lines, pieces}`` when a
recorded game ends. The AI pretrainer (``tetris.ai.imitation``) replays
these games to pre-train the V-network before RL.

Human games write to ``data/human/``, bot games to ``data/bot/`` — one
JSONL file per game (``game_000001.jsonl``, ``game_000002.jsonl``, ...),
separate directories so the two data sources stay unpolluted. Only
``HumanState`` and god-level ``ElTetrisState`` attach a recorder — AI and
MCP states never do (same architectural guarantee as human stats).
"""

from __future__ import annotations

import glob
import json
import os
import time
from typing import IO

from tetris.logger import get_logger
from typing_extensions import Self

_logger = get_logger("imitation")


def next_game_path(dir_path: str) -> str:
    """First free ``game_XXXXXX.jsonl`` path in ``dir_path``.

    Sequential index starting at 1, counting existing ``game_*.jsonl``
    files. If the computed path already exists (manual copy, race), a
    numeric suffix ``-2``, ``-3``, ... is appended until the path is
    free — an existing file is never overwritten.
    """
    existing = {os.path.basename(p) for p in glob.glob(os.path.join(dir_path, "game_*.jsonl"))}
    i = len(existing) + 1
    while True:
        name = f"game_{i:06d}.jsonl"
        if name not in existing:
            return os.path.join(dir_path, name)
        i += 1


class PlacementsLog:
    """JSONL log of piece placements, one file per game.

    Two modes:

    - ``path=`` (single-file mode): append all games to one JSONL file —
      the historical layout, used by tests and explicit overrides.
    - ``dir=`` (per-game mode): ``start_game`` opens a fresh
      ``game_XXXXXX.jsonl`` in the directory and writes the header;
      ``record``/``end_game`` append to that file.

    One instance per human game. Call :meth:`start_game` once, then
    :meth:`record` after each locked piece. File errors are best-effort:
    they never crash gameplay.
    """

    def __init__(self, path: str | None = None, dir: str | None = None) -> None:
        if path is None and dir is None:
            raise ValueError("PlacementsLog requires path or dir")
        self.path = path
        self.dir = dir
        self._fh: IO[str] | None = None

    def start_game(self, seed: int | None, handicap: int) -> None:
        """Write the game header record (seed, handicap, timestamp).

        In per-game mode this opens the game's own file first.
        """
        if self.dir is not None:
            try:
                os.makedirs(self.dir, exist_ok=True)
                self._fh = open(next_game_path(self.dir), "a", encoding="utf-8")  # noqa: SIM115 — append-only log, handle kept open per game
            except OSError as exc:
                _logger.error("PlacementsLog open failed: %s", exc)
                self._fh = None
                return
        self._write({"type": "game", "seed": seed, "handicap": handicap, "ts": int(time.time())})

    def record(self, piece: str, rot: int, x: int, hold: bool) -> None:
        """Append one locked-piece record."""
        self._write({"type": "move", "piece": piece, "rot": rot, "x": x, "hold": hold})

    def end_game(self, score: int, tetris: int, triple: int, lines: int, pieces: int) -> None:
        """Append the game-end summary record (for bot-game ranking)."""
        self._write(
            {
                "type": "game_end",
                "score": score,
                "tetris": tetris,
                "triple": triple,
                "lines": lines,
                "pieces": pieces,
            }
        )

    def _write(self, record: dict) -> None:
        """Append one JSON line, opening the file lazily. Best-effort."""
        try:
            if self._fh is None:
                if self.dir is not None:
                    return  # per-game mode: no game started, nothing to write to
                assert self.path is not None  # single-file mode requires a path
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


def read_placements(path: str) -> list[dict]:
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


def read_placements_dir(dir_path: str) -> list[dict]:
    """Read all ``game_*.jsonl`` files in ``dir_path``, in game order.

    Files are sorted by filename (``game_000001`` < ``game_000002`` ...),
    so the concatenated record stream preserves game order. Missing
    directory → ``[]``; malformed lines are skipped (same contract as
    :func:`read_placements`). Non-``game_*.jsonl`` files are ignored.
    """
    records: list[dict] = []
    try:
        names = sorted(glob.glob(os.path.join(dir_path, "game_*.jsonl")))
    except OSError:
        return []
    for name in names:
        records.extend(read_placements(name))
    return records
