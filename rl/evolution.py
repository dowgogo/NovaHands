import os
import time
from learning.pattern_miner import PatternMiner
from skills.skill_manager import SkillManager
from learning.skill_generator import GeneratedSkill, SkillGenerator
from utils.logger import logger

# 进化技能默认持久化目录
_DEFAULT_USER_SKILL_DIR = os.path.join(
    os.path.dirname(__file__), "..", "skills", "user"
)


class SkillEvolution:
    def __init__(self, skill_manager: SkillManager, recorder, persist_dir: str = None):
        """
        Parameters
        ----------
        persist_dir : str | None
            进化技能的持久化目录，None 时使用 skills/user/。
            程序重启后可自动加载（需在 SkillManager 中扫描此目录）。
        """
        self.skill_manager = skill_manager
        self.recorder = recorder
        self.miner = PatternMiner()
        self.persist_dir = persist_dir or os.path.realpath(_DEFAULT_USER_SKILL_DIR)

    def evolve(self, success_threshold: float = 0.8) -> list:
        """从录制的动作中挖掘模式并自动生成技能。

        新增：
        - 使用 SkillManager.register_skill() 公开 API 注册（不再直接写私有字典）
        - 持久化到 self.persist_dir，重启后不丢失
        """
        actions = self.recorder.get_actions()
        patterns = self.miner.mine_patterns(actions)
        generator = SkillGenerator(self.recorder)
        new_skills = []

        for pattern, support in patterns:
            if support >= 3:
                # 名称加时间戳避免重名覆盖
                skill_name = f"auto_{int(time.time())}_{len(self.skill_manager.skills)}"
                skill = GeneratedSkill(
                    name=skill_name,
                    description=f"Auto-generated from pattern with support {support}",
                    actions_pattern=pattern
                )
                # 使用公开 API 注册（已存在则跳过）
                registered = self.skill_manager.register_skill(skill, overwrite=False)
                if not registered:
                    logger.debug(f"Skill '{skill_name}' already registered, skipping")
                    continue

                # 持久化到 skills/user/（重启后不丢失）
                try:
                    generator._save_skill(skill, self.persist_dir)
                    logger.info(f"Evolved + persisted skill: {skill_name} (support={support})")
                except OSError as e:
                    logger.warning(f"Failed to persist skill '{skill_name}': {e}")

                new_skills.append(skill)

        return new_skills
