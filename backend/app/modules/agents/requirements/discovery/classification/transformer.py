"""Lazy local Hugging Face zero-shot classifier implementation."""

from threading import Lock
from typing import Any, Callable
from importlib.metadata import PackageNotFoundError, version

from app.modules.agents.requirements.discovery.classification.protocol import (
    ClassifierConfiguration,
    ProviderClassification,
    RequirementClassifierError,
)
from app.modules.agents.requirements.discovery.contracts import (
    ClassificationScore,
    RequirementCandidate,
    RequirementClassificationLabel,
)


DEFAULT_MODEL_ID = "MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli"
DEFAULT_MODEL_REVISION = "6f5cf0a2b59cabb106aca4c287eed12e357e90eb"
ZERO_SHOT_TASK = "zero-shot-classification"
HYPOTHESIS_TEMPLATE = "This statement is {}."
LABEL_DESCRIPTIONS: dict[RequirementClassificationLabel, str] = {
    RequirementClassificationLabel.FUNCTIONAL: "a functional software requirement",
    RequirementClassificationLabel.NON_FUNCTIONAL: "a non-functional software requirement",
    RequirementClassificationLabel.OTHER: "not a software requirement",
}


class TransformerRequirementClassifier:
    """CPU-first, bounded-batch, non-generative zero-shot NLI provider."""

    def __init__(
        self,
        *,
        model_id: str = DEFAULT_MODEL_ID,
        revision: str | None = DEFAULT_MODEL_REVISION,
        device: str = "cpu",
        batch_size: int = 4,
        local_files_only: bool = False,
        pipeline_factory: Callable[[], tuple[Any, str | None]] | None = None,
    ) -> None:
        if not model_id.strip():
            raise ValueError("Transformer model ID is required")
        if device not in {"cpu", "cuda"}:
            raise ValueError("Transformer device must be cpu or cuda")
        if not 1 <= batch_size <= 32:
            raise ValueError("Transformer batch size must be between 1 and 32")
        self._model_id = model_id.strip()
        self._revision = revision.strip() if revision else None
        self._device = device
        self._batch_size = batch_size
        self._local_files_only = local_files_only
        self._pipeline_factory = pipeline_factory or self._build_pipeline
        self._pipeline: Any | None = None
        self._resolved_revision: str | None = None
        self._initialization_lock = Lock()
        self._inference_lock = Lock()

    @property
    def configuration(self) -> ClassifierConfiguration:
        try:
            provider_version = version("transformers")
        except PackageNotFoundError:
            provider_version = "unavailable"
        return ClassifierConfiguration(
            provider_type="HUGGING_FACE_ZERO_SHOT_NLI",
            provider_version=provider_version,
            model_id=self._model_id,
            requested_revision=self._revision,
            resolved_revision=self._resolved_revision or self._revision,
            task=ZERO_SHOT_TASK,
            label_descriptions=dict(LABEL_DESCRIPTIONS),
            hypothesis_template=HYPOTHESIS_TEMPLATE,
            device=self._device,
            batch_size=self._batch_size,
            local_files_only=self._local_files_only,
        )

    def classify(
        self, candidates: tuple[RequirementCandidate, ...]
    ) -> tuple[ProviderClassification, ...]:
        if not candidates:
            return ()
        model_pipeline = self._get_pipeline()
        output: list[ProviderClassification] = []
        try:
            with self._inference_lock:
                for start in range(0, len(candidates), self._batch_size):
                    batch = candidates[start : start + self._batch_size]
                    raw = model_pipeline(
                        [candidate.text for candidate in batch],
                        candidate_labels=list(LABEL_DESCRIPTIONS.values()),
                        hypothesis_template=HYPOTHESIS_TEMPLATE,
                        multi_label=False,
                        truncation=True,
                        batch_size=self._batch_size,
                    )
                    responses = [raw] if isinstance(raw, dict) else list(raw)
                    if len(responses) != len(batch):
                        raise ValueError("Transformer returned an incomplete batch")
                    output.extend(
                        self._map_response(candidate, response)
                        for candidate, response in zip(batch, responses, strict=True)
                    )
        except RequirementClassifierError:
            raise
        except Exception as exc:
            raise RequirementClassifierError(
                "Local transformer inference failed"
            ) from exc
        return tuple(output)

    def _get_pipeline(self):
        if self._pipeline is not None:
            return self._pipeline
        with self._initialization_lock:
            if self._pipeline is not None:
                return self._pipeline
            try:
                self._pipeline, self._resolved_revision = self._pipeline_factory()
            except Exception as exc:
                raise RequirementClassifierError(
                    "Local transformer model is unavailable"
                ) from exc
            return self._pipeline

    def _build_pipeline(self) -> tuple[Any, str | None]:
        import torch
        from transformers import AutoModelForSequenceClassification, AutoTokenizer, pipeline

        if self._device == "cuda" and not torch.cuda.is_available():
            raise RuntimeError("CUDA was configured but is unavailable")
        tokenizer = AutoTokenizer.from_pretrained(
            self._model_id,
            revision=self._revision,
            local_files_only=self._local_files_only,
        )
        model = AutoModelForSequenceClassification.from_pretrained(
            self._model_id,
            revision=self._revision,
            local_files_only=self._local_files_only,
            use_safetensors=True,
        )
        model_pipeline = pipeline(
            ZERO_SHOT_TASK,
            model=model,
            tokenizer=tokenizer,
            device=0 if self._device == "cuda" else -1,
        )
        return model_pipeline, getattr(model.config, "_commit_hash", None)

    @staticmethod
    def _map_response(candidate: RequirementCandidate, response: dict[str, Any]) -> ProviderClassification:
        labels = response.get("labels")
        values = response.get("scores")
        if not isinstance(labels, list) or not isinstance(values, list) or len(labels) != len(values):
            raise ValueError("Transformer returned malformed scores")
        score_by_description = {
            str(label): float(score)
            for label, score in zip(labels, values, strict=True)
        }
        if set(score_by_description) != set(LABEL_DESCRIPTIONS.values()):
            raise ValueError("Transformer returned an incomplete label taxonomy")
        scores = tuple(
            ClassificationScore(label=label, score=score_by_description[description])
            for label, description in LABEL_DESCRIPTIONS.items()
        )
        winner = max(scores, key=lambda item: item.score).label
        return ProviderClassification(
            candidate_id=candidate.candidate_id,
            winner=winner,
            scores=scores,
        )
