import json
import time
from pathlib import Path
from .environment import NovaHandsEnv
from .policy import PolicyModel
from utils.logger import logger

# 默认数据路径：~/.novahands/rl_data.json（绝对路径，与启动目录无关）
_DEFAULT_SAVE_PATH = Path.home() / ".novahands" / "rl_data.json"


class DataCollector:
    def __init__(
        self,
        env: NovaHandsEnv,
        policy: PolicyModel,
        save_path=None,
        epsilon: float = 0.1,
        train_frequency: int = 100,
    ):
        self.env = env
        self.policy = policy
        self.save_path = Path(save_path) if save_path else _DEFAULT_SAVE_PATH
        # rl.exploration_prob / rl.train_frequency 从 config 传入，不再硬编码
        self.epsilon = epsilon
        self.train_frequency = train_frequency
        self.data = []
        self._episodes_since_train = 0
        self.load()

    def load(self):
        if self.save_path.exists():
            try:
                with open(self.save_path, 'r') as f:
                    self.data = json.load(f)
                logger.info(f"Loaded {len(self.data)} RL samples from {self.save_path}")
            except (json.JSONDecodeError, ValueError):
                # 修复：JSON 损坏时清空重建，防止构造时崩溃
                logger.warning(
                    f"Corrupted RL data file '{self.save_path}', resetting. "
                    "Previous samples are lost."
                )
                self.data = []

    def save(self):
        # 确保目录存在
        self.save_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.save_path, 'w') as f:
            json.dump(self.data, f, indent=2)

    def collect_episode(self):
        # 适配新版 gymnasium API：reset() 返回 (observation, info)
        obs, _info = self.env.reset()
        state = obs
        done = False
        trajectory = []

        while not done:
            action = self.policy.sample(state, epsilon=self.epsilon)
            next_state, reward, done, truncated, info = self.env.step(action)
            trajectory.append((state, action, reward))
            state = next_state
            if truncated:
                break

        # 只保留含有正向奖励的轨迹
        if any(r > 0 for _, _, r in trajectory):
            for s, a, r in trajectory:
                self.data.append({"state": s, "action": a, "reward": r})
            self.save()
            logger.info(f"Collected trajectory with {len(trajectory)} steps")
        else:
            logger.debug("Discarded trajectory with no positive reward")

        # 每 train_frequency 个 episode 触发一次训练（预留接口）
        self._episodes_since_train += 1
        if self.train_frequency > 0 and self._episodes_since_train >= self.train_frequency:
            self._episodes_since_train = 0
            logger.info(f"train_frequency={self.train_frequency} reached, trigger point for fine-tuning")
