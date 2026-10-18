from dataclasses import dataclass
from threading import Lock
from time import perf_counter

from app.modules.agents.implementation.preparation.schemas import (
    ArtifactDetectionLabel,
    SemanticChunk,
)

from .constants import (
    CANDIDATE_LABELS,
    HYPOTHESIS_TEMPLATE,
    INFERENCE_BATCH_SIZE,
    MAX_DISPLAY_LABELS,
    MODEL_DISPLAY_THRESHOLD,
)
from .model_loader import LoadedZeroShotModel, ZeroShotModelLoader
from .schemas import ZeroShotScore


@dataclass(frozen=True)
class ClassificationOutcome:
    chunk_id: str
    text_hash: str
    model_token_count: int
    model_max_length: int
    input_truncated: bool
    inference_ms: float
    scores: list[ZeroShotScore]
    display_predictions: list[ZeroShotScore]
    error: bool = False


class ZeroShotClassifier:
    _inference_lock = Lock()

    def __init__(self, *, local_files_only: bool = False,
                 loader=ZeroShotModelLoader) -> None:
        self._local_files_only = local_files_only
        self._loader = loader

    def classify_chunks(self, chunks: list[SemanticChunk]):
        loaded = self._loader.load(local_files_only=self._local_files_only)
        outcomes: list[ClassificationOutcome] = []
        with self._inference_lock:
            for start in range(0, len(chunks), INFERENCE_BATCH_SIZE):
                batch = chunks[start:start + INFERENCE_BATCH_SIZE]
                outcomes.extend(self._classify_batch_with_isolation(loaded, batch))
        return loaded, outcomes

    def _classify_batch_with_isolation(
        self, loaded: LoadedZeroShotModel, chunks: list[SemanticChunk]
    ) -> list[ClassificationOutcome]:
        started = perf_counter()
        try:
            raw = loaded.pipeline(
                [chunk.text for chunk in chunks],
                candidate_labels=list(CANDIDATE_LABELS.values()),
                hypothesis_template=HYPOTHESIS_TEMPLATE,
                multi_label=True,
                truncation=True,
                batch_size=INFERENCE_BATCH_SIZE,
            )
            if isinstance(raw, dict):
                raw = [raw]
            elapsed = (perf_counter() - started) * 1000
            return [
                self._outcome(loaded, chunk, response, elapsed / len(chunks))
                for chunk, response in zip(chunks, raw, strict=True)
            ]
        except Exception:
            if len(chunks) == 1:
                return [self._failed_outcome(loaded, chunks[0], (perf_counter() - started) * 1000)]
            return [
                outcome
                for chunk in chunks
                for outcome in self._classify_batch_with_isolation(loaded, [chunk])
            ]

    @staticmethod
    def _token_count(loaded: LoadedZeroShotModel, text: str) -> int:
        counts = []
        for description in CANDIDATE_LABELS.values():
            hypothesis = HYPOTHESIS_TEMPLATE.format(description)
            encoded = loaded.tokenizer(
                text,
                hypothesis,
                add_special_tokens=True,
                truncation=False,
            )
            counts.append(len(encoded["input_ids"]))
        return max(counts, default=0)

    def _outcome(self, loaded, chunk, response, inference_ms):
        score_by_description = {
            label: float(score)
            for label, score in zip(response["labels"], response["scores"], strict=True)
        }
        if set(score_by_description) != set(CANDIDATE_LABELS.values()):
            raise ValueError("Model response did not contain the complete candidate taxonomy")
        scores = [
            ZeroShotScore(label=label, score=round(score_by_description[description], 6))
            for label, description in CANDIDATE_LABELS.items()
        ]
        display = sorted(
            [item for item in scores if item.label is not ArtifactDetectionLabel.OTHER_CONTEXT and item.score >= MODEL_DISPLAY_THRESHOLD],
            key=lambda item: (-item.score, item.label.value),
        )[:MAX_DISPLAY_LABELS]
        other = next(item for item in scores if item.label is ArtifactDetectionLabel.OTHER_CONTEXT)
        if not display and other.score == max(item.score for item in scores):
            display = [other]
        token_count = self._token_count(loaded, chunk.text)
        return ClassificationOutcome(
            chunk_id=chunk.chunk_id,
            text_hash=chunk.text_hash,
            model_token_count=token_count,
            model_max_length=loaded.model_max_length,
            input_truncated=token_count > loaded.model_max_length,
            inference_ms=round(inference_ms, 3),
            scores=scores,
            display_predictions=display,
        )

    def _failed_outcome(self, loaded, chunk, inference_ms):
        token_count = self._token_count(loaded, chunk.text)
        return ClassificationOutcome(
            chunk_id=chunk.chunk_id,
            text_hash=chunk.text_hash,
            model_token_count=token_count,
            model_max_length=loaded.model_max_length,
            input_truncated=token_count > loaded.model_max_length,
            inference_ms=round(inference_ms, 3),
            scores=[],
            display_predictions=[],
            error=True,
        )
