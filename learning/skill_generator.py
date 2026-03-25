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
                # 占位：实际需要坐标或模板匹配
                pass
            elif action_str.startswith("key_"):
                # 修复：防止 split('_')[1] IndexError
                parts = action_str.split("_", 1)
                key = parts[1] if len(parts) > 1 else ""
                if not key or key == "<LETTER>":
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
        # 修复：将 actions_pattern 正确序列化为 claw_parser 可解析的 steps 格式
        steps = []
        for action_str in skill.actions_pattern:
            if action_str.startswith("key_"):
                parts = action_str.split("_", 1)
                key = parts[1] if len(parts) > 1 else ""
                if key and key != "<LETTER>":
                    steps.append({"action": "press", "key": key})
            elif action_str.startswith("click_"):
                # click 动作需要坐标，暂时跳过序列化
                pass
        if not steps:
            steps = [{"action": "press", "key": "unknown"}]  # 至少保留一个步骤

        data = {
            "name": skill.name,
            "description": skill.description,
            "steps": steps,
            "parameters": {}
        }
        with open(os.path.join(output_dir, f"{skill.name}.json"), "w") as f:
            json.dump(data, f, indent=2)
