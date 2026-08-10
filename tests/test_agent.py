"""Tests for DQN agent: n-step returns and prioritized replay."""

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import numpy as np

from tetris.ai.agent import N_STEP, DQNAgent
from tetris.ai.replay_buffer import PrioritizedReplayBuffer


def _state(seed: int) -> np.ndarray:
    rng = np.random.RandomState(seed)
    return rng.randn(17).astype(np.float32)


class TestNStepReturns:
    def test_n_step_buffer_flush_at_done(self):
        """N-step transitions flush immediately when done=True."""
        agent = DQNAgent()
        agent.store(_state(0), 0, 1.0, _state(1), done=True)
        # done=True triggers immediate flush
        assert len(agent._n_step_buffer) == 0
        assert len(agent.buffer) == 1

    def test_n_step_accumulates_before_flush(self):
        """Transitions accumulate in n-step buffer until N_STEP reached."""
        agent = DQNAgent()
        for i in range(N_STEP - 1):
            agent.store(_state(i), 0, float(i), _state(i + 1), done=False)
        # Not enough transitions yet — buffer empty
        assert len(agent.buffer) == 0
        assert len(agent._n_step_buffer) == N_STEP - 1

    def test_n_step_pushes_at_capacity(self):
        """When n-step buffer reaches N_STEP, a transition is pushed to PER."""
        agent = DQNAgent()
        for i in range(N_STEP):
            agent.store(_state(i), 0, float(i), _state(i + 1), done=False)
        # After N_STEP transitions, one n-step return is pushed
        assert len(agent.buffer) == 1
        # Window slides — 2 remaining in n-step buffer
        assert len(agent._n_step_buffer) == N_STEP - 1

    def test_n_step_return_value(self):
        """N-step return = sum(gamma^i * r_i) for i in 0..N-1."""
        agent = DQNAgent(gamma=0.9)
        rewards = [1.0, 2.0, 3.0]
        for i in range(N_STEP):
            agent.store(_state(i), 0, rewards[i], _state(i + 1), done=False)
        # Expected: 1.0 + 0.9*2.0 + 0.81*3.0 = 1.0 + 1.8 + 2.43 = 5.23
        transition = agent.buffer.buffer[0]
        expected = sum(0.9 ** i * rewards[i] for i in range(N_STEP))
        assert abs(transition[2] - expected) < 0.01

    def test_flush_n_step(self):
        """flush_n_step empties the n-step buffer, pushing all partial returns."""
        agent = DQNAgent()
        agent.store(_state(0), 0, 1.0, _state(1), done=False)
        agent.store(_state(1), 0, 2.0, _state(2), done=False)
        agent.flush_n_step()
        assert len(agent._n_step_buffer) == 0
        assert len(agent.buffer) == 2


class TestPrioritizedReplay:
    def test_prioritized_replay_sample_proportional(self):
        """Sampling probability is proportional to priority^alpha."""
        buf = PrioritizedReplayBuffer(capacity=100, alpha=1.0, beta=0.0)
        for i in range(10):
            buf.push(_state(i), 0, float(i), _state(i + 1), done=False)
        # Set known priorities
        for i in range(10):
            buf.priorities[i] = float(i + 1)  # priorities 1..10
        # Sample many times and check high-priority transitions sampled more
        counts = np.zeros(10)
        for _ in range(1000):
            _, _, indices = buf.sample(1)
            counts[indices[0]] += 1
        # Transition with priority 10 should be sampled more than priority 1
        assert counts[9] > counts[0]

    def test_prioritized_replay_update_priorities(self):
        """update_priorities sets priority from |TD error| + epsilon."""
        buf = PrioritizedReplayBuffer(capacity=100)
        for i in range(10):
            buf.push(_state(i), 0, float(i), _state(i + 1), done=False)
        indices = np.array([0, 3, 7])
        td_errors = np.array([2.0, 5.0, 0.1])
        buf.update_priorities(indices, td_errors)
        assert abs(buf.priorities[0] - (2.0 + 1e-5)) < 1e-6
        assert abs(buf.priorities[3] - (5.0 + 1e-5)) < 1e-6
        assert abs(buf.priorities[7] - (0.1 + 1e-5)) < 1e-6

    def test_importance_weights(self):
        """IS weights correct the sampling bias."""
        buf = PrioritizedReplayBuffer(capacity=100, alpha=1.0, beta=1.0)
        for i in range(10):
            buf.push(_state(i), 0, float(i), _state(i + 1), done=False)
        for i in range(10):
            buf.priorities[i] = float(i + 1)
        _, weights, _ = buf.sample(5)
        # Weights should be (N * p_i)^(-beta) / max
        assert len(weights) == 5
        assert np.all(weights > 0)
        assert np.all(weights <= 1.0 + 1e-6)

    def test_sample_fallback_when_too_small(self):
        """When buffer < batch_size, returns all transitions with uniform weights."""
        buf = PrioritizedReplayBuffer(capacity=100)
        for i in range(3):
            buf.push(_state(i), 0, float(i), _state(i + 1), done=False)
        samples, weights, _ = buf.sample(10)
        assert len(samples) == 3
        assert np.allclose(weights, 1.0)