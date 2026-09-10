#!/usr/bin/env python3
"""Split legacy flat placement logs into one file per game.

Legacy format (pre-2026-09): a single JSONL stream per player type where
``game`` / ``move`` / ``game_end`` records are grouped implicitly by line
order. New format: one ``game_<N>.jsonl`` file per game under
``data/human/`` and ``data/bot/``.

This script migrates the legacy files in place:

1. Streams the legacy file line by line.
2. Opens a new per-game output file at each ``{"type": "game"}`` header.
3. Appends ``move`` / ``game_end`` records to the current game file.
4. Renames the legacy file to ``<name>.backup.jsonl`` (kept as backup).

Idempotent: if the legacy file is already renamed to ``.backup.jsonl``,
the script reports nothing to do. Existing per-game files are never
overwritten (a fresh game file is picked per game index).

Usage:
    python scripts/split_placements.py [--dry-run]

Read-only with ``--dry-run``: prints what would be done, changes nothing.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import TextIO

from tetris.settings import BOT_PLACEMENTS_DIR, DATA_DIR, HUMAN_PLACEMENTS_DIR

LEGACY_FILES = [
    (os.path.join(DATA_DIR, "human_placements.jsonl"), HUMAN_PLACEMENTS_DIR, "human"),
    (os.path.join(DATA_DIR, "bot_placements.jsonl"), BOT_PLACEMENTS_DIR, "bot"),
]


def _next_game_path(dir_path: str) -> str:
    """Return the next free ``game_<N>.jsonl`` path in ``dir_path``."""
    existing = [f for f in os.listdir(dir_path) if f.startswith("game_") and f.endswith(".jsonl")]
    index = len(existing) + 1
    while os.path.exists(os.path.join(dir_path, f"game_{index:06d}.jsonl")):
        index += 1
    return os.path.join(dir_path, f"game_{index:06d}.jsonl")


def split_file(legacy_path: str, dir_path: str, label: str, dry_run: bool) -> int:
    """Split one legacy placements file into per-game files.

    Returns the number of games written (0 if nothing to do).
    """
    backup_path = legacy_path + ".backup.jsonl"
    if not os.path.exists(legacy_path):
        if os.path.exists(backup_path):
            print(f"[{label}] already migrated ({os.path.basename(backup_path)} present) — nothing to do")
        else:
            print(f"[{label}] no legacy file at {legacy_path} — nothing to do")
        return 0
    if dry_run:
        print(f"[{label}] would split {legacy_path} into {dir_path}/game_*.jsonl and rename to {backup_path}")
        return 0

    os.makedirs(dir_path, exist_ok=True)
    games = 0
    current: TextIO | None = None
    with open(legacy_path, encoding="utf-8") as src:
        for line in src:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                print(f"[{label}] skipping malformed line: {line[:80]!r}", file=sys.stderr)
                continue
            if record.get("type") == "game":
                current = open(_next_game_path(dir_path), "a", encoding="utf-8")  # noqa: SIM115 — one handle per game, closed on game_end
                games += 1
            if current is not None:
                current.write(line + "\n")
                if record.get("type") == "game_end":
                    current.close()
                    current = None
    if current is not None:
        current.close()
    os.rename(legacy_path, backup_path)
    print(f"[{label}] split {games} games into {dir_path}/, legacy renamed to {backup_path}")
    return games


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dry-run", action="store_true", help="report what would be done without changing anything")
    args = parser.parse_args()
    total = 0
    for legacy_path, dir_path, label in LEGACY_FILES:
        total += split_file(legacy_path, dir_path, label, args.dry_run)
    print(f"total games written: {total}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
