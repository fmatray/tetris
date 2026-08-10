"""AI player package: V-network DQN agent, DT-20 features, training log.

Provides the learning agent and reward computation used by
``AIState``. The base game remains playable without PyTorch —
``AIState`` handles the missing-dependency case gracefully.
"""

from tetris.ai.agent import DQNAgent
from tetris.ai.network import DQNetwork
from tetris.ai.replay_buffer import PrioritizedReplayBuffer
from tetris.ai.rewards import compute_reward, dellacherie_value, extract_features
from tetris.ai.trainer import TrainingLog

__all__ = [
    "DQNAgent",
    "DQNetwork",
    "PrioritizedReplayBuffer",
    "TrainingLog",
    "compute_reward",
    "dellacherie_value",
    "extract_features",
]