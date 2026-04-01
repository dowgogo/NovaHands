"""
世界模型训练器

协调世界模型各组件的训练。

特点：
- 端到端训练（可选）
- 数据集管理
- 评估和检查点
"""

import numpy as np
import logging
from typing import Optional, List, Dict, Any
from pathlib import Path

from .world_model import WorldModel, WorldModelConfig
from .data import WorldModelDataset
from .encoder import EncoderConfig
from .dynamics import DynamicsConfig
from .reward import RewardConfig

logger = logging.getLogger("novahands")


class WorldModelTrainer:
    """
    世界模型训练器
    
    协调编码器、动态模型和奖励模型的训练
    """
    
    def __init__(
        self,
        world_model: WorldModel,
        checkpoint_dir: str = "checkpoints/world_model"
    ):
        """
        Parameters
        ----------
        world_model : WorldModel
            世界模型实例
        checkpoint_dir : str
            检查点保存目录
        """
        self.world_model = world_model
        self.checkpoint_dir = Path(checkpoint_dir)
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)
        
        self.current_epoch = 0
        self.best_metrics = {}
        
        logger.info(f"WorldModelTrainer initialized: checkpoint_dir={checkpoint_dir}")
    
    def train(
        self,
        train_dataset: WorldModelDataset,
        val_dataset: Optional[WorldModelDataset] = None,
        num_epochs: int = 100,
        epochs_dynamics: int = 10,
        epochs_reward: int = 5,
        eval_interval: int = 10,
        save_interval: int = 20
    ) -> Dict[str, Any]:
        """
        训练世界模型
        
        Parameters
        ----------
        train_dataset : WorldModelDataset
            训练数据集
        val_dataset : WorldModelDataset, optional
            验证数据集
        num_epochs : int
            总训练轮数
        epochs_dynamics : int
            动态模型每轮训练轮数
        epochs_reward : int
            奖励模型每轮训练轮数
        eval_interval : int
            评估间隔
        save_interval : int
            保存间隔
            
        Returns
        -------
        training_history : dict
            训练历史
        """
        training_history = {
            "epochs": [],
            "train_metrics": [],
            "val_metrics": []
        }
        
        logger.info(
            f"Starting training: "
            f"num_epochs={num_epochs}, "
            f"train_size={len(train_dataset)}"
        )
        
        for epoch in range(num_epochs):
            self.current_epoch = epoch + 1
            
            logger.info(f"Epoch {epoch + 1}/{num_epochs}")
            
            # 训练动态模型
            logger.debug("Training dynamics model...")
            self.world_model.dynamics.train(
                self._prepare_dynamics_dataset(train_dataset),
                epochs=epochs_dynamics
            )
            
            # 训练奖励模型
            logger.debug("Training reward model...")
            self.world_model.reward.train(
                self._prepare_reward_dataset(train_dataset),
                epochs=epochs_reward
            )
            
            # 评估
            if (epoch + 1) % eval_interval == 0:
                train_metrics = self.world_model.evaluate(train_dataset)
                training_history["epochs"].append(epoch + 1)
                training_history["train_metrics"].append(train_metrics)
                
                # 验证
                if val_dataset is not None:
                    val_metrics = self.world_model.evaluate(val_dataset)
                    training_history["val_metrics"].append(val_metrics)
                    
                    logger.info(
                        f"Epoch {epoch + 1}: "
                        f"train_dynamics_mse={train_metrics['dynamics_mse']:.6f}, "
                        f"val_dynamics_mse={val_metrics['dynamics_mse']:.6f}"
                    )
                else:
                    logger.info(
                        f"Epoch {epoch + 1}: "
                        f"dynamics_mse={train_metrics['dynamics_mse']:.6f}, "
                        f"reward_mse={train_metrics['reward_mse']:.6f}"
                    )
                
                # 保存最佳模型
                self._save_if_best(val_dataset or train_dataset, train_metrics)
            
            # 保存检查点
            if (epoch + 1) % save_interval == 0:
                self._save_checkpoint(epoch + 1, train_metrics)
        
        logger.info("Training completed")
        
        # 保存最终模型
        self._save_checkpoint(num_epochs, training_history["train_metrics"][-1])
        
        return training_history
    
    def _prepare_dynamics_dataset(
        self,
        dataset: WorldModelDataset
    ) -> List[tuple]:
        """
        准备动态模型训练数据
        
        Returns
        -------
        dynamics_data : list of (state, action, next_state)
        """
        states = self.world_model.encoder.encode_batch(
            [t.observation for t in dataset.transitions]
        )
        next_states = self.world_model.encoder.encode_batch(
            [t.next_observation for t in dataset.transitions]
        )
        actions = [t.action for t in dataset.transitions]
        
        return list(zip(states, actions, next_states))
    
    def _prepare_reward_dataset(
        self,
        dataset: WorldModelDataset
    ) -> List[tuple]:
        """
        准备奖励模型训练数据
        
        Returns
        -------
        reward_data : list of (state, reward)
        """
        states = self.world_model.encoder.encode_batch(
            [t.observation for t in dataset.transitions]
        )
        rewards = [t.reward for t in dataset.transitions]
        
        return list(zip(states, rewards))
    
    def _save_if_best(
        self,
        dataset: WorldModelDataset,
        current_metrics: Dict[str, float]
    ):
        """如果当前模型最好，则保存"""
        # 选择评估指标（越小越好）
        score = current_metrics.get("dynamics_mse", np.inf) + current_metrics.get("reward_mse", np.inf)
        
        if not self.best_metrics or score < self.best_metrics.get("best_score", np.inf):
            self.best_metrics = current_metrics
            self.best_metrics["best_score"] = score
            self.best_metrics["epoch"] = self.current_epoch
            
            logger.info(
                f"New best model: score={score:.6f}, epoch={self.current_epoch}"
            )
            
            # 保存最佳模型
            best_path = self.checkpoint_dir / "best"
            self.world_model.save(str(best_path))
    
    def _save_checkpoint(
        self,
        epoch: int,
        metrics: Dict[str, float]
    ):
        """保存检查点"""
        checkpoint_path = self.checkpoint_dir / f"epoch_{epoch}"
        self.world_model.save(str(checkpoint_path))
        
        # 保存训练历史
        history_path = checkpoint_path / "metrics.json"
        import json
        with open(history_path, "w", encoding="utf-8") as f:
            json.dump(metrics, f, indent=2, ensure_ascii=False)
        
        logger.debug(f"Checkpoint saved: epoch={epoch}")
    
    def load_best(self) -> bool:
        """
        加载最佳模型
        
        Returns
        -------
        success : bool
            是否成功加载
        """
        best_path = self.checkpoint_dir / "best"
        if best_path.exists():
            self.world_model = WorldModel.load(str(best_path))
            logger.info(f"Loaded best model from {best_path}")
            return True
        else:
            logger.warning(f"Best model not found at {best_path}")
            return False
    
    def load_checkpoint(self, epoch: int) -> bool:
        """
        加载指定检查点
        
        Returns
        -------
        success : bool
            是否成功加载
        """
        checkpoint_path = self.checkpoint_dir / f"epoch_{epoch}"
        if checkpoint_path.exists():
            self.world_model = WorldModel.load(str(checkpoint_path))
            self.current_epoch = epoch
            logger.info(f"Loaded checkpoint: epoch={epoch}")
            return True
        else:
            logger.warning(f"Checkpoint not found: epoch={epoch}")
            return False
    
    def resume_training(
        self,
        train_dataset: WorldModelDataset,
        val_dataset: Optional[WorldModelDataset] = None,
        num_additional_epochs: int = 50,
        **kwargs
    ) -> Dict[str, Any]:
        """
        恢复训练
        
        Parameters
        ----------
        train_dataset : WorldModelDataset
            训练数据集
        val_dataset : WorldModelDataset, optional
            验证数据集
        num_additional_epochs : int
            额外训练轮数
        **kwargs
            传递给 train 的其他参数
            
        Returns
        -------
        training_history : dict
            训练历史
        """
        # 加载最佳模型
        if not self.load_best():
            logger.warning("No best model found, starting from scratch")
        
        # 继续训练
        return self.train(
            train_dataset,
            val_dataset,
            num_epochs=num_additional_epochs,
            **kwargs
        )
