"""Tests for PieceProvider: normal and replay modes."""

import json

from tetris.game.piece_provider import (
    _WT_BOOST,
    _WT_DECAY,
    _WT_INIT,
    _WT_MIN,
    BagGenerator,
    PieceProvider,
    RandomGenerator,
    ReplayGenerator,
    SevenBagGenerator,
    WeightedGenerator,
)
from tetris.game.shapes import SHAPES, SHAPES_TYPES
from tetris.settings import FIRST_PIECE_TYPES


def test_normal_mode_returns_valid_types():
    provider = PieceProvider(mode="normal", path="/tmp/_test_replay.json")
    for _ in range(20):
        assert provider.next_type() in SHAPES


def test_normal_mode_records():
    provider = PieceProvider(mode="normal", path="/tmp/_test_replay.json")
    for _ in range(10):
        provider.next_type()
    assert len(provider._recorded) == 10


def test_replay_mode_serves_from_queue(tmp_path):
    path = tmp_path / "replay.json"
    saved = ["I", "O", "T", "S", "Z"]
    path.write_text(json.dumps(saved))
    provider = PieceProvider(mode="replay", path=path)
    served = [provider.next_type() for _ in range(len(saved))]
    assert served == saved


def test_replay_exhausted_falls_back_to_random(tmp_path):
    path = tmp_path / "replay.json"
    saved = ["I", "O"]
    path.write_text(json.dumps(saved))
    provider = PieceProvider(mode="replay", path=path)
    # Consume the saved sequence
    assert provider.next_type() == "I"
    assert provider.next_type() == "O"
    # Further calls should return random valid types
    for _ in range(10):
        assert provider.next_type() in SHAPES


def test_save_persists_to_file(tmp_path):
    path = tmp_path / "replay.json"
    provider = PieceProvider(mode="normal", path=path)
    pieces = [provider.next_type() for _ in range(5)]
    provider.save()
    saved = json.loads(path.read_text())
    assert saved == pieces


def test_allowed_types_restricts_pool(tmp_path):
    provider = PieceProvider(mode="normal", path=tmp_path / "c.json", allowed_types=["I", "O"])
    for _ in range(20):
        assert provider.next_type() in ("I", "O")


def test_set_allowed_types_updates_pool(tmp_path):
    provider = PieceProvider(mode="normal", path=tmp_path / "c.json", allowed_types=["I"])
    assert provider.next_type() == "I"
    provider.set_allowed_types(["I", "O", "T"])
    for _ in range(20):
        assert provider.next_type() in ("I", "O", "T")


def test_no_allowed_types_uses_all(tmp_path):
    provider = PieceProvider(mode="normal", path=tmp_path / "c.json")
    seen = set()
    for _ in range(200):
        seen.add(provider.next_type())
    assert seen == set(SHAPES.keys())


def test_replay_mode_filters_by_allowed_types(tmp_path):
    """Replay mode skips queue pieces not in allowed_types (curriculum support)."""
    path = tmp_path / "replay.json"
    saved = ["I", "O", "T", "S", "Z", "L", "J", "I", "O", "T"]
    path.write_text(json.dumps(saved))
    provider = PieceProvider(mode="replay", path=path, allowed_types=["I", "O"])
    for _ in range(20):
        assert provider.next_type() in ("I", "O")


def test_replay_mode_no_allowed_types_serves_all(tmp_path):
    """Replay mode without allowed_types serves from queue as before."""
    path = tmp_path / "replay.json"
    saved = ["I", "O", "T"]
    path.write_text(json.dumps(saved))
    provider = PieceProvider(mode="replay", path=path)
    served = [provider.next_type() for _ in range(3)]
    assert served == saved


def test_7bag_deals_all_seven_pieces(tmp_path):
    """7-bag: each piece appears exactly once per 7 draws."""
    provider = PieceProvider(mode="normal", path=tmp_path / "bag.json", generator="7bag")
    bag = [provider.next_type() for _ in range(7)]
    assert sorted(bag) == sorted(SHAPES.keys())


def test_7bag_respects_allowed_types(tmp_path):
    """7-bag with allowed_types=["O"] deals only O pieces."""
    provider = PieceProvider(
        mode="normal", path=tmp_path / "bag.json", generator="7bag", allowed_types=["O"]
    )
    for _ in range(50):
        assert provider.next_type() == "O"


def test_7bag_allowed_types_subset(tmp_path):
    """7-bag with a subset deals each subset piece once per bag."""
    provider = PieceProvider(
        mode="normal", path=tmp_path / "bag.json", generator="7bag", allowed_types=["O", "I", "T"]
    )
    bag = [provider.next_type() for _ in range(3)]
    assert sorted(bag) == ["I", "O", "T"]


def test_7bag_set_allowed_types_resets_bag(tmp_path):
    """set_allowed_types invalidates the bag so the new pool takes effect immediately."""
    provider = PieceProvider(mode="normal", path=tmp_path / "bag.json", generator="7bag")
    provider.next_type()
    provider.next_type()
    provider.set_allowed_types(["O"])
    assert provider.next_type() == "O"
    assert provider.next_type() == "O"


def test_35bag_deals_thirty_five_pieces(tmp_path):
    """35-bag: each piece appears exactly 5 times per 35 draws."""
    provider = PieceProvider(mode="normal", path=tmp_path / "bag.json", generator="35bag")
    bag = [provider.next_type() for _ in range(35)]
    counts = {t: bag.count(t) for t in SHAPES}
    assert all(c == 5 for c in counts.values()), f"Expected 5 of each, got {counts}"


def test_35bag_respects_allowed_types(tmp_path):
    """35-bag with allowed_types=["O"] deals only O pieces."""
    provider = PieceProvider(
        mode="normal", path=tmp_path / "bag.json", generator="35bag", allowed_types=["O"]
    )
    for _ in range(50):
        assert provider.next_type() == "O"


def test_35bag_allowed_types_subset(tmp_path):
    """35-bag with a subset deals each subset piece 5 times per bag."""
    provider = PieceProvider(
        mode="normal", path=tmp_path / "bag.json", generator="35bag", allowed_types=["O", "I", "T"]
    )
    bag = [provider.next_type() for _ in range(15)]
    counts = {t: bag.count(t) for t in ("I", "O", "T")}
    assert all(c == 5 for c in counts.values()), f"Expected 5 of each, got {counts}"


def test_first_piece_35bag_is_safe(tmp_path):
    """35-bag generator: first piece is always I, J, L, or T."""
    for _ in range(50):
        provider = PieceProvider(mode="normal", path=tmp_path / "bag.json", generator="35bag")
        first = provider.next_type()
        assert first in ("I", "J", "L", "T")


def test_35bag_completeness(tmp_path):
    """35-bag stays complete: all 7 pieces appear 5× in the first bag even with
    the first-piece swap."""
    provider = PieceProvider(mode="normal", path=tmp_path / "bag.json", generator="35bag")
    bag = [provider.next_type() for _ in range(35)]
    counts = {t: bag.count(t) for t in SHAPES}
    assert all(c == 5 for c in counts.values()), f"Expected 5 of each, got {counts}"


def test_default_generator_is_random(tmp_path):
    """Without the generator param, default is 'random'."""
    provider = PieceProvider(mode="normal", path=tmp_path / "bag.json")
    assert provider.generator == "random"
    for _ in range(20):
        assert provider.next_type() in SHAPES


def test_bag_remaining_shows_current_bag(tmp_path):
    """bag_remaining returns the 6 pieces left after popping one from a fresh 7-bag."""
    provider = PieceProvider(mode="normal", path=tmp_path / "b.json", generator="7bag")
    provider.next_type()  # pops one, bag has 6 left
    remaining = provider.bag_remaining
    assert len(remaining) == 6
    assert all(t in SHAPES for t in remaining)


def test_first_piece_random_is_safe(tmp_path):
    """Random generator: first piece is always I, J, L, or T."""
    for _ in range(50):
        provider = PieceProvider(mode="normal", path=tmp_path / "fp.json")
        first = provider.next_type()
        assert first in ("I", "J", "L", "T")


def test_first_piece_7bag_is_safe(tmp_path):
    """7-bag generator: first piece is always I, J, L, or T."""
    for _ in range(50):
        provider = PieceProvider(mode="normal", path=tmp_path / "fp.json", generator="7bag")
        first = provider.next_type()
        assert first in ("I", "J", "L", "T")


def test_first_piece_7bag_completeness(tmp_path):
    """7-bag stays complete: all 7 pieces appear in the first bag even with
    the first-piece swap."""
    provider = PieceProvider(mode="normal", path=tmp_path / "fp.json", generator="7bag")
    bag = [provider.next_type() for _ in range(7)]
    assert sorted(bag) == sorted(SHAPES.keys())


def test_second_piece_not_restricted(tmp_path):
    """Only the first piece is restricted; the second can be anything."""
    for _ in range(50):
        provider = PieceProvider(mode="normal", path=tmp_path / "fp.json")
        provider.next_type()  # first (restricted)
        second = provider.next_type()
        assert second in SHAPES


def test_reset_rearms_first_piece(tmp_path):
    """reset() re-arms the first-piece restriction for the next game."""
    provider = PieceProvider(mode="normal", path=tmp_path / "fp.json", generator="7bag")
    first = provider.next_type()
    assert first in ("I", "J", "L", "T")
    # Drain rest of bag
    for _ in range(6):
        provider.next_type()
    provider.reset()
    first_again = provider.next_type()
    assert first_again in ("I", "J", "L", "T")


def test_first_piece_respects_curriculum(tmp_path):
    """When curriculum restricts to ["O"], first piece is O (no safe overlap)."""
    provider = PieceProvider(
        mode="normal", path=tmp_path / "fp.json", allowed_types=["O"]
    )
    first = provider.next_type()
    assert first == "O"


def test_first_piece_replay_skips_unsafe(tmp_path):
    """Replay mode skips queue pieces not in the safe set for the first piece."""
    path = tmp_path / "replay.json"
    path.write_text(json.dumps(["S", "Z", "I", "T"]))
    provider = PieceProvider(mode="replay", path=path)
    first = provider.next_type()
    assert first in ("I", "J", "L", "T")


# ---------------------------------------------------------------------------
# Generator unit tests (internal classes)
# ---------------------------------------------------------------------------


def test_random_generator_no_bag():
    gen = RandomGenerator()
    assert gen.bag_remaining == []
    gen.reset()  # no-op, should not raise


def test_random_generator_first_piece_safe():
    gen = RandomGenerator()
    pool = SHAPES_TYPES
    for _ in range(50):
        assert gen.next(pool, True) in FIRST_PIECE_TYPES


def test_random_generator_subsequent_unrestricted():
    gen = RandomGenerator()
    pool = SHAPES_TYPES
    gen.next(pool, True)
    assert gen.next(pool, False) in SHAPES


def test_bag_generator_copies():
    gen = BagGenerator(copies=1)
    pool = SHAPES_TYPES
    bag = [gen.next(pool, False) for _ in range(7)]
    assert sorted(bag) == sorted(SHAPES.keys())


def test_bag_generator_reset_clears_bag():
    gen = SevenBagGenerator()
    pool = SHAPES_TYPES
    gen.next(pool, False)
    assert len(gen.bag_remaining) == 6
    gen.reset()
    assert gen.bag_remaining == []


def test_bag_generator_first_piece_swap_keeps_completeness():
    gen = SevenBagGenerator()
    pool = SHAPES_TYPES
    first = gen.next(pool, True)
    assert first in FIRST_PIECE_TYPES
    rest = [gen.next(pool, False) for _ in range(6)]
    assert sorted([first] + rest) == sorted(SHAPES.keys())


def test_replay_generator_serves_queue(tmp_path):
    path = tmp_path / "r.json"
    path.write_text(json.dumps(["I", "O", "T"]))
    gen = ReplayGenerator(path)
    pool = SHAPES_TYPES
    assert gen.next(pool, False) == "I"
    assert gen.next(pool, False) == "O"
    assert gen.next(pool, False) == "T"
    assert gen.next(pool, False) is None  # exhausted


def test_replay_generator_curriculum_filter(tmp_path):
    """ReplayGenerator skips queue pieces not in the pool (curriculum)."""
    path = tmp_path / "r.json"
    path.write_text(json.dumps(["I", "S", "O", "Z", "T"]))
    gen = ReplayGenerator(path)
    pool = ["I", "O"]
    assert gen.next(pool, False) == "I"   # S skipped (not in pool)
    assert gen.next(pool, False) == "O"   # Z, T skipped (not in pool)
    assert gen.next(pool, False) is None  # exhausted


def test_replay_generator_first_piece_filter(tmp_path):
    """ReplayGenerator skips queue pieces unsafe for first spawn."""
    path = tmp_path / "r.json"
    path.write_text(json.dumps(["S", "Z", "I", "T"]))
    gen = ReplayGenerator(path)
    pool = SHAPES_TYPES
    # S, Z unsafe → skip; I safe → return
    assert gen.next(pool, True) == "I"


def test_replay_generator_reset_does_not_restart_queue(tmp_path):
    """ReplayGenerator.reset() is a no-op — queue position persists."""
    path = tmp_path / "r.json"
    path.write_text(json.dumps(["I", "O"]))
    gen = ReplayGenerator(path)
    pool = SHAPES_TYPES
    gen.next(pool, False)
    gen.next(pool, False)
    gen.reset()
    assert gen.next(pool, False) is None


def test_replay_generator_empty_file(tmp_path):
    """ReplayGenerator returns None when the file doesn't exist."""
    path = tmp_path / "nonexistent.json"
    gen = ReplayGenerator(path)
    pool = SHAPES_TYPES
    assert gen.next(pool, False) is None


def test_replay_provider_switches_to_fallback(tmp_path):
    """PieceProvider switches to fallback generator when replay exhausts."""
    path = tmp_path / "r.json"
    path.write_text(json.dumps(["I"]))
    provider = PieceProvider(mode="replay", path=path, generator="7bag")
    assert provider.next_type() == "I"
    # Exhausted → switches to 7bag fallback
    for _ in range(7):
        assert provider.next_type() in SHAPES




# ---------------------------------------------------------------------------
# WeightedGenerator tests
# ---------------------------------------------------------------------------


def test_weighted_generator_starts_uniform():
    """After one spawn, selected piece at _WT_INIT * _WT_DECAY, others boosted."""
    gen = WeightedGenerator()
    pool = SHAPES_TYPES
    gen.next(pool, False)
    w = gen.weights
    assert len(w) == 7
    selected_count = sum(1 for v in w.values() if abs(v - _WT_INIT * _WT_DECAY) < 0.01)
    other_count = sum(1 for v in w.values() if abs(v - (_WT_INIT + _WT_BOOST)) < 0.01)
    assert selected_count == 1
    assert other_count == 6


def test_weighted_generator_no_bag():
    gen = WeightedGenerator()
    assert gen.bag_remaining == []


def test_weighted_generator_reset_clears_weights():
    gen = WeightedGenerator()
    pool = SHAPES_TYPES
    gen.next(pool, False)
    assert len(gen.weights) == 7
    gen.reset()
    assert gen.weights == {}


def test_weighted_generator_first_piece_safe():
    gen = WeightedGenerator()
    pool = SHAPES_TYPES
    for _ in range(50):
        gen.reset()
        assert gen.next(pool, True) in FIRST_PIECE_TYPES


def test_weighted_generator_respects_curriculum():
    gen = WeightedGenerator()
    pool = ["O"]
    for _ in range(20):
        assert gen.next(pool, False) == "O"


def test_weighted_generator_weights_never_below_min():
    """No weight drops below _WT_MIN."""
    gen = WeightedGenerator()
    pool = SHAPES_TYPES
    for _ in range(500):
        gen.next(pool, False)
    assert all(w >= _WT_MIN - 0.001 for w in gen.weights.values())


def test_weighted_generator_distributes_all_types():
    """Over 500 spawns, all 7 types appear at least once."""
    gen = WeightedGenerator()
    pool = SHAPES_TYPES
    seen = {gen.next(pool, False) for _ in range(500)}
    assert seen == set(SHAPES.keys())


def test_weighted_provider_integration():
    """PieceProvider with generator='weighted' spawns valid types."""
    provider = PieceProvider(generator="weighted")
    for _ in range(50):
        assert provider.next_type() in SHAPES


def test_weighted_provider_first_piece_safe():
    for _ in range(50):
        provider = PieceProvider(generator="weighted")
        assert provider.next_type() in ("I", "J", "L", "T")


def test_weighted_provider_weights_property():
    """PieceProvider.weights delegates to WeightedGenerator."""
    provider = PieceProvider(generator="weighted")
    provider.next_type()
    w = provider.weights
    assert len(w) == 7
    assert all(v > 0 for v in w.values())


def test_weighted_provider_weights_empty_for_non_weighted():
    """weights returns {} for non-weighted generators."""
    provider = PieceProvider(generator="7bag")
    assert provider.weights == {}


def test_weighted_provider_reset_rearms_first_piece():
    provider = PieceProvider(generator="weighted")
    provider.next_type()
    provider.reset()
    assert provider.next_type() in ("I", "J", "L", "T")


def test_weighted_provider_curriculum():
    provider = PieceProvider(generator="weighted", allowed_types=["O"])
    for _ in range(20):
        assert provider.next_type() == "O"


def test_provider_generator_property():
    """generator property returns the configured name, not the active class."""
    assert PieceProvider(generator="7bag").generator == "7bag"
    assert PieceProvider(generator="35bag").generator == "35bag"
    assert PieceProvider(generator="weighted").generator == "weighted"
    assert PieceProvider().generator == "random"