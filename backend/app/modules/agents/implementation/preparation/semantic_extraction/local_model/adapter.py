from dataclasses import dataclass
import json
from threading import Lock
from time import perf_counter

from pydantic import TypeAdapter, ValidationError

from ..protocols import SemanticExtractorAdapter
from ..schemas import SemanticExtractionProposal, SemanticExtractionRequest
from . import constants
from .json_parser import SemanticModelJsonError, parse_single_json_object
from .model_loader import (
    SemanticModelLoader, SemanticModelUnavailableError,
)
from .prompt_builder import build_prompt, build_proposal_prefix


class SemanticModelOutputInvalidError(ValueError):
    pass


class SemanticModelGenerationError(RuntimeError):
    pass


@dataclass(frozen=True)
class SemanticGenerationMetadata:
    attempt_count: int
    input_token_count: int
    output_token_count: int
    generation_ms: int
    first_model_load_ms: int
    model_id: str
    revision: str
    device: str


class LocalSemanticExtractorAdapter(SemanticExtractorAdapter):
    _proposal_adapter = TypeAdapter(SemanticExtractionProposal)
    _generation_lock = Lock()

    def __init__(
        self, *, model_id: str, revision: str,
        local_files_only: bool, device: str = "auto",
        loader=SemanticModelLoader,
    ) -> None:
        self._model_id = model_id
        self._revision = revision
        self._local_files_only = local_files_only
        self._device = device
        self._loader = loader
        self.last_generation_metadata: SemanticGenerationMetadata | None = None

    def extract(self, request: SemanticExtractionRequest) -> SemanticExtractionProposal:
        loaded = self._loader.load(
            model_id=self._model_id, revision=self._revision,
            local_files_only=self._local_files_only, device=self._device,
        )
        total_generation_ms = 0
        last_error = None
        for attempt in range(1, constants.MAX_SEMANTIC_GENERATION_ATTEMPTS + 1):
            prompt = build_prompt(request, correction=attempt > 1)
            try:
                output, input_tokens, output_tokens, generation_ms = self._generate(
                    loaded, prompt, request.artifact_type
                )
                total_generation_ms += generation_ms
                self.last_generation_metadata = SemanticGenerationMetadata(
                    attempt_count=attempt,
                    input_token_count=input_tokens,
                    output_token_count=output_tokens,
                    generation_ms=total_generation_ms,
                    first_model_load_ms=loaded.load_ms,
                    model_id=loaded.model_id, revision=loaded.revision,
                    device=loaded.device,
                )
                parsed = parse_single_json_object(output)
                proposal = self._proposal_adapter.validate_json(json.dumps(parsed))
                if proposal.artifact_type is not request.artifact_type:
                    raise SemanticModelJsonError("MODEL_OUTPUT_WRONG_ARTIFACT_TYPE")
                return proposal
            except (SemanticModelJsonError, ValidationError) as exc:
                last_error = exc
                continue
            except (MemoryError, OSError, RuntimeError, ValueError) as exc:
                raise SemanticModelGenerationError(
                    "Local semantic generation failed."
                ) from exc
        raise SemanticModelOutputInvalidError(
            "MODEL_OUTPUT_INVALID"
        ) from last_error

    @classmethod
    def _generate(cls, loaded, prompt, artifact_type):
        started = perf_counter()
        try:
            import torch
            from transformers import StoppingCriteria, StoppingCriteriaList

            tokenizer = loaded.tokenizer
            proposal_prefix = build_proposal_prefix(artifact_type)
            messages = [
                {"role": "system", "content": "Return source-grounded JSON only. Never provide reasoning."},
                {"role": "user", "content": prompt},
                {"role": "assistant", "content": proposal_prefix},
            ]
            try:
                rendered = tokenizer.apply_chat_template(
                    messages, tokenize=False, continue_final_message=True,
                    enable_thinking=False,
                )
            except (AttributeError, TypeError, ValueError):
                rendered = prompt
            inputs = tokenizer(
                rendered, return_tensors="pt", truncation=True,
                max_length=constants.MAX_SEMANTIC_INPUT_TOKENS,
            )
            inputs = {key: value.to(loaded.device) for key, value in inputs.items()}
            input_count = int(inputs["input_ids"].shape[-1])

            class CompleteJsonObjectCriteria(StoppingCriteria):
                """Stop once the generated suffix satisfies the JSON-only contract."""

                def __call__(self, input_ids, scores, **kwargs):
                    suffix = tokenizer.decode(
                        input_ids[0][input_count:], skip_special_tokens=True
                    ).strip()
                    try:
                        parse_single_json_object(proposal_prefix + suffix)
                    except SemanticModelJsonError:
                        return False
                    return True

            with cls._generation_lock, torch.inference_mode():
                generated = loaded.model.generate(
                    **inputs, do_sample=False,
                    max_new_tokens=constants.MAX_SEMANTIC_NEW_TOKENS,
                    stopping_criteria=StoppingCriteriaList([
                        CompleteJsonObjectCriteria()
                    ]),
                    pad_token_id=(tokenizer.pad_token_id
                                  if tokenizer.pad_token_id is not None
                                  else tokenizer.eos_token_id),
                    eos_token_id=tokenizer.eos_token_id,
                )
            new_tokens = generated[0][input_count:]
            output = proposal_prefix + tokenizer.decode(
                new_tokens, skip_special_tokens=True
            ).strip()
            return (
                output, input_count, int(new_tokens.shape[-1]),
                round((perf_counter() - started) * 1000),
            )
        except (MemoryError, OSError, RuntimeError, ValueError) as exc:
            raise SemanticModelGenerationError(
                "Local semantic generation failed."
            ) from exc

    @property
    def configured_model(self):
        return self._model_id, self._revision
