import torch
import numpy as np
from models.local_model import LocalModel
from utils.logger import logger
from rl.utils import format_state


class PolicyModel(LocalModel):
    def __init__(self, skill_list, **kwargs):
        super().__init__(**kwargs)
        self.skill_list = skill_list
        self.skill_to_id = {skill: i for i, skill in enumerate(skill_list)}

    def get_action_logits(self, state_text: str) -> torch.Tensor:
        prompt = f"根据以下状态，选择最合适的技能：\n{state_text}\n技能列表：{', '.join(self.skill_list)}\n输出技能名称："
        response = self.generate(prompt, max_new_tokens=10)
        skill = response.strip()
        if skill not in self.skill_to_id:
            # Fallback: uniform distribution
            logits = torch.ones(len(self.skill_list)) / len(self.skill_list)
        else:
            logits = torch.zeros(len(self.skill_list))
            logits[self.skill_to_id[skill]] = 1.0
        return logits

    def sample(self, state: dict, epsilon: float = 0.1):
        state_text = format_state(state)
        logits = self.get_action_logits(state_text)
        probs = torch.softmax(logits, dim=-1).numpy()
        if np.random.random() < epsilon:
            # Explore uniformly
            action = np.random.randint(len(self.skill_list))
        else:
            action = np.random.choice(len(self.skill_list), p=probs)
        return action

