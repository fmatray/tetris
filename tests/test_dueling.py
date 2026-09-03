"""Tests for the dueling V-network head (roadmap #4).

Covers: architecture switch, checkpoint round-trip, architecture-mismatch
guard on load, save key presence, and settings/menu plumbing.
"""

from __future__ import annotations

import os

import numpy as np
import pygame
import pytest
import torch

from tetris.ai.agent import DQNAgent
from tetris.ai.network import DQNetwork
from tetris.ai.rewards import FEATURE_SIZE

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")


def _tmp_checkpoint(tmp_path):
    return str(tmp_path / "dueling_model.pt")


def test_dueling_network_architecture():
    net = DQNetwork(FEATURE_SIZE, dueling=True)
    assert net.dueling is True
    assert hasattr(net, "value_head") and hasattr(net, "advantage_head")
    out = net(torch.randn(3, FEATURE_SIZE))
    assert out.shape == (3, 1)


def test_plain_network_architecture():
    net = DQNetwork(FEATURE_SIZE)
    assert net.dueling is False
    assert not hasattr(net, "value_head")
    out = net(torch.randn(3, FEATURE_SIZE))
    assert out.shape == (3, 1)


def test_plain_network_keeps_legacy_keys():
    """Non-dueling layout must keep the original net.0/2/4 state_dict keys
    so shipped checkpoints load unchanged."""
    net = DQNetwork(FEATURE_SIZE)
    keys = set(net.state_dict().keys())
    assert "net.0.weight" in keys
    assert "net.4.weight" in keys
    assert "trunk.0.weight" not in keys


def test_dueling_save_roundtrip(tmp_path):
    path = _tmp_checkpoint(tmp_path)
    agent = DQNAgent(dueling=True, seed=11)
    agent.save(path)
    loaded_ckpt = torch.load(path, map_location="cpu", weights_only=True)
    assert loaded_ckpt["dueling"] is True
    restored = DQNAgent(dueling=True, seed=12)
    restored.load(path)
    x = torch.randn(4, FEATURE_SIZE)
    assert torch.allclose(agent.online_net(x), restored.online_net(x))


def test_dueling_load_mismatch_guard(tmp_path):
    path = _tmp_checkpoint(tmp_path)
    dueling_agent = DQNAgent(dueling=True, seed=1)
    dueling_agent.save(path)
    plain_agent = DQNAgent(dueling=False, seed=2)
    with pytest.raises(ValueError, match="architecture mismatch"):
        plain_agent.load(path)


def test_plain_checkpoint_missing_dueling_key_loads_as_plain(tmp_path):
    """Legacy checkpoints without a 'dueling' key must load into a plain
    agent without error (defaulted to False)."""
    path = _tmp_checkpoint(tmp_path)
    plain_agent = DQNAgent(dueling=False, seed=3)
    plain_agent.save(path)
    # strip the dueling key to simulate a legacy checkpoint
    ckpt = torch.load(path, map_location="cpu", weights_only=True)
    ckpt.pop("dueling", None)
    torch.save(ckpt, path)
    legacy = DQNAgent(dueling=False, seed=4)
    legacy.load(path)  # must not raise


def test_dueling_agent_learns():
    """One learn step with dueling nets must produce finite loss."""
    agent = DQNAgent(dueling=True, buffer_size=100, batch_size=4, seed=5)
    state = np.zeros(FEATURE_SIZE, dtype=np.float32)
    for i in range(8):
        agent.store(state, 0, 1.0, state, done=(i % 4 == 3))
    loss = agent.learn()
    assert loss is not None
    assert np.isfinite(loss)


def test_dueling_learns_per_candidate_equivalence():
    """Dueling forward must stay per-sample valid: no batch coupling
    (advantage is not centered across the candidate batch)."""
    net = DQNetwork(FEATURE_SIZE, dueling=True)
    xs = torch.randn(6, FEATURE_SIZE)
    batched = net(xs)
    singles = torch.cat([net(x.unsqueeze(0)) for x in xs])
    assert torch.allclose(batched, singles, atol=1e-6)


def test_settings_plumbing():
    """MenuState must expose ai_dueling and persist it under 'ai_dueling'."""
    from tetris.states.menu import MenuState

    screen = pygame.Surface((100, 100))
    font = pygame.font.Font(None, 20)
    from tetris.audio import AudioManager

    audio = AudioManager(sound_volume=0, music_volume=0)
    menu = MenuState(screen, font, audio)
    assert menu.ai_dueling is False
    assert "ai_dueling" in MenuState._SETTINGS_MAP
    menu.ai_dueling = True
    menu.save_settings()
    menu2 = MenuState(screen, font, audio)
    assert menu2.ai_dueling is True
    # cleanup: restore persisted default
    menu2.ai_dueling = False
    menu2.save_settings()


def test_aiconfig_dueling_field():
    from tetris.states.ai import AIConfig

    def make(dueling: bool = False) -> AIConfig:
        return AIConfig(
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
            dueling=dueling,
        )

    assert make().dueling is False
    assert make(dueling=True).dueling is True
