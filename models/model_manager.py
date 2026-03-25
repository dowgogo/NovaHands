import logging
import threading
from typing import Optional
from .base_model import BaseModel
from .openai_model import OpenAIModel
from .anthropic_model import AnthropicModel
from .ollama_model import OllamaModel
from .local_model import LocalModel
from utils.config_loader import ConfigLoader

logger = logging.getLogger('novahands')


class ModelManager:
    def __init__(self):
        self.config = ConfigLoader()
        self.current_model: Optional[BaseModel] = None
        self._lock = threading.Lock()  # 防止多线程并发初始化
        self._init_model()

    def _init_model(self):
        provider = self.config.get('llm.default', 'openai')
        self.set_model(provider)

    def set_model(self, provider: str):
        with self._lock:
            provider_config = self.config.get(f'llm.{provider}', {})
            if not provider_config:
                raise ValueError(f"Model config for {provider} not found")

            # 切换前释放旧模型的 GPU 资源
            if self.current_model is not None:
                old_model = self.current_model
                self.current_model = None
                if isinstance(old_model, LocalModel):
                    try:
                        del old_model.model
                        del old_model.tokenizer
                        import torch
                        if torch.cuda.is_available():
                            torch.cuda.empty_cache()
                        logger.info("Released previous local model GPU resources")
                    except Exception as e:
                        logger.warning(f"Failed to release old model resources: {e}")

            if provider == "openai":
                api_key = provider_config.get("api_key", "")
                if not api_key:
                    raise ValueError("OpenAI API key is not configured. Set OPENAI_API_KEY environment variable.")
                self.current_model = OpenAIModel(
                    model_name=provider_config.get("model", "gpt-4"),
                    api_key=api_key,
                    **provider_config.get("params", {})
                )
            elif provider == "anthropic":
                api_key = provider_config.get("api_key", "")
                if not api_key:
                    raise ValueError("Anthropic API key is not configured. Set ANTHROPIC_API_KEY environment variable.")
                self.current_model = AnthropicModel(
                    model_name=provider_config.get("model", "claude-3-opus-20240229"),
                    api_key=api_key,
                    **provider_config.get("params", {})
                )
            elif provider == "ollama":
                self.current_model = OllamaModel(
                    model_name=provider_config.get("model", "llama2"),
                    base_url=provider_config.get("base_url", "http://localhost:11434"),
                    **provider_config.get("params", {})
                )
            elif provider == "local":
                self.current_model = LocalModel(
                    model_name=provider_config.get("model", "Qwen/Qwen2.5-0.5B-Instruct"),
                    device=provider_config.get("device", "cpu"),
                    quantize_4bit=provider_config.get("quantize_4bit", False),
                    cache_dir=provider_config.get("cache_dir"),
                    trust_remote_code=provider_config.get("trust_remote_code", False),
                    **provider_config.get("params", {})
                )
            else:
                raise ValueError(f"Unknown model provider: {provider}")
            logger.info(f"Switched to model: {provider} - {self.current_model.model_name}")

    def get_model(self) -> BaseModel:
        with self._lock:
            if not self.current_model:
                self._init_model()
            return self.current_model

