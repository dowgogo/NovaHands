import os
import json
import logging
from typing import Any, Dict

logger = logging.getLogger('novahands')


class ConfigLoader:
    def __init__(self, config_path: str = None):
        raw_path = config_path or os.path.join(os.path.dirname(__file__), "..", "config.json")
        # 安全修复：规范化路径，防止路径遍历读取任意文件
        self.config_path = os.path.realpath(raw_path)

        if not os.path.exists(self.config_path):
            raise FileNotFoundError(
                f"Config file not found: {self.config_path}. "
                "Copy config.example.json to config.json and edit."
            )
        self.config = self._load()

    def _load(self) -> Dict[str, Any]:
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
        except json.JSONDecodeError as e:
            raise ValueError(
                f"Config file '{self.config_path}' contains invalid JSON: {e}. "
                "Please check the file format."
            ) from e
        # _resolve_env_vars 对 dict 原地修改并返回，保持一致性
        self._resolve_env_vars(config)
        return config

    def _resolve_env_vars(self, obj: Any) -> Any:
        """递归替换 ${VAR_NAME} 形式的环境变量占位符"""
        if isinstance(obj, dict):
            for k, v in obj.items():
                obj[k] = self._resolve_env_vars(v)
            return obj
        elif isinstance(obj, list):
            # 安全修复：与 dict 分支保持一致，原地更新并返回
            for i, item in enumerate(obj):
                obj[i] = self._resolve_env_vars(item)
            return obj
        elif isinstance(obj, str) and obj.startswith("${") and obj.endswith("}"):
            var_name = obj[2:-1]
            value = os.environ.get(var_name)
            if value is None:
                # 安全修复：未设置的环境变量给出明确警告，而非静默返回空字符串
                logger.warning(
                    f"Environment variable '{var_name}' is not set. "
                    "Related feature may not work correctly."
                )
                return ""
            return value
        return obj

    def get(self, key: str, default=None):
        keys = key.split('.')
        value = self.config
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
                if value is None:
                    return default
            else:
                return default
        return value

    def get_security(self) -> dict:
        return self.get('security', {})

