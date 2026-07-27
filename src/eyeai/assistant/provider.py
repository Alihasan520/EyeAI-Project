from __future__ import annotations

import gc
import json
import threading
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Sequence


class AssistantProvider(ABC):
    """Provider contract used by the clinical assistant service."""

    name: str = "unknown"

    @property
    @abstractmethod
    def loaded(self) -> bool:
        raise NotImplementedError

    @abstractmethod
    def load(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def generate(self, messages: Sequence[dict[str, str]]) -> str:
        raise NotImplementedError

    def memory_status(self) -> dict[str, float] | None:
        return None


class DisabledProvider(AssistantProvider):
    name = "disabled"

    @property
    def loaded(self) -> bool:
        return False

    def load(self) -> None:
        raise RuntimeError("The clinical assistant provider is disabled.")

    def generate(self, messages: Sequence[dict[str, str]]) -> str:
        del messages
        raise RuntimeError("The clinical assistant provider is disabled.")


class MockProvider(AssistantProvider):
    """Deterministic provider for tests and offline workflow validation."""

    name = "mock"

    def __init__(self, response: dict[str, Any] | str | None = None) -> None:
        self._loaded = False
        self.response = response or {
            "answer": "The available EyeAI records were summarized without adding a diagnosis.",
            "suggested_review": "Review the fundus image, image quality, and clinical findings.",
        }
        self.last_messages: list[dict[str, str]] = []

    @property
    def loaded(self) -> bool:
        return self._loaded

    def load(self) -> None:
        self._loaded = True

    def generate(self, messages: Sequence[dict[str, str]]) -> str:
        if not self.loaded:
            self.load()
        self.last_messages = [dict(message) for message in messages]
        if isinstance(self.response, str):
            return self.response
        return json.dumps(self.response, ensure_ascii=False)


class TransformersQwenProvider(AssistantProvider):
    """Lazy 4-bit Qwen provider intended for a single Kaggle T4 GPU."""

    name = "qwen_transformers"

    def __init__(
        self,
        *,
        model_path: str | Path,
        lock: threading.RLock | threading.Lock | None = None,
        load_in_4bit: bool = True,
        maximum_gpu_memory_gib: int = 5,
        maximum_input_tokens: int = 3072,
        maximum_new_tokens: int = 256,
        temperature: float = 0.0,
        top_p: float = 0.8,
        top_k: int = 20,
        local_files_only: bool = True,
        use_cache: bool = True,
        release_cuda_cache_after_generate: bool = True,
    ) -> None:
        self.model_path = Path(model_path)
        self.lock = lock or threading.RLock()
        self.load_in_4bit = load_in_4bit
        self.maximum_gpu_memory_gib = maximum_gpu_memory_gib
        self.maximum_input_tokens = maximum_input_tokens
        self.maximum_new_tokens = maximum_new_tokens
        self.temperature = temperature
        self.top_p = top_p
        self.top_k = top_k
        self.local_files_only = local_files_only
        self.use_cache = use_cache
        self.release_cuda_cache_after_generate = release_cuda_cache_after_generate
        self.tokenizer: Any | None = None
        self.model: Any | None = None

    @property
    def loaded(self) -> bool:
        return self.model is not None and self.tokenizer is not None

    def load(self) -> None:
        if self.loaded:
            return
        if not self.model_path.is_dir():
            raise FileNotFoundError(
                f"Qwen model directory was not found: {self.model_path}"
            )

        try:
            import torch
            from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
        except ImportError as exc:
            raise RuntimeError(
                "Install requirements-assistant-kaggle.txt before enabling Qwen."
            ) from exc

        if not torch.cuda.is_available():
            raise RuntimeError(
                "The configured 4-bit Qwen provider requires a CUDA GPU."
            )

        quantization_config = None
        if self.load_in_4bit:
            quantization_config = BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_quant_type="nf4",
                bnb_4bit_compute_dtype=torch.float16,
                bnb_4bit_use_double_quant=True,
            )

        self.tokenizer = AutoTokenizer.from_pretrained(
            self.model_path,
            local_files_only=self.local_files_only,
            padding_side="left",
        )
        self.model = AutoModelForCausalLM.from_pretrained(
            self.model_path,
            local_files_only=self.local_files_only,
            quantization_config=quantization_config,
            dtype=torch.float16,
            device_map="auto",
            max_memory={
                0: f"{self.maximum_gpu_memory_gib}GiB",
                "cpu": "20GiB",
            },
            low_cpu_mem_usage=True,
        )
        self.model.eval()
        if hasattr(self.model, "config"):
            self.model.config.use_cache = self.use_cache

    def generate(self, messages: Sequence[dict[str, str]]) -> str:
        if not self.loaded:
            self.load()
        assert self.model is not None
        assert self.tokenizer is not None

        import torch

        with self.lock:
            rendered = self.tokenizer.apply_chat_template(
                list(messages),
                tokenize=False,
                add_generation_prompt=True,
            )
            inputs = self.tokenizer(
                rendered,
                return_tensors="pt",
                truncation=True,
                max_length=self.maximum_input_tokens,
            )
            input_device = self._input_device()
            inputs = {key: value.to(input_device) for key, value in inputs.items()}
            generation_kwargs: dict[str, Any] = {
                "max_new_tokens": self.maximum_new_tokens,
                "pad_token_id": self.tokenizer.eos_token_id,
                "eos_token_id": self.tokenizer.eos_token_id,
                "repetition_penalty": 1.05,
                "use_cache": self.use_cache,
            }
            if self.temperature > 0:
                generation_kwargs.update(
                    {
                        "do_sample": True,
                        "temperature": self.temperature,
                        "top_p": self.top_p,
                        "top_k": self.top_k,
                    }
                )
            else:
                generation_kwargs["do_sample"] = False

            output = None
            generated = None
            try:
                with torch.inference_mode():
                    output = self.model.generate(**inputs, **generation_kwargs)
                generated = output[0, inputs["input_ids"].shape[-1] :]
                return self.tokenizer.decode(
                    generated,
                    skip_special_tokens=True,
                ).strip()
            finally:
                del rendered
                del inputs
                if generated is not None:
                    del generated
                if output is not None:
                    del output
                if self.release_cuda_cache_after_generate:
                    _release_cuda_cache()

    def memory_status(self) -> dict[str, float] | None:
        try:
            import torch
        except ImportError:
            return None
        if not torch.cuda.is_available():
            return None
        gib = float(1024**3)
        return {
            "allocated_gib": round(torch.cuda.memory_allocated() / gib, 3),
            "reserved_gib": round(torch.cuda.memory_reserved() / gib, 3),
            "peak_allocated_gib": round(torch.cuda.max_memory_allocated() / gib, 3),
            "peak_reserved_gib": round(torch.cuda.max_memory_reserved() / gib, 3),
        }

    def _input_device(self) -> Any:
        assert self.model is not None
        try:
            embedding = self.model.get_input_embeddings()
            return next(embedding.parameters()).device
        except (AttributeError, StopIteration):
            return next(self.model.parameters()).device


def _release_cuda_cache() -> None:
    try:
        import torch
    except ImportError:
        return
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
        try:
            torch.cuda.ipc_collect()
        except RuntimeError:
            pass
