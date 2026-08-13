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
from tetris.settings import FIRST_PIECE_TYPES, REPLAY_PATH, SHAPES

_logger = get_logger("piece_provider")

class PieceProvider:
    """Controls tetromino spawning: random, recorded, or replayed.

    Bag generators repeat each pool piece a fixed number of times:
    7-bag = 1 copy, 35-bag = 5 copies. Everything else (shuffle, pop,
    first-piece swap) is shared.

    Parameters
    ----------
    mode : str
        ``"normal"`` — random spawns, record each piece.
        ``"replay"`` — serve from saved sequence, then random + record.
    path : Path
        File path for the recorded/replayed piece sequence.
    """

    _BAG_MULTIPLIERS: dict[str, int] = {"7bag": 1, "35bag": 5}

    def __init__(
        self,
        mode: str = "normal",
        path: Path | str = REPLAY_PATH,
        allowed_types: list[str] | None = None,
        generator: str = "random",  # "random", "7bag", or "35bag"
    ) -> None:
        self.mode = mode
        self.path = Path(path)
        self.allowed_types: list[str] | None = allowed_types
        self.generator = generator
        self._bag: list[str] = []
        self._recorded: list[str] = []
        self._first_piece = True
        self._replay_queue: list[str] = []
        self._replay_idx = 0

        if mode == "replay":
            self._load_replay()

    # --- Public API ----------------------------------------------------

    def reset(self) -> None:
        """Re-arm the first-piece restriction and clear the bag.

        Called by AIState between episodes so each game starts with a
        safe piece (I, J, L, or T).
        """
        self._first_piece = True
        self._bag = []

    def next_type(self) -> str:
        if self.mode == "replay" and self._replay_idx < len(self._replay_queue):
            piece_type = self._replay_queue[self._replay_idx]
            self._replay_idx += 1
            # Curriculum: skip pieces outside allowed_types
            if self.allowed_types is not None and piece_type not in self.allowed_types:
                return self.next_type()
            # First-piece restriction: skip queue pieces not in the safe set
            if self._first_piece and piece_type not in FIRST_PIECE_TYPES:
                return self.next_type()
            self._first_piece = False
            self._recorded.append(piece_type)
            return piece_type

        # Normal mode, or replay exhausted → generator-based spawn
        pool = self.allowed_types if self.allowed_types is not None else list(SHAPES.keys())
        if self.generator in self._BAG_MULTIPLIERS:
            piece_type = self._bag_next(pool)
        else:
            piece_type = self._first_piece_choice(pool)
        self._first_piece = False
        self._recorded.append(piece_type)
        _logger.debug("Spawned %s | bag=%s", piece_type, self._bag)
        return piece_type

    def set_allowed_types(self, types: list[str]) -> None:
        self.allowed_types = types
        self._bag = []  # force refill with new pool


    def _bag_next(self, pool: list[str]) -> str:
        if not self._bag:
            self._bag = pool * self._BAG_MULTIPLIERS[self.generator]
            random.shuffle(self._bag)
        piece = self._bag.pop()
        if self._first_piece and piece not in FIRST_PIECE_TYPES:
            # Swap the popped piece with an eligible one still in the bag
            # so the 7-bag stays complete (no duplicates, no missing pieces).
            for i, t in enumerate(self._bag):
                if t in FIRST_PIECE_TYPES:
                    self._bag[i] = piece
                    piece = t
                    break
        return piece

    def _first_piece_choice(self, pool: list[str]) -> str:
        """Pick a piece, restricting the first to the safe set when possible."""
        if self._first_piece:
            safe = [t for t in pool if t in FIRST_PIECE_TYPES]
            if safe:
                return random.choice(safe)
        return random.choice(pool)

    def save(self) -> None:
        """Persist the recorded piece sequence to disk."""
        if not self._recorded:
            return
        self.path.write_text(json.dumps(self._recorded))


    @property
    def bag_remaining(self) -> list[str]:
        """Remaining pieces in the current bag (empty if random or bag exhausted)."""
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