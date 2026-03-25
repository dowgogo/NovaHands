import anthropic
import logging
from .base_model import BaseModel

logger = logging.getLogger('novahands')


class AnthropicModel(BaseModel):
    def __init__(self, model_name: str, api_key: str, **kwargs):
        super().__init__(model_name, **kwargs)
        self.client = anthropic.Anthropic(api_key=api_key)

    def chat(self, messages: list, **kwargs) -> str:
        try:
            system = None
            if messages and messages[0]["role"] == "system":
                system = messages[0]["content"]
                messages = messages[1:]
            response = self.client.messages.create(
                model=self.model_name,
                system=system,
                messages=messages,
                **{**self.kwargs, **kwargs}
            )
            return response.content[0].text
        except Exception as e:
            logger.error(f"Anthropic call failed: {e}")
            raise

    def generate(self, prompt: str, **kwargs) -> str:
        return self.chat([{"role": "user", "content": prompt}], **kwargs)
