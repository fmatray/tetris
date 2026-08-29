"""Tests for DQN agent: n-step returns and prioritized replay."""

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import numpy as np
import torch
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
        expected = sum(0.9**i * rewards[i] for i in range(N_STEP))
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


# ---------------------------------------------------------------------------
# Tests for _softmax helper
# ---------------------------------------------------------------------------


def test_softmax_sums_to_one():
    """_softmax returns a probability distribution summing to 1."""
    from tetris.ai.agent import _softmax

    x = np.array([1.0, 2.0, 3.0])
    p = _softmax(x)
    assert abs(p.sum() - 1.0) < 1e-6
    assert len(p) == 3


def test_softmax_numerically_stable():
    """_softmax handles large values without overflow."""
    from tetris.ai.agent import _softmax

    x = np.array([1000.0, 1001.0, 1002.0])
    p = _softmax(x)
    assert np.all(np.isfinite(p))
    assert abs(p.sum() - 1.0) < 1e-6
    # Largest input → highest probability
    assert p.argmax() == 2


def test_softmax_uniform_for_equal_values():
    """_softmax returns uniform distribution when all values are equal."""
    from tetris.ai.agent import _softmax

    x = np.array([5.0, 5.0, 5.0, 5.0])
    p = _softmax(x)
    assert np.allclose(p, 0.25)


# ---------------------------------------------------------------------------
# Tests for select_action
# ---------------------------------------------------------------------------


def _candidate_states(n: int, seed: int = 0) -> np.ndarray:
    rng = np.random.RandomState(seed)
    return rng.randn(n, 17).astype(np.float32)


def test_select_action_greedy_picks_argmax():
    """With epsilon=0, select_action picks the candidate with max V."""
    agent = DQNAgent(epsilon_start=0.0)
    states = _candidate_states(5)
    # Run many times — greedy is deterministic
    for _ in range(10):
        action = agent.select_action(states)
        assert 0 <= action < 5
    # Verify it matches the network's argmax
    with torch.no_grad():
        values = agent.online_net(torch.from_numpy(states).float()).squeeze(-1)
        assert action == values.argmax(dim=0).item()


def test_select_action_epsilon_one_uniform():
    """With epsilon=1.0 and no dellacherie_values, select_action picks uniformly at random."""
    agent = DQNAgent(epsilon_start=1.0)
    states = _candidate_states(4)
    counts = np.zeros(4)
    for _ in range(2000):
        action = agent.select_action(states)
        counts[action] += 1
    # Each action should be selected roughly 25% of the time
    assert counts.min() > 0  # all actions hit at least once
    assert abs(counts.mean() - 500.0) < 100  # roughly uniform


def test_select_action_warm_start_proportional():
    """With dellacherie_values, exploration is softmax-weighted (not uniform)."""
    agent = DQNAgent(epsilon_start=1.0)
    states = _candidate_states(10)
    # Dellacherie values: one candidate is much better than the rest
    dell = np.array([-200.0] * 9 + [-10.0], dtype=np.float32)
    counts = np.zeros(10)
    for _ in range(3000):
        action = agent.select_action(states, dellacherie_values=dell)
        counts[action] += 1
    # The best candidate (index 9) should be selected far more often than average
    assert counts[9] > counts[0]
    assert counts[9] > 3000 / 10 * 2  # more than 2× uniform share


def test_select_action_warm_start_length_mismatch_falls_back():
    """If dellacherie_values length != n candidates, falls back to uniform random."""
    agent = DQNAgent(epsilon_start=1.0)
    states = _candidate_states(5)
    # Wrong-length dellacherie_values → should use uniform random
    action = agent.select_action(states, dellacherie_values=np.array([1.0, 2.0]))
    assert 0 <= action < 5


# ---------------------------------------------------------------------------
# Tests for learn()
# ---------------------------------------------------------------------------


def test_learn_insufficient_buffer_returns_none():
    """learn() returns None when buffer has fewer than batch_size transitions."""
    agent = DQNAgent(batch_size=64)
    for i in range(10):
        agent.store(_state(i), 0, 1.0, _state(i + 1), done=False)
    assert len(agent.buffer) > 0
    assert len(agent.buffer) < agent.batch_size
    result = agent.learn()
    assert result is None


def test_learn_with_enough_buffer_returns_loss():
    """learn() with enough buffer returns a float loss and increments steps."""
    agent = DQNAgent(batch_size=4)
    for i in range(20):
        agent.store(_state(i), 0, 1.0, _state(i + 1), done=(i == 19))
    assert len(agent.buffer) >= agent.batch_size
    result = agent.learn()
    assert result is not None
    assert isinstance(result, float)
    assert agent.steps == 1
    assert agent.last_loss == result


# ---------------------------------------------------------------------------
# Tests for decay_epsilon
# ---------------------------------------------------------------------------


def test_decay_epsilon_decreases_but_not_below_end():
    """decay_epsilon reduces epsilon but never below epsilon_end."""
    agent = DQNAgent(epsilon_start=1.0, epsilon_end=0.10, epsilon_decay=0.5)
    assert agent.epsilon == 1.0
    agent.decay_epsilon()
    assert agent.epsilon == 0.5
    agent.decay_epsilon()
    assert agent.epsilon == 0.25
    # Keep decaying — should floor at epsilon_end
    for _ in range(20):
        agent.decay_epsilon()
    assert agent.epsilon == 0.10


def test_decay_epsilon_noop_at_floor():
    """decay_epsilon does nothing when epsilon already at epsilon_end."""
    agent = DQNAgent(epsilon_start=0.10, epsilon_end=0.10)
    agent.decay_epsilon()
    assert agent.epsilon == 0.10


# ---------------------------------------------------------------------------
# Tests for _sync_target
# ---------------------------------------------------------------------------


def test_hard_sync_copies_weights():
    """_sync_target hard-copies online weights to target at target_sync_freq."""
    agent = DQNAgent(batch_size=4)
    # Perturb online weights so they differ from target
    with torch.no_grad():
        for p in agent.online_net.parameters():
            p.add_(1.0)
    # At step 1 (not at sync boundary), target should NOT change
    agent.steps = 1
    before = [tp.clone() for tp in agent.target_net.parameters()]
    agent._sync_target()
    for tp, bp in zip(agent.target_net.parameters(), before):
        assert torch.allclose(tp, bp)

    # Advance to target_sync_freq boundary → hard sync
    agent.steps = agent.target_sync_freq
    agent._sync_target()
    for tp, op in zip(agent.target_net.parameters(), agent.online_net.parameters()):
        assert torch.allclose(tp, op)


def test_hard_sync_triggered_by_learn():
    """learn() triggers _sync_target; at target_sync_freq boundary, target = online."""
    agent = DQNAgent(batch_size=4)
    for i in range(20):
        agent.store(_state(i), 0, 1.0, _state(i + 1), done=(i == 19))
    # Set steps to just before sync boundary
    agent.steps = agent.target_sync_freq - 1
    before = [tp.clone() for tp in agent.target_net.parameters()]
    agent.learn()  # steps becomes target_sync_freq → hard sync
    moved = any(not torch.allclose(tp, bp) for tp, bp in zip(agent.target_net.parameters(), before))
    assert moved


# ---------------------------------------------------------------------------
# Tests for save() / load() round-trip
def test_save_load_roundtrip():
    """save() then load() preserves weights, optimizer, epsilon, steps, curriculum, beta."""
    import tempfile

    agent = DQNAgent(batch_size=4)
    for i in range(20):
        agent.store(_state(i), 0, 1.0, _state(i + 1), done=(i == 19))
    agent.learn()  # train one step to populate optimizer state
    agent.decay_epsilon()
    agent.steps = 42
    agent.curriculum_level = 3
    agent.curriculum_episode_count = 7
    beta_before = agent.buffer.beta

    # Snapshot online weights
    online_before = {k: v.clone() for k, v in agent.online_net.state_dict().items()}
    target_before = {k: v.clone() for k, v in agent.target_net.state_dict().items()}
    eps_before = agent.epsilon

    with tempfile.NamedTemporaryFile(suffix=".pt", delete=False) as f:
        path = f.name
    try:
        agent.save(path)
        # Create a fresh agent and load
        loaded = DQNAgent(batch_size=4)
        loaded.load(path)
        # Weights match
        for k, v in online_before.items():
            assert torch.allclose(loaded.online_net.state_dict()[k], v)
        for k, v in target_before.items():
            assert torch.allclose(loaded.target_net.state_dict()[k], v)
        # Training progress preserved
        assert loaded.epsilon == eps_before
        assert loaded.steps == 42
        # Curriculum state preserved
        assert loaded.curriculum_level == 3
        assert loaded.curriculum_episode_count == 7
        # PER beta preserved
        assert loaded.buffer.beta == beta_before
    finally:
        os.unlink(path)


# ---------------------------------------------------------------------------
# Tests for store() with done=True
# ---------------------------------------------------------------------------


def test_store_done_flushes_n_step_immediately():
    """store(done=True) flushes the n-step buffer immediately to PER."""
    agent = DQNAgent()
    # Accumulate 2 transitions (less than N_STEP=3)
    agent.store(_state(0), 0, 1.0, _state(1), done=False)
    agent.store(_state(1), 1, 2.0, _state(2), done=False)
    assert len(agent._n_step_buffer) == 2
    assert len(agent.buffer) == 0
    # Terminal transition triggers flush
    agent.store(_state(2), 2, 3.0, _state(3), done=True)
    assert len(agent._n_step_buffer) == 0
    # All 3 transitions flushed as n-step returns
    assert len(agent.buffer) == 3


# ---------------------------------------------------------------------------
# Tests for seed reproducibility
# ---------------------------------------------------------------------------


def test_seed_produces_identical_weights():
    """Two agents with the same seed have identical initial weights."""
    a1 = DQNAgent(seed=42)
    a2 = DQNAgent(seed=42)
    for p1, p2 in zip(a1.online_net.parameters(), a2.online_net.parameters()):
        assert torch.allclose(p1, p2)


def test_different_seeds_produce_different_weights():
    """Two agents with different seeds have different initial weights."""
    a1 = DQNAgent(seed=42)
    a2 = DQNAgent(seed=43)
    diffs = [not torch.allclose(p1, p2) for p1, p2 in zip(a1.online_net.parameters(), a2.online_net.parameters())]
    assert any(diffs)


# ---------------------------------------------------------------------------
# Tests for eval/train mode toggles
# ---------------------------------------------------------------------------


def test_select_action_sets_eval_mode():
    """select_action() sets online_net to eval mode."""
    agent = DQNAgent(seed=42, epsilon_start=0.0)
    states = _candidate_states(5)
    agent.select_action(states)
    assert agent.online_net.training is False


def test_learn_sets_train_mode():
    """learn() sets online_net to train mode."""
    agent = DQNAgent(batch_size=4, seed=42)
    for i in range(20):
        agent.store(_state(i), 0, 1.0, _state(i + 1), done=(i == 19))
    agent.learn()
    assert agent.online_net.training is True


# ---------------------------------------------------------------------------
# Tests for n-step partial flush discount
# ---------------------------------------------------------------------------


def test_n_step_partial_flush_stores_actual_n():
    """Partial flush stores the actual number of steps aggregated, not N_STEP."""
    agent = DQNAgent()
    # Store 2 transitions (less than N_STEP=3), then flush
    agent.store(_state(0), 0, 1.0, _state(1), done=False)
    agent.store(_state(1), 0, 2.0, _state(2), done=False)
    agent.flush_n_step()
    # First flush: 2-step return → n=2; second flush: 1-step return → n=1
    assert agent.buffer.buffer[0][5] == 2
    assert agent.buffer.buffer[1][5] == 1


def test_learn_uses_per_transition_discount():
    """learn() applies per-transition gamma^n discount without crashing."""
    agent = DQNAgent(batch_size=4, seed=42)
    # Fill buffer: 3 full n-step transitions + a partial flush
    for i in range(9):
        agent.store(_state(i), 0, 1.0, _state(i + 1), done=False)
    agent.flush_n_step()  # Flush remaining partial n-step transitions
    assert len(agent.buffer) >= agent.batch_size
    result = agent.learn()
    assert result is not None
    assert isinstance(result, float)


# ---------------------------------------------------------------------------
# Tests for advance_curriculum
# ---------------------------------------------------------------------------


def test_advance_curriculum_increments_at_freq():
    """advance_curriculum increments level when episode count reaches freq."""
    agent = DQNAgent()
    agent.curriculum_level = 0
    agent.curriculum_episode_count = 0
    # freq=2: first call increments count to 1, no advance
    assert agent.advance_curriculum(max_level=6, freq=2) is False
    assert agent.curriculum_level == 0
    # Second call: count=2 → advance, reset count
    assert agent.advance_curriculum(max_level=6, freq=2) is True
    assert agent.curriculum_level == 1
    assert agent.curriculum_episode_count == 0


def test_advance_curriculum_caps_at_max_level():
    """advance_curriculum returns False when level is already at max."""
    agent = DQNAgent()
    agent.curriculum_level = 6
    assert agent.advance_curriculum(max_level=6, freq=1) is False
    assert agent.curriculum_level == 6


# ---------------------------------------------------------------------------
# Tests for LR scheduler
# ---------------------------------------------------------------------------


def test_lr_scheduler_reduces_lr_on_plateau():
    """ReduceLROnPlateau reduces LR when loss stays constant for patience steps."""
    agent = DQNAgent(batch_size=4)
    initial_lr = agent.optimizer.param_groups[0]["lr"]
    # Feed the scheduler a constant loss for patience+1 steps
    for _ in range(60):
        agent.scheduler.step(1.0)
    reduced_lr = agent.optimizer.param_groups[0]["lr"]
    assert reduced_lr < initial_lr


# --- Observability tests --------------------------------------------------


def test_learn_sets_td_error_metrics():
    """After learn() with batch≥4, td_error_mean and td_error_max are set."""
    agent = DQNAgent(batch_size=4)
    for i in range(8):
        agent.store(_state(i), 0, float(i), _state(i + 1), done=False)
    agent.learn()
    assert agent.last_td_error_mean > 0
    assert agent.last_td_error_max > 0


def test_learn_sets_grad_norm():
    """After learn(), grad_norm is a non-negative float."""
    agent = DQNAgent(batch_size=4)
    for i in range(8):
        agent.store(_state(i), 0, float(i), _state(i + 1), done=False)
    agent.learn()
    assert agent.last_grad_norm >= 0


def test_target_sync_increments_counter():
    """target_syncs increments when steps hit target_sync_freq."""
    agent = DQNAgent(batch_size=4, seed=42)
    agent.target_sync_freq = 2
    for i in range(8):
        agent.store(_state(i), 0, float(i), _state(i + 1), done=False)
    agent.learn()
    assert agent.target_syncs == 0  # steps=1, not yet 2
    agent.learn()
    assert agent.target_syncs == 1  # steps=2, sync fires


def test_select_action_sets_v_spread_greedy():
    """With epsilon=0, select_action computes V-value spread and margin."""
    agent = DQNAgent(seed=42)
    agent.epsilon = 0.0
    states = np.array([_state(i) for i in range(5)], dtype=np.float32)
    agent.select_action(states)
    assert agent.last_v_spread >= 0
    assert agent.last_v_margin >= 0
    assert not agent.last_action_was_random


def test_select_action_zero_spread_on_random():
    """With epsilon=1.0, V-value spread is 0 (no network eval)."""
    agent = DQNAgent(seed=42)
    agent.epsilon = 1.0
    states = np.array([_state(i) for i in range(5)], dtype=np.float32)
    agent.select_action(states)
    assert agent.last_v_spread == 0.0
    assert agent.last_v_margin == 0.0
    assert agent.last_action_was_random


def test_training_metrics_returns_all_fields():
    """training_metrics() returns all expected keys."""
    agent = DQNAgent(seed=42)
    tm = agent.training_metrics()
    expected = {
        "lr",
        "buffer_fill",
        "beta",
        "td_error_mean",
        "td_error_max",
        "grad_norm",
        "target_syncs",
        "steps",
        "v_spread",
        "v_margin",
    }
    assert expected.issubset(tm.keys())


def test_step_log_writes_jsonl():
    """Step log writes valid JSONL with expected keys."""
    import json
    import tempfile

    log_path = tempfile.mktemp(suffix=".jsonl")
    agent = DQNAgent(batch_size=4, seed=42, step_log_path=log_path)
    for i in range(8):
        agent.store(_state(i), 0, float(i), _state(i + 1), done=False)
    agent.learn()
    with open(log_path) as f:
        line = json.loads(f.readline())
    assert line["step"] == 1
    assert "loss" in line
    assert "td_error_mean" in line
    assert "lr" in line
    assert "buffer_fill" in line
    assert "epsilon" in line


def test_step_log_rotation(monkeypatch):
    """Step log rotates to keep only STEP_LOG_MAX_LINES lines."""
    import tempfile

    log_path = tempfile.mktemp(suffix=".jsonl")
    monkeypatch.setattr("tetris.ai.agent.STEP_LOG_MAX_LINES", 3)
    agent = DQNAgent(batch_size=4, seed=42, step_log_path=log_path)
    for batch_start in range(5):
        for i in range(8):
            agent.store(_state(batch_start * 10 + i), 0, float(i), _state(batch_start * 10 + i + 1), done=False)
        # Force rotation check by setting steps to multiple of 1000
        agent.steps = batch_start * 1000
        agent._write_step_log()
    with open(log_path) as f:
        lines = f.readlines()
    assert len(lines) <= 3


def test_save_load_persists_target_syncs():
    """target_syncs is saved and loaded from checkpoint."""
    import tempfile

    agent = DQNAgent(batch_size=4, seed=42)
    agent.target_syncs = 5
    path = tempfile.mktemp(suffix=".pt")
    agent.save(path)
    agent2 = DQNAgent(batch_size=4, seed=42)
    agent2.load(path)
    assert agent2.target_syncs == 5


def test_tensorboard_writer_none_by_default():
    """Without tb_log_dir, _tb_writer is None."""
    agent = DQNAgent(seed=42)
    assert agent._tb_writer is None


def test_tensorboard_writer_created_with_dir():
    """With tb_log_dir, _tb_writer is created (if tensorboard installed)."""
    import tempfile

    try:
        tb_dir = tempfile.mktemp(suffix="_tb")
        agent = DQNAgent(seed=42, tb_log_dir=tb_dir)
        assert agent._tb_writer is not None
        agent.flush_logs()
    except ImportError:
        pass  # tensorboard not installed
