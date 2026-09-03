"""Tests for the post-training tournament loop runner (run_tournament_loops)."""

import json
import os


import pytest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import tetris.tournament as t


def _canned_report(gen: int = 0, best: float = 100.0, mean: float = 50.0) -> dict:
    return {
        "config": {},
        "generations": [{"gen": gen, "best": best, "mean": mean, "scores": [best, mean]}],
    }


class _Recorder:
    """Fake run_tournament: writes a distinct best file per loop, records calls."""

    def __init__(self, best_path: str) -> None:
        self.best_path = best_path
        self.calls: list[dict] = []

    def __call__(
        self,
        *,
        generations,
        episodes,
        population,
        sigma,
        seed,
        model_path,
        piece_cap,
        report_path,
        best_path,
        should_stop=None,
        evaluate=None,
    ):
        self.calls.append(
            {
                "seed": seed,
                "sigma": sigma,
                "model_path": model_path,
                "should_stop": should_stop,
            }
        )
        # Distinct best weights per loop so copyback order is observable.
        with open(self.best_path, "w") as f:
            f.write(f"best-of-loop-{len(self.calls) - 1}")
        return _canned_report(best=100.0 + len(self.calls), mean=50.0 + len(self.calls))


@pytest.fixture()
def paths(tmp_path):
    return {
        "model": str(tmp_path / "ai_model.pt"),
        "pre": str(tmp_path / "ai_model.pre_tournament.pt"),
        "best": str(tmp_path / "tournament_best.pt"),
        "report": str(tmp_path / "report.json"),
        "loops": str(tmp_path / "tournament" / "loops.json"),
    }


def _install_fake(monkeypatch, paths):
    recorder = _Recorder(paths["best"])

    def fake_run_tournament(**kwargs):
        return recorder(**kwargs)

    monkeypatch.setattr(t, "run_tournament", fake_run_tournament)
    monkeypatch.setattr(t, "PRE_TOURNAMENT_PATH", paths["pre"])
    return recorder


def test_loops_copies_checkpoint_best_and_appends_entries(monkeypatch, tmp_path, paths):
    model = paths["model"]
    with open(model, "w") as f:
        f.write("base-model")
    recorder = _install_fake(monkeypatch, paths)

    progress = {}
    result = t.run_tournament_loops(
        loops=3,
        generations=2,
        episodes=1,
        population=2,
        sigma=0.02,
        seed=5,
        model_path=model,
        report_path=paths["report"],
        best_path=paths["best"],
        loops_path=paths["loops"],
        progress=progress,
    )

    # (a) checkpoint copy happened before loop 0
    with open(paths["pre"]) as f:
        assert f.read() == "base-model"
    # three loops ran, seeds 5, 6, 7
    assert [c["seed"] for c in recorder.calls] == [5, 6, 7]
    # (d) next_seed returned
    assert result == {"loops_run": 3, "next_seed": 8}
    # (b) best -> model copy per loop: model now holds the last winner
    with open(model) as f:
        assert f.read() == "best-of-loop-2"
    # (c) loops.json entries appended with the right seeds
    with open(paths["loops"]) as f:
        entries = json.load(f)
    assert [e["loop"] for e in entries] == [0, 1, 2]
    assert [e["seed"] for e in entries] == [5, 6, 7]
    assert [e["best"] for e in entries] == [101.0, 102.0, 103.0]
    assert [e["mean"] for e in entries] == [51.0, 52.0, 53.0]
    assert all("elapsed_s" in e and "timestamp" in e for e in entries)
    # progress keys updated from the worker
    assert progress["loop"] == 2
    assert progress["done"] == 3


def test_should_stop_between_loops_stops_after_first(monkeypatch, tmp_path, paths):
    model = paths["model"]
    with open(model, "w") as f:
        f.write("base-model")
    recorder = _install_fake(monkeypatch, paths)

    # Fake run_tournament sets the stop flag as it finishes loop 0, so the
    # between-loops check trips before loop 1 starts.
    real_calls = recorder.calls

    def should_stop():
        return len(real_calls) >= 1

    result = t.run_tournament_loops(
        loops=5,
        generations=1,
        episodes=1,
        population=2,
        sigma=0.02,
        seed=1,
        model_path=model,
        report_path=paths["report"],
        best_path=paths["best"],
        loops_path=paths["loops"],
        should_stop=should_stop,
    )
    # only loop 0 ran before the between-loops check tripped
    assert result["loops_run"] == 1
    assert result["next_seed"] == 2
    assert len(recorder.calls) == 1
    with open(paths["loops"]) as f:
        assert len(json.load(f)) == 1


def test_cancel_inside_generation_still_appends_and_copies(monkeypatch, tmp_path, paths):
    model = paths["model"]
    with open(model, "w") as f:
        f.write("base-model")

    # Fake run_tournament that honors should_stop after its first generation.
    def fake_run_tournament(**kwargs):
        with open(paths["best"], "w") as f:
            f.write("partial-best")
        rep = _canned_report(best=42.0, mean=21.0)
        # Simulate: generation 0 ran, then should_stop became true → partial report.
        kwargs["should_stop"] and kwargs["should_stop"]()
        return rep

    monkeypatch.setattr(t, "run_tournament", fake_run_tournament)
    monkeypatch.setattr(t, "PRE_TOURNAMENT_PATH", paths["pre"])

    called = {"flag": False}

    def should_stop():
        return called["flag"]

    called["flag"] = True  # stop was requested before we even start
    result = t.run_tournament_loops(
        loops=2,
        generations=3,
        episodes=1,
        population=2,
        sigma=0.02,
        seed=9,
        model_path=model,
        report_path=paths["report"],
        best_path=paths["best"],
        loops_path=paths["loops"],
        should_stop=should_stop,
    )
    # The between-loops check fires first → zero loops run, no entry appended.
    assert result["loops_run"] == 0
    assert not os.path.exists(paths["loops"])


def test_cancel_mid_generation_appends_partial_entry(monkeypatch, tmp_path, paths):
    """Cancel arriving inside run_tournament: entry still appended, best copied."""
    model = paths["model"]
    with open(model, "w") as f:
        f.write("base-model")

    def fake_run_tournament(**kwargs):
        with open(paths["best"], "w") as f:
            f.write("gen0-best")
        # Honor the cancel: pretend should_stop fired inside the gen loop and
        # run_tournament returned a partial (1-generation) report.
        return _canned_report(best=7.0, mean=3.5)

    monkeypatch.setattr(t, "run_tournament", fake_run_tournament)
    monkeypatch.setattr(t, "PRE_TOURNAMENT_PATH", paths["pre"])

    result = t.run_tournament_loops(
        loops=2,
        generations=3,
        episodes=1,
        population=2,
        sigma=0.02,
        seed=9,
        model_path=model,
        report_path=paths["report"],
        best_path=paths["best"],
        loops_path=paths["loops"],
        should_stop=lambda: False,  # never true outside; cancel happened inside
    )
    assert result["loops_run"] == 2
    with open(model) as f:
        assert f.read() == "gen0-best"
    with open(paths["loops"]) as f:
        entries = json.load(f)
    assert len(entries) == 2
    assert entries[0]["best"] == 7.0
    assert entries[0]["mean"] == 3.5


def test_missing_model_raises_file_not_found(monkeypatch, tmp_path, paths):
    monkeypatch.setattr(t, "PRE_TOURNAMENT_PATH", paths["pre"])
    with pytest.raises(FileNotFoundError):
        t.run_tournament_loops(
            loops=1,
            generations=1,
            episodes=1,
            population=2,
            sigma=0.02,
            seed=1,
            model_path=str(tmp_path / "missing.pt"),
            report_path=paths["report"],
            best_path=paths["best"],
            loops_path=paths["loops"],
        )


def test_appends_to_existing_loops_json(monkeypatch, tmp_path, paths):
    model = paths["model"]
    with open(model, "w") as f:
        f.write("base-model")
    _install_fake(monkeypatch, paths)
    os.makedirs(os.path.dirname(paths["loops"]), exist_ok=True)
    with open(paths["loops"], "w") as f:
        json.dump(
            [{"loop": 0, "seed": 99, "best": 1.0, "mean": 0.5, "elapsed_s": 1.0, "timestamp": "2026-01-01T00:00:00"}], f
        )

    result = t.run_tournament_loops(
        loops=1,
        generations=1,
        episodes=1,
        population=2,
        sigma=0.02,
        seed=1,
        model_path=model,
        report_path=paths["report"],
        best_path=paths["best"],
        loops_path=paths["loops"],
    )
    with open(paths["loops"]) as f:
        entries = json.load(f)
    assert len(entries) == 2
    assert entries[0]["seed"] == 99  # pre-existing entry untouched
    assert entries[1]["loop"] == 0
    assert result["next_seed"] == 2


def test_invalid_existing_loops_json_restarts_list(monkeypatch, tmp_path, paths):
    model = paths["model"]
    with open(model, "w") as f:
        f.write("base-model")
    _install_fake(monkeypatch, paths)
    os.makedirs(os.path.dirname(paths["loops"]), exist_ok=True)
    with open(paths["loops"], "w") as f:
        f.write("{not json")

    t.run_tournament_loops(
        loops=1,
        generations=1,
        episodes=1,
        population=2,
        sigma=0.02,
        seed=1,
        model_path=model,
        report_path=paths["report"],
        best_path=paths["best"],
        loops_path=paths["loops"],
    )
    with open(paths["loops"]) as f:
        entries = json.load(f)
    assert len(entries) == 1


def test_shutil_copyfile_used_for_checkpoint(monkeypatch, tmp_path, paths):
    """Checkpoint copy is a real byte copy, not a move: source still exists."""
    model = paths["model"]
    with open(model, "w") as f:
        f.write("base-model")
    _install_fake(monkeypatch, paths)
    t.run_tournament_loops(
        loops=1,
        generations=1,
        episodes=1,
        population=2,
        sigma=0.02,
        seed=1,
        model_path=model,
        report_path=paths["report"],
        best_path=paths["best"],
        loops_path=paths["loops"],
    )
    assert os.path.exists(model)  # not moved
    assert os.path.exists(paths["pre"])
    with open(model) as f:
        assert f.read() == "best-of-loop-0"  # replaced by winner
