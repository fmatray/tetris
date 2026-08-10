"""Piece provider: records and replays tetromino spawn sequences.

Normal mode: every spawned piece type is appended to the recorded
sequence and saved to disk on game exit.

Replay mode: piece types are served from a previously saved sequence.
When the saved sequence is exhausted, the provider falls back to
random spawns (just like Normal mode), and also begins recording so
the session's pieces are captured for future replays.
"""

from __future__ import annotations

import json
import random
from pathlib import Path

from tetris.logger import get_logger
from tetris.settings import REPLAY_PATH, SHAPES

_logger = get_logger("piece_provider")

class PieceProvider:
    """Controls tetromino spawning: random, recorded, or replayed.

    Parameters
    ----------
    mode : str
        ``"normal"`` — random spawns, record each piece.
        ``"replay"`` — serve from saved sequence, then random + record.
    path : Path
        File path for the recorded/replayed piece sequence.
    """

    def __init__(
        self,
        mode: str = "normal",
        path: Path | str = REPLAY_PATH,
        allowed_types: list[str] | None = None,
        generator: str = "random",  # "random" or "7bag"
    ) -> None:
        self.mode = mode
        self.path = Path(path)
        self.allowed_types: list[str] | None = allowed_types
        self.generator = generator
        self._bag: list[str] = []
        self._recorded: list[str] = []
        self._replay_queue: list[str] = []
        self._replay_idx = 0

        if mode == "replay":
            self._load_replay()

    # --- Public API ----------------------------------------------------

    def next_type(self) -> str:
        if self.mode == "replay" and self._replay_idx < len(self._replay_queue):
            piece_type = self._replay_queue[self._replay_idx]
            self._replay_idx += 1
            # Curriculum: skip pieces outside allowed_types
            if self.allowed_types is not None and piece_type not in self.allowed_types:
                return self.next_type()
            self._recorded.append(piece_type)
            return piece_type

        # Normal mode, or replay exhausted → generator-based spawn
        pool = self.allowed_types if self.allowed_types is not None else list(SHAPES.keys())
        if self.generator == "7bag":
            piece_type = self._bag_next()
        else:
            piece_type = random.choice(pool)
        self._recorded.append(piece_type)
        _logger.debug("Spawned %s | bag=%s", piece_type, self._bag)
        return piece_type

    def set_allowed_types(self, types: list[str]) -> None:
        self.allowed_types = types
        self._bag = []  # force refill with new pool


    def _bag_next(self) -> str:
        pool = self.allowed_types if self.allowed_types is not None else list(SHAPES.keys())
        if not self._bag:
            self._bag = pool[:]
            random.shuffle(self._bag)
        return self._bag.pop()

    def save(self) -> None:
        """Persist the recorded piece sequence to disk."""
        if not self._recorded:
            return
        self.path.write_text(json.dumps(self._recorded))

    @property
    def replay_remaining(self) -> int:
        """Number of replay pieces still queued (0 in normal mode)."""
        if self.mode != "replay":
            return 0
        return max(0, len(self._replay_queue) - self._replay_idx)

    @property
    def bag_remaining(self) -> list[str]:
        """Remaining pieces in the current 7-bag (empty if random or bag exhausted)."""
        return self._bag[:]

    # --- Internal -----------------------------------------------------

    def _load_replay(self) -> None:
        """Load the saved piece sequence for replay mode."""
        if not self.path.exists():
            return
        try:
            self._replay_queue = json.loads(self.path.read_text())
        except (json.JSONDecodeError, OSError):
            self._replay_queue = []