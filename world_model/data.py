"""
世界模型数据结构定义
"""

from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
import numpy as np
import json
from pathlib import Path


@dataclass
class WorldModelTransition:
    """
    世界模型训练样本
    
    单个时间步的 (observation, action, reward, next_observation, done)
    """
    observation: Dict[str, Any]  # 当前观察
    action: str  # 技能名称或动作标识
    reward: float  # 奖励（可选，用于监督学习）
    next_observation: Dict[str, Any]  # 下一时刻观察
    done: bool  # 是否终止
    timestamp: float  # 时间戳
    
    def __post_init__(self):
        """验证数据格式"""
        if not isinstance(self.observation, dict):
            raise ValueError("observation must be a dict")
        if not isinstance(self.action, str):
            raise ValueError("action must be a string")
        if not isinstance(self.reward, (int, float)):
            raise ValueError("reward must be a number")
        if not isinstance(self.done, bool):
            raise ValueError("done must be a bool")
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典（用于序列化）"""
        # 将 numpy 数组转换为列表
        obs_dict = self._convert_ndarrays(self.observation)
        next_obs_dict = self._convert_ndarrays(self.next_observation)
        
        return {
            "observation": obs_dict,
            "action": self.action,
            "reward": self.reward,
            "next_observation": next_obs_dict,
            "done": self.done,
            "timestamp": self.timestamp
        }
    
    @staticmethod
    def _convert_ndarrays(data: Any) -> Any:
        """递归转换 numpy 数组为列表"""
        if isinstance(data, np.ndarray):
            return data.tolist()
        elif isinstance(data, dict):
            return {k: WorldModelTransition._convert_ndarrays(v) for k, v in data.items()}
        elif isinstance(data, (list, tuple)):
            return [WorldModelTransition._convert_ndarrays(v) for v in data]
        else:
            return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WorldModelTransition":
        """从字典构建"""
        return cls(
            observation=data["observation"],
            action=data["action"],
            reward=data["reward"],
            next_observation=data["next_observation"],
            done=data["done"],
            timestamp=data["timestamp"]
        )
    
    def save(self, filepath: str):
        """保存到文件（JSON 格式）"""
        path = Path(filepath)
        path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)
    
    @classmethod
    def load(cls, filepath: str) -> "WorldModelTransition":
        """从文件加载"""
        path = Path(filepath)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {filepath}")
        
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        return cls.from_dict(data)


@dataclass
class WorldModelDataset:
    """
    世界模型训练数据集
    
    管理多个 WorldModelTransition 样本，支持：
    - 添加样本
    - 批量采样
    - 持久化存储
    - 数据过滤
    """
    transitions: List[WorldModelTransition] = field(default_factory=list)
    max_size: int = 100000  # 最大样本数
    skill_vocab: Dict[str, int] = field(default_factory=dict)  # 技能名称到索引的映射
    
    def __len__(self) -> int:
        return len(self.transitions)
    
    def add(
        self,
        observation: Dict[str, Any],
        action: str,
        reward: float = 0.0,
        next_observation: Optional[Dict[str, Any]] = None,
        done: bool = False,
        timestamp: Optional[float] = None
    ):
        """
        添加单个样本
        
        Parameters
        ----------
        observation : dict
            当前观察
        action : str
            技能名称
        reward : float, optional
            奖励（默认 0.0）
        next_observation : dict, optional
            下一时刻观察（默认 None，使用 observation）
        done : bool
            是否终止
        timestamp : float, optional
            时间戳（默认当前时间）
        """
        import time
        
        if next_observation is None:
            next_observation = observation.copy()
        
        if timestamp is None:
            timestamp = time.time()
        
        # 更新技能词汇表
        if action not in self.skill_vocab:
            self.skill_vocab[action] = len(self.skill_vocab)
        
        transition = WorldModelTransition(
            observation=observation,
            action=action,
            reward=reward,
            next_observation=next_observation,
            done=done,
            timestamp=timestamp
        )
        
        # 限制最大样本数
        if len(self.transitions) >= self.max_size:
            # 删除最旧的样本
            self.transitions.pop(0)
        
        self.transitions.append(transition)
    
    def add_batch(self, transitions: List[WorldModelTransition]):
        """批量添加样本"""
        for t in transitions:
            self.add(
                observation=t.observation,
                action=t.action,
                reward=t.reward,
                next_observation=t.next_observation,
                done=t.done,
                timestamp=t.timestamp
            )
    
    def sample(
        self,
        batch_size: int,
        replace: bool = True
    ) -> List[WorldModelTransition]:
        """
        随机采样样本
        
        Parameters
        ----------
        batch_size : int
            采样数量
        replace : bool
            是否放回采样（默认 True）
        
        Returns
        -------
        samples : list of WorldModelTransition
        """
        if len(self.transitions) == 0:
            return []
        
        indices = np.random.choice(
            len(self.transitions),
            size=min(batch_size, len(self.transitions)),
            replace=replace
        )
        
        return [self.transitions[i] for i in indices]
    
    def sample_by_skill(
        self,
        skill_name: str,
        batch_size: int
    ) -> List[WorldModelTransition]:
        """
        按技能名称采样（用于特定技能的训练）
        """
        filtered = [t for t in self.transitions if t.action == skill_name]
        
        if len(filtered) == 0:
            return []
        
        indices = np.random.choice(
            len(filtered),
            size=min(batch_size, len(filtered)),
            replace=len(filtered) < batch_size
        )
        
        return [filtered[i] for i in indices]
    
    def filter_by_time(
        self,
        start_time: Optional[float] = None,
        end_time: Optional[float] = None
    ) -> List[WorldModelTransition]:
        """
        按时间范围过滤
        
        Parameters
        ----------
        start_time : float, optional
            起始时间戳
        end_time : float, optional
            结束时间戳
        
        Returns
        -------
        filtered : list of WorldModelTransition
        """
        filtered = self.transitions
        
        if start_time is not None:
            filtered = [t for t in filtered if t.timestamp >= start_time]
        
        if end_time is not None:
            filtered = [t for t in filtered if t.timestamp <= end_time]
        
        return filtered
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        获取数据集统计信息
        """
        if len(self.transitions) == 0:
            return {
                "total_transitions": 0,
                "unique_skills": 0,
                "average_reward": 0.0,
                "time_span": 0.0
            }
        
        rewards = [t.reward for t in self.transitions]
        timestamps = [t.timestamp for t in self.transitions]
        
        return {
            "total_transitions": len(self.transitions),
            "unique_skills": len(self.skill_vocab),
            "average_reward": np.mean(rewards),
            "reward_std": np.std(rewards),
            "time_span": max(timestamps) - min(timestamps),
            "oldest_timestamp": min(timestamps),
            "newest_timestamp": max(timestamps)
        }
    
    def save(self, filepath: str):
        """保存到文件"""
        path = Path(filepath)
        path.parent.mkdir(parents=True, exist_ok=True)
        
        data = {
            "transitions": [t.to_dict() for t in self.transitions],
            "skill_vocab": self.skill_vocab,
            "max_size": self.max_size
        }
        
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    
    @classmethod
    def load(cls, filepath: str) -> "WorldModelDataset":
        """从文件加载"""
        path = Path(filepath)
        if not path.exists():
            raise FileNotFoundError(f"Dataset file not found: {filepath}")
        
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        dataset = cls(
            max_size=data.get("max_size", 100000),
            skill_vocab=data.get("skill_vocab", {})
        )
        
        for t_dict in data.get("transitions", []):
            dataset.transitions.append(WorldModelTransition.from_dict(t_dict))
        
        return dataset
    
    def clear(self):
        """清空数据集"""
        self.transitions.clear()
        self.skill_vocab.clear()
    
    def split(
        self,
        train_ratio: float = 0.8,
        val_ratio: float = 0.1
    ) -> tuple["WorldModelDataset", "WorldModelDataset", "WorldModelDataset"]:
        """
        分割数据集为训练集、验证集和测试集
        
        Parameters
        ----------
        train_ratio : float
            训练集比例（默认 0.8）
        val_ratio : float
            验证集比例（默认 0.1）
        
        Returns
        -------
        train_set, val_set, test_set : WorldModelDataset
        """
        total = len(self.transitions)
        train_size = int(total * train_ratio)
        val_size = int(total * val_ratio)
        
        # 打乱数据
        indices = np.random.permutation(total)
        train_indices = indices[:train_size]
        val_indices = indices[train_size:train_size + val_size]
        test_indices = indices[train_size + val_size:]
        
        # 创建子集
        train_set = WorldModelDataset(max_size=self.max_size)
        val_set = WorldModelDataset(max_size=self.max_size)
        test_set = WorldModelDataset(max_size=self.max_size)
        
        for idx in train_indices:
            train_set.transitions.append(self.transitions[idx])
        for idx in val_indices:
            val_set.transitions.append(self.transitions[idx])
        for idx in test_indices:
            test_set.transitions.append(self.transitions[idx])
        
        # 共享技能词汇表
        train_set.skill_vocab = self.skill_vocab.copy()
        val_set.skill_vocab = self.skill_vocab.copy()
        test_set.skill_vocab = self.skill_vocab.copy()
        
        return train_set, val_set, test_set
