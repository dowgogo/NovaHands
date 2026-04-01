"""
潜在空间规划器

在世界模型的潜在空间中执行模型预测控制（MPC）。

特点：
- 随机打靶或交叉熵方法（CEM）
- 不确定性感知规划
- 可配置规划视野和候选数量
"""

import numpy as np
import logging
from typing import List, Tuple, Optional, Callable
from dataclasses import dataclass

from .world_model import WorldModel

logger = logging.getLogger("novahands")


@dataclass
class PlannerConfig:
    """规划器配置"""
    horizon: int = 10  # 规划视野
    num_candidates: int = 100  # 候选序列数量
    num_iterations: int = 5  # CEM 迭代次数
    top_k_ratio: float = 0.2  # CEM 保留比例
    uncertainty_weight: float = 0.1  # 不确定性惩罚权重
    planning_method: str = "random_shooting"  # "random_shooting" 或 "cem"
    action_noise_std: float = 0.1  # 动作噪声标准差


class LatentPlanner:
    """
    潜在空间规划器
    
    在世界模型的潜在空间中执行 MPC 规划
    """
    
    def __init__(
        self,
        world_model: WorldModel,
        config: Optional[PlannerConfig] = None
    ):
        """
        Parameters
        ----------
        world_model : WorldModel
            世界模型实例
        config : PlannerConfig, optional
            规划器配置
        """
        self.world_model = world_model
        self.config = config or PlannerConfig()
        
        logger.info(
            f"LatentPlanner initialized: "
            f"method={self.config.planning_method}, "
            f"horizon={self.config.horizon}"
        )
    
    def plan(
        self,
        current_state: np.ndarray,
        available_actions: List[str],
        horizon: Optional[int] = None
    ) -> Tuple[str, float, List[str]]:
        """
        规划最优动作
        
        Parameters
        ----------
        current_state : np.ndarray
            当前潜在状态
        available_actions : list of str
            可用动作列表
        horizon : int, optional
            规划视野（默认使用配置中的值）
            
        Returns
        -------
        best_action : str
            最优动作
        expected_return : float
            预期回报
        action_sequence : list of str
            完整动作序列（用于可视化）
        """
        if not available_actions:
            raise ValueError("No available actions to plan with")
        
        if horizon is None:
            horizon = self.config.horizon
        
        if self.config.planning_method == "random_shooting":
            best_sequence, best_return = self._random_shooting(
                current_state,
                available_actions,
                horizon
            )
        elif self.config.planning_method == "cem":
            best_sequence, best_return = self._cross_entropy_method(
                current_state,
                available_actions,
                horizon
            )
        else:
            raise ValueError(f"Unknown planning method: {self.config.planning_method}")
        
        # 返回第一个动作
        best_action = best_sequence[0]
        
        logger.debug(
            f"Planned action: {best_action}, "
            f"expected_return: {best_return:.3f}"
        )
        
        return best_action, best_return, best_sequence
    
    def _random_shooting(
        self,
        current_state: np.ndarray,
        available_actions: List[str],
        horizon: int
    ) -> Tuple[List[str], float]:
        """
        随机打靶方法
        
        Parameters
        ----------
        current_state : np.ndarray
            当前状态
        available_actions : list of str
            可用动作
        horizon : int
            规划视野
            
        Returns
        -------
        best_sequence : list of str
            最优动作序列
        best_return : float
            最优回报
        """
        best_return = -np.inf
        best_sequence = None
        
        # 采样多个候选序列
        for _ in range(self.config.num_candidates):
            # 随机采样动作序列
            sequence = np.random.choice(
                available_actions,
                size=horizon,
                replace=True
            ).tolist()
            
            # 评估序列
            total_reward, avg_uncertainty = self._evaluate_sequence(
                current_state,
                sequence
            )
            
            # 不确定性惩罚
            penalty = self.config.uncertainty_weight * avg_uncertainty
            adjusted_return = total_reward - penalty
            
            # 更新最优序列
            if adjusted_return > best_return:
                best_return = adjusted_return
                best_sequence = sequence
        
        return best_sequence, best_return
    
    def _cross_entropy_method(
        self,
        current_state: np.ndarray,
        available_actions: List[str],
        horizon: int
    ) -> Tuple[List[str], float]:
        """
        交叉熵方法（CEM）
        
        迭代优化动作序列分布
        """
        # 初始化：均匀分布
        action_probs = np.ones(len(available_actions)) / len(available_actions)
        
        best_return = -np.inf
        best_sequence = None
        
        for iteration in range(self.config.num_iterations):
            # 采样候选序列
            candidate_sequences = []
            candidate_returns = []
            
            for _ in range(self.config.num_candidates):
                # 从当前分布采样
                indices = np.random.choice(
                    len(available_actions),
                    size=horizon,
                    p=action_probs
                )
                sequence = [available_actions[i] for i in indices]
                
                # 评估序列
                total_reward, avg_uncertainty = self._evaluate_sequence(
                    current_state,
                    sequence
                )
                penalty = self.config.uncertainty_weight * avg_uncertainty
                adjusted_return = total_reward - penalty
                
                candidate_sequences.append(sequence)
                candidate_returns.append(adjusted_return)
            
            # 选择前 k 个序列
            top_k = int(self.config.top_k_ratio * self.config.num_candidates)
            top_indices = np.argsort(candidate_returns)[-top_k:]
            top_sequences = [candidate_sequences[i] for i in top_indices]
            
            # 更新最优
            if candidate_returns[top_indices[-1]] > best_return:
                best_return = candidate_returns[top_indices[-1]]
                best_sequence = top_sequences[-1]
            
            # 更新分布（统计每个动作的频率）
            action_counts = np.zeros(len(available_actions))
            for seq in top_sequences:
                for action in seq:
                    action_idx = available_actions.index(action)
                    action_counts[action_idx] += 1
            
            # 平滑分布
            action_probs = action_counts / (top_k * horizon)
            action_probs = np.maximum(action_probs, 1e-6)  # 避免 0
            action_probs = action_probs / action_probs.sum()
            
            logger.debug(
                f"CEM iteration {iteration + 1}/{self.config.num_iterations}, "
                f"best_return: {best_return:.3f}"
            )
        
        return best_sequence, best_return
    
    def _evaluate_sequence(
        self,
        current_state: np.ndarray,
        action_sequence: List[str]
    ) -> Tuple[float, float]:
        """
        评估动作序列
        
        Parameters
        ----------
        current_state : np.ndarray
            初始状态
        action_sequence : list of str
            动作序列
            
        Returns
        -------
        total_reward : float
            总奖励
        avg_uncertainty : float
            平均不确定性
        """
        # 在世界模型中模拟
        states, rewards, uncertainties = self.world_model.imagine_rollout(
            current_state,
            action_sequence,
            include_uncertainty=True
        )
        
        # 计算总奖励（不包含初始状态）
        total_reward = sum(rewards[1:])  # rewards[0] 是初始状态奖励
        
        # 计算平均不确定性
        avg_uncertainty = np.mean(uncertainties[1:])  # uncertainties[0] 是 0
        
        return total_reward, avg_uncertainty
    
    def plan_with_callback(
        self,
        current_state: np.ndarray,
        available_actions: List[str],
        callback: Optional[Callable[[List[str], float, float], None]] = None
    ) -> Tuple[str, float]:
        """
        规划最优动作（带回调）
        
        Parameters
        ----------
        current_state : np.ndarray
            当前状态
        available_actions : list of str
            可用动作
        callback : callable, optional
            回调函数 callback(sequence, reward, uncertainty)
            
        Returns
        -------
        best_action : str
            最优动作
        expected_return : float
            预期回报
        """
        best_action, best_return, best_sequence = self.plan(
            current_state,
            available_actions
        )
        
        # 调用回调
        if callback is not None:
            # 重新评估不确定性
            _, _, uncertainties = self.world_model.imagine_rollout(
                current_state,
                best_sequence,
                include_uncertainty=True
            )
            avg_uncertainty = np.mean(uncertainties[1:])
            callback(best_sequence, best_return, avg_uncertainty)
        
        return best_action, best_return
    
    def visualize_plan(
        self,
        current_state: np.ndarray,
        action_sequence: List[str]
    ) -> dict:
        """
        可视化规划结果
        
        Parameters
        ----------
        current_state : np.ndarray
            当前状态
        action_sequence : list of str
            动作序列
            
        Returns
        -------
        visualization : dict
            可视化数据
        """
        # 模拟轨迹
        states, rewards, uncertainties = self.world_model.imagine_rollout(
            current_state,
            action_sequence,
            include_uncertainty=True
        )
        
        visualization = {
            "action_sequence": action_sequence,
            "states": states,
            "rewards": rewards,
            "uncertainties": uncertainties,
            "total_reward": sum(rewards[1:]),
            "max_reward": max(rewards[1:]),
            "min_reward": min(rewards[1:]),
            "avg_uncertainty": np.mean(uncertainties[1:]),
            "max_uncertainty": max(uncertainties[1:])
        }
        
        return visualization
