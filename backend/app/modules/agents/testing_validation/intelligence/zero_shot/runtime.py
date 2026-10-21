"""Lazy local Hugging Face runtime. Importing this module never loads a model."""

from dataclasses import dataclass
from threading import Lock
from typing import Any

from .constants import MODEL_ID, MODEL_REVISION, MODEL_TASK


class Agent4ZeroShotModelLoadError(RuntimeError):
    code = "ZERO_SHOT_MODEL_LOAD_FAILED"


class Agent4ZeroShotTokenizationError(RuntimeError):
    code = "ZERO_SHOT_TOKENIZATION_FAILED"


@dataclass(frozen=True, slots=True)
class LoadedAgent4ZeroShotRuntime:
    pipeline: Any
    tokenizer: Any
    device: str
    model_max_length: int


@dataclass(frozen=True, slots=True)
class RuntimeBatchOutput:
    responses: list[dict]
    input_token_counts: list[int]
    model_max_length: int
    device: str


class Agent4ZeroShotModelLoader:
    """Process-wide cache keyed by pinned model configuration and device."""

    _instances: dict[tuple[str, str, bool, str], LoadedAgent4ZeroShotRuntime] = {}
    _lock = Lock()

    @classmethod
    def load(cls, *, local_files_only: bool = False):
        try:
            import torch
        except ImportError as exc:
            raise Agent4ZeroShotModelLoadError(
                "The local zero-shot runtime is unavailable."
            ) from exc
        device = "cuda" if torch.cuda.is_available() else "cpu"
        key = (MODEL_ID, MODEL_REVISION, local_files_only, device)
        if key in cls._instances:
            return cls._instances[key]
        with cls._lock:
            if key in cls._instances:
                return cls._instances[key]
            try:
                from transformers import (
                    AutoModelForSequenceClassification,
                    AutoTokenizer,
                    pipeline,
                )
                tokenizer = AutoTokenizer.from_pretrained(
                    MODEL_ID, revision=MODEL_REVISION,
                    local_files_only=local_files_only,
                )
                model = AutoModelForSequenceClassification.from_pretrained(
                    MODEL_ID, revision=MODEL_REVISION,
                    local_files_only=local_files_only, use_safetensors=True,
                )
                configured = getattr(model.config, "max_position_embeddings", 512)
                tokenizer_max = getattr(tokenizer, "model_max_length", configured)
                if not isinstance(tokenizer_max, int) or tokenizer_max > 100_000:
                    tokenizer_max = configured
                loaded = LoadedAgent4ZeroShotRuntime(
                    pipeline=pipeline(
                        MODEL_TASK, model=model, tokenizer=tokenizer,
                        device=0 if device == "cuda" else -1,
                    ),
                    tokenizer=tokenizer,
                    device=device,
                    model_max_length=min(configured, tokenizer_max),
                )
            except (ImportError, MemoryError, OSError, RuntimeError, ValueError) as exc:
                raise Agent4ZeroShotModelLoadError(
                    "The pinned local zero-shot model could not be loaded."
                ) from exc
            cls._instances[key] = loaded
            return loaded

    @classmethod
    def reset_for_tests(cls):
        with cls._lock:
            cls._instances.clear()


class Agent4ZeroShotRuntime:
    def __init__(self, *, local_files_only=False, loader=Agent4ZeroShotModelLoader):
        self._local_files_only = local_files_only
        self._loader = loader

    def infer(self, texts, *, candidate_labels, hypothesis_template, batch_size):
        loaded = self._loader.load(local_files_only=self._local_files_only)
        try:
            counts = []
            for text in texts:
                candidate_counts = []
                for description in candidate_labels:
                    encoded = loaded.tokenizer(
                        text, hypothesis_template.format(description),
                        add_special_tokens=True, truncation=False,
                    )
                    candidate_counts.append(len(encoded["input_ids"]))
                counts.append(max(candidate_counts))
        except Exception as exc:
            raise Agent4ZeroShotTokenizationError(
                "The zero-shot input could not be tokenized."
            ) from exc
        raw = loaded.pipeline(
            texts,
            candidate_labels=candidate_labels,
            hypothesis_template=hypothesis_template,
            multi_label=True,
            truncation="only_first",
            batch_size=batch_size,
        )
        if isinstance(raw, dict):
            raw = [raw]
        return RuntimeBatchOutput(
            responses=list(raw), input_token_counts=counts,
            model_max_length=loaded.model_max_length, device=loaded.device,
        )

