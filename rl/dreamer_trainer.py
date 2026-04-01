"""
世界模型驱动的 RL 训练器

基于 DreamerV3 的思想，使用世界模型进行：
1. 想境回放（Imagined Rollout）：在潜在空间中模拟交互
2. 样本高效训练：减少真实环境交互次数
3. 不确定性感知：在高不确定性区域增加探索
"""

import logging
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
from dataclasses import dataclass
import numpy as np

from world_model import WorldModel, WorldModelConfig, WorldModelDataset
from rl.utils import format_state

logger = logging.getLogger("novahands")


class DreamerRLTrainer:
    """
    世界模型驱动的 RL 训练器
    
    训练流程：
    1. 收集真实环境数据
    2. 训练世界模型（编码器、动态、奖励）
    3. 想境回放：使用世界模型模拟大量交互
    4. 联合训练：真实 + 想境数据
    """
    
    def __init__(
        self,
        world_model: WorldModel,
        skill_list: Dict[int, str],
        config: Optional['DreamerRLConfig'] = None
    ):
        """
        Parameters
        ----------
        world_model : WorldModel
            世界模型
        skill_list : dict
            动作 ID -> 技能名称映射
        config : DreamerRLConfig, optional
            配置对象
        """
        self.world_model = world_model
        self.skill_list = skill_list
        self.config = config or DreamerRLConfig()
        
        # Q-函数（简化版：表格）
        self.q_table: Dict[str, Dict[str, float]] = {}
        
        logger.info(
            f"DreamerRLTrainer initialized: "
            f"num_skills={len(skill_list)}, "
            f"imagine_ratio={self.config.imagine_ratio}"
        )
    
    def collect_real_data(
        self,
        executor,
        num_steps: int = 100
    ) -> WorldModelDataset:
        """
        收集真实环境数据
        
        Parameters
        ----------
        executor : Executor
            执行器
        num_steps : int
            收集步数
            
        Returns
        -------
        dataset : WorldModelDataset
            收集的数据集
        """
        logger.info(f"Collecting {num_steps} real environment steps...")
        
        dataset = WorldModelDataset()
        
        for step in range(num_steps):
            # 使用当前策略选择动作
            observation = executor.get_observation()
            action_id, _ = self.select_action(observation)
            action_name = self.skill_list[action_id]
            
            # 执行动作
            result = executor.execute(action_name)
            
            # 记录数据
            dataset.add(
                observation=observation,
                action=action_name,
                reward=result.get("reward", 0.0),
                next_observation=result.get("next_observation", observation),
                done=result.get("done", False)
            )
        
        logger.info(f"Collected {len(dataset)} real transitions")
        return dataset
    
    def imagine_rollouts(
        self,
        num_rollouts: int = 100,
        horizon: int = 10
    ) -> WorldModelDataset:
        """
        想境回放：使用世界模型模拟交互
        
        Parameters
        ----------
        num_rollouts : int
            想境回放数量
        horizon : int
            每个回放的步数
            
        Returns
        -------
        dataset : WorldModelDataset
            想境数据集
        """
        logger.info(f"Imagining {num_rollouts} rollouts with horizon {horizon}...")
        
        dataset = WorldModelDataset()
        
        for rollout_idx in range(num_rollouts):
            # 随机选择起始状态（从真实数据中采样）
            if len(self.world_model.skill_embeddings) > 0:
                # 从真实数据中随机选择起始状态
                start_action = list(self.world_model.skill_embeddings.keys())[0]
                start_state = self.world_model._get_action_embedding(start_action)
            else:
                start_state = np.random.randn(self.world_model.state_dim)
            
            # 执行想境回放
            current_state = start_state
            
            for step in range(horizon):
                # 使用 Q-函数选择动作
                action_name, _ = self.select_action_from_state(current_state)
                
                # 世界模型预测
                next_state, uncertainty = self.world_model.predict_next_state(
                    current_state,
                    action_name
                )
                
                # 预测奖励
                reward = self.world_model.predict_reward(current_state)
                
                # 想境终止条件
                done = (
                    uncertainty > self.config.uncertainty_threshold or
                    np.random.rand() < self.config.exploration_rate
                )
                
                # 记录想境数据（不保存观察，因为只有潜在状态）
                # 这里使用伪观察（只包含状态信息）
                pseudo_obs = {
                    "window_title": f"state_{step}",
                    "active_app": "dreamer",
                    "cursor_pos": (0, 0)
                }
                
                dataset.add(
                    observation=pseudo_obs,
                    action=action_name,
                    reward=reward,
                    next_observation=pseudo_obs,
                    done=done,
                    timestamp=0.0
                )
                
                current_state = next_state
                
                if done:
                    break
        
        logger.info(f"Imagined {len(dataset)} transitions")
        return dataset
    
    def select_action(
        self,
        observation: Dict[str, Any]
    ) -> Tuple[int, float]:
        """
        根据观察选择动作（ε-greedy）
        
        Parameters
        ----------
        observation : dict
            当前观察
            
        Returns
        -------
        action_id : int
            动作 ID
        q_value : float
            对应的 Q 值
        """
        # 探索
        if np.random.rand() < self.config.exploration_rate:
            action_id = np.random.randint(len(self.skill_list))
            q_value = 0.0
            return action_id, q_value
        
        # 利用：使用 Q-函数
        state_key = self._state_to_key(observation)
        
        if state_key not in self.q_table:
            # 初始化 Q 值
            self.q_table[state_key] = {
                skill_name: 0.0
                for skill_name in self.skill_list.values()
            }
        
        # 选择最大 Q 值的动作
        best_skill = max(
            self.q_table[state_key].items(),
            key=lambda x: x[1]
        )
        action_name, q_value = best_skill
        
        # 找到对应的 action_id
        action_id = None
        for aid, sname in self.skill_list.items():
            if sname == action_name:
                action_id = aid
                break
        
        if action_id is None:
            action_id = np.random.randint(len(self.skill_list))
        
        return action_id, q_value
    
    def select_action_from_state(
        self,
        state: np.ndarray
    ) -> Tuple[str, float]:
        """
        根据潜在状态选择动作（用于想境回放）
        
        Parameters
        ----------
        state : np.ndarray
            潜在状态
            
        Returns
        -------
        action_name : str
            动作名称
        q_value : float
            对应的 Q 值
        """
        state_key = self._state_vector_to_key(state)
        
        if state_key not in self.q_table:
            self.q_table[state_key] = {
                skill_name: 0.0
                for skill_name in self.skill_list.values()
            }
        
        best_skill = max(
            self.q_table[state_key].items(),
            key=lambda x: x[1]
        )
        return best_skill
    
    def update_q_values(
        self,
        dataset: WorldModelDataset,
        discount_factor: float = 0.99
    ):
        """
        使用 Q-learning 更新 Q 值
        
        Parameters
        ----------
        dataset : WorldModelDataset
            训练数据集
        discount_factor : float
            折扣因子
        """
        logger.info(f"Updating Q-values with {len(dataset)} transitions...")
        
        for transition in dataset.transitions:
            # 当前状态
            current_state_key = self._state_to_key(transition.observation)
            
            # 初始化 Q 表
            if current_state_key not in self.q_table:
                self.q_table[current_state_key] = {
                    skill_name: 0.0
                    for skill_name in self.skill_list.values()
                }
            
            # 下一状态
            next_state_key = self._state_to_key(transition.next_observation)
            if next_state_key not in self.q_table:
                self.q_table[next_state_key] = {
                    skill_name: 0.0
                    for skill_name in self.skill_list.values()
                }
            
            # Q-learning 更新
            action = transition.action
            reward = transition.reward
            
            if transition.done:
                # 终止状态
                target = reward
            else:
                # 非终止状态：使用下一状态的最大 Q 值
                max_next_q = max(self.q_table[next_state_key].values())
                target = reward + discount_factor * max_next_q
            
            # 更新 Q 值
            old_q = self.q_table[current_state_key].get(action, 0.0)
            new_q = old_q + self.config.learning_rate * (target - old_q)
            self.q_table[current_state_key][action] = new_q
        
        logger.info("Q-values updated")
    
    def train(
        self,
        executor,
        num_iterations: int = 10,
        real_steps_per_iter: int = 100,
        imagine_rollouts_per_iter: int = 100
    ):
        """
        训练 RL 智能体
        
        Parameters
        ----------
        executor : Executor
            执行器
        num_iterations : int
            训练迭代次数
        real_steps_per_iter : int
            每次迭代的真实环境步数
        imagine_rollouts_per_iter : int
            每次迭代的想境回放数量
        """
        logger.info(
            f"Starting DreamerRL training: "
            f"{num_iterations} iterations, "
            f"{real_steps_per_iter} real steps/iter, "
            f"{imagine_rollouts_per_iter} imaginations/iter"
        )
        
        for iteration in range(num_iterations):
            logger.info(f"\n=== Iteration {iteration + 1}/{num_iterations} ===")
            
            # 1. 收集真实环境数据
            real_dataset = self.collect_real_data(executor, real_steps_per_iter)
            
            # 2. 训练世界模型
            if len(real_dataset) > 0:
                logger.info("Training world model...")
                self.world_model.train(
                    real_dataset,
                    epochs_dynamics=10,
                    epochs_reward=10
                )
            
            # 3. 想境回放
            imagine_dataset = self.imagine_rollouts(
                num_rollouts=imagine_rollouts_per_iter,
                horizon=self.config.imagination_horizon
            )
            
            # 4. 合并数据并更新 Q 值
            combined_dataset = self._merge_datasets(real_dataset, imagine_dataset)
            self.update_q_values(combined_dataset)
            
            # 5. 评估
            if (iteration + 1) % 5 == 0:
                avg_reward = self.evaluate(executor, num_episodes=5)
                logger.info(f"Iteration {iteration + 1}: avg_reward = {avg_reward:.4f}")
        
        logger.info("DreamerRL training completed")
    
    def evaluate(
        self,
        executor,
        num_episodes: int = 10,
        max_steps: int = 100
    ) -> float:
        """
        评估智能体
        
        Parameters
        ----------
        executor : Executor
            执行器
        num_episodes : int
            评估回合数
        max_steps : int
            每回合最大步数
            
        Returns
        -------
        avg_reward : float
            平均奖励
        """
        total_reward = 0.0
        
        for episode in range(num_episodes):
            episode_reward = 0.0
            
            for step in range(max_steps):
                observation = executor.get_observation()
                action_id, _ = self.select_action(observation)
                action_name = self.skill_list[action_id]
                
                result = executor.execute(action_name)
                reward = result.get("reward", 0.0)
                episode_reward += reward
                
                if result.get("done", False):
                    break
            
            total_reward += episode_reward
        
        avg_reward = total_reward / num_episodes
        return avg_reward
    
    def _state_to_key(self, observation: Dict[str, Any]) -> str:
        """将观察转换为 Q 表的键"""
        # 简化：使用窗口标题和光标位置
        title = observation.get("window_title", "")
        cursor = observation.get("cursor_pos", (0, 0))
        return f"{title}_{cursor[0]}_{cursor[1]}"
    
    def _state_vector_to_key(self, state: np.ndarray) -> str:
        """将潜在状态向量转换为键（离散化）"""
        # 简单离散化：使用前几个维度
        discretized = tuple(np.round(state[:4] * 10).astype(int))
        return f"state_{discretized}"
    
    def _merge_datasets(
        self,
        dataset1: WorldModelDataset,
        dataset2: WorldModelDataset
    ) -> WorldModelDataset:
        """合并两个数据集"""
        merged = WorldModelDataset()
        
        for t in dataset1.transitions:
            merged.transitions.append(t)
        
        for t in dataset2.transitions:
            merged.transitions.append(t)
        
        return merged
    
    def save(self, filepath: str):
        """保存模型"""
        path = Path(filepath)
        path.parent.mkdir(parents=True, exist_ok=True)
        
        model_data = {
            "q_table": self.q_table,
            "config": self.config
        }
        
        import pickle
        with open(path, "wb") as f:
            pickle.dump(model_data, f)
        
        logger.info(f"DreamerRLTrainer saved to {filepath}")
    
    def load(self, filepath: str):
        """加载模型"""
        import pickle
        with open(filepath, "rb") as f:
            model_data = pickle.load(f)
        
        self.q_table = model_data["q_table"]
        self.config = model_data.get("config", self.config)
        
        logger.info(f"DreamerRLTrainer loaded from {filepath}")


@dataclass
class DreamerRLConfig:
    """DreamerRL 配置"""
    # 训练
    learning_rate: float = 0.01
    discount_factor: float = 0.99
    
    # 探索
    exploration_rate: float = 0.1
    exploration_decay: float = 0.995
    
    # 想境
    imagine_ratio: float = 10.0  # 想境/真实数据比例
    imagination_horizon: int = 10  # 想境步数
    uncertainty_threshold: float = 0.5  # 不确定性阈值
