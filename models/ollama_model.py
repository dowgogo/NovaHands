import requests
import logging
from .base_model import BaseModel

logger = logging.getLogger('novahands')


class OllamaModel(BaseModel):
    def __init__(self, model_name: str, base_url: str = "http://localhost:11434", **kwargs):
        super().__init__(model_name, **kwargs)
        self.base_url = base_url

    def chat(self, messages: list, **kwargs) -> str:
        try:
            payload = {
                "model": self.model_name,
                "messages": messages,
                "stream": False,
                **{**self.kwargs, **kwargs}
            }
            response = requests.post(f"{self.base_url}/api/chat", json=payload, timeout=30)
            response.raise_for_status()
            return response.json()["message"]["content"]
        except Exception as e:
            logger.error(f"Ollama call failed: {e}")
            raise

    def generate(self, prompt: str, **kwargs) -> str:
        return self.chat([{"role": "user", "content": prompt}], **kwargs)
