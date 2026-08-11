"""Tests for PieceProvider: normal and replay modes."""

import json

from tetris.game.piece_provider import PieceProvider
from tetris.settings import SHAPES


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