import logging
import os
from .base_model import BaseModel

logger = logging.getLogger('novahands')

# max_new_tokens 硬性上限，防止外部传入极大值耗尽显存
_MAX_NEW_TOKENS_LIMIT = 1024

# 受信任的模型来源白名单（当 trust_remote_code=True 时才检查）
_TRUSTED_MODEL_PREFIXES = (
    "Qwen/",
    "microsoft/",
    "meta-llama/",
    "mistralai/",
)


class LocalModel(BaseModel):
    def __init__(
        self,
        model_name: str = "Qwen/Qwen2.5-0.5B-Instruct",
        device: str = "cpu",
        quantize_4bit: bool = True,
        cache_dir: str = None,
        trust_remote_code: bool = False,
        **kwargs
    ):
        super().__init__(model_name, **kwargs)
        self.device = device

        # 懒导入：torch/transformers 是重量级依赖，仅在 LocalModel 实例化时加载
        try:
            import torch
            from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
        except ImportError as e:
            raise ImportError(
                f"Local model requires torch and transformers: {e}\n"
                "Run: pip install torch transformers"
            ) from e

        # 安全修复：路径规范化，防止路径遍历
        raw_cache = cache_dir or os.path.join(
            os.path.expanduser("~"), ".cache", "novahands", "models"
        )
        self.cache_dir = os.path.realpath(raw_cache)

        # 安全修复：trust_remote_code 默认 False；若开启则限制受信任来源
        if trust_remote_code:
            if not any(model_name.startswith(p) for p in _TRUSTED_MODEL_PREFIXES):
                raise ValueError(
                    f"trust_remote_code=True is not allowed for untrusted model '{model_name}'. "
                    f"Allowed prefixes: {_TRUSTED_MODEL_PREFIXES}"
                )
            logger.warning(
                f"trust_remote_code=True enabled for '{model_name}'. "
                "Only use models from trusted sources."
            )

        bnb_config = None
        if quantize_4bit:
            if device == "cuda":
                bnb_config = BitsAndBytesConfig(
                    load_in_4bit=True,
                    bnb_4bit_compute_dtype=torch.float16,
                    bnb_4bit_use_double_quant=True,
                    bnb_4bit_quant_type="nf4"
                )
                logger.info("Enabling 4-bit quantization on GPU")
            else:
                logger.warning(
                    "quantize_4bit=True requires CUDA device; ignoring on CPU. "
                    "Model will run in full precision and may use more memory."
                )

        self.tokenizer = AutoTokenizer.from_pretrained(
            model_name,
            cache_dir=self.cache_dir,
            trust_remote_code=trust_remote_code
        )
        self.model = AutoModelForCausalLM.from_pretrained(
            model_name,
            quantization_config=bnb_config,
            device_map=device,
            torch_dtype=torch.float16 if device == "cuda" else torch.float32,
            cache_dir=self.cache_dir,
            trust_remote_code=trust_remote_code,
            low_cpu_mem_usage=True
        )
        self.model.eval()
        self._torch = torch
        logger.info(f"Loaded local model: {model_name} on {device}")

    def _get_model_device(self):
        """安全获取模型所在设备（兼容 device_map='auto' 分片情况）"""
        try:
            return next(self.model.parameters()).device
        except StopIteration:
            return self._torch.device("cpu")

    def chat(self, messages: list, **kwargs) -> str:
        # 优先使用 tokenizer 内置 chat_template（兼容多模型格式）
        if hasattr(self.tokenizer, "apply_chat_template"):
            try:
                prompt = self.tokenizer.apply_chat_template(
                    messages, tokenize=False, add_generation_prompt=True
                )
            except Exception:
                prompt = self._build_prompt(messages)
        else:
            prompt = self._build_prompt(messages)

        inputs = self.tokenizer(prompt, return_tensors="pt", truncation=True, max_length=2048)
        # 修复：使用 next(parameters()).device 而非 self.model.device（兼容 device_map='auto'）
        target_device = self._get_model_device()
        inputs = {k: v.to(target_device) for k, v in inputs.items()}

        # 安全修复：对 max_new_tokens 设置硬性上限，防止外部传入极大值
        requested_tokens = kwargs.get("max_new_tokens", 256)
        safe_max_tokens = min(int(requested_tokens), _MAX_NEW_TOKENS_LIMIT)

        with self._torch.no_grad():
            outputs = self.model.generate(
                **inputs,
                max_new_tokens=safe_max_tokens,
                temperature=kwargs.get("temperature", 0.7),
                do_sample=kwargs.get("do_sample", True),
                top_p=kwargs.get("top_p", 0.9),
                repetition_penalty=1.1,
                pad_token_id=self.tokenizer.eos_token_id
            )
        response = self.tokenizer.decode(
            outputs[0][inputs["input_ids"].shape[1]:],
            skip_special_tokens=True
        )
        return response.strip()

    def generate(self, prompt: str, **kwargs) -> str:
        return self.chat([{"role": "user", "content": prompt}], **kwargs)

    def _build_prompt(self, messages: list) -> str:
        """Fallback：Qwen2.5 格式的 prompt 构建，当 tokenizer 无 chat_template 时使用"""
        prompt = ""
        for msg in messages:
            role = msg.get("role", "")
            content = msg.get("content", "")
            if role == "system":
                prompt += f"<|im_start|>system\n{content}<|im_end|>\n"
            elif role == "user":
                prompt += f"<|im_start|>user\n{content}<|im_end|>\n"
            elif role == "assistant":
                prompt += f"<|im_start|>assistant\n{content}<|im_end|>\n"
        prompt += "<|im_start|>assistant\n"
        return prompt
