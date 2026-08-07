"""AI player package: DQN agent, board features, training log.

Provides the learning agent and reward computation used by
``AIState``. The base game remains playable without PyTorch —
``AIState`` handles the missing-dependency case gracefully.
"""

from tetris.ai.agent import DQNAgent
from tetris.ai.network import DQNetwork
from tetris.ai.replay_buffer import ReplayBuffer
from tetris.ai.rewards import compute_reward, extract_state
from tetris.ai.trainer import TrainingLog

__all__ = [
    "DQNAgent",
    "DQNetwork",
    "ReplayBuffer",
    "TrainingLog",
    "compute_reward",
    "extract_state",
]