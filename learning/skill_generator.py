import json
import os
import logging
from typing import List
from skills.base_skill import BaseSkill
from .pattern_miner import PatternMiner

logger = logging.getLogger('novahands')


class GeneratedSkill(BaseSkill):
    def __init__(self, name, description, actions_pattern):
        super().__init__(name, description)
        self.actions_pattern = actions_pattern

    def execute(self, controller, **kwargs):
        for action_str in self.actions_pattern:
            if action_str.startswith("click_"):
                # This is a placeholder; in practice we'd need coordinates or template.
                pass
            elif action_str.startswith("key_"):
                key = action_str.split("_")[1]
                if key == "<LETTER>":
                    continue
                controller.press(key)
            controller.wait(0.3)


class SkillGenerator:
    def __init__(self, recorder):
        self.recorder = recorder
        self.miner = PatternMiner()

    def generate_skills(self, output_dir: str = None) -> List[BaseSkill]:
        actions = self.recorder.get_actions()
        patterns = self.miner.mine_patterns(actions)
        skills = []
        for idx, (pattern, support) in enumerate(patterns):
            skill = GeneratedSkill(
                name=f"auto_skill_{idx}",
                description=f"Auto-generated skill (support {support}): {' → '.join(pattern)}",
                actions_pattern=pattern
            )
            skills.append(skill)
            if output_dir:
                self._save_skill(skill, output_dir)
        return skills

    def _save_skill(self, skill: BaseSkill, output_dir: str):
        os.makedirs(output_dir, exist_ok=True)
        data = {
            "name": skill.name,
            "description": skill.description,
            "steps": [{"action": "press", "key": "unknown"}],  # placeholder
            "parameters": {}
        }
        with open(os.path.join(output_dir, f"{skill.name}.json"), "w") as f:
            json.dump(data, f, indent=2)
