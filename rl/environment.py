import gymnasium as gym
from gymnasium import spaces
from typing import Dict, Any, Optional
from skills.skill_manager import SkillManager
import logging

logger = logging.getLogger('novahands')

# RL 训练的默认最大步数，防止 done=False 导致无限循环
_DEFAULT_MAX_STEPS = 50


class MockController:
    """
    安全修复：RL 训练环境专用的模拟 Controller。
    所有操作只记录日志，不会真实操控鼠标/键盘，
    防止 RL 探索阶段对真实系统造成不可预知的破坏。
    """
    def click(self, x, y, **kwargs):
        logger.debug(f"[MockController] click({x}, {y})")

    def type_text(self, text, **kwargs):
        logger.debug(f"[MockController] type_text(len={len(text)})")

    def press(self, key, **kwargs):
        logger.debug(f"[MockController] press({key})")

    def press_hotkey(self, *keys, **kwargs):
        logger.debug(f"[MockController] hotkey({'+'.join(keys)})")

    def wait(self, seconds):
        pass  # 训练时跳过真实等待，加速采样

    def move_to(self, x, y, **kwargs):
        logger.debug(f"[MockController] move_to({x}, {y})")

    def scroll(self, clicks, **kwargs):
        logger.debug(f"[MockController] scroll({clicks})")


class NovaHandsEnv(gym.Env):
    """
    NovaHands RL 训练环境。

    重要安全说明：
    - 默认使用 MockController，不会操控真实鼠标键盘。
    - 如需接入真实 Controller，请显式传入 real_controller 参数，
      并确保在安全的沙箱或测试环境中使用。
    """

    def __init__(
        self,
        skill_manager: SkillManager,
        real_controller=None,
        max_steps: int = _DEFAULT_MAX_STEPS
    ):
        super().__init__()
        self.skill_manager = skill_manager
        self.skill_list = skill_manager.list_skills()
        self.max_steps = max_steps
        self._step_count = 0

        # 安全修复：默认使用 MockController，防止随机操作真实系统
        if real_controller is not None:
            logger.warning(
                "NovaHandsEnv is using a REAL controller. "
                "This will perform actual mouse/keyboard actions on the system. "
                "Only use in a sandboxed/test environment!"
            )
            self.controller = real_controller
        else:
            self.controller = MockController()

        if not self.skill_list:
            raise ValueError("SkillManager has no skills loaded; cannot create action space.")

        self.action_space = spaces.Discrete(len(self.skill_list))
        self.observation_space = spaces.Dict({
            "current_app": spaces.Text(64),
            "last_user_input": spaces.Text(256),
            "last_skill": spaces.Text(32),
            "last_result": spaces.Discrete(2)
        })
        self.state = self._initial_state()

    def _initial_state(self) -> dict:
        return {
            "current_app": "unknown",
            "last_user_input": "",
            "last_skill": "",
            "last_result": 0
        }

    def reset(self, **kwargs):
        """符合新版 gymnasium API，返回 (observation, info)"""
        self._step_count = 0
        self.state = self._initial_state()
        return self.state, {}

    def step(self, action_idx: int):
        # 安全修复：边界检查
        if not (0 <= action_idx < len(self.skill_list)):
            raise ValueError(
                f"action_idx {action_idx} out of range [0, {len(self.skill_list)})"
            )

        skill_name = self.skill_list[action_idx]
        try:
            self.skill_manager.execute_skill(skill_name, self.controller)
            result = 1
        except Exception as e:
            logger.debug(f"Skill '{skill_name}' failed in RL step: {e}")
            result = 0

        self._step_count += 1
        new_state = self.state.copy()
        new_state["last_skill"] = skill_name
        new_state["last_result"] = result

        # Reward: +1 成功, -0.5 失败
        reward = 1.0 if result == 1 else -0.5

        # 安全修复：设置明确的终止条件，防止无限循环
        done = self._step_count >= self.max_steps
        truncated = done  # gymnasium 兼容

        self.state = new_state
        return new_state, reward, done, truncated, {"skill": skill_name, "step": self._step_count}

    def render(self, mode='human'):
        logger.info(
            f"Step {self._step_count}/{self.max_steps} | "
            f"last_skill={self.state['last_skill']} | "
            f"last_result={self.state['last_result']}"
        )

