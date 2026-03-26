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
        self._lock = threading.RLock()  # RLock 可重入，防止 get_model()->set_model() 调用链死锁
        self._init_model()

    def _init_model(self):
        provider = self.config.get('llm.default', 'openai')
        self.set_model(provider)

    def set_model(self, provider: str):
        with self._lock:
            # "none" 模式：无需 provider config
            if provider != "none":
                provider_config = self.config.get(f'llm.{provider}', {})
                if not provider_config:
                    raise ValueError(f"Model config for {provider} not found")
            else:
                provider_config = {}

            # 构建新模型实例（在释放旧模型之前完成，避免中间状态窗口期）
            new_model = None
            if provider == "openai":
                api_key = provider_config.get("api_key", "")
                if not api_key:
                    raise ValueError("OpenAI API key is not configured. Set OPENAI_API_KEY environment variable.")
                new_model = OpenAIModel(
                    model_name=provider_config.get("model", "gpt-4"),
                    api_key=api_key,
                    **provider_config.get("params", {})
                )
            elif provider == "anthropic":
                api_key = provider_config.get("api_key", "")
                if not api_key:
                    raise ValueError("Anthropic API key is not configured. Set ANTHROPIC_API_KEY environment variable.")
                new_model = AnthropicModel(
                    model_name=provider_config.get("model", "claude-3-opus-20240229"),
                    api_key=api_key,
                    **provider_config.get("params", {})
                )
            elif provider == "ollama":
                new_model = OllamaModel(
                    model_name=provider_config.get("model", "llama2"),
                    base_url=provider_config.get("base_url", "http://localhost:11434"),
                    **provider_config.get("params", {})
                )
            elif provider == "local":
                new_model = LocalModel(
                    model_name=provider_config.get("model", "Qwen/Qwen2.5-0.5B-Instruct"),
                    device=provider_config.get("device", "cpu"),
                    quantize_4bit=provider_config.get("quantize_4bit", False),
                    cache_dir=provider_config.get("cache_dir"),
                    trust_remote_code=provider_config.get("trust_remote_code", False),
                    **provider_config.get("params", {})
                )
            elif provider == "none":
                # 无模型模式：程序正常启动，NLExecutor 降级到关键词匹配
                pass
            else:
                raise ValueError(f"Unknown model provider: {provider}")

            # 新模型构建成功后，再释放旧模型的 GPU 资源，缩短 current_model=None 的窗口期
            old_model = self.current_model
            self.current_model = new_model

            if old_model is not None and isinstance(old_model, LocalModel):
                try:
                    del old_model.model
                    del old_model.tokenizer
                    import torch
                    if torch.cuda.is_available():
                        torch.cuda.empty_cache()
                    logger.info("Released previous local model GPU resources")
                except Exception as e:
                    logger.warning(f"Failed to release old model resources: {e}")

            if provider == "none":
                logger.info("No LLM configured (provider=none). NL execution will use keyword matching only.")
            else:
                logger.info(f"Switched to model: {provider} - {self.current_model.model_name}")

    def get_model(self) -> Optional[BaseModel]:
        with self._lock:
            return self.current_model

