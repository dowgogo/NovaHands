"""
奖励预测模型

预测给定状态的预期奖励。

特点：
- 轻量级（MLP）
- 支持稀疏奖励泛化
- 可训练（从 RL 数据学习）
"""

import numpy as np
import logging
from typing import List, Tuple, Optional
from dataclasses import dataclass
import pickle
from pathlib import Path

logger = logging.getLogger("novahands")


@dataclass
class RewardConfig:
    """奖励模型配置"""
    input_dim: int = 128  # 状态维度
    hidden_dim: int = 128  # 隐藏层维度
    num_layers: int = 2  # 隐藏层数量
    
    # 训练
    learning_rate: float = 1e-4
    batch_size: int = 64
    max_epochs: int = 50


class RewardModel:
    """
    奖励预测模型
    
    预测：r = f(s)
    """
    
    def __init__(self, config: Optional[RewardConfig] = None):
        """
        Parameters
        ----------
        config : RewardConfig, optional
            配置对象
        """
        self.config = config or RewardConfig()
        
        # 初始化模型权重
        self.model = self._init_model()
        
        logger.info(
            f"RewardModel initialized: "
            f"input_dim={self.config.input_dim}, "
            f"hidden_dim={self.config.hidden_dim}"
        )
    
    def _init_model(self):
        """初始化 MLP 模型"""
        model = {
            "W1": np.random.randn(
                self.config.hidden_dim,
                self.config.input_dim
            ) * 0.01,
            "b1": np.zeros(self.config.hidden_dim),
            "W2": np.random.randn(
                1,
                self.config.hidden_dim
            ) * 0.01,
            "b2": np.zeros(1)
        }
        return model
    
    def _forward(self, x: np.ndarray, model: Optional[dict] = None) -> np.ndarray:
        """前向传播"""
        if model is None:
            model = self.model

        # 第一层
        z1 = np.dot(model["W1"], x) + model["b1"]
        a1 = np.tanh(z1)

        # 输出层（标量奖励）
        z2 = np.dot(model["W2"], a1) + model["b2"]
        return z2[0]
    
    def predict(self, state: np.ndarray) -> float:
        """
        预测状态奖励
        
        Parameters
        ----------
        state : np.ndarray (state_dim,)
            状态
            
        Returns
        -------
        reward : float
            预测奖励
        """
        return self._forward(state)
    
    def predict_batch(self, states: np.ndarray) -> np.ndarray:
        """
        批量预测
        
        Parameters
        ----------
        states : np.ndarray (batch_size, state_dim)
            状态批次
            
        Returns
        -------
        rewards : np.ndarray (batch_size,)
            预测奖励
        """
        return np.array([self.predict(state) for state in states])
    
    def train(
        self,
        dataset: List[Tuple[np.ndarray, float]],
        epochs: Optional[int] = None
    ):
        """
        训练奖励模型
        
        Parameters
        ----------
        dataset : list of (state, reward)
            训练数据
        epochs : int, optional
            训练轮数
        """
        if epochs is None:
            epochs = self.config.max_epochs
        
        logger.info(
            f"Training RewardModel: "
            f"dataset_size={len(dataset)}, "
            f"epochs={epochs}"
        )
        
        batch_size = min(self.config.batch_size, len(dataset))
        learning_rate = self.config.learning_rate
        
        for epoch in range(epochs):
            # 打乱数据
            indices = np.random.permutation(len(dataset))
            
            epoch_loss = 0
            num_batches = 0
            
            for i in range(0, len(dataset), batch_size):
                # 采样批次
                batch_indices = indices[i:i + batch_size]
                batch_data = [dataset[idx] for idx in batch_indices]

                # 计算梯度并更新
                batch_loss = self._update_batch(self.model, batch_data, learning_rate)
                epoch_loss += batch_loss
                num_batches += 1
            
            # 打印进度
            if (epoch + 1) % 10 == 0:
                avg_loss = epoch_loss / max(num_batches, 1)
                logger.debug(f"Epoch {epoch + 1}/{epochs}, Loss: {avg_loss:.6f}")
        
        logger.info("RewardModel training completed")
    
    def _update_batch(
        self,
        model: dict,
        batch_data: List[Tuple[np.ndarray, float]],
        learning_rate: float
    ) -> float:
        """更新模型权重"""
        total_loss = 0

        for state, reward in batch_data:
            # 前向传播
            reward_pred = self._forward(state, model=model)

            # 计算损失（MSE）
            loss = (reward_pred - reward) ** 2
            total_loss += loss

            # 反向传播
            grad = self._compute_gradient(state, reward, reward_pred, model=model)

            # 更新权重
            model["W1"] -= learning_rate * grad["W1"]
            model["b1"] -= learning_rate * grad["b1"]
            model["W2"] -= learning_rate * grad["W2"]
            model["b2"] -= learning_rate * grad["b2"]

        return total_loss / len(batch_data)
    
    def _compute_gradient(
        self,
        state: np.ndarray,
        reward: float,
        reward_pred: float,
        model: Optional[dict] = None
    ) -> dict:
        """计算梯度"""
        if model is None:
            model = self.model

        # 前向传播（缓存中间值）
        z1 = np.dot(model["W1"], state) + model["b1"]
        a1 = np.tanh(z1)

        # 反向传播
        delta_loss = 2 * (reward_pred - reward)

        # 输出层梯度
        # W2: (1, hidden_dim), a1: (hidden_dim,)
        # grad_W2 = delta_loss * a1 -> (hidden_dim,) -> reshape to (1, hidden_dim)
        grad_W2 = (delta_loss * a1).reshape(1, -1)
        # grad_b2 = delta_loss -> scalar -> reshape to (1,)
        grad_b2 = np.array([delta_loss])

        # 隐藏层梯度
        # W2.T: (hidden_dim, 1), delta_loss: scalar
        # grad_hidden = delta_loss * W2.T * (1 - a1**2) -> (hidden_dim,)
        grad_hidden = (delta_loss * model["W2"].T.flatten()) * (1 - a1 ** 2)

        # W1: (hidden_dim, input_dim), state: (input_dim,)
        # grad_W1 = outer(grad_hidden, state) -> (hidden_dim, input_dim)
        grad_W1 = np.outer(grad_hidden, state)

        # grad_b1 = grad_hidden -> (hidden_dim,)
        grad_b1 = grad_hidden

        return {
            "W1": grad_W1,
            "b1": grad_b1,
            "W2": grad_W2,
            "b2": grad_b2
        }
    
    def save(self, filepath: str):
        """保存模型"""
        path = Path(filepath)
        path.parent.mkdir(parents=True, exist_ok=True)
        
        model_data = {
            "model": self.model,
            "config": self.config
        }
        
        with open(path, "wb") as f:
            pickle.dump(model_data, f)
        
        logger.info(f"RewardModel saved to {filepath}")
    
    @classmethod
    def load(cls, filepath: str) -> "RewardModel":
        """加载模型"""
        path = Path(filepath)
        if not path.exists():
            raise FileNotFoundError(f"Model file not found: {filepath}")
        
        with open(path, "rb") as f:
            model_data = pickle.load(f)
        
        model = cls(config=model_data["config"])
        model.model = model_data["model"]
        
        logger.info(f"RewardModel loaded from {filepath}")
        return model
