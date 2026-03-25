import logging
from .base_model import BaseModel

logger = logging.getLogger('novahands')


class AnthropicModel(BaseModel):
    def __init__(self, model_name: str, api_key: str, max_tokens: int = 1024, **kwargs):
        super().__init__(model_name, **kwargs)
        self.max_tokens = max_tokens
        try:
            import anthropic
        except ImportError:
            raise ImportError(
                "anthropic package is not installed. Run: pip install anthropic"
            )
        self.client = anthropic.Anthropic(api_key=api_key)

    def chat(self, messages: list, **kwargs) -> str:
        try:
            system = None
            if messages and messages[0]["role"] == "system":
                system = messages[0]["content"]
                messages = messages[1:]

            # 确保 max_tokens 始终传入（Anthropic API 必需参数）
            max_tokens = kwargs.pop("max_tokens", self.max_tokens)

            # 仅在 system 不为 None 时传入，避免部分 SDK 版本对 system=None 报错
            create_kwargs = {**self.kwargs, **kwargs}
            if system is not None:
                create_kwargs["system"] = system

            response = self.client.messages.create(
                model=self.model_name,
                messages=messages,
                max_tokens=max_tokens,
                **create_kwargs
            )
            return response.content[0].text
        except Exception as e:
            logger.error(f"Anthropic call failed: {e}")
            raise

    def generate(self, prompt: str, **kwargs) -> str:
        return self.chat([{"role": "user", "content": prompt}], **kwargs)
