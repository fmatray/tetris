"""Tests for TrainingLog: persistence, properties, trends."""

import json
import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import tempfile
from pathlib import Path
from unittest import mock

import pytest

from tetris.ai.trainer import TrainingLog


def _ep(
    episode: int = 0,
    score: int = 100,
    lines: int = 5,
    level: int = 3,
    steps: int = 200,
    epsilon: float = 0.1,
    loss: float = 0.01,
) -> dict:
    """Build a minimal episode dict matching record() output."""
    return {
        "episode": episode,
        "score": score,
        "lines": lines,
        "level": level,
        "steps": steps,
        "epsilon": epsilon,
        "loss": loss,
        "timestamp": "2025-01-01T00:00:00+00:00",
    }


def _tmp_path() -> str:
    """A temp .json path that does not exist yet."""
    return tempfile.mktemp(suffix=".json")


# --- init / load -----------------------------------------------------------


def test_init_no_file_starts_empty():
    """Constructor with a missing file starts with empty episodes."""
    log = TrainingLog(path=_tmp_path())
    assert log.episodes == []
    assert log.total_episodes == 0


def test_load_valid_json():
    """_load populates episodes from a valid JSON file."""
    path = _tmp_path()
    Path(path).write_text(json.dumps([_ep(0), _ep(1)]))
    log = TrainingLog(path=path)
    assert log.total_episodes == 2


def test_load_invalid_json():
    """_load silently resets to empty on corrupt JSON."""
    path = _tmp_path()
    Path(path).write_text("{not valid json")
    log = TrainingLog(path=path)
    assert log.episodes == []


def test_load_missing_file():
    """_load on a non-existent path leaves episodes empty."""
    log = TrainingLog(path=_tmp_path())
    assert log.episodes == []


def test_load_os_error():
    """_load handles OSError (e.g. permission) gracefully."""
    path = _tmp_path()
    Path(path).write_text("[]")
    log = TrainingLog(path=path)
    with mock.patch.object(Path, "read_text", side_effect=OSError("denied")):
        log._load()
    assert log.episodes == []


# --- record / flush / save -------------------------------------------------


def test_record_appends_episode():
    """record() appends a dict with the given fields."""
    log = TrainingLog(path=_tmp_path())
    log.record(0, 100, 5, 3, 200, 0.1, 0.01)
    assert len(log.episodes) == 1
    ep = log.episodes[0]
    assert ep["score"] == 100
    assert ep["lines"] == 5
    assert ep["level"] == 3
    assert ep["steps"] == 200
    assert ep["epsilon"] == 0.1
    assert ep["loss"] == 0.01
    assert "timestamp" in ep


def test_record_saves_at_interval():
    """record() saves to disk every _SAVE_INTERVAL episodes."""
    path = _tmp_path()
    log = TrainingLog(path=path)
    for i in range(TrainingLog._SAVE_INTERVAL):
        log.record(i, 100, 5, 3, 200, 0.1, 0.01)
    # After exactly _SAVE_INTERVAL records, file should exist on disk.
    assert Path(path).exists()
    loaded = json.loads(Path(path).read_text())
    assert len(loaded) == TrainingLog._SAVE_INTERVAL


def test_record_no_save_before_interval():
    """record() does NOT save before reaching _SAVE_INTERVAL."""
    path = _tmp_path()
    log = TrainingLog(path=path)
    for i in range(TrainingLog._SAVE_INTERVAL - 1):
        log.record(i, 100, 5, 3, 200, 0.1, 0.01)
    assert not Path(path).exists()


def test_flush_forces_save():
    """flush() writes to disk regardless of count."""
    path = _tmp_path()
    log = TrainingLog(path=path)
    log.record(0, 100, 5, 3, 200, 0.1, 0.01)
    assert not Path(path).exists()
    log.flush()
    assert Path(path).exists()
    assert len(json.loads(Path(path).read_text())) == 1


def test_save_writes_valid_json():
    """_save() writes parseable JSON matching episodes."""
    path = _tmp_path()
    log = TrainingLog(path=path)
    log.episodes = [_ep(0), _ep(1)]
    log._save()
    assert json.loads(Path(path).read_text()) == log.episodes


def test_save_handles_os_error(caplog):
    """_save() logs an error but does not raise on OSError."""
    log = TrainingLog(path=_tmp_path())
    log.episodes = [_ep(0)]
    with mock.patch.object(Path, "write_text", side_effect=OSError("disk full")):
        log._save()  # must not raise


# --- helpers ---------------------------------------------------------------


def test_safe_sum_empty():
    log = TrainingLog(path=_tmp_path())
    assert log._safe_sum("score") == 0


def test_safe_sum_populated():
    log = TrainingLog(path=_tmp_path())
    log.episodes = [_ep(score=100), _ep(score=200), _ep(score=300)]
    assert log._safe_sum("score") == 600


def test_safe_max_empty():
    log = TrainingLog(path=_tmp_path())
    assert log._safe_max("score") == 0


def test_safe_max_populated():
    log = TrainingLog(path=_tmp_path())
    log.episodes = [_ep(score=100), _ep(score=500), _ep(score=200)]
    assert log._safe_max("score") == 500


def test_safe_avg_empty():
    log = TrainingLog(path=_tmp_path())
    assert log._safe_avg("score") == 0.0


def test_safe_avg_populated():
    log = TrainingLog(path=_tmp_path())
    log.episodes = [_ep(score=100), _ep(score=200), _ep(score=300)]
    assert log._safe_avg("score") == 200.0


def test_last_n_avg_empty():
    log = TrainingLog(path=_tmp_path())
    assert log._last_n_avg("score") == 0.0


def test_last_n_avg_fewer_than_n():
    """Returns avg of all episodes when fewer than n exist."""
    log = TrainingLog(path=_tmp_path())
    log.episodes = [_ep(score=100), _ep(score=200)]
    assert log._last_n_avg("score") == 150.0


def test_last_n_avg_exactly_n():
    """Returns avg of last n episodes when >= n exist."""
    log = TrainingLog(path=_tmp_path())
    log.episodes = [_ep(score=i * 10) for i in range(150)]
    # Last 100: indices 50..149 → scores 500..1490
    expected = sum(i * 10 for i in range(50, 150)) / 100
    assert log._last_n_avg("score") == expected


def test_last_n_avg_custom_n():
    """_last_n_avg respects a custom n argument."""
    log = TrainingLog(path=_tmp_path())
    log.episodes = [_ep(score=i) for i in range(10)]
    assert log._last_n_avg("score", n=3) == 8.0  # (7+8+9)/3


# --- properties: empty -----------------------------------------------------


@pytest.fixture
def empty_log():
    return TrainingLog(path=_tmp_path())


def test_empty_total_episodes(empty_log):
    assert empty_log.total_episodes == 0


def test_empty_avg_score(empty_log):
    assert empty_log.avg_score == 0.0


def test_empty_best_score(empty_log):
    assert empty_log.best_score == 0


def test_empty_total_lines(empty_log):
    assert empty_log.total_lines == 0


def test_empty_total_steps(empty_log):
    assert empty_log.total_steps == 0


def test_empty_avg_level(empty_log):
    assert empty_log.avg_level == 0.0


def test_empty_best_level(empty_log):
    assert empty_log.best_level == 0


def test_empty_total_score(empty_log):
    assert empty_log.total_score == 0


def test_empty_best_lines(empty_log):
    assert empty_log.best_lines == 0


def test_empty_avg_lines(empty_log):
    assert empty_log.avg_lines == 0.0


def test_empty_best_steps(empty_log):
    assert empty_log.best_steps == 0


def test_empty_avg_steps(empty_log):
    assert empty_log.avg_steps == 0.0


def test_empty_last_100_avg(empty_log):
    assert empty_log.last_100_avg == 0.0


def test_empty_last_100_avg_lines(empty_log):
    assert empty_log.last_100_avg_lines == 0.0


def test_empty_last_100_avg_level(empty_log):
    assert empty_log.last_100_avg_level == 0.0


def test_empty_last_100_avg_steps(empty_log):
    assert empty_log.last_100_avg_steps == 0.0


# --- properties: populated -------------------------------------------------


@pytest.fixture
def populated_log():
    """5 episodes with distinct values."""
    log = TrainingLog(path=_tmp_path())
    log.episodes = [
        _ep(episode=0, score=100, lines=2, level=1, steps=50),
        _ep(episode=1, score=300, lines=4, level=2, steps=100),
        _ep(episode=2, score=500, lines=8, level=5, steps=200),
        _ep(episode=3, score=200, lines=1, level=3, steps=75),
        _ep(episode=4, score=400, lines=6, level=4, steps=150),
    ]
    return log


def test_pop_total_episodes(populated_log):
    assert populated_log.total_episodes == 5


def test_pop_avg_score(populated_log):
    assert populated_log.avg_score == 300.0  # (100+300+500+200+400)/5


def test_pop_best_score(populated_log):
    assert populated_log.best_score == 500


def test_pop_total_lines(populated_log):
    assert populated_log.total_lines == 21  # 2+4+8+1+6


def test_pop_total_steps(populated_log):
    assert populated_log.total_steps == 575  # 50+100+200+75+150


def test_pop_avg_level(populated_log):
    assert populated_log.avg_level == 3.0  # (1+2+5+3+4)/5


def test_pop_best_level(populated_log):
    assert populated_log.best_level == 5


def test_pop_total_score(populated_log):
    assert populated_log.total_score == 1500  # 100+300+500+200+400


def test_pop_best_lines(populated_log):
    assert populated_log.best_lines == 8


def test_pop_avg_lines(populated_log):
    assert populated_log.avg_lines == 4.2  # 21/5


def test_pop_best_steps(populated_log):
    assert populated_log.best_steps == 200


def test_pop_avg_steps(populated_log):
    assert populated_log.avg_steps == 115.0  # 575/5


def test_pop_last_100_avg(populated_log):
    # All 5 are in the last 100
    assert populated_log.last_100_avg == 300.0


def test_pop_last_100_avg_lines(populated_log):
    assert populated_log.last_100_avg_lines == 4.2


def test_pop_last_100_avg_level(populated_log):
    assert populated_log.last_100_avg_level == 3.0


def test_pop_last_100_avg_steps(populated_log):
    assert populated_log.last_100_avg_steps == 115.0


# --- last_100 with >100 episodes -------------------------------------------


def test_last_100_avg_with_over_100():
    """last_100_avg uses only the last 100 episodes when >100 exist."""
    log = TrainingLog(path=_tmp_path())
    # 150 episodes: first 50 have score=0, last 100 have score=10
    log.episodes = [_ep(score=0) for _ in range(50)] + [_ep(score=10) for _ in range(100)]
    assert log.last_100_avg == 10.0
    assert log.total_episodes == 150


def test_last_100_avg_lines_with_over_100():
    log = TrainingLog(path=_tmp_path())
    log.episodes = [_ep(lines=0) for _ in range(50)] + [_ep(lines=4) for _ in range(100)]
    assert log.last_100_avg_lines == 4.0


def test_last_100_avg_level_with_over_100():
    log = TrainingLog(path=_tmp_path())
    log.episodes = [_ep(level=1) for _ in range(50)] + [_ep(level=7) for _ in range(100)]
    assert log.last_100_avg_level == 7.0


def test_last_100_avg_steps_with_over_100():
    log = TrainingLog(path=_tmp_path())
    log.episodes = [_ep(steps=10) for _ in range(50)] + [_ep(steps=90) for _ in range(100)]
    assert log.last_100_avg_steps == 90.0


# --- _trend ----------------------------------------------------------------


def test_trend_insufficient_data():
    """_trend returns 'stable' when < 200 episodes."""
    log = TrainingLog(path=_tmp_path())
    log.episodes = [_ep(score=100) for _ in range(199)]
    assert log._trend("score") == "stable"


def test_trend_exactly_200_stable():
    """With exactly 200 episodes where recent≈previous, returns 'stable'."""
    log = TrainingLog(path=_tmp_path())
    # Previous 100: score=100; recent 100: score=105 → ratio 1.05, not > 1.05
    log.episodes = [_ep(score=100) for _ in range(100)] + [_ep(score=105) for _ in range(100)]
    assert log._trend("score") == "stable"


def test_trend_up():
    """_trend returns 'up' when recent avg > 5% above previous avg."""
    log = TrainingLog(path=_tmp_path())
    log.episodes = [_ep(score=100) for _ in range(100)] + [_ep(score=200) for _ in range(100)]
    assert log._trend("score") == "up"


def test_trend_down():
    """_trend returns 'down' when recent avg < 5% below previous avg."""
    log = TrainingLog(path=_tmp_path())
    log.episodes = [_ep(score=200) for _ in range(100)] + [_ep(score=100) for _ in range(100)]
    assert log._trend("score") == "down"


def test_trend_prev_avg_zero_recent_positive():
    """When prev_avg=0 and recent>0, returns 'up'."""
    log = TrainingLog(path=_tmp_path())
    log.episodes = [_ep(score=0) for _ in range(100)] + [_ep(score=50) for _ in range(100)]
    assert log._trend("score") == "up"


def test_trend_prev_avg_zero_recent_zero():
    """When prev_avg=0 and recent=0, returns 'stable'."""
    log = TrainingLog(path=_tmp_path())
    log.episodes = [_ep(score=0) for _ in range(200)]
    assert log._trend("score") == "stable"


def test_trend_just_above_threshold():
    """ratio > 1.05 strictly → 'up'; ratio == 1.05 → 'stable'."""
    log = TrainingLog(path=_tmp_path())
    # 100 / 100 * 1.05 = 105 → exactly 1.05, not > 1.05 → stable
    log.episodes = [_ep(score=100) for _ in range(100)] + [_ep(score=105) for _ in range(100)]
    assert log._trend("score") == "stable"
    # 106 / 100 = 1.06 > 1.05 → up
    log2 = TrainingLog(path=_tmp_path())
    log2.episodes = [_ep(score=100) for _ in range(100)] + [_ep(score=106) for _ in range(100)]
    assert log2._trend("score") == "up"


def test_trend_just_below_threshold():
    """ratio < 0.95 strictly → 'down'; ratio == 0.95 → 'stable'."""
    log = TrainingLog(path=_tmp_path())
    # 95 / 100 = 0.95, not < 0.95 → stable
    log.episodes = [_ep(score=100) for _ in range(100)] + [_ep(score=95) for _ in range(100)]
    assert log._trend("score") == "stable"
    # 94 / 100 = 0.94 < 0.95 → down
    log2 = TrainingLog(path=_tmp_path())
    log2.episodes = [_ep(score=100) for _ in range(100)] + [_ep(score=94) for _ in range(100)]
    assert log2._trend("score") == "down"
