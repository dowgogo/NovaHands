import json
import time
from pathlib import Path
from .environment import NovaHandsEnv
from .policy import PolicyModel
from utils.logger import logger


class DataCollector:
    def __init__(self, env: NovaHandsEnv, policy: PolicyModel, save_path: str = "rl_data.json"):
        self.env = env
        self.policy = policy
        self.save_path = Path(save_path)
        self.data = []
        self.load()

    def load(self):
        if self.save_path.exists():
            with open(self.save_path, 'r') as f:
                self.data = json.load(f)
            logger.info(f"Loaded {len(self.data)} RL samples")

    def save(self):
        with open(self.save_path, 'w') as f:
            json.dump(self.data, f, indent=2)

    def collect_episode(self):
        # 适配新版 gymnasium API：reset() 返回 (observation, info)
        obs, _info = self.env.reset()
        state = obs
        done = False
        trajectory = []

        while not done:
            action = self.policy.sample(state, epsilon=0.1)
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

