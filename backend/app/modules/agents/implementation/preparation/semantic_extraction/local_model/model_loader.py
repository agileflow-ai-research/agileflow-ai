from dataclasses import dataclass
from threading import Lock
from time import perf_counter
from typing import Any


class SemanticModelUnavailableError(RuntimeError):
    pass


@dataclass(frozen=True)
class LoadedSemanticModel:
    model: Any
    tokenizer: Any
    device: str
    model_id: str
    revision: str
    load_ms: int


class SemanticModelLoader:
    """Lazily loads and process-caches pinned local causal language models."""

    _instances: dict[tuple[str, str, bool, str], LoadedSemanticModel] = {}
    _initialization_lock = Lock()

    @classmethod
    def load(
        cls, *, model_id: str, revision: str,
        local_files_only: bool, device: str,
    ) -> LoadedSemanticModel:
        key = (model_id, revision, local_files_only, device)
        if key in cls._instances:
            return cls._instances[key]
        with cls._initialization_lock:
            if key in cls._instances:
                return cls._instances[key]
            if len(revision) != 40 or any(character not in "0123456789abcdef" for character in revision):
                raise SemanticModelUnavailableError(
                    "The semantic model revision must be a full immutable commit hash."
                )
            started = perf_counter()
            try:
                import torch
                from transformers import AutoModelForCausalLM, AutoTokenizer

                selected_device = cls._select_device(torch, device)
                tokenizer = AutoTokenizer.from_pretrained(
                    model_id, revision=revision,
                    local_files_only=local_files_only,
                )
                model = AutoModelForCausalLM.from_pretrained(
                    model_id, revision=revision,
                    local_files_only=local_files_only,
                    use_safetensors=True,
                    dtype="auto",
                )
                model.to(selected_device)
                model.eval()
                loaded = LoadedSemanticModel(
                    model=model, tokenizer=tokenizer,
                    device=selected_device, model_id=model_id,
                    revision=revision,
                    load_ms=round((perf_counter() - started) * 1000),
                )
            except (ImportError, MemoryError, OSError, RuntimeError, ValueError) as exc:
                raise SemanticModelUnavailableError(
                    "The pinned local semantic model could not be loaded. "
                    "Verify its cache, revision, safetensors files, and runtime memory."
                ) from exc
            cls._instances[key] = loaded
            return loaded

    @staticmethod
    def _select_device(torch, requested: str) -> str:
        normalized = requested.casefold()
        if normalized not in {"auto", "cpu", "cuda"}:
            raise SemanticModelUnavailableError(
                "Semantic model device must be auto, cpu, or cuda."
            )
        cuda_available = bool(torch.cuda.is_available())
        if normalized == "cuda" and not cuda_available:
            raise SemanticModelUnavailableError(
                "CUDA was requested but is not available."
            )
        return "cuda" if normalized == "cuda" or (normalized == "auto" and cuda_available) else "cpu"

    @classmethod
    def reset_for_tests(cls) -> None:
        with cls._initialization_lock:
            cls._instances = {}
