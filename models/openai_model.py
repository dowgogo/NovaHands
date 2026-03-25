import openai
import logging
from .base_model import BaseModel

logger = logging.getLogger('novahands')


class OpenAIModel(BaseModel):
    def __init__(self, model_name: str, api_key: str, **kwargs):
        super().__init__(model_name, **kwargs)
        openai.api_key = api_key

    def chat(self, messages: list, **kwargs) -> str:
        try:
            response = openai.ChatCompletion.create(
                model=self.model_name,
                messages=messages,
                **{**self.kwargs, **kwargs}
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"OpenAI call failed: {e}")
            raise

    def generate(self, prompt: str, **kwargs) -> str:
        return self.chat([{"role": "user", "content": prompt}], **kwargs)
