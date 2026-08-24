"""Piece provider: tetromino spawn strategies with record/replay support.

Class hierarchy:

- ``PieceGenerator`` — abstract base for all spawn strategies.
- ``RandomGenerator`` — uniform random spawns.
- ``BagGenerator`` — generic bag generator (N copies of each tetromino).
  - ``SevenBagGenerator`` — 7-bag (1 copy each).
- ``ThirtyFiveBagGenerator`` — 35-bag (5 copies each).
- ``WeightedGenerator`` — weighted random with anti-repeat rebalancing.
- ``ReplayGenerator`` — serve from a saved sequence, exhaustible.
- ``PieceProvider`` — facade that owns curriculum state, first-piece
  safety, replay recording, and delegates to a generator.

Normal mode: every spawned piece type is appended to the recorded
sequence and saved to disk on game exit.

Replay mode: piece types are served from a previously saved sequence.
When the saved sequence is exhausted, the provider switches to the
configured fallback generator (random/7-bag/35-bag) and begins
recording so the session's pieces are captured for future replays.
"""

from __future__ import annotations

import json
import random
from abc import ABC, abstractmethod
from pathlib import Path

from tetris.logger import get_logger
from tetris.game.shapes import SHAPES_TYPES
from tetris.settings import FIRST_PIECE_TYPES, REPLAY_PATH

_logger = get_logger("piece_provider")

# --- Weighted generator tuning ----------------------------------------------
_WT_DECAY = 0.5  # selected piece weight *= _WT_DECAY
_WT_BOOST = 0.1  # every other piece weight += _WT_BOOST
_WT_MIN = 0.1  # weight floor (never zero/negative)
_WT_INIT = 1.0  # starting weight for all pieces


# ---------------------------------------------------------------------------
# Generators
# ---------------------------------------------------------------------------


class PieceGenerator(ABC):
    """Abstract tetromino spawn strategy.

    Generators receive ``(pool, is_first)`` from the facade and own only
    their own generation internals (bag, queue, etc.). Curriculum and
    first-piece state live on :class:`PieceProvider`.
    """

    @abstractmethod
    def next(self, pool: list[str], is_first: bool) -> str | None:
        """Return the next piece type from ``pool``.

        Args:
            pool: Active piece pool (``allowed_types`` or all SHAPES keys).
            is_first: ``True`` if this is the first piece of a game — apply
                the first-piece safety restriction (I, J, L, T only).

        Returns:
            Piece type string, or ``None`` if the generator is exhausted
            (replay-only; bag and random never return ``None``).
        """

    @abstractmethod
    def reset(self) -> None:
        """Clear internal state (bag, etc.) for a new game."""

    @property
    @abstractmethod
    def bag_remaining(self) -> list[str]:
        """Pieces left in the current bag (empty for non-bag generators)."""


class RandomGenerator(PieceGenerator):
    """Uniform random spawns with first-piece safety filter."""

    def next(self, pool: list[str], is_first: bool) -> str:
        if is_first:
            safe = [t for t in pool if t in FIRST_PIECE_TYPES]
            if safe:
                return random.choice(safe)
        return random.choice(pool)

    def reset(self) -> None:
        pass

    @property
    def bag_remaining(self) -> list[str]:
        return []


class BagGenerator(PieceGenerator):
    """Generic bag generator: ``pool * copies`` pieces, shuffled.

    The first-piece swap keeps the bag complete: if the popped piece is
    not in the safe set, swap it with an eligible piece still in the bag.
    """

    def __init__(self, copies: int) -> None:
        self._copies = copies
        self._bag: list[str] = []

    def next(self, pool: list[str], is_first: bool) -> str:
        if not self._bag:
            self._bag = pool * self._copies
            random.shuffle(self._bag)
        piece = self._bag.pop()
        if is_first and piece not in FIRST_PIECE_TYPES:
            for i, t in enumerate(self._bag):
                if t in FIRST_PIECE_TYPES:
                    self._bag[i] = piece
                    piece = t
                    break
        return piece

    def reset(self) -> None:
        self._bag = []

    @property
    def bag_remaining(self) -> list[str]:
        return self._bag[:]


class SevenBagGenerator(BagGenerator):
    """7-bag: each tetromino appears once per bag."""

    def __init__(self) -> None:
        super().__init__(copies=1)


class ThirtyFiveBagGenerator(BagGenerator):
    """35-bag: each tetromino appears 5 times per bag."""

    def __init__(self) -> None:
        super().__init__(copies=5)


class WeightedGenerator(PieceGenerator):
    """Weighted random spawns with anti-repeat rebalancing.

    Each piece starts at weight ``_WT_INIT``. After a piece is selected,
    its weight is halved (``_WT_DECAY``) and every other piece's weight
    is increased by ``_WT_BOOST``. Weights never drop below ``_WT_MIN``.
    This creates a soft anti-drought/anti-flood effect: pieces seen
    recently become less likely, pieces absent for a while become more
    likely.
    """

    def __init__(self) -> None:
        self._weights: dict[str, float] = {}

    def next(self, pool: list[str], is_first: bool) -> str:
        if not self._weights:
            self._weights = {t: _WT_INIT for t in SHAPES_TYPES}
        if is_first:
            safe = [t for t in pool if t in FIRST_PIECE_TYPES]
            if safe:
                weights = [self._weights[t] for t in safe]
                piece = random.choices(safe, weights=weights)[0]
            else:
                weights = [self._weights[t] for t in pool]
                piece = random.choices(pool, weights=weights)[0]
        else:
            weights = [self._weights[t] for t in pool]
            piece = random.choices(pool, weights=weights)[0]
        self._rebalance(piece)
        return piece

    def reset(self) -> None:
        self._weights = {}

    @property
    def bag_remaining(self) -> list[str]:
        return []

    @property
    def weights(self) -> dict[str, float]:
        """Current weight per tetromino type (copy for read-only access)."""
        return dict(self._weights)

    def _rebalance(self, piece: str) -> None:
        for t in self._weights:
            if t == piece:
                self._weights[t] = max(self._weights[t] * _WT_DECAY, _WT_MIN)
            else:
                self._weights[t] += _WT_BOOST


class ReplayGenerator(PieceGenerator):
    """Serve piece types from a saved JSON sequence.

    Once the queue is exhausted, ``next`` returns ``None`` so the facade
    can switch to the fallback generator. Curriculum and first-piece
    filters are applied internally by skipping queue pieces that don't
    match.
    """

    def __init__(self, path: Path | str) -> None:
        self._queue = self._load(path)
        self._idx = 0

    def next(self, pool: list[str], is_first: bool) -> str | None:
        while self._idx < len(self._queue):
            piece = self._queue[self._idx]
            self._idx += 1
            if piece not in pool:
                continue
            if is_first and piece not in FIRST_PIECE_TYPES:
                continue
            return piece
        return None

    def reset(self) -> None:
        pass

    @property
    def bag_remaining(self) -> list[str]:
        return []

    @staticmethod
    def _load(path: Path | str) -> list[str]:
        p = Path(path)
        if not p.exists():
            return []
        try:
            return json.loads(p.read_text())
        except (json.JSONDecodeError, OSError):
            return []


def _make_generator(name: str) -> PieceGenerator:
    """Factory: map a settings string to a concrete generator."""
    match name:
        case "7bag":
            return SevenBagGenerator()
        case "35bag":
            return ThirtyFiveBagGenerator()
        case "weighted":
            return WeightedGenerator()
        case _:
            return RandomGenerator()


# ---------------------------------------------------------------------------
# Facade
# ---------------------------------------------------------------------------


class PieceProvider:
    """Facade controlling tetromino spawning.

    Owns curriculum state (``allowed_types``), first-piece safety, and
    replay recording. Delegates piece generation to a
    :class:`PieceGenerator`. In replay mode, delegates to
    :class:`ReplayGenerator` until exhausted, then switches to the
    configured fallback generator.

    Parameters
    ----------
    mode : str
        ``"normal"`` — random/bag spawns, record each piece.
        ``"replay"`` — serve from saved sequence, then fallback + record.
    path : Path
        File path for the recorded/replayed piece sequence.
    allowed_types : list[str] | None
        Optional restriction on the piece pool (curriculum).
    generator : str
        ``"random"``, ``"7bag"``, ``"35bag"``, or ``"weighted"`` spawn strategy.
    """

    def __init__(
        self,
        mode: str = "normal",
        path: Path | str = REPLAY_PATH,
        allowed_types: list[str] | None = None,
        generator: str = "random",
    ) -> None:
        self.mode = mode
        self.path = Path(path)
        self.allowed_types: list[str] | None = allowed_types
        self._generator_name = generator
        self._recorded: list[str] = []
        self._first_piece = True
        self._fallback = _make_generator(generator)
        self._generator: PieceGenerator = ReplayGenerator(path) if mode == "replay" else self._fallback

    def reset(self) -> None:
        """Re-arm the first-piece restriction and clear the active generator.

        Called by AIState between episodes so each game starts with a
        safe piece (I, J, L, or T).
        """
        self._first_piece = True
        self._generator.reset()

    def next_type(self) -> str:
        """Return the next piece type, applying generator and first-piece rules."""
        pool = self.allowed_types if self.allowed_types is not None else SHAPES_TYPES
        piece = self._generator.next(pool, self._first_piece)
        if piece is None:  # replay exhausted → switch to fallback
            self._generator = self._fallback
            piece = self._generator.next(pool, self._first_piece)
            if piece is None:
                raise RuntimeError("piece_provider: fallback generator exhausted")
        self._first_piece = False
        self._recorded.append(piece)
        _logger.debug("Spawned %s | bag=%s", piece, self._generator.bag_remaining)
        return piece

    def set_allowed_types(self, types: list[str]) -> None:
        """Restrict the spawn pool and reset the active generator.

        Args:
            types: Piece types to allow (e.g. ``["O"]`` for curriculum level 0).
        """
        self.allowed_types = types
        self._generator.reset()

    def save(self) -> None:
        """Persist the recorded piece sequence to disk."""
        if not self._recorded:
            return
        self.path.write_text(json.dumps(self._recorded))

    @property
    def bag_remaining(self) -> list[str]:
        """Remaining pieces in the current bag (empty if random or bag exhausted)."""
        return self._generator.bag_remaining

    @property
    def generator(self) -> str:
        """Configured generator name (``"random"``, ``"7bag"``, ``"35bag"``, ``"weighted"``)."""
        return self._generator_name

    @property
    def weights(self) -> dict[str, float]:
        """Current per-type weights (weighted generator only, empty dict otherwise)."""
        gen = self._generator
        if isinstance(gen, WeightedGenerator):
            return gen.weights
        return {}
