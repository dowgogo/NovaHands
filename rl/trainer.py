import torch
from transformers import Trainer, TrainingArguments
from peft import LoraConfig, get_peft_model
from utils.logger import logger


class RLFineTuner:
    def __init__(self, base_model, tokenizer, skill_list):
        self.base_model = base_model
        self.tokenizer = tokenizer
        self.skill_list = skill_list
        self.lora_model = self._prepare_lora_model()

    def _prepare_lora_model(self):
        lora_config = LoraConfig(
            r=8,
            lora_alpha=32,
            target_modules=["q_proj", "v_proj"],  # Adjust for model architecture
            lora_dropout=0.1,
            bias="none"
        )
        model = get_peft_model(self.base_model, lora_config)
        return model

    def prepare_dataset(self, dataset):
        texts = []
        labels = []
        for item in dataset:
            state_text = self._format_state(item["state"])
            skill_name = self.skill_list[item["action"]]
            texts.append(state_text)
            labels.append(skill_name)
        return texts, labels

    def train(self, dataset, epochs=3):
        if not dataset:
            logger.warning("No dataset to train on")
            return
        texts, labels = self.prepare_dataset(dataset)
        # For simplicity, we'll just print a message; actual training requires tokenization and Trainer.
        logger.info(f"Training on {len(texts)} samples for {epochs} epochs")
        # Placeholder for actual training loop using HuggingFace Trainer
        # ...
        # After training, save LoRA weights
        self.lora_model.save_pretrained("./lora_weights")
        logger.info("Training completed, LoRA weights saved.")

    def _format_state(self, state):
        return (
            f"当前应用: {state['current_app']}\n"
            f"上一条指令: {state['last_user_input']}\n"
            f"上一技能: {state['last_skill']}\n"
            f"结果: {'成功' if state['last_result'] else '失败'}"
        )
