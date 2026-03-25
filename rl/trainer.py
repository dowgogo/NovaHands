import os
import logging
from pathlib import Path
from utils.logger import logger


class RLFineTuner:
    def __init__(self, base_model, tokenizer, skill_list, output_dir: str = None):
        self.base_model = base_model
        self.tokenizer = tokenizer
        self.skill_list = skill_list
        # 修复：输出路径可配置，默认在项目根目录下的 lora_weights/
        self.output_dir = Path(output_dir) if output_dir else (
            Path(__file__).parent.parent / "lora_weights"
        )
        # 懒导入：peft/transformers 是重量级依赖
        try:
            from peft import LoraConfig, get_peft_model
            self._LoraConfig = LoraConfig
            self._get_peft_model = get_peft_model
        except ImportError as e:
            raise ImportError(
                f"RL fine-tuning requires peft: {e}\n"
                "Run: pip install peft"
            ) from e
        self.lora_model = self._prepare_lora_model()

    def _prepare_lora_model(self):
        lora_config = self._LoraConfig(
            r=8,
            lora_alpha=32,
            target_modules=["q_proj", "v_proj"],
            lora_dropout=0.1,
            bias="none"
        )
        model = self._get_peft_model(self.base_model, lora_config)
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
        """
        LoRA 微调训练。
        注意：当前为基础实现，需要足够的 CUDA 显存（建议 8GB+）。
        CPU 上运行会非常慢。
        """
        if not dataset:
            logger.warning("No dataset to train on")
            return

        try:
            import torch
            from transformers import Trainer, TrainingArguments
        except ImportError as e:
            raise ImportError(f"Training requires transformers: {e}") from e

        texts, labels = self.prepare_dataset(dataset)
        logger.info(f"Starting LoRA training on {len(texts)} samples for {epochs} epochs...")

        # 构建简单的文本序列训练数据
        train_encodings = self.tokenizer(
            texts,
            truncation=True,
            padding=True,
            max_length=512,
            return_tensors="pt"
        )

        # 标签：使用 skill 名称的 token id 作为监督信号
        label_encodings = self.tokenizer(
            labels,
            truncation=True,
            padding=True,
            max_length=16,
            return_tensors="pt"
        )

        class SimpleDataset(torch.utils.data.Dataset):
            def __init__(self, inputs, label_ids):
                self.inputs = inputs
                self.label_ids = label_ids

            def __len__(self):
                return len(self.label_ids["input_ids"])

            def __getitem__(self, idx):
                item = {k: v[idx] for k, v in self.inputs.items()}
                item["labels"] = self.label_ids["input_ids"][idx]
                return item

        train_dataset = SimpleDataset(train_encodings, label_encodings)

        training_args = TrainingArguments(
            output_dir=str(self.output_dir / "checkpoints"),
            num_train_epochs=epochs,
            per_device_train_batch_size=2,
            logging_steps=10,
            save_steps=100,
            no_cuda=not torch.cuda.is_available(),
            report_to="none",
        )

        trainer = Trainer(
            model=self.lora_model,
            args=training_args,
            train_dataset=train_dataset,
        )

        try:
            trainer.train()
            # 修复：保存到可配置的绝对路径，并处理磁盘/权限异常
            self.output_dir.mkdir(parents=True, exist_ok=True)
            self.lora_model.save_pretrained(str(self.output_dir))
            logger.info(f"Training completed, LoRA weights saved to {self.output_dir}")
        except OSError as e:
            logger.error(f"Failed to save LoRA weights: {e}")
            raise

    def _format_state(self, state):
        return (
            f"当前应用: {state['current_app']}\n"
            f"上一条指令: {state['last_user_input']}\n"
            f"上一技能: {state['last_skill']}\n"
            f"结果: {'成功' if state['last_result'] else '失败'}"
        )
