"""Conflict evidence from embedding-related pairs and bidirectional NLI."""

import math
from enum import StrEnum

from app.modules.agents.requirements.infrastructure.digests import stable_json_sha256
from app.modules.agents.requirements.quality.conflicts.protocol import (
    RequirementConflictProviderError,
)
from app.modules.agents.requirements.quality.contracts import (
    ConflictModelIdentity, DirectionalConflictEvidence, ExactDuplicateResult,
    NliRelation, NliScoreVector, RequirementConflictPair, RequirementConflictResult,
    SemanticDuplicateResult, ValidatedQualityInput,
)
from app.modules.agents.requirements.quality.semantic_duplicates.protocol import (
    RequirementEmbeddingProviderError,
)


CONFLICT_CONTRACT_VERSION = "1"
CONFLICT_DETECTOR_VERSION = "1"
DEFAULT_RELATEDNESS_THRESHOLD = 0.55
DEFAULT_CONTRADICTION_THRESHOLD = 0.80
DEFAULT_MAX_REQUIREMENTS = 500
DIRECTIONAL_POLICY = "LEFT_TO_RIGHT_AND_RIGHT_TO_LEFT"
AGGREGATION_POLICY = "ARITHMETIC_MEAN_DIRECTIONAL_CONTRADICTION"


class ConflictDetectionErrorCode(StrEnum):
    INPUT_INVALID = "CONFLICT_INPUT_INVALID"
    INPUT_LIMIT_EXCEEDED = "CONFLICT_INPUT_LIMIT_EXCEEDED"
    RELATEDNESS_FAILED = "CONFLICT_RELATEDNESS_FAILED"
    RELATEDNESS_INVALID = "CONFLICT_RELATEDNESS_INVALID"
    PROVIDER_FAILED = "CONFLICT_PROVIDER_FAILED"
    MODEL_RESPONSE_INVALID = "CONFLICT_MODEL_RESPONSE_INVALID"


class ConflictDetectionError(RuntimeError):
    def __init__(self, code, message):
        self.code = code
        super().__init__(message)


class RequirementConflictService:
    def __init__(self, embedding_provider, conflict_provider, *,
                 relatedness_threshold=DEFAULT_RELATEDNESS_THRESHOLD,
                 contradiction_threshold=DEFAULT_CONTRADICTION_THRESHOLD,
                 max_requirements=DEFAULT_MAX_REQUIREMENTS):
        if not -1 <= relatedness_threshold <= 1 or not 0 <= contradiction_threshold <= 1 or max_requirements < 2:
            raise ValueError("Conflict detector configuration is invalid")
        self._embeddings = embedding_provider
        self._nli = conflict_provider
        self._relatedness_threshold = relatedness_threshold
        self._contradiction_threshold = contradiction_threshold
        self._max_requirements = max_requirements

    @property
    def nli_model_identity(self):
        values = dict(self._nli.configuration)
        values.update({
            "directional_policy": DIRECTIONAL_POLICY,
            "aggregation_policy": AGGREGATION_POLICY,
            "contradiction_threshold": self._contradiction_threshold,
        })
        return ConflictModelIdentity(
            **values, configuration_fingerprint=stable_json_sha256(values)
        )

    @property
    def configuration_fingerprint(self):
        return stable_json_sha256({
            "detector_version": CONFLICT_DETECTOR_VERSION,
            "contract_version": CONFLICT_CONTRACT_VERSION,
            "embedding_configuration_fingerprint": self._embeddings.model_identity.configuration_fingerprint,
            "nli_configuration_fingerprint": self.nli_model_identity.configuration_fingerprint,
            "relatedness_threshold": self._relatedness_threshold,
            "contradiction_threshold": self._contradiction_threshold,
            "max_requirements": self._max_requirements,
        })

    def detect(self, value: ValidatedQualityInput, exact: ExactDuplicateResult,
               semantic: SemanticDuplicateResult) -> RequirementConflictResult:
        exact_pairs = self._validate_inputs(value, exact, semantic)
        requirements = value.requirements
        if len(requirements) > self._max_requirements:
            self._reject(ConflictDetectionErrorCode.INPUT_LIMIT_EXCEEDED,
                         "Requirement count exceeds the conflict comparison limit")
        total_pairs = len(requirements) * (len(requirements) - 1) // 2
        if len(requirements) < 2 or total_pairs == len(exact_pairs):
            return self._result(value, exact, semantic, (), total_pairs, 0)
        try:
            embeddings = self._embeddings.encode(tuple(item.statement for item in requirements))
        except Exception as exc:
            code = ConflictDetectionErrorCode.RELATEDNESS_FAILED
            raise ConflictDetectionError(code, "Requirement relatedness is unavailable") from exc
        self._validate_embeddings(embeddings, len(requirements))
        candidates = []
        for left_index in range(len(requirements)):
            for right_index in range(left_index + 1, len(requirements)):
                left, right = requirements[left_index], requirements[right_index]
                if frozenset((left.requirement_id, right.requirement_id)) in exact_pairs:
                    continue
                relatedness = self._cosine(embeddings[left_index], embeddings[right_index])
                if relatedness >= self._relatedness_threshold:
                    candidates.append((left, right, relatedness))
        if not candidates:
            return self._result(value, exact, semantic, (), total_pairs, 0)
        directional_inputs = tuple(
            pair for left, right, _ in candidates
            for pair in ((left.statement, right.statement), (right.statement, left.statement))
        )
        try:
            directional = self._nli.evaluate(directional_inputs)
        except RequirementConflictProviderError as exc:
            raise ConflictDetectionError(ConflictDetectionErrorCode.PROVIDER_FAILED,
                                         "Conflict inference is unavailable") from exc
        except Exception as exc:
            raise ConflictDetectionError(ConflictDetectionErrorCode.PROVIDER_FAILED,
                                         "Conflict provider failed") from exc
        if len(directional) != len(candidates) * 2:
            self._reject(ConflictDetectionErrorCode.MODEL_RESPONSE_INVALID,
                         "Conflict model returned incomplete evidence")
        conflicts = []
        nli_identity = self.nli_model_identity
        embedding_fp = self._embeddings.model_identity.configuration_fingerprint
        for index, (left, right, relatedness) in enumerate(candidates):
            forward, reverse = directional[index * 2:index * 2 + 2]
            if not isinstance(forward, NliScoreVector) or not isinstance(reverse, NliScoreVector):
                self._reject(ConflictDetectionErrorCode.MODEL_RESPONSE_INVALID,
                             "Conflict model returned invalid evidence")
            try:
                forward_score = forward.score_for(NliRelation.CONTRADICTION)
                reverse_score = reverse.score_for(NliRelation.CONTRADICTION)
            except Exception as exc:
                raise ConflictDetectionError(ConflictDetectionErrorCode.MODEL_RESPONSE_INVALID,
                                             "Conflict model returned invalid evidence") from exc
            final_score = (forward_score + reverse_score) / 2.0
            if final_score < self._contradiction_threshold:
                continue
            identity = stable_json_sha256({
                "contract_version": CONFLICT_CONTRACT_VERSION,
                "quality_input_identity": value.input_identity,
                "left_requirement_id": left.requirement_id,
                "right_requirement_id": right.requirement_id,
                "embedding_configuration_fingerprint": embedding_fp,
                "nli_configuration_fingerprint": nli_identity.configuration_fingerprint,
                "relatedness_threshold": self._relatedness_threshold,
                "contradiction_threshold": self._contradiction_threshold,
                "directional_aggregation_policy": AGGREGATION_POLICY,
            })
            conflicts.append(RequirementConflictPair(
                conflict_id=f"QCON-{identity[:16].upper()}",
                quality_input_identity=value.input_identity,
                left=left, right=right, relatedness_score=relatedness,
                relatedness_threshold=self._relatedness_threshold,
                left_to_right=DirectionalConflictEvidence(
                    premise_requirement_id=left.requirement_id,
                    hypothesis_requirement_id=right.requirement_id,
                    relation_scores=forward,
                ),
                right_to_left=DirectionalConflictEvidence(
                    premise_requirement_id=right.requirement_id,
                    hypothesis_requirement_id=left.requirement_id,
                    relation_scores=reverse,
                ),
                final_contradiction_score=final_score,
                contradiction_threshold=self._contradiction_threshold,
                final_relation=NliRelation.CONTRADICTION,
                embedding_configuration_fingerprint=embedding_fp,
                nli_configuration_fingerprint=nli_identity.configuration_fingerprint,
            ))
        return self._result(value, exact, semantic, tuple(conflicts),
                            total_pairs, len(candidates))

    def _validate_inputs(self, value, exact, semantic):
        if (exact.agent_project_id != value.agent_project_id
                or exact.quality_input_identity != value.input_identity
                or semantic.agent_project_id != value.agent_project_id
                or semantic.quality_input_identity != value.input_identity
                or semantic.exact_duplicate_result_identity != exact.result_identity):
            self._reject(ConflictDetectionErrorCode.INPUT_INVALID,
                         "Quality evidence inputs are incompatible")
        by_id = {item.requirement_id: item for item in value.requirements}
        if len(by_id) != len(value.requirements):
            self._reject(ConflictDetectionErrorCode.INPUT_INVALID,
                         "Quality input contains duplicate requirement identities")
        exact_pairs = set()
        for group in exact.duplicate_groups:
            for member in group.members:
                if by_id.get(member.requirement.requirement_id) != member.requirement:
                    self._reject(ConflictDetectionErrorCode.INPUT_INVALID,
                                 "Exact duplicate traceability is inconsistent")
            for left in range(len(group.members)):
                for right in range(left + 1, len(group.members)):
                    exact_pairs.add(frozenset((group.members[left].requirement.requirement_id,
                                               group.members[right].requirement.requirement_id)))
        for pair in semantic.pairs:
            if by_id.get(pair.left.requirement_id) != pair.left or by_id.get(pair.right.requirement_id) != pair.right:
                self._reject(ConflictDetectionErrorCode.INPUT_INVALID,
                             "Semantic duplicate traceability is inconsistent")
        return exact_pairs

    def _validate_embeddings(self, embeddings, count):
        if len(embeddings) != count:
            self._relatedness_reject()
        dimension = self._embeddings.model_identity.embedding_dimension
        for embedding in embeddings:
            if len(embedding) != dimension or not embedding or any(not math.isfinite(v) for v in embedding):
                self._relatedness_reject()
            if math.sqrt(math.fsum(v * v for v in embedding)) == 0:
                self._relatedness_reject()

    @staticmethod
    def _cosine(left, right):
        numerator = math.fsum(a * b for a, b in zip(left, right, strict=True))
        denominator = math.sqrt(math.fsum(v * v for v in left)) * math.sqrt(math.fsum(v * v for v in right))
        return max(-1.0, min(1.0, numerator / denominator))

    def _result(self, value, exact, semantic, conflicts, total_pairs, candidate_count):
        identity = stable_json_sha256({
            "quality_input_identity": value.input_identity,
            "exact_duplicate_result_identity": exact.result_identity,
            "semantic_duplicate_result_identity": semantic.result_identity,
            "detector_fingerprint": self.configuration_fingerprint,
            "ordered_conflict_ids": [item.conflict_id for item in conflicts],
        })
        return RequirementConflictResult(
            contract_version=CONFLICT_CONTRACT_VERSION,
            agent_project_id=value.agent_project_id,
            quality_input_identity=value.input_identity,
            exact_duplicate_result_identity=exact.result_identity,
            semantic_duplicate_result_identity=semantic.result_identity,
            embedding_configuration_fingerprint=self._embeddings.model_identity.configuration_fingerprint,
            nli_model=self.nli_model_identity,
            detector_fingerprint=self.configuration_fingerprint,
            relatedness_threshold=self._relatedness_threshold,
            contradiction_threshold=self._contradiction_threshold,
            total_potential_pair_count=total_pairs,
            relatedness_candidate_pair_count=candidate_count,
            nli_evaluated_pair_count=candidate_count,
            conflicts=conflicts, conflict_count=len(conflicts),
            result_identity=identity,
        )

    @staticmethod
    def _relatedness_reject():
        raise ConflictDetectionError(ConflictDetectionErrorCode.RELATEDNESS_INVALID,
                                     "Requirement relatedness output is invalid")

    @staticmethod
    def _reject(code, message):
        raise ConflictDetectionError(code, message)
