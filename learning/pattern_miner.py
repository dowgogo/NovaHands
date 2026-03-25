from collections import Counter
from typing import List, Tuple
import logging

logger = logging.getLogger('novahands')


class PatternMiner:
    def __init__(self, min_support=2, min_length=2, max_length=5):
        self.min_support = min_support
        self.min_length = min_length
        self.max_length = max_length

    def mine_patterns(self, actions: List[object]) -> List[Tuple[List[str], int]]:
        seq = [self._action_to_str(a) for a in actions]
        patterns = []
        for length in range(self.min_length, self.max_length + 1):
            counter = Counter()
            for i in range(len(seq) - length + 1):
                pattern = tuple(seq[i:i + length])
                counter[pattern] += 1
            for pattern, count in counter.items():
                if count >= self.min_support:
                    patterns.append((list(pattern), count))
        return patterns

    def _action_to_str(self, action):
        if action.type == "click":
            # 保留坐标，格式 click_<x>_<y>，供 GeneratedSkill 回放
            x = action.details.get('x', 0)
            y = action.details.get('y', 0)
            return f"click_{x}_{y}"
        elif action.type == "key_press":
            key = action.details['key']
            # Avoid recording actual letters for privacy
            if len(key) == 1 and key.isalpha():
                key = "<LETTER>"
            return f"key_{key}"
        else:
            return action.type
