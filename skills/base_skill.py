from abc import ABC, abstractmethod

# 安全的类型映射表，替代危险的 eval()
_TYPE_MAP = {
    "str": str,
    "int": int,
    "float": float,
    "bool": bool,
    "list": list,
    "dict": dict,
    "tuple": tuple,
    "any": None,
}


class BaseSkill(ABC):
    def __init__(self, name: str, description: str, parameters: dict = None):
        self.name = name
        self.description = description
        self.parameters = parameters or {}

    @abstractmethod
    def execute(self, controller, **kwargs):
        pass

    def validate_parameters(self, **kwargs) -> bool:
        for key, expected_type in self.parameters.items():
            if key not in kwargs:
                return False
            if expected_type == "any":
                continue
            expected_cls = _TYPE_MAP.get(expected_type)
            if expected_cls is None:
                # 未知类型名，拒绝执行，避免 eval() 注入
                raise ValueError(
                    f"Unknown parameter type '{expected_type}' for key '{key}'. "
                    f"Allowed types: {list(_TYPE_MAP.keys())}"
                )
            if not isinstance(kwargs[key], expected_cls):
                return False
        return True

    def to_dict(self):
        return {
            "type": "native",
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters
        }
