"""
World Model Module

基于 Yann LeCun 的联合嵌入预测架构（JEPA）的世界模型实现。

核心组件：
- Encoder: 观察编码器
- Dynamics: 动态预测模型
- Reward: 奖励预测模型
- Planner: 潜在空间规划器
- WorldModel: 统一世界模型接口

参考论文：
- LeWorldModel: Stable End-to-End Joint-Embedding Predictive Architecture from Pixels (2026)
- Dreamer V3: Mastering Diverse Domains through World Models (2023)
"""

from .encoder import BaseObservationEncoder
from .dynamics import DynamicsModel
from .reward import RewardModel
from .planner import LatentPlanner
from .world_model import WorldModel
from .trainer import WorldModelTrainer
from .data import WorldModelTransition, WorldModelDataset

__all__ = [
    "ObservationEncoder",
    "DynamicsModel",
    "RewardModel",
    "LatentPlanner",
    "WorldModel",
    "WorldModelTrainer",
    "WorldModelTransition",
    "WorldModelDataset"
]
