import hashlib
import json
import math
from dataclasses import dataclass
from time import perf_counter

from app.modules.agents.testing_validation.intelligence.schemas import (
    ClassificationWarning,
    TestingZeroShotClassificationResult,
    ZeroShotInputMetadata,
    current_chunk_reference,
)
from app.modules.agents.testing_validation.intelligence.taxonomy import (
    AGENT4_TESTING_TAXONOMY_VERSION,
    AGENT4_ZERO_SHOT_LABEL_DESCRIPTION_VERSION,
    TESTING_INTELLIGENCE_LABEL_ORDER,
    TESTING_INTELLIGENCE_TAXONOMY,
)

from . import constants
from .runtime import Agent4ZeroShotModelLoadError, Agent4ZeroShotTokenizationError


class Agent4ZeroShotConfigurationError(RuntimeError):
    code = "ZERO_SHOT_LABEL_MAPPING_FAILED"


class Agent4ZeroShotInferenceError(RuntimeError):
    code = "ZERO_SHOT_INFERENCE_FAILED"

    def __init__(self, chunk_id):
        self.chunk_id = chunk_id
        super().__init__(f"Zero-shot inference failed for chunk {chunk_id}.")


class Agent4ZeroShotInvalidResponseError(RuntimeError):
    code = "ZERO_SHOT_INVALID_MODEL_RESPONSE"


def candidate_mapping():
    mapping = {
        label: TESTING_INTELLIGENCE_TAXONOMY[label].model_description
        for label in TESTING_INTELLIGENCE_LABEL_ORDER
    }
    descriptions = list(mapping.values())
    if len(mapping) != 15 or any(not value.strip() for value in descriptions) \
            or len(descriptions) != len(set(descriptions)):
        raise Agent4ZeroShotConfigurationError(
            "The T1 zero-shot candidate mapping is invalid."
        )
    return mapping


def inference_configuration_fingerprint():
    mapping = candidate_mapping()
    payload = {
        "stage": constants.ZERO_SHOT_STAGE_VERSION,
        "taxonomy": AGENT4_TESTING_TAXONOMY_VERSION,
        "descriptions": AGENT4_ZERO_SHOT_LABEL_DESCRIPTION_VERSION,
        "candidates": [(label.value, mapping[label]) for label in mapping],
        "hypothesis_version": constants.HYPOTHESIS_TEMPLATE_VERSION,
        "hypothesis": constants.HYPOTHESIS_TEMPLATE,
        "model_id": constants.MODEL_ID,
        "model_revision": constants.MODEL_REVISION,
        "task": constants.MODEL_TASK,
        "multi_label": True,
        "batch_size": constants.INFERENCE_BATCH_SIZE,
        "truncation": constants.TRUNCATION_STRATEGY,
    }
    return hashlib.sha256(json.dumps(payload, separators=(",", ":")).encode()).hexdigest()


class Agent4ZeroShotClassifier:
    def __init__(self, runtime):
        self._runtime = runtime

    def classify(self, chunk_set, *, confirmed_source_ids, processed_at):
        mapping = candidate_mapping()
        descriptions = list(mapping.values())
        reverse = {description: label for label, description in mapping.items()}
        chunks = chunk_set.chunks
        outputs = []
        device = None
        for start in range(0, len(chunks), constants.INFERENCE_BATCH_SIZE):
            batch = chunks[start:start + constants.INFERENCE_BATCH_SIZE]
            batch_results, batch_device = self._infer_with_isolation(
                batch, descriptions, reverse, chunk_set,
                confirmed_source_ids, processed_at,
            )
            outputs.extend(batch_results)
            device = device or batch_device
        return device, outputs

    def _infer_with_isolation(self, chunks, descriptions, reverse, chunk_set,
                              confirmed_source_ids, processed_at):
        started = perf_counter()
        try:
            raw = self._runtime.infer(
                [chunk.text for chunk in chunks],
                candidate_labels=descriptions,
                hypothesis_template=constants.HYPOTHESIS_TEMPLATE,
                batch_size=constants.INFERENCE_BATCH_SIZE,
            )
            if len(raw.responses) != len(chunks) or len(raw.input_token_counts) != len(chunks):
                raise Agent4ZeroShotInvalidResponseError(
                    "The zero-shot runtime returned an incomplete batch."
                )
            per_item_ms = (perf_counter() - started) * 1000 / len(chunks)
            results = [
                self._result(chunk, chunk_set, confirmed_source_ids, response,
                             reverse, token_count, raw.model_max_length,
                             per_item_ms, processed_at)
                for chunk, response, token_count in zip(
                    chunks, raw.responses, raw.input_token_counts, strict=True
                )
            ]
            return results, raw.device
        except (
            Agent4ZeroShotInvalidResponseError,
            Agent4ZeroShotConfigurationError,
            Agent4ZeroShotModelLoadError,
            Agent4ZeroShotTokenizationError,
        ):
            raise
        except Exception as exc:
            if len(chunks) == 1:
                error = Agent4ZeroShotInferenceError(chunks[0].chunk_id)
                raise error from exc
            midpoint = len(chunks) // 2
            left, left_device = self._infer_with_isolation(
                chunks[:midpoint], descriptions, reverse, chunk_set,
                confirmed_source_ids, processed_at,
            )
            right, right_device = self._infer_with_isolation(
                chunks[midpoint:], descriptions, reverse, chunk_set,
                confirmed_source_ids, processed_at,
            )
            return left + right, left_device or right_device

    @staticmethod
    def _result(chunk, chunk_set, confirmed_source_ids, response, reverse,
                token_count, model_max_length, inference_ms, processed_at):
        labels = response.get("labels")
        scores = response.get("scores")
        if not isinstance(labels, list) or not isinstance(scores, list) \
                or len(labels) != len(scores) or len(labels) != 15 \
                or len(labels) != len(set(labels)) or set(labels) != set(reverse):
            raise Agent4ZeroShotInvalidResponseError(
                "The model response does not contain the complete ZL1 mapping."
            )
        score_map = {}
        for description, raw_score in zip(labels, scores, strict=True):
            try:
                score = float(raw_score)
            except (TypeError, ValueError) as exc:
                raise Agent4ZeroShotInvalidResponseError(
                    "The model returned an invalid score."
                ) from exc
            if not math.isfinite(score) or not 0 <= score <= 1:
                raise Agent4ZeroShotInvalidResponseError(
                    "The model returned an invalid score."
                )
            score_map[reverse[description]] = score
        truncated = token_count > model_max_length
        warnings = []
        if truncated:
            warnings.append(ClassificationWarning(
                code="MODEL_INPUT_TRUNCATED",
                message=(
                    "The premise exceeded the model limit and was truncated; "
                    "the candidate hypothesis was preserved."
                ),
            ))
        config = inference_configuration_fingerprint()
        identity = hashlib.sha256("\x1f".join((
            chunk.chunk_id, chunk.text_sha256, config
        )).encode()).hexdigest()[:32]
        return TestingZeroShotClassificationResult(
            result_id=f"A4ZSC-{identity}",
            chunk=current_chunk_reference(
                chunk, chunk_set, confirmed_source_ids=confirmed_source_ids
            ),
            taxonomy_version=AGENT4_TESTING_TAXONOMY_VERSION,
            model_id=constants.MODEL_ID,
            model_revision=constants.MODEL_REVISION,
            label_scores=score_map,
            label_description_version=AGENT4_ZERO_SHOT_LABEL_DESCRIPTION_VERSION,
            hypothesis_template_version=constants.HYPOTHESIS_TEMPLATE_VERSION,
            input_metadata=ZeroShotInputMetadata(
                input_token_count=token_count,
                model_max_tokens=model_max_length,
                truncated=truncated,
                tokens_discarded=max(0, token_count - model_max_length),
            ),
            inference_duration_ms=round(inference_ms, 3),
            warnings=warnings,
            processed_at=processed_at,
        )
