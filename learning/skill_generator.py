import json
import os
import logging
from typing import List
from skills.base_skill import BaseSkill
from .pattern_miner import PatternMiner

logger = logging.getLogger('novahands')


class GeneratedSkill(BaseSkill):
    """从录制的动作模式自动生成的技能。

    actions_pattern 中每个元素格式：
    - "click_<x>_<y>"   → 鼠标左键单击坐标 (x, y)
    - "key_<keyname>"   → 键盘按键
    """

    def __init__(self, name, description, actions_pattern):
        super().__init__(name, description)
        self.actions_pattern = actions_pattern

    def execute(self, controller, **kwargs):
        for action_str in self.actions_pattern:
            if action_str.startswith("click_"):
                # 格式：click_<x>_<y>，直接用坐标回放
                parts = action_str.split("_")
                try:
                    x = int(parts[1])
                    y = int(parts[2])
                    controller.click(x, y)
                    logger.debug(f"GeneratedSkill: click ({x}, {y})")
                except (IndexError, ValueError):
                    logger.warning(f"GeneratedSkill: invalid click action '{action_str}', skipping")

            elif action_str.startswith("key_"):
                # 格式：key_<keyname>
                parts = action_str.split("_", 1)
                key = parts[1] if len(parts) > 1 else ""
                if not key or key in ("<LETTER>", "<CHAR>", "unknown"):
                    # 隐私保护：字符键已被脱敏，无法回放，跳过
                    continue
                controller.press(key)
                logger.debug(f"GeneratedSkill: press {key!r}")

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
        """将生成的技能持久化为 JSON，供 claw_parser 加载。"""
        os.makedirs(output_dir, exist_ok=True)
        steps = []
        for action_str in skill.actions_pattern:
            if action_str.startswith("key_"):
                parts = action_str.split("_", 1)
                key = parts[1] if len(parts) > 1 else ""
                if key and key not in ("<LETTER>", "<CHAR>", "unknown"):
                    steps.append({"action": "press", "key": key})
            elif action_str.startswith("click_"):
                # 坐标已嵌入动作名，可完整序列化
                parts = action_str.split("_")
                try:
                    x, y = int(parts[1]), int(parts[2])
                    steps.append({"action": "click", "x": x, "y": y})
                except (IndexError, ValueError):
                    pass

        if not steps:
            steps = [{"action": "press", "key": "unknown"}]

        data = {
            "name": skill.name,
            "description": skill.description,
            "steps": steps,
            "parameters": {}
        }
        file_path = os.path.join(output_dir, f"{skill.name}.json")
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        logger.info(f"Saved generated skill: {file_path}")
