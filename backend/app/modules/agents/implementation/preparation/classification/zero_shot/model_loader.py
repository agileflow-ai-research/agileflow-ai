from dataclasses import dataclass
from threading import Lock
from typing import Any

from .constants import MODEL_ID, MODEL_REVISION, MODEL_TASK


class ZeroShotModelUnavailableError(RuntimeError):
    pass


@dataclass(frozen=True)
class LoadedZeroShotModel:
    pipeline: Any
    tokenizer: Any
    device: str
    model_max_length: int


class ZeroShotModelLoader:
    """Lazily loads and reuses one local tokenizer/model pipeline per process."""

    _instance: LoadedZeroShotModel | None = None
    _initialization_lock = Lock()

    @classmethod
    def load(cls, *, local_files_only: bool) -> LoadedZeroShotModel:
        if cls._instance is not None:
            return cls._instance
        with cls._initialization_lock:
            if cls._instance is not None:
                return cls._instance
            try:
                import torch
                from transformers import (
                    AutoModelForSequenceClassification,
                    AutoTokenizer,
                    pipeline,
                )

                tokenizer = AutoTokenizer.from_pretrained(
                    MODEL_ID,
                    revision=MODEL_REVISION,
                    local_files_only=local_files_only,
                )
                model = AutoModelForSequenceClassification.from_pretrained(
                    MODEL_ID,
                    revision=MODEL_REVISION,
                    local_files_only=local_files_only,
                    use_safetensors=True,
                )
                use_cuda = bool(torch.cuda.is_available())
                device_index = 0 if use_cuda else -1
                model_pipeline = pipeline(
                    MODEL_TASK,
                    model=model,
                    tokenizer=tokenizer,
                    device=device_index,
                )
                configured = getattr(model.config, "max_position_embeddings", 512)
                tokenizer_max = getattr(tokenizer, "model_max_length", configured)
                if not isinstance(tokenizer_max, int) or tokenizer_max > 100_000:
                    tokenizer_max = configured
                cls._instance = LoadedZeroShotModel(
                    pipeline=model_pipeline,
                    tokenizer=tokenizer,
                    device="cuda" if use_cuda else "cpu",
                    model_max_length=min(configured, tokenizer_max),
                )
            except (ImportError, MemoryError, OSError, RuntimeError, ValueError) as exc:
                raise ZeroShotModelUnavailableError(
                    "The local zero-shot model could not be loaded. Verify the model cache and runtime dependencies."
                ) from exc
        return cls._instance

    @classmethod
    def reset_for_tests(cls) -> None:
        with cls._initialization_lock:
            cls._instance = None
