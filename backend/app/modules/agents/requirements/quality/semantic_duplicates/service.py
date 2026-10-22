"""Traceable pairwise semantic duplicate evidence over validated quality input."""

import math
from enum import StrEnum

from app.modules.agents.requirements.infrastructure.digests import stable_json_sha256
from app.modules.agents.requirements.quality.contracts import (
    ExactDuplicateResult,
    SemanticDuplicatePair,
    SemanticDuplicateResult,
    SemanticSimilarityEvidence,
    ValidatedQualityInput,
)
from app.modules.agents.requirements.quality.semantic_duplicates.protocol import (
    RequirementEmbeddingProviderError,
)


SEMANTIC_DUPLICATE_CONTRACT_VERSION = "1"
SEMANTIC_DUPLICATE_DETECTOR_VERSION = "1"
DEFAULT_SEMANTIC_DUPLICATE_THRESHOLD = 0.82
DEFAULT_MAX_REQUIREMENTS = 500


class SemanticDuplicateErrorCode(StrEnum):
    INPUT_MISMATCH = "SEMANTIC_INPUT_MISMATCH"
    INPUT_INVALID = "SEMANTIC_INPUT_INVALID"
    REQUIREMENT_LIMIT_EXCEEDED = "SEMANTIC_REQUIREMENT_LIMIT_EXCEEDED"
    PROVIDER_FAILURE = "SEMANTIC_PROVIDER_FAILURE"
    EMBEDDING_INVALID = "SEMANTIC_EMBEDDING_INVALID"


class SemanticDuplicateError(RuntimeError):
    def __init__(self, code: SemanticDuplicateErrorCode, message: str) -> None:
        self.code = code
        super().__init__(message)


class SemanticDuplicateService:
    def __init__(self, provider, *, threshold: float = DEFAULT_SEMANTIC_DUPLICATE_THRESHOLD,
                 max_requirements: int = DEFAULT_MAX_REQUIREMENTS) -> None:
        if not -1.0 <= threshold <= 1.0 or max_requirements < 2:
            raise ValueError("Semantic duplicate detector configuration is invalid")
        self._provider = provider
        self._threshold = threshold
        self._max_requirements = max_requirements

    @property
    def configuration_fingerprint(self) -> str:
        return stable_json_sha256({
            "detector_type": "SEMANTIC_DUPLICATE",
            "detector_version": SEMANTIC_DUPLICATE_DETECTOR_VERSION,
            "contract_version": SEMANTIC_DUPLICATE_CONTRACT_VERSION,
            "model_configuration_fingerprint": self._provider.model_identity.configuration_fingerprint,
            "threshold": self._threshold,
            "similarity": "COSINE",
            "pair_policy": "ORDERED_ALL_PAIRS_EXCLUDING_EXACT",
            "max_requirements": self._max_requirements,
        })

    def detect(self, value: ValidatedQualityInput,
               exact: ExactDuplicateResult) -> SemanticDuplicateResult:
        exact_pairs = self._validate_inputs(value, exact)
        requirements = value.requirements
        if len(requirements) > self._max_requirements:
            self._reject(SemanticDuplicateErrorCode.REQUIREMENT_LIMIT_EXCEEDED,
                         "Requirement count exceeds the semantic comparison limit")
        if len(requirements) < 2:
            return self._result(value, exact, ())
        has_comparable_pair = any(
            frozenset((requirements[left].requirement_id,
                       requirements[right].requirement_id)) not in exact_pairs
            for left in range(len(requirements))
            for right in range(left + 1, len(requirements))
        )
        if not has_comparable_pair:
            return self._result(value, exact, ())
        try:
            embeddings = self._provider.encode(tuple(item.statement for item in requirements))
        except RequirementEmbeddingProviderError as exc:
            raise SemanticDuplicateError(SemanticDuplicateErrorCode.PROVIDER_FAILURE,
                                         "Requirement embeddings are unavailable") from exc
        except Exception as exc:
            raise SemanticDuplicateError(SemanticDuplicateErrorCode.PROVIDER_FAILURE,
                                         "Requirement embedding provider failed") from exc
        self._validate_embeddings(embeddings, len(requirements))

        pairs: list[SemanticDuplicatePair] = []
        model_fingerprint = self._provider.model_identity.configuration_fingerprint
        for left_index, left in enumerate(requirements):
            for right_index in range(left_index + 1, len(requirements)):
                right = requirements[right_index]
                if frozenset((left.requirement_id, right.requirement_id)) in exact_pairs:
                    continue
                similarity = self._cosine(embeddings[left_index], embeddings[right_index])
                if similarity < self._threshold:
                    continue
                identity = stable_json_sha256({
                    "contract_version": SEMANTIC_DUPLICATE_CONTRACT_VERSION,
                    "quality_input_identity": value.input_identity,
                    "left_requirement_id": left.requirement_id,
                    "right_requirement_id": right.requirement_id,
                    "model_configuration_fingerprint": model_fingerprint,
                    "threshold": self._threshold,
                })
                pairs.append(SemanticDuplicatePair(
                    semantic_duplicate_id=f"QSEM-{identity[:16].upper()}",
                    quality_input_identity=value.input_identity,
                    left=left, right=right,
                    evidence=SemanticSimilarityEvidence(
                        cosine_similarity=similarity, threshold=self._threshold,
                        model_configuration_fingerprint=model_fingerprint,
                    ),
                ))
        return self._result(value, exact, tuple(pairs))

    def _validate_inputs(self, value, exact):
        if (exact.quality_input_identity != value.input_identity
                or exact.agent_project_id != value.agent_project_id):
            self._reject(SemanticDuplicateErrorCode.INPUT_MISMATCH,
                         "Exact duplicate evidence belongs to another quality input")
        by_id = {item.requirement_id: item for item in value.requirements}
        if len(by_id) != len(value.requirements):
            self._reject(SemanticDuplicateErrorCode.INPUT_INVALID,
                         "Quality input contains duplicate requirement identities")
        exact_pairs: set[frozenset[str]] = set()
        for group in exact.duplicate_groups:
            members = group.members
            for member in members:
                current = by_id.get(member.requirement.requirement_id)
                if current is None or current != member.requirement:
                    self._reject(SemanticDuplicateErrorCode.INPUT_INVALID,
                                 "Exact duplicate traceability is inconsistent")
            for left_index in range(len(members)):
                for right_index in range(left_index + 1, len(members)):
                    exact_pairs.add(frozenset((
                        members[left_index].requirement.requirement_id,
                        members[right_index].requirement.requirement_id,
                    )))
        return exact_pairs

    def _validate_embeddings(self, embeddings, expected_count):
        if len(embeddings) != expected_count:
            self._embedding_reject()
        expected_dimension = self._provider.model_identity.embedding_dimension
        for embedding in embeddings:
            if len(embedding) != expected_dimension or not embedding:
                self._embedding_reject()
            if any(not math.isfinite(value) for value in embedding):
                self._embedding_reject()
            if math.sqrt(math.fsum(value * value for value in embedding)) == 0.0:
                self._embedding_reject()

    @staticmethod
    def _cosine(left, right):
        left_norm = math.sqrt(math.fsum(value * value for value in left))
        right_norm = math.sqrt(math.fsum(value * value for value in right))
        score = math.fsum(a * b for a, b in zip(left, right, strict=True)) / (left_norm * right_norm)
        return max(-1.0, min(1.0, score))

    def _result(self, value, exact, pairs):
        identity = stable_json_sha256({
            "quality_input_identity": value.input_identity,
            "exact_duplicate_result_identity": exact.result_identity,
            "contract_version": SEMANTIC_DUPLICATE_CONTRACT_VERSION,
            "detector_fingerprint": self.configuration_fingerprint,
            "threshold": self._threshold,
            "ordered_semantic_duplicate_pair_ids": [item.semantic_duplicate_id for item in pairs],
        })
        return SemanticDuplicateResult(
            contract_version=SEMANTIC_DUPLICATE_CONTRACT_VERSION,
            agent_project_id=value.agent_project_id,
            quality_input_identity=value.input_identity,
            exact_duplicate_result_identity=exact.result_identity,
            model=self._provider.model_identity,
            detector_fingerprint=self.configuration_fingerprint,
            threshold=self._threshold, pairs=pairs, pair_count=len(pairs),
            result_identity=identity,
        )

    @staticmethod
    def _embedding_reject():
        raise SemanticDuplicateError(SemanticDuplicateErrorCode.EMBEDDING_INVALID,
                                     "Embedding output is invalid")

    @staticmethod
    def _reject(code, message):
        raise SemanticDuplicateError(code, message)
