import json
import os
import logging
from typing import List
from ..base_skill import BaseSkill

logger = logging.getLogger('novahands')


class ClawSkill(BaseSkill):
    def __init__(self, name, description, steps, parameters):
        super().__init__(name, description, parameters)
        self.steps = steps

    def execute(self, controller, **kwargs):
        # Bug fix: self.parameters 是类型声明字典（如 {"key": "str"}），不应合并到实际参数中
        # 正确做法：只用 kwargs 作为实际参数，self.parameters 只用于 validate_parameters
        params = dict(kwargs)
        for step in self.steps:
            action = step.get("action")
            if action == "hotkey":
                keys = step.get("keys", [])
                keys = [self._substitute(k, params) for k in keys]
                controller.press_hotkey(*keys)
            elif action == "type":
                text = self._substitute(step.get("text", ""), params)
                controller.type_text(text)
            elif action == "press":
                key = self._substitute(step.get("key", ""), params)
                controller.press(key)
            elif action == "click":
                # Could use template matching if needed
                pass
            controller.wait(0.5)

    def _substitute(self, text, params):
        for k, v in params.items():
            text = text.replace(f"{{{k}}}", str(v))
        return text


def parse_claw_skills(claw_dir: str) -> List[ClawSkill]:
    skills = []
    for file in os.listdir(claw_dir):
        if file.endswith(".json"):
            file_path = os.path.join(claw_dir, file)
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if "name" not in data or "steps" not in data:
                    logger.warning(f"Invalid claw skill file: {file}")
                    continue
                skill = ClawSkill(
                    name=data["name"],
                    description=data.get("description", ""),
                    steps=data["steps"],
                    parameters=data.get("parameters", {})
                )
                skills.append(skill)
            except Exception as e:
                logger.error(f"Failed to parse claw skill {file}: {e}")
    return skills
