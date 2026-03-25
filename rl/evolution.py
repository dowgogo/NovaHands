from learning.pattern_miner import PatternMiner
from skills.skill_manager import SkillManager
from learning.skill_generator import GeneratedSkill
from utils.logger import logger


class SkillEvolution:
    def __init__(self, skill_manager: SkillManager, recorder):
        self.skill_manager = skill_manager
        self.recorder = recorder
        self.miner = PatternMiner()

    def evolve(self, success_threshold=0.8):
        actions = self.recorder.get_actions()
        patterns = self.miner.mine_patterns(actions)
        for pattern, support in patterns:
            if support >= 3:  # threshold
                # Check if pattern is already a skill? Not implemented for demo.
                skill = GeneratedSkill(
                    name=f"auto_{len(self.skill_manager.skills)}",
                    description=f"Auto-generated from pattern with support {support}",
                    actions_pattern=pattern
                )
                self.skill_manager.skills[skill.name] = skill
                logger.info(f"Evolved new skill: {skill.name}")
