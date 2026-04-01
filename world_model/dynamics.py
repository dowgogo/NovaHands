"""
动态预测模型

学习环境动态：给定当前状态和动作，预测下一个状态。

特点：
- 支持集成学习（估计不确定性）
- 预测状态转移残差（提升稳定性）
- 不确定性估计（安全规划）
"""

import numpy as np
import logging
from typing import Tuple, Optional, List
from dataclasses import dataclass
import pickle
from pathlib import Path

logger = logging.getLogger("novahands")


@dataclass
class DynamicsConfig:
    """动态模型配置"""
    # 网络结构
    input_dim: int = 128  # 状态维度 + 动作维度
    hidden_dim: int = 256  # 隐藏层维度
    output_dim: int = 128  # 输出维度（状态维度）
    num_layers: int = 2  # 隐藏层数量
    
    # 集成学习
    num_ensembles: int = 5  # 集成数量
    ensemble_diversity: float = 0.1  # 集成多样性
    
    # 训练
    learning_rate: float = 1e-4
    batch_size: int = 64
    max_epochs: int = 100
    
    # 不确定性估计
    uncertainty_threshold: float = 0.5  # 不确定性阈值


class DynamicsModel:
    """
    动态预测模型（集成学习）
    
    预测：s_{t+1} = s_t + f(s_t, a_t)
    使用集成学习估计不确定性
    """
    
    def __init__(self, config: Optional[DynamicsConfig] = None):
        """
        Parameters
        ----------
        config : DynamicsConfig, optional
            配置对象
        """
        self.config = config or DynamicsConfig()
        
        # 初始化集成模型
        self.ensembles = [
            self._init_model()
            for _ in range(self.config.num_ensembles)
        ]
        
        logger.info(
            f"DynamicsModel initialized: "
            f"num_ensembles={self.config.num_ensembles}, "
            f"hidden_dim={self.config.hidden_dim}"
        )
    
    def _init_model(self):
        """初始化单个模型（MLP）"""
        # 简单 MLP：输入 -> 隐藏 -> 输出
        # 使用 numpy 实现轻量级版本
        model = {
            "W1": np.random.randn(
                self.config.hidden_dim,
                self.config.input_dim
            ) * 0.01,
            "b1": np.zeros(self.config.hidden_dim),
            "W2": np.random.randn(
                self.config.output_dim,
                self.config.hidden_dim
            ) * 0.01,
            "b2": np.zeros(self.config.output_dim)
        }
        return model
    
    def _forward(self, model: dict, x: np.ndarray) -> np.ndarray:
        """前向传播"""
        # 第一层
        z1 = np.dot(model["W1"], x) + model["b1"]
        a1 = np.tanh(z1)  # 激活
        
        # 输出层
        z2 = np.dot(model["W2"], a1) + model["b2"]
        return z2
    
    def predict(
        self,
        current_state: np.ndarray,
        action_embedding: np.ndarray
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        预测下一个状态及其不确定性
        
        Parameters
        ----------
        current_state : np.ndarray (state_dim,)
            当前状态
        action_embedding : np.ndarray (action_dim,)
            动作嵌入
            
        Returns
        -------
        next_state : np.ndarray (state_dim,)
            预测的下一个状态
        uncertainty : float
            预测不确定性（集成方差）
        """
        # 拼接状态和动作
        x = np.concatenate([current_state, action_embedding])
        
        # 每个集成模型预测
        predictions = []
        for model in self.ensembles:
            delta = self._forward(model, x)  # 预测状态差
            pred_state = current_state + delta
            predictions.append(pred_state)
        
        # 平均预测
        next_state = np.mean(predictions, axis=0)
        
        # 不确定性：预测的标准差
        uncertainty = np.std(predictions, axis=0).mean()
        
        return next_state, uncertainty
    
    def predict_batch(
        self,
        states: np.ndarray,
        actions: np.ndarray
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        批量预测
        
        Parameters
        ----------
        states : np.ndarray (batch_size, state_dim)
            状态批次
        actions : np.ndarray (batch_size, action_dim)
            动作批次
            
        Returns
        -------
        next_states : np.ndarray (batch_size, state_dim)
            预测的下一状态
        uncertainties : np.ndarray (batch_size,)
            每个预测的不确定性
        """
        next_states = []
        uncertainties = []
        
        for state, action in zip(states, actions):
            next_state, uncertainty = self.predict(state, action)
            next_states.append(next_state)
            uncertainties.append(uncertainty)
        
        return np.array(next_states), np.array(uncertainties)
    
    def train(
        self,
        dataset: List[Tuple[np.ndarray, np.ndarray, np.ndarray]],
        epochs: Optional[int] = None
    ):
        """
        训练动态模型
        
        Parameters
        ----------
        dataset : list of (state, action, next_state)
            训练数据
        epochs : int, optional
            训练轮数（默认使用配置中的值）
        """
        if epochs is None:
            epochs = self.config.max_epochs
        
        logger.info(
            f"Training DynamicsModel: "
            f"dataset_size={len(dataset)}, "
            f"epochs={epochs}"
        )
        
        # 为每个集成模型训练
        for model_idx, model in enumerate(self.ensembles):
            logger.info(f"Training ensemble {model_idx + 1}/{self.config.num_ensembles}")
            self._train_single_model(model, dataset, epochs)
        
        logger.info("DynamicsModel training completed")
    
    def _train_single_model(
        self,
        model: dict,
        dataset: List[Tuple[np.ndarray, np.ndarray, np.ndarray]],
        epochs: int
    ):
        """训练单个集成模型"""
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
                batch_loss = self._update_batch(model, batch_data, learning_rate)
                epoch_loss += batch_loss
                num_batches += 1
            
            # 打印进度
            if (epoch + 1) % 10 == 0:
                avg_loss = epoch_loss / max(num_batches, 1)
                logger.debug(f"Epoch {epoch + 1}/{epochs}, Loss: {avg_loss:.6f}")
    
    def _update_batch(
        self,
        model: dict,
        batch_data: List[Tuple[np.ndarray, np.ndarray, np.ndarray]],
        learning_rate: float
    ) -> float:
        """更新模型权重"""
        total_loss = 0
        
        for state, action, next_state in batch_data:
            # 前向传播
            x = np.concatenate([state, action])
            delta_pred = self._forward(model, x)
            next_state_pred = state + delta_pred
            
            # 计算损失（MSE）
            loss = np.mean((next_state_pred - next_state) ** 2)
            total_loss += loss
            
            # 反向传播（数值梯度，简化版）
            grad = self._compute_gradient(model, x, next_state, delta_pred)
            
            # 更新权重
            model["W1"] -= learning_rate * grad["W1"]
            model["b1"] -= learning_rate * grad["b1"]
            model["W2"] -= learning_rate * grad["W2"]
            model["b2"] -= learning_rate * grad["b2"]
        
        return total_loss / len(batch_data)
    
    def _compute_gradient(
        self,
        model: dict,
        x: np.ndarray,
        next_state: np.ndarray,
        delta_pred: np.ndarray
    ) -> dict:
        """计算梯度（数值微分，简化版）"""
        eps = 1e-5
        
        # 计算损失
        def loss_fn(W):
            model["W1"] = W
            delta = self._forward(model, x)
            pred = x[:len(delta)] + delta  # state from x
            return np.mean((pred - next_state) ** 2)
        
        # 数值梯度（仅演示，实际应使用解析梯度）
        grad_W1 = np.zeros_like(model["W1"])
        grad_W2 = np.zeros_like(model["W2"])
        grad_b1 = np.zeros_like(model["b1"])
        grad_b2 = np.zeros_like(model["b2"])
        
        # 计算输出层梯度
        delta_loss = 2 * (delta_pred - (next_state - x[:len(delta_pred)]))
        grad_W2 = np.outer(delta_loss, np.tanh(np.dot(model["W1"], x) + model["b1"]))
        grad_b2 = delta_loss
        
        # 计算隐藏层梯度
        hidden = np.tanh(np.dot(model["W1"], x) + model["b1"])
        grad_hidden = np.dot(model["W2"].T, delta_loss) * (1 - hidden ** 2)
        grad_W1 = np.outer(grad_hidden, x)
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
            "ensembles": self.ensembles,
            "config": self.config
        }
        
        with open(path, "wb") as f:
            pickle.dump(model_data, f)
        
        logger.info(f"DynamicsModel saved to {filepath}")
    
    @classmethod
    def load(cls, filepath: str) -> "DynamicsModel":
        """加载模型"""
        path = Path(filepath)
        if not path.exists():
            raise FileNotFoundError(f"Model file not found: {filepath}")
        
        with open(path, "rb") as f:
            model_data = pickle.load(f)
        
        model = cls(config=model_data["config"])
        model.ensembles = model_data["ensembles"]
        
        logger.info(f"DynamicsModel loaded from {filepath}")
        return model
