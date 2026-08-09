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
from tetris.settings import MODEL_PATH, ensure_data_dir
from tetris.states.ai import AIState
from tetris.visuals.fonts import get_small_font
from tetris.visuals.particles import ParticleSystem

ensure_data_dir()

# Step duration in ms (matches 60fps game loop)
DT = 16.67
# AI acts every 80ms, so each step is ~5 frames
AI_INTERVAL = 80.0


def run_training(n_episodes: int) -> None:
    screen = pygame.display.set_mode((800, 700))
    font = get_small_font()
    audio = AudioManager(False)

    state = AIState(screen, font, audio, 0, False)
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

    print(f"\n{'='*60}")
    print(f"Training Results ({len(episodes)} episodes)")
    print(f"{'='*60}")
    print(f"Best score:       {best_score}")
    print(f"Avg score:         {avg_score:.1f}")
    print(f"Avg duration:      {avg_duration:.1f}s")
    print(f"Max loss:          {max_loss:.4f}")
    print(f"Final epsilon:     {state.agent.epsilon:.4f}")
    print(f"Total frames:      {frame}")
    print(f"{'='*60}")

    # Check criteria
    c1 = best_score > 10000
    c2 = avg_score > 1000
    c3 = avg_duration > 30.0
    c4 = max_loss < 1000

    print("\nCriteria:")
    print(f"  Best score > 10000:     {'PASS' if c1 else 'FAIL'} ({best_score})")
    print(f"  Avg score > 1000:       {'PASS' if c2 else 'FAIL'} ({avg_score:.1f})")
    print(f"  Avg duration > 30s:      {'PASS' if c3 else 'FAIL'} ({avg_duration:.1f}s)")
    print(f"  Loss < 1000 (stable):   {'PASS' if c4 else 'FAIL'} ({max_loss:.4f})")

    if c1 and c2 and c3 and c4:
        print("\nALL CRITERIA MET")
        sys.exit(0)
    else:
        print("\nCriteria not yet met — more training needed")
        sys.exit(1)


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 500
    run_training(n)