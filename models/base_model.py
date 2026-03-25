from abc import ABC, abstractmethod


class BaseModel(ABC):
    def __init__(self, model_name: str, **kwargs):
        self.model_name = model_name
        self.kwargs = kwargs

    @abstractmethod
    def chat(self, messages: list, **kwargs) -> str:
        pass

    @abstractmethod
    def generate(self, prompt: str, **kwargs) -> str:
        pass
