import requests
import logging
from typing import Optional
from .base_model import BaseModel

logger = logging.getLogger('novahands')


class OllamaModel(BaseModel):
    """Ollama 本地 LLM 模型适配器。

    新增功能（对应 Ollama v0.9.0+）：
    - thinking 模式：设置 think=True 启用推理模型的 <think> 标签输出，
      自动剥离思考过程，只返回最终答案。
    - 可配置超时：默认 60s（thinking 模式下推理更耗时）。
    - 连接错误细化日志。
    """

    def __init__(self, model_name: str, base_url: str = "http://localhost:11434",
                 think: bool = False, timeout: int = 60, **kwargs):
        """
        Parameters
        ----------
        model_name : str
            Ollama 模型名称，如 "qwen2.5:7b"、"llama3.1:8b"。
        base_url : str
            Ollama API 地址，默认 http://localhost:11434。
        think : bool
            是否启用 thinking 模式（Ollama v0.9.0+，适用于 qwq/deepseek-r1 等推理模型）。
            启用后 API 会返回 message.thinking 字段（内部推理），
            本实现自动剥离，只返回 message.content。
        timeout : int
            HTTP 请求超时秒数，thinking 模式建议设为 120。
        """
        super().__init__(model_name, **kwargs)
        self.base_url = base_url.rstrip("/")
        self.think = think
        self.timeout = timeout

    def chat(self, messages: list, **kwargs) -> str:
        """发送 chat 请求，返回模型回复文本。

        若 think=True，payload 中加入 think:true（Ollama v0.9.0+ 支持），
        响应中的 message.thinking 字段（推理过程）会被记录到 DEBUG 日志后丢弃，
        只返回 message.content（最终答案）。
        """
        payload = {
            "model": self.model_name,
            "messages": messages,
            "stream": False,
        }
        # think 参数优先级：调用时 kwargs > 实例配置
        effective_think = kwargs.pop("think", self.think)
        if effective_think:
            payload["think"] = True

        # 合并实例级 kwargs 和调用级 kwargs（调用级优先）
        merged = {**self.kwargs, **kwargs}
        payload.update(merged)

        try:
            response = requests.post(
                f"{self.base_url}/api/chat",
                json=payload,
                timeout=self.timeout,
            )
            response.raise_for_status()
            data = response.json()
            msg = data.get("message", {})

            # thinking 模式：记录推理过程，返回最终答案
            thinking = msg.get("thinking")
            if thinking:
                logger.debug(f"[Ollama thinking] {thinking[:500]!r}...")

            content = msg.get("content", "")
            if not content:
                raise ValueError("Ollama returned empty content")
            return content

        except requests.exceptions.ConnectionError:
            logger.error(
                f"Ollama connection failed: cannot reach {self.base_url}. "
                "Is Ollama running? Try: ollama serve"
            )
            raise
        except requests.exceptions.Timeout:
            logger.error(
                f"Ollama request timed out after {self.timeout}s "
                f"(model={self.model_name}). Consider increasing timeout."
            )
            raise
        except requests.exceptions.HTTPError as e:
            status = e.response.status_code if e.response is not None else "?"
            logger.error(f"Ollama HTTP error {status}: {e}")
            raise
        except Exception as e:
            logger.error(f"Ollama call failed: {e}")
            raise

    def generate(self, prompt: str, **kwargs) -> str:
        """单轮生成接口（内部转换为 chat 格式）。"""
        return self.chat([{"role": "user", "content": prompt}], **kwargs)

    def is_available(self) -> bool:
        """检查 Ollama 服务是否可达（用于健康检查）。"""
        try:
            resp = requests.get(f"{self.base_url}/api/tags", timeout=5)
            return resp.status_code == 200
        except Exception:
            return False

    def list_local_models(self) -> list:
        """列出 Ollama 本地已拉取的模型名称列表。"""
        try:
            resp = requests.get(f"{self.base_url}/api/tags", timeout=5)
            resp.raise_for_status()
            return [m["name"] for m in resp.json().get("models", [])]
        except Exception as e:
            logger.warning(f"Failed to list Ollama models: {e}")
            return []
