import os
import importlib
import logging
from typing import Dict, List, Optional
from .base_skill import BaseSkill

logger = logging.getLogger('novahands')


class SkillManager:
    def __init__(self):
        self.skills: Dict[str, BaseSkill] = {}
        self._load_native_skills()
        self._load_claw_skills()

    def _load_native_skills(self):
        native_dir = os.path.join(os.path.dirname(__file__), "native")
        if not os.path.exists(native_dir):
            return
        for file in os.listdir(native_dir):
            if file.endswith(".py") and not file.startswith("__"):
                module_name = f"skills.native.{file[:-3]}"
                try:
                    module = importlib.import_module(module_name)
                    for attr_name in dir(module):
                        attr = getattr(module, attr_name)
                        if isinstance(attr, type) and issubclass(attr, BaseSkill) and attr != BaseSkill:
                            skill_instance = attr()
                            self.skills[skill_instance.name] = skill_instance
                            logger.info(f"Loaded native skill: {skill_instance.name}")
                except Exception as e:
                    logger.error(f"Failed to load skill module {module_name}: {e}")

    def _load_claw_skills(self):
        claw_dir = os.path.join(os.path.dirname(__file__), "claw_compat")
        if os.path.exists(claw_dir):
            from skills.claw_compat.claw_parser import parse_claw_skills
            try:
                claw_skills = parse_claw_skills(claw_dir)
                for skill in claw_skills:
                    self.skills[skill.name] = skill
                    logger.info(f"Loaded claw skill: {skill.name}")
            except Exception as e:
                logger.error(f"Failed to load claw skills: {e}")

    def get_skill(self, name: str) -> Optional[BaseSkill]:
        return self.skills.get(name)

    def list_skills(self) -> List[str]:
        return list(self.skills.keys())

    def register_skill(self, skill: BaseSkill, overwrite: bool = False) -> bool:
        """公开的技能注册接口。

        Parameters
        ----------
        skill : BaseSkill
            要注册的技能实例。
        overwrite : bool
            False（默认）：若同名技能已存在，跳过并返回 False。
            True：强制覆盖已有技能。

        Returns
        -------
        bool
            True 表示注册成功，False 表示已存在且未覆盖。
        """
        if not isinstance(skill, BaseSkill):
            raise TypeError(f"Expected BaseSkill instance, got {type(skill)}")
        if not skill.name:
            raise ValueError("Skill name cannot be empty")

        if skill.name in self.skills and not overwrite:
            logger.debug(f"Skill '{skill.name}' already registered, skipping (pass overwrite=True to force)")
            return False

        self.skills[skill.name] = skill
        logger.info(f"Registered skill: {skill.name} (overwrite={overwrite})")
        return True

    def execute_skill(self, name: str, controller, **kwargs):
        skill = self.get_skill(name)
        if not skill:
            raise ValueError(f"Skill '{name}' not found")
        if not skill.validate_parameters(**kwargs):
            raise ValueError(f"Parameter validation failed for {name}, expected {skill.parameters}")
        try:
            skill.execute(controller, **kwargs)
            logger.info(f"Skill {name} executed successfully")
        except Exception as e:
            logger.error(f"Skill {name} execution failed: {e}")
            raise
