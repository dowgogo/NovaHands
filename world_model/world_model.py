"""
世界模型统一接口

整合编码器、动态模型、奖励模型和规划器。
提供统一的世界模型 API。
"""

import numpy as np
import logging
from typing import Dict, Any, Optional, Tuple, List
from pathlib import Path
import json
from dataclasses import dataclass

from .encoder import BaseObservationEncoder, create_encoder, EncoderConfig
from .dynamics import DynamicsModel, DynamicsConfig
from .reward import RewardModel, RewardConfig
from .data import WorldModelTransition, WorldModelDataset

logger = logging.getLogger("novahands")


@dataclass
class WorldModelConfig:
    """世界模型配置"""
    # 编码器
    encoder_config: Optional[EncoderConfig] = None
    encoder_type: str = "simple"
    
    # 动态模型
    dynamics_config: Optional[DynamicsConfig] = None
    
    # 奖励模型
    reward_config: Optional[RewardConfig] = None
    
    # 技能嵌入
    action_embedding_dim: int = 64
    max_skills: int = 1000  # 最大技能数量
    
    # 缓存
    cache_dir: str = "cache/world_model"


class WorldModel:
    """
    世界模型
    
    核心组件：
    1. 编码器：观察 -> 潜在状态
    2. 动态模型：(s, a) -> s' + 不确定性
    3. 奖励模型：s -> r
    4. 技能嵌入：技能名 -> 向量
    """
    
    def __init__(self, config: Optional[WorldModelConfig] = None):
        """
        Parameters
        ----------
        config : WorldModelConfig, optional
            配置对象
        """
        self.config = config or WorldModelConfig()
        
        # 初始化组件
        self.encoder = create_encoder(
            self.config.encoder_type,
            self.config.encoder_config
        )
        self.dynamics = DynamicsModel(self.config.dynamics_config)
        self.reward = RewardModel(self.config.reward_config)
        
        # 技能嵌入（随机初始化，可训练）
        self.skill_embeddings = {}
        self.action_embedding_dim = self.config.action_embedding_dim
        
        logger.info("WorldModel initialized")
    
    def _get_action_embedding(self, action: str) -> np.ndarray:
        """
        获取技能动作嵌入
        
        Parameters
        ----------
        action : str
            技能名称
            
        Returns
        -------
        embedding : np.ndarray (action_embedding_dim,)
        """
        # 检查缓存
        if action in self.skill_embeddings:
            return self.skill_embeddings[action]
        
        # 创建新嵌入（随机初始化）
        embedding = np.random.randn(self.action_embedding_dim) * 0.01
        embedding = embedding / (np.linalg.norm(embedding) + 1e-8)
        
        self.skill_embeddings[action] = embedding
        return embedding
    
    def encode_observation(
        self,
        observation: Dict[str, Any]
    ) -> np.ndarray:
        """
        编码观察为潜在状态
        
        Parameters
        ----------
        observation : dict
            观察数据
            
        Returns
        -------
        latent_state : np.ndarray (latent_dim,)
            潜在状态
        """
        return self.encoder.encode(observation)
    
    def predict_next_state(
        self,
        current_state: np.ndarray,
        action: str
    ) -> Tuple[np.ndarray, float]:
        """
        预测下一个状态及其不确定性
        
        Parameters
        ----------
        current_state : np.ndarray
            当前潜在状态
        action : str
            技能动作
            
        Returns
        -------
        next_state : np.ndarray
            预测的下一个状态
        uncertainty : float
            预测不确定性
        """
        action_embedding = self._get_action_embedding(action)
        return self.dynamics.predict(current_state, action_embedding)
    
    def predict_reward(
        self,
        state: np.ndarray
    ) -> float:
        """
        预测状态奖励
        
        Parameters
        ----------
        state : np.ndarray
            潜在状态
            
        Returns
        -------
        reward : float
            预测奖励
        """
        return self.reward.predict(state)
    
    def imagine_rollout(
        self,
        initial_state: np.ndarray,
        action_sequence: List[str],
        include_uncertainty: bool = True
    ) -> Tuple[List[np.ndarray], List[float], List[float]]:
        """
        想象/模拟动作序列
        
        Parameters
        ----------
        initial_state : np.ndarray
            初始状态
        action_sequence : list of str
            动作序列
        include_uncertainty : bool
            是否包含不确定性（默认 True）
            
        Returns
        -------
        states : list of np.ndarray
            状态轨迹（包括初始状态）
        rewards : list of float
            奖励轨迹
        uncertainties : list of float
            不确定性轨迹（如果 include_uncertainty=True）
        """
        states = [initial_state]
        rewards = [self.predict_reward(initial_state)]
        uncertainties = [0.0] if include_uncertainty else []
        
        current_state = initial_state
        
        for action in action_sequence:
            # 预测下一状态
            next_state, uncertainty = self.predict_next_state(current_state, action)
            
            # 预测奖励
            reward = self.predict_reward(next_state)
            
            # 记录
            states.append(next_state)
            rewards.append(reward)
            if include_uncertainty:
                uncertainties.append(uncertainty)
            
            current_state = next_state
        
        return states, rewards, uncertainties
    
    def collect_training_data(
        self,
        observations: List[Dict[str, Any]],
        actions: List[str],
        rewards: Optional[List[float]] = None,
        next_observations: Optional[List[Dict[str, Any]]] = None,
        dones: Optional[List[bool]] = None
    ) -> WorldModelDataset:
        """
        收集训练数据
        
        Parameters
        ----------
        observations : list of dict
            观察列表
        actions : list of str
            动作列表
        rewards : list of float, optional
            奖励列表（默认全 0）
        next_observations : list of dict, optional
            下一观察列表（默认同 observations）
        dones : list of bool, optional
            终止标志列表（默认全 False）
            
        Returns
        -------
        dataset : WorldModelDataset
            训练数据集
        """
        n = len(observations)
        assert len(actions) == n, "observations and actions must have same length"
        
        if rewards is None:
            rewards = [0.0] * n
        if next_observations is None:
            next_observations = observations.copy()
        if dones is None:
            dones = [False] * n
        
        dataset = WorldModelDataset()
        
        import time
        current_time = time.time()
        
        for i in range(n):
            dataset.add(
                observation=observations[i],
                action=actions[i],
                reward=rewards[i],
                next_observation=next_observations[i],
                done=dones[i],
                timestamp=current_time - (n - i)
            )
        
        logger.info(f"Collected {n} training samples")
        return dataset
    
    def train(
        self,
        dataset: WorldModelDataset,
        epochs_dynamics: int = 100,
        epochs_reward: int = 50
    ):
        """
        训练世界模型
        
        Parameters
        ----------
        dataset : WorldModelDataset
            训练数据集
        epochs_dynamics : int
            动态模型训练轮数
        epochs_reward : int
            奖励模型训练轮数
        """
        # 编码观察
        logger.info("Encoding observations...")
        states = self.encoder.encode_batch([t.observation for t in dataset.transitions])
        next_states = self.encoder.encode_batch([t.next_observation for t in dataset.transitions])
        actions = [t.action for t in dataset.transitions]
        rewards = [t.reward for t in dataset.transitions]
        
        # 准备动态模型训练数据
        dynamics_dataset = list(zip(
            states,
            actions,
            next_states
        ))
        
        # 准备奖励模型训练数据
        reward_dataset = list(zip(states, rewards))
        
        # 训练动态模型
        logger.info("Training dynamics model...")
        self.dynamics.train(dynamics_dataset, epochs=epochs_dynamics)
        
        # 训练奖励模型
        logger.info("Training reward model...")
        self.reward.train(reward_dataset, epochs=epochs_reward)
        
        logger.info("WorldModel training completed")
    
    def evaluate(
        self,
        dataset: WorldModelDataset,
        num_samples: int = 100
    ) -> Dict[str, float]:
        """
        评估世界模型性能
        
        Parameters
        ----------
        dataset : WorldModelDataset
            评估数据集
        num_samples : int
            采样数量
            
        Returns
        -------
        metrics : dict
            评估指标
        """
        # 采样评估数据
        samples = dataset.sample(num_samples)
        
        if not samples:
            return {
                "num_samples": 0,
                "dynamics_mse": 0.0,
                "reward_mse": 0.0
            }
        
        # 编码观察
        states = self.encoder.encode_batch([t.observation for t in samples])
        next_states = self.encoder.encode_batch([t.next_observation for t in samples])
        actions = [t.action for t in samples]
        rewards = [t.reward for t in samples]
        
        # 评估动态模型
        dynamics_errors = []
        reward_errors = []
        
        for state, action, true_next_state, true_reward in zip(
            states, actions, next_states, rewards
        ):
            # 预测下一状态
            pred_next_state, _ = self.predict_next_state(state, action)
            dynamics_error = np.mean((pred_next_state - true_next_state) ** 2)
            dynamics_errors.append(dynamics_error)
            
            # 预测奖励
            pred_reward = self.predict_reward(state)
            reward_error = (pred_reward - true_reward) ** 2
            reward_errors.append(reward_error)
        
        metrics = {
            "num_samples": num_samples,
            "dynamics_mse": np.mean(dynamics_errors),
            "dynamics_mse_std": np.std(dynamics_errors),
            "reward_mse": np.mean(reward_errors),
            "reward_mse_std": np.std(reward_errors)
        }
        
        logger.info(f"Evaluation metrics: {metrics}")
        return metrics
    
    def save(self, filepath: str):
        """
        保存世界模型
        
        Parameters
        ----------
        filepath : str
            保存路径（目录）
        """
        path = Path(filepath)
        path.mkdir(parents=True, exist_ok=True)
        
        # 保存组件
        self.encoder.save_cache(path / "encoder_cache.pkl")
        self.dynamics.save(path / "dynamics.pkl")
        self.reward.save(path / "reward.pkl")
        
        # 保存技能嵌入
        with open(path / "skill_embeddings.json", "w", encoding="utf-8") as f:
            # 转换 numpy 数组为列表
            skill_embeddings_json = {
                skill: embedding.tolist()
                for skill, embedding in self.skill_embeddings.items()
            }
            json.dump(skill_embeddings_json, f, indent=2, ensure_ascii=False)
        
        # 保存配置
        with open(path / "config.json", "w", encoding="utf-8") as f:
            config_dict = {
                "encoder_type": self.config.encoder_type,
                "action_embedding_dim": self.config.action_embedding_dim,
                "max_skills": self.config.max_skills
            }
            json.dump(config_dict, f, indent=2, ensure_ascii=False)
        
        logger.info(f"WorldModel saved to {filepath}")
    
    @classmethod
    def load(cls, filepath: str) -> "WorldModel":
        """
        加载世界模型
        
        Parameters
        ----------
        filepath : str
            加载路径（目录）
            
        Returns
        -------
        world_model : WorldModel
            加载的世界模型
        """
        path = Path(filepath)
        if not path.exists():
            raise FileNotFoundError(f"WorldModel not found: {filepath}")
        
        # 加载配置
        with open(path / "config.json", "r", encoding="utf-8") as f:
            config_dict = json.load(f)
        
        config = WorldModelConfig(
            encoder_type=config_dict.get("encoder_type", "simple"),
            action_embedding_dim=config_dict.get("action_embedding_dim", 64),
            max_skills=config_dict.get("max_skills", 1000)
        )
        
        # 创建世界模型
        world_model = cls(config)
        
        # 加载组件
        world_model.encoder.load_cache(path / "encoder_cache.pkl")
        world_model.dynamics = DynamicsModel.load(path / "dynamics.pkl")
        world_model.reward = RewardModel.load(path / "reward.pkl")
        
        # 加载技能嵌入
        with open(path / "skill_embeddings.json", "r", encoding="utf-8") as f:
            skill_embeddings_json = json.load(f)
            world_model.skill_embeddings = {
                skill: np.array(embedding)
                for skill, embedding in skill_embeddings_json.items()
            }
        
        logger.info(f"WorldModel loaded from {filepath}")
        return world_model
