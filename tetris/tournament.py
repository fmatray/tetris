"""Evolutionary self-play tournament over DQN agent weights.

``python -m tetris.tournament`` — population of Gaussian mutants derived
from the shipped checkpoint, evaluated headless in playing mode, evolved
over generations (top-half survival + mutated/crossover offspring).

Reuses :class:`~tetris.states.ai.AIState` for evaluation so the exact
shipped playing loop (seeding, lock delay, scoring) measures fitness.
Path isolation: playing-mode logs are redirected into ``data/tournament/``
by patching module attributes before each ``AIState`` construction; the
shipped model checkpoint is never written.

Outputs:
- ``data/tournament_report.json`` — per-generation fitness statistics.
- ``data/tournament_best.pt`` — best weights (never ``MODEL_PATH``).
"""

from __future__ import annotations

import argparse
import json
import os
import random
from collections.abc import Callable, Sequence
from typing import Any

import numpy as np
import torch

from tetris.ai.agent import DQNAgent
from tetris.logger import get_logger
from tetris.settings import MODEL_PATH

logger = get_logger(__name__)

# Step cap: episodes end early so evaluation stays fast. High enough that
# strong agents diverge from weak ones, low enough for practical runtime.
PIECE_CAP: int = 400

REPORT_DIR = os.path.join("data", "tournament")
REPORT_PATH = os.path.join(REPORT_DIR, "tournament_report.json")
BEST_PATH = os.path.join(REPORT_DIR, "tournament_best.pt")

# Playing-config constants mirrored from verify_training's fast setup.
_BATCH = 64
_BUFFER = 10_000


def mutate_weights(state_dict: dict[str, torch.Tensor], sigma: float, rng: random.Random) -> dict[str, torch.Tensor]:
    """Gaussian noise on every float parameter tensor (in-place on a copy)."""
    out: dict[str, torch.Tensor] = {}
    for key, tensor in state_dict.items():
        if tensor.is_floating_point():
            noise = torch.from_numpy(
                np.asarray([rng.gauss(0.0, sigma) for _ in range(tensor.numel())])
                .reshape(tensor.shape)
                .astype(np.float32)
            )
            out[key] = tensor + noise.to(tensor.device)
        else:
            out[key] = tensor
    return out


def crossover(a: dict[str, torch.Tensor], b: dict[str, torch.Tensor], rng: random.Random) -> dict[str, torch.Tensor]:
    """Per-parameter uniform crossover between two state dicts."""
    out: dict[str, torch.Tensor] = {}
    for key, tensor in a.items():
        out[key] = tensor if rng.random() < 0.5 else b[key]
    return out


def select_survivors(fitness: Sequence[float]) -> list[int]:
    """Indices of the top half of the population, best first."""
    ranked = sorted(range(len(fitness)), key=lambda i: fitness[i], reverse=True)
    return ranked[: len(ranked) // 2]


def make_agent(checkpoint: dict[str, Any], dueling: bool, device: str | None = None) -> DQNAgent:
    """Fresh agent loaded from a (possibly mutated) checkpoint dict."""
    agent = DQNAgent(
        lr=1e-3, gamma=0.97, batch_size=_BATCH, buffer_size=_BUFFER, dueling=dueling, device=device or "auto"
    )
    agent.online_net.load_state_dict(checkpoint["online_net"])
    agent.target_net.load_state_dict(checkpoint["online_net"])
    agent.epsilon = 0.0
    return agent


def run_episode(
    agent: DQNAgent,
    seed: int,
    piece_cap: int = PIECE_CAP,
    ai_config_kwargs: dict[str, Any] | None = None,
) -> float:
    """One seeded playing-mode episode via AIState; returns final score.

    The injected ``agent`` replaces the state's agent before the first
    update, so whatever AIState loaded at init is discarded. Playing mode
    never saves the model, so ``MODEL_PATH`` is never written here.

    ``AIState._on_episode_end`` auto-resets, which would hide the final
    score from this loop. A tiny subclass captures the score at the
    episode boundary instead of resetting.
    """
    import pygame

    from tetris.audio import AudioManager
    from tetris.game.piece_provider import PieceProvider
    from tetris.states.ai import AIConfig, AIState
    from tetris.states.game import GameConfig
    from tetris.visuals.particles import ParticleSystem

    class _EvalState(AIState):
        final_score: float | None = None

        def _on_episode_end(self) -> None:
            if self.game_over:
                self.final_score = float(self.stats.score)

    pygame.init()
    screen = pygame.Surface((800, 600))
    font = pygame.font.Font(None, 20)
    audio = AudioManager(sound_volume=0, music_volume=0)
    config = GameConfig(
        seed=seed,
        handicap=0,
        sound_volume=0,
        music_volume=0,
        music_song="korobeiniki",
        debug=False,
        ghost_piece=True,
        preview_count=1,
        speed_mode="normal",
    )
    kwargs = dict(ai_config_kwargs or {})
    kwargs.setdefault("ai_mode", "playing")
    ai_config = AIConfig(
        epsilon_decay=0.999,
        epsilon_end=0.0,
        lr=1e-3,
        gamma=0.97,
        batch_size=_BATCH,
        buffer_size=_BUFFER,
        curriculum=False,
        curriculum_freq=50,
        curriculum_epsilon="boost",
        warm_start=True,
        learn_per_action=0,
        lookahead=True,
        lookahead_depth=1,
        **kwargs,
    )
    state = _EvalState(
        screen=screen,
        font=font,
        audio=audio,
        config=config,
        ai_config=ai_config,
        piece_provider=PieceProvider(generator="7bag", seed=seed),
        speed="fast",
        seed=seed,
    )
    state.agent = agent
    # select_action draws from global random even in greedy mode; the
    # global state differs across episodes in one process. Re-seed.
    random.seed(seed)
    np.random.seed(seed)
    particles = ParticleSystem()
    dt = 1000 / 60
    pieces0 = state.stats.piece_count
    while state.final_score is None and state.stats.piece_count - pieces0 < piece_cap:
        state.update(dt, particles)
    if state.final_score is None:
        # Capped episode: fitness = score at the cap, game still alive.
        state.final_score = float(state.stats.score)
    return state.final_score


def evaluate_population(
    checkpoints: Sequence[dict[str, Any]],
    episodes: int,
    seed: int,
    dueling: bool,
    piece_cap: int = PIECE_CAP,
    evaluate: Callable[[DQNAgent, int], float] | None = None,
) -> list[float]:
    """Mean fitness (score) of each checkpoint across seeded episodes."""
    if evaluate is None:

        def evaluate(agent: DQNAgent, ep_seed: int) -> float:
            return run_episode(agent, ep_seed, piece_cap=piece_cap)

    scores: list[float] = []
    for ckpt in checkpoints:
        agent = make_agent(ckpt, dueling)
        total = sum(evaluate(agent, seed + e) for e in range(episodes))
        scores.append(total / episodes)
    return scores


def run_tournament(
    generations: int,
    episodes: int,
    population: int,
    sigma: float,
    seed: int,
    model_path: str = MODEL_PATH,
    piece_cap: int = PIECE_CAP,
    report_path: str = REPORT_PATH,
    best_path: str = BEST_PATH,
    evaluate: Callable[[DQNAgent, int], float] | None = None,
) -> dict[str, Any]:
    """Full evolutionary loop; returns and persists the report."""
    import tetris.states.ai as ai_mod

    if not os.path.exists(model_path):
        raise FileNotFoundError(f"no checkpoint at {model_path} — train the agent before running a tournament")
    base_ckpt = torch.load(model_path, map_location="cpu", weights_only=True)
    dueling = bool(base_ckpt.get("dueling", False))
    rng = random.Random(seed)

    # Path isolation: AIState reads these module constants at construction
    # time; redirect them so tournament episodes never touch shipped logs.
    orig_log, orig_beh = ai_mod.PLAYING_LOG_PATH, ai_mod.PLAYING_BEHAVIOR_LOG_PATH
    os.makedirs(REPORT_DIR, exist_ok=True)
    ai_mod.PLAYING_LOG_PATH = os.path.join(REPORT_DIR, "playing_log.json")
    ai_mod.PLAYING_BEHAVIOR_LOG_PATH = os.path.join(REPORT_DIR, "playing_behavior.jsonl")
    try:
        checkpoints: list[dict[str, Any]] = [base_ckpt]
        for _ in range(population - 1):
            m = dict(base_ckpt)
            m["online_net"] = mutate_weights(base_ckpt["online_net"], sigma, rng)
            checkpoints.append(m)

        report: dict[str, Any] = {
            "config": {
                "generations": generations,
                "population": population,
                "episodes": episodes,
                "sigma": sigma,
                "seed": seed,
                "model": model_path,
                "piece_cap": piece_cap,
            },
            "generations": [],
        }
        best_ckpt = base_ckpt
        best_score = float("-inf")
        for gen in range(generations):
            fitness = evaluate_population(checkpoints, episodes, seed, dueling, piece_cap, evaluate)
            gen_best = int(np.argmax(fitness))
            if fitness[gen_best] > best_score:
                best_score = fitness[gen_best]
                best_ckpt = checkpoints[gen_best]
            report["generations"].append(
                {
                    "gen": gen,
                    "best": fitness[gen_best],
                    "mean": float(np.mean(fitness)),
                    "scores": [float(f) for f in fitness],
                }
            )
            logger.info("generation %d: best=%.0f mean=%.0f", gen, fitness[gen_best], float(np.mean(fitness)))
            if gen == generations - 1:
                break
            survivors = select_survivors(fitness)
            elites = [checkpoints[i] for i in survivors]
            children: list[dict[str, Any]] = list(elites)
            # Mutated elites and uniform-crossover pairs refill the population.
            while len(children) < population:
                if rng.random() < 0.5 or len(elites) < 2:
                    parent = elites[rng.randrange(len(elites))]
                    child = dict(parent)
                    child["online_net"] = mutate_weights(parent["online_net"], sigma, rng)
                else:
                    a, b = rng.sample(elites, 2)
                    child = dict(a)
                    child["online_net"] = crossover(a["online_net"], b["online_net"], rng)
                children.append(child)
            checkpoints = children

        torch.save(best_ckpt, best_path)
        os.makedirs(os.path.dirname(report_path) or ".", exist_ok=True)
        with open(report_path, "w") as f:
            json.dump(report, f, indent=2)
        return report
    finally:
        ai_mod.PLAYING_LOG_PATH, ai_mod.PLAYING_BEHAVIOR_LOG_PATH = orig_log, orig_beh


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Evolutionary self-play tournament")
    parser.add_argument("--generations", type=int, default=3)
    parser.add_argument("--episodes", type=int, default=2)
    parser.add_argument("--population", type=int, default=8)
    parser.add_argument("--sigma", type=float, default=0.02)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--model", default=MODEL_PATH)
    parser.add_argument("--piece-cap", type=int, default=PIECE_CAP)
    args = parser.parse_args(argv)
    run_tournament(
        generations=args.generations,
        episodes=args.episodes,
        population=args.population,
        sigma=args.sigma,
        seed=args.seed,
        model_path=args.model,
        piece_cap=args.piece_cap,
    )
    print(f"Tournament report: {REPORT_PATH}")
    print(f"Best weights: {BEST_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
