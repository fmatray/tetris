"""Tests for leaderboard storage: save_score with generator/mode, legacy normalization."""

import json

from tetris.storage import load_leaderboard, save_score


def test_save_score_stores_generator_and_mode(tmp_path, monkeypatch):
    """save_score persists generator and mode fields."""
    lb_path = tmp_path / "leaderboard.json"
    monkeypatch.setattr("tetris.storage.LEADERBOARD_PATH", str(lb_path))
    save_score("Alice", 5000, 5, 20, generator="7bag", mode="Normal")
    scores = load_leaderboard()
    assert len(scores) == 1
    assert scores[0]["generator"] == "7bag"
    assert scores[0]["mode"] == "Normal"


def test_save_score_defaults_empty_generator_mode(tmp_path, monkeypatch):
    """save_score without generator/mode stores empty strings."""
    lb_path = tmp_path / "leaderboard.json"
    monkeypatch.setattr("tetris.storage.LEADERBOARD_PATH", str(lb_path))
    save_score("Bob", 3000, 3, 10)
    scores = load_leaderboard()
    assert scores[0]["generator"] == ""
    assert scores[0]["mode"] == ""


def test_load_leaderboard_normalizes_legacy_dict(tmp_path, monkeypatch):
    """Dict entries missing generator/mode get defaults via .get()."""
    lb_path = tmp_path / "leaderboard.json"
    lb_path.write_text(json.dumps([
        {"name": "Old", "score": 1000, "level": 1, "lines": 5, "date": "2020-01-01"}
    ]))
    monkeypatch.setattr("tetris.storage.LEADERBOARD_PATH", str(lb_path))
    scores = load_leaderboard()
    assert len(scores) == 1
    assert scores[0]["name"] == "Old"
    # .get() in the view handles missing keys; storage preserves the dict as-is
    assert "generator" not in scores[0]


def test_load_leaderboard_normalizes_legacy_tuple(tmp_path, monkeypatch):
    """Legacy tuple entries are converted to dict with generator/mode defaults."""
    lb_path = tmp_path / "leaderboard.json"
    lb_path.write_text(json.dumps([["Legacy", 999]]))
    monkeypatch.setattr("tetris.storage.LEADERBOARD_PATH", str(lb_path))
    scores = load_leaderboard()
    assert len(scores) == 1
    assert scores[0]["name"] == "Legacy"
    assert scores[0]["generator"] == "-"
    assert scores[0]["mode"] == "-"


def test_save_score_sorts_descending(tmp_path, monkeypatch):
    """Scores are sorted descending after insert."""
    lb_path = tmp_path / "leaderboard.json"
    monkeypatch.setattr("tetris.storage.LEADERBOARD_PATH", str(lb_path))
    save_score("Low", 100, 1, 1, generator="random", mode="Normal")
    save_score("High", 9000, 9, 90, generator="35bag", mode="Replay")
    scores = load_leaderboard()
    assert scores[0]["name"] == "High"
    assert scores[1]["name"] == "Low"
