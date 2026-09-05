"""Tests for the evolutionary self-play tournament (tetris/tournament.py)."""

import os
import random
import tempfile

import pytest
import torch

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import tetris.tournament as t
from tetris.tournament import (
    PIECE_CAP,
    crossover,
    make_agent,
    mutate_weights,
    run_episode,
)


def _tiny_state_dict() -> dict[str, torch.Tensor]:
    return {
        "w": torch.arange(6, dtype=torch.float32).reshape(2, 3),
        "b": torch.zeros(3, dtype=torch.float32),
    }


def test_mutate_weights_is_gaussian_noise_on_copy():
    sd = _tiny_state_dict()
    rng = random.Random(1)
    out = mutate_weights(sd, sigma=0.5, rng=rng)
    # Source untouched
    assert torch.equal(sd["w"], torch.arange(6, dtype=torch.float32).reshape(2, 3))
    # Shape/dtype preserved, actually perturbed
    assert out["w"].shape == sd["w"].shape
    assert out["w"].dtype == torch.float32
    assert not torch.equal(out["w"], sd["w"])
    # Deterministic for same rng seed
    out2 = mutate_weights(sd, sigma=0.5, rng=random.Random(1))
    assert torch.equal(out["w"], out2["w"])
    # sigma=0 → identity
    zero = mutate_weights(sd, sigma=0.0, rng=random.Random(9))
    assert torch.equal(zero["w"], sd["w"])


def test_crossover_uniform_per_parameter():
    a, b = _tiny_state_dict(), _tiny_state_dict()
    b["w"] = torch.ones(2, 3)
    rng = random.Random(2)
    out = crossover(a, b, rng)
    # Every parameter chosen from exactly one parent
    assert all(torch.equal(out[k], a[k]) or torch.equal(out[k], b[k]) for k in out)


def test_make_agent_restores_weights_and_is_greedy():
    from tetris.ai.agent import DQNAgent

    sd = {k: v.clone() for k, v in DQNAgent(dueling=False, device="cpu").online_net.state_dict().items()}
    ckpt = {"online_net": sd, "dueling": False}
    agent = make_agent(ckpt, dueling=False, device="cpu")
    assert agent.epsilon == 0.0
    for k, v in sd.items():
        assert torch.equal(agent.online_net.state_dict()[k], v)
        assert torch.equal(agent.target_net.state_dict()[k], v)


def test_make_agent_missing_online_net_raises():
    with pytest.raises(KeyError):
        make_agent({}, dueling=False)


def _write_checkpoint(path: str) -> None:
    """Fresh random checkpoint; the episode logic needs no trained weights."""
    from tetris.ai.agent import DQNAgent

    sd = DQNAgent(dueling=False, device="cpu").online_net.state_dict()
    torch.save({"online_net": sd, "dueling": False}, path)


def test_run_episode_respects_piece_cap_and_is_deterministic(tmp_path):
    model = str(tmp_path / "model.pt")
    _write_checkpoint(model)
    agent = make_agent(torch.load(model, map_location="cpu", weights_only=True), dueling=False, device="cpu")
    torch.set_num_threads(1)
    a = run_episode(agent, seed=7, piece_cap=12)
    b = run_episode(agent, seed=7, piece_cap=12)
    assert a == b  # same seed → identical episode
    assert a >= 0.0


def test_run_episode_defaults_to_piece_cap():
    import inspect

    sig = inspect.signature(run_episode)
    assert sig.parameters["piece_cap"].default == PIECE_CAP


def test_evaluate_population_uses_all_episodes_and_cap(monkeypatch):
    # Monkeypatched run_episode isolates the loop logic from pygame; the
    # default evaluate closure is what must forward piece_cap.
    seen: list[tuple[int, int]] = []
    monkeypatch.setattr(t, "make_agent", lambda ckpt, dueling: None)

    def fake_run_episode(agent, ep_seed, piece_cap=PIECE_CAP):
        seen.append((ep_seed, piece_cap))
        return float(ep_seed)

    monkeypatch.setattr(t, "run_episode", fake_run_episode)
    scores = t.evaluate_population(
        [{"online_net": {}} for _ in range(3)],
        episodes=3,
        seed=7,
        dueling=False,
        piece_cap=5,
    )
    assert scores == [8.0, 8.0, 8.0]  # mean(7,8,9)
    assert seen == [(7, 5), (8, 5), (9, 5)] * 3


def test_evaluate_population_reports_progress(monkeypatch):
    progress: dict = {}
    monkeypatch.setattr(t, "make_agent", lambda ckpt, dueling: None)

    def fake_evaluate(agent, ep_seed, piece_cap=PIECE_CAP):
        return float(ep_seed)

    scores = t.evaluate_population(
        [{"online_net": {}} for _ in range(2)],
        episodes=2,
        seed=7,
        dueling=False,
        evaluate=fake_evaluate,
        progress=progress,
    )
    assert scores == [7.5, 7.5]  # mean(7,8) — no default piece_cap path
    assert progress["member"] == 1
    assert progress["episode"] == 1


def test_run_tournament_writes_progress(tmp_path):
    model = str(tmp_path / "model.pt")
    _write_checkpoint(model)
    progress: dict = {}
    t.run_tournament(
        generations=2,
        episodes=1,
        population=2,
        sigma=0.02,
        seed=7,
        piece_cap=10,
        report_path=str(tmp_path / "report.json"),
        best_path=str(tmp_path / "best.pt"),
        model_path=model,
        progress=progress,
    )
    assert progress["gen"] == 1  # last generation index
    assert progress["best"] >= 0.0
    assert progress["mean"] >= 0.0
    assert len(progress["history"]) == 2  # one entry per generation
    assert progress["member"] >= 0 and progress["episode"] >= 0


def test_run_tournament_without_progress_still_works(tmp_path):
    model = str(tmp_path / "model.pt")
    _write_checkpoint(model)
    report = t.run_tournament(
        generations=1,
        episodes=1,
        population=2,
        sigma=0.02,
        seed=7,
        piece_cap=10,
        report_path=str(tmp_path / "report.json"),
        best_path=str(tmp_path / "best.pt"),
        model_path=model,
    )
    assert len(report["generations"]) == 1


def test_run_tournament_end_to_end_isolated(tmp_path):
    rep = str(tmp_path / "report.json")
    best = str(tmp_path / "best.pt")
    model = str(tmp_path / "model.pt")
    _write_checkpoint(model)
    report = t.run_tournament(
        generations=2,
        episodes=1,
        population=2,
        sigma=0.02,
        seed=7,
        piece_cap=10,
        report_path=rep,
        best_path=best,
        model_path=model,
    )
    assert len(report["generations"]) == 2
    assert report["config"]["piece_cap"] == 10
    assert os.path.exists(rep) and os.path.exists(best)
    # Best weights load cleanly
    torch.load(best, map_location="cpu", weights_only=True)


def test_run_tournament_missing_model_raises():
    with pytest.raises(FileNotFoundError):
        t.run_tournament(
            generations=1,
            episodes=1,
            population=2,
            sigma=0.02,
            seed=7,
            model_path="/nonexistent/model.pt",
            report_path=os.path.join(tempfile.mkdtemp(), "r.json"),
            best_path=os.path.join(tempfile.mkdtemp(), "b.pt"),
        )
