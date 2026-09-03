"""Headless training verification: run N episodes, check success criteria.

Usage: SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy python -m tetris.verify_training [episodes]

Exit 0 if all criteria met, 1 otherwise.
"""

import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

pygame.init()
pygame.mixer.init()

from tetris.audio import AudioManager
from tetris.settings import DATA_DIR, MODEL_PATH
from tetris.states.game import GameConfig
from tetris.states.ai import AIConfig
from tetris.states.ai import AIState
from tetris.visuals.fonts import get_small_font
from tetris.visuals.particles import ParticleSystem

os.makedirs(DATA_DIR, exist_ok=True)

# Step duration in ms (matches 60fps game loop)
DT = 16.67


def run_training(n_episodes: int) -> None:
    """Run ``n_episodes`` headless AI training episodes and print progress.

    Args:
        n_episodes: Number of new episodes to train (appended to any
            existing log).
    """
    screen = pygame.display.set_mode((800, 700))
    font = get_small_font()
    audio = AudioManager(sound_volume=0, music_volume=0)

    config = GameConfig(
        handicap=0,
        sound_volume=0,
        music_volume=0,
        music_song="korobeiniki",
        debug=False,
        ghost_piece=True,
        preview_count=1,
        speed_mode="normal",
    )
    ai_config = AIConfig(
        epsilon_decay=0.999,
        epsilon_end=0.1,
        lr=1e-3,
        gamma=0.97,
        batch_size=64,
        buffer_size=50_000,
        ai_mode="learning",
        curriculum=False,
        curriculum_freq=50,
        curriculum_epsilon="reset",
        warm_start=True,
        learn_per_action=2,
        lookahead=True,
        lookahead_depth=1,
    )
    state = AIState(
        screen,
        font,
        audio,
        config,
        ai_config,
    )
    particles = ParticleSystem()
    initial_episodes = state.log.total_episodes
    target = initial_episodes + n_episodes

    print(f"Starting training: {initial_episodes} existing episodes, target {target}")

    frame = 0
    while state.log.total_episodes < target:
        state.update(DT, particles)
        state.draw(screen, particles=particles)
        particles.update()
        frame += 1

        if frame % 10000 == 0:
            ep = state.log.total_episodes
            print(f"  Frame {frame}: {ep} episodes, eps={state.agent.epsilon:.4f}")

    # Save model and flush training log at end
    state.log.flush()
    try:
        state.agent.save(MODEL_PATH)
    except (OSError, RuntimeError) as e:
        print(f"Failed to save model: {e}")

    # Analyze results
    episodes = state.log.episodes[-n_episodes:]
    if not episodes:
        print("ERROR: No episodes recorded")
        sys.exit(1)

    scores = [e["score"] for e in episodes]
    steps = [e["steps"] for e in episodes]
    best_score = max(scores)
    avg_score = sum(scores) / len(scores)
    # Episode duration: steps * PLACEMENT_DELAY_MS / 1000 seconds
    avg_duration = sum(s * 0.1 for s in steps) / len(steps)
    max_loss = max(abs(e["loss"]) for e in episodes)

    print(f"\n{'=' * 60}")
    print(f"Training Results ({len(episodes)} episodes)")
    print(f"{'=' * 60}")
    print(f"Best score:       {best_score}")
    print(f"Avg score:         {avg_score:.1f}")
    print(f"Avg duration:      {avg_duration:.1f}s")
    print(f"Max loss:          {max_loss:.4f}")
    print(f"Final epsilon:     {state.agent.epsilon:.4f}")
    print(f"Total frames:      {frame}")
    print(f"{'=' * 60}")

    # Check criteria: best and average score only.
    # Duration and loss stay informational — mature episodes make
    # duration trivially large, and loss magnitude is architecture-dependent.
    c1 = best_score > 10000
    c2 = avg_score > 1000

    print("\nCriteria:")
    print(f"  Best score > 10000:     {'PASS' if c1 else 'FAIL'} ({best_score})")
    print(f"  Avg score > 1000:       {'PASS' if c2 else 'FAIL'} ({avg_score:.1f})")

    if c1 and c2:
        print("\nALL CRITERIA MET")
        sys.exit(0)
    else:
        print("\nCriteria not yet met — more training needed")
        sys.exit(1)


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 500
    run_training(n)
