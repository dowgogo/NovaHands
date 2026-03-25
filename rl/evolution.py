import time
from learning.pattern_miner import PatternMiner
from skills.skill_manager import SkillManager
from learning.skill_generator import GeneratedSkill
from utils.logger import logger


class SkillEvolution:
    def __init__(self, skill_manager: SkillManager, recorder):
        self.skill_manager = skill_manager
        self.recorder = recorder
        self.miner = PatternMiner()

    def evolve(self, success_threshold: float = 0.8):
        """
        从录制的动作中挖掘模式并自动生成技能。
        success_threshold: 预留参数，用于未来基于成功率过滤模式。
        """
        actions = self.recorder.get_actions()
        patterns = self.miner.mine_patterns(actions)
        new_skills = []
        for pattern, support in patterns:
            if support >= 3:
                # 修复：名称加时间戳避免重名覆盖
                skill_name = f"auto_{int(time.time())}_{len(self.skill_manager.skills)}"
                # 修复：通过公开方法注册技能，避免直接操作私有字典
                if self.skill_manager.get_skill(skill_name):
                    logger.debug(f"Skill '{skill_name}' already exists, skipping")
                    continue
                skill = GeneratedSkill(
                    name=skill_name,
                    description=f"Auto-generated from pattern with support {support}",
                    actions_pattern=pattern
                )
                # 通过 skills 字典注册（SkillManager 目前无 register 方法，保留向后兼容）
                self.skill_manager.skills[skill_name] = skill
                new_skills.append(skill)
                logger.info(f"Evolved new skill: {skill_name} (support={support})")
        return new_skills
