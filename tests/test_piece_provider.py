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