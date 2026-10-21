from dataclasses import dataclass
import json
from threading import Lock
from time import perf_counter

from . import constants


class SemanticModelLoadError(RuntimeError):
    pass


class SemanticGenerationError(RuntimeError):
    pass


class SemanticInputTooLargeError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class SemanticRuntimeOutput:
    text: str
    input_token_count: int
    output_token_count: int
    generation_duration_ms: int
    device: str


@dataclass(frozen=True, slots=True)
class LoadedQwenRuntime:
    model: object
    tokenizer: object
    device: str


class Agent4QwenLoader:
    """Lazy process cache matching Agent 3's pinned local-runtime mechanics."""

    _instances = {}
    _lock = Lock()

    @classmethod
    def load(cls, *, model_id, revision, local_files_only, device):
        key = (model_id, revision, local_files_only, device)
        if key in cls._instances:
            return cls._instances[key]
        with cls._lock:
            if key in cls._instances:
                return cls._instances[key]
            try:
                import torch
                from transformers import AutoModelForCausalLM, AutoTokenizer

                resolved = cls._device(torch, device)
                tokenizer = AutoTokenizer.from_pretrained(
                    model_id, revision=revision, local_files_only=local_files_only
                )
                model = AutoModelForCausalLM.from_pretrained(
                    model_id, revision=revision, local_files_only=local_files_only,
                    use_safetensors=True, dtype="auto",
                )
                model.to(resolved)
                model.eval()
                loaded = LoadedQwenRuntime(model, tokenizer, resolved)
            except (ImportError, MemoryError, OSError, RuntimeError, ValueError) as exc:
                raise SemanticModelLoadError(
                    "SEMANTIC_MODEL_LOAD_FAILED"
                ) from exc
            cls._instances[key] = loaded
            return loaded

    @staticmethod
    def _device(torch, requested):
        if requested not in {"auto", "cpu", "cuda"}:
            raise SemanticModelLoadError("SEMANTIC_MODEL_LOAD_FAILED")
        available = bool(torch.cuda.is_available())
        if requested == "cuda" and not available:
            raise SemanticModelLoadError("SEMANTIC_MODEL_LOAD_FAILED")
        return "cuda" if requested == "cuda" or (requested == "auto" and available) else "cpu"

    @classmethod
    def reset_for_tests(cls):
        with cls._lock:
            cls._instances = {}


class Agent4QwenRuntime:
    _generation_lock = Lock()

    def __init__(self, *, local_files_only=True, device="auto", loader=Agent4QwenLoader):
        self._local_files_only = local_files_only
        self._device = device
        self._loader = loader

    def generate(self, prompt):
        loaded = self._loader.load(
            model_id=constants.SEMANTIC_MODEL_ID,
            revision=constants.SEMANTIC_MODEL_REVISION,
            local_files_only=self._local_files_only,
            device=self._device,
        )
        started = perf_counter()
        try:
            import torch
            from transformers import StoppingCriteria, StoppingCriteriaList

            messages = [
                {"role": "system", "content": "Return grounded JSON only. Never provide reasoning."},
                {"role": "user", "content": prompt},
            ]
            try:
                rendered = loaded.tokenizer.apply_chat_template(
                    messages, tokenize=False, add_generation_prompt=True,
                    enable_thinking=False,
                )
            except (AttributeError, TypeError, ValueError):
                rendered = prompt
            inputs = loaded.tokenizer(rendered, return_tensors="pt", truncation=False)
            input_count = int(inputs["input_ids"].shape[-1])
            if input_count > constants.MAX_SEMANTIC_INPUT_TOKENS:
                raise SemanticInputTooLargeError("SEMANTIC_INPUT_TOO_LARGE")
            inputs = {key: value.to(loaded.device) for key, value in inputs.items()}

            class CompleteJsonObjectCriteria(StoppingCriteria):
                def __call__(self, input_ids, scores, **kwargs):
                    suffix = loaded.tokenizer.decode(
                        input_ids[0][input_count:], skip_special_tokens=True
                    ).strip()
                    if not suffix.startswith("{") or not suffix.endswith("}"):
                        return False
                    try:
                        parsed = json.loads(suffix)
                    except ValueError:
                        return False
                    return isinstance(parsed, dict) and set(parsed) == {"facts"}

            with self._generation_lock, torch.inference_mode():
                generated = loaded.model.generate(
                    **inputs,
                    do_sample=constants.DO_SAMPLE,
                    max_new_tokens=constants.MAX_SEMANTIC_NEW_TOKENS,
                    stopping_criteria=StoppingCriteriaList([
                        CompleteJsonObjectCriteria()
                    ]),
                    pad_token_id=(loaded.tokenizer.pad_token_id
                                  if loaded.tokenizer.pad_token_id is not None
                                  else loaded.tokenizer.eos_token_id),
                    eos_token_id=loaded.tokenizer.eos_token_id,
                )
            new_tokens = generated[0][input_count:]
            return SemanticRuntimeOutput(
                text=loaded.tokenizer.decode(new_tokens, skip_special_tokens=True).strip(),
                input_token_count=input_count,
                output_token_count=int(new_tokens.shape[-1]),
                generation_duration_ms=round((perf_counter() - started) * 1000),
                device=loaded.device,
            )
        except SemanticInputTooLargeError:
            raise
        except (MemoryError, OSError, RuntimeError, ValueError) as exc:
            raise SemanticGenerationError("SEMANTIC_GENERATION_FAILED") from exc
