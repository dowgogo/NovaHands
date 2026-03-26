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
            # _TYPE_MAP["any"] = None，需在此前已 continue；其他 None 才是真正未知类型
            if expected_type not in _TYPE_MAP:
                # 未知类型名，拒绝执行，避免 eval() 注入
                raise ValueError(
                    f"Unknown parameter type '{expected_type}' for key '{key}'. "
                    f"Allowed types: {list(_TYPE_MAP.keys())}"
                )
            expected_cls = _TYPE_MAP[expected_type]
            if expected_cls is None:
                # "any" 已在上方 continue，此处不应到达；防御性跳过
                continue
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
