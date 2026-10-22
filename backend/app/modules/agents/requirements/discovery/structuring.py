"""Pure evidence-grounded projection from classified candidates to FR/NFR records."""

from app.modules.agents.requirements.discovery.candidate_detection import (
    CANDIDATE_CONTRACT_VERSION,
)
from app.modules.agents.requirements.discovery.contracts import (
    ClassifierModelIdentity,
    ExcludedCandidateReference,
    FunctionalRequirement,
    NonFunctionalRequirement,
    RequirementCandidate,
    RequirementClassification,
    RequirementClassificationLabel,
    RequirementClassificationSet,
    StructuredRequirementSet,
)
from app.modules.agents.requirements.infrastructure.digests import stable_json_sha256


STRUCTURING_CONTRACT_VERSION = "1"
REQUIREMENT_IDENTITY_VERSION = "1"


class RequirementStructuringError(RuntimeError):
    """Safe failure for incompatible or corrupted classification input."""


class RequirementStructuringService:
    def structure(
        self, classifications: RequirementClassificationSet
    ) -> StructuredRequirementSet:
        candidate_set = classifications.candidate_set
        self._validate_model_identity(classifications.model)
        self._validate_candidates(classifications)

        by_id = {item.candidate_id: item for item in classifications.classifications}
        functional: list[FunctionalRequirement] = []
        non_functional: list[NonFunctionalRequirement] = []
        excluded: list[ExcludedCandidateReference] = []
        ordered_outcomes: list[dict[str, str]] = []

        for candidate in candidate_set.candidates:
            classification = by_id[candidate.candidate_id]
            if classification.label is RequirementClassificationLabel.OTHER:
                excluded.append(
                    ExcludedCandidateReference(
                        candidate_id=candidate.candidate_id,
                        candidate_identity=candidate.candidate_identity,
                        confidence=classification.confidence,
                        raw_winner=classification.raw_winner,
                        policy_reason=classification.policy_reason,
                    )
                )
                ordered_outcomes.append(
                    {"kind": "EXCLUDED", "identity": candidate.candidate_id}
                )
                continue
            identity = self._requirement_identity(
                candidate, classification.label, candidate_set.agent_project_id
            )
            values = {
                "requirement_identity": identity,
                "agent_project_id": candidate_set.agent_project_id,
                "candidate_id": candidate.candidate_id,
                "candidate_identity": candidate.candidate_identity,
                "statement": candidate.text,
                "chunk_id": candidate.chunk_id,
                "source_id": candidate.source_id,
                "source_type": candidate.source_type,
                "start_offset": candidate.start_offset,
                "end_offset": candidate.end_offset,
                "classification_confidence": classification.confidence,
                "classifier_configuration_fingerprint": (
                    classifications.model.configuration_fingerprint
                ),
                "provenance": candidate.provenance,
            }
            if classification.label is RequirementClassificationLabel.FUNCTIONAL:
                functional.append(
                    FunctionalRequirement(
                        requirement_id=f"FR-{identity[:16].upper()}", **values
                    )
                )
                ordered_outcomes.append(
                    {"kind": "FUNCTIONAL", "identity": identity}
                )
            else:
                non_functional.append(
                    NonFunctionalRequirement(
                        requirement_id=f"NFR-{identity[:16].upper()}", **values
                    )
                )
                ordered_outcomes.append(
                    {"kind": "NON_FUNCTIONAL", "identity": identity}
                )

        set_values = {
            "contract_version": STRUCTURING_CONTRACT_VERSION,
            "agent_project_id": candidate_set.agent_project_id,
            "discovery_input_identity": candidate_set.discovery_input_identity,
            "chunk_set_digest": candidate_set.chunk_set_digest,
            "classifier_configuration_fingerprint": (
                classifications.model.configuration_fingerprint
            ),
            "functional_requirement_identities": [
                item.requirement_identity for item in functional
            ],
            "non_functional_requirement_identities": [
                item.requirement_identity for item in non_functional
            ],
            "excluded_candidate_ids": [item.candidate_id for item in excluded],
            "ordered_outcomes": ordered_outcomes,
        }
        return StructuredRequirementSet(
            contract_version=STRUCTURING_CONTRACT_VERSION,
            agent_project_id=candidate_set.agent_project_id,
            discovery_input_identity=candidate_set.discovery_input_identity,
            chunk_set_digest=candidate_set.chunk_set_digest,
            classifier_configuration_fingerprint=(
                classifications.model.configuration_fingerprint
            ),
            functional_requirements=tuple(functional),
            non_functional_requirements=tuple(non_functional),
            excluded_candidates=tuple(excluded),
            structured_set_identity=stable_json_sha256(set_values),
        )

    @staticmethod
    def _validate_model_identity(model: ClassifierModelIdentity) -> None:
        values = model.model_dump(mode="json", exclude={"configuration_fingerprint"})
        if stable_json_sha256(values) != model.configuration_fingerprint:
            raise RequirementStructuringError(
                "Classifier configuration identity is invalid"
            )

    def _validate_candidates(
        self, classifications: RequirementClassificationSet
    ) -> None:
        candidate_set = classifications.candidate_set
        candidates = candidate_set.candidates
        results = classifications.classifications
        candidate_ids = [item.candidate_id for item in candidates]
        result_ids = [item.candidate_id for item in results]
        if len(set(candidate_ids)) != len(candidate_ids):
            raise RequirementStructuringError("Candidate identities are duplicated")
        if len(set(result_ids)) != len(result_ids):
            raise RequirementStructuringError("Candidate classifications are duplicated")
        if set(result_ids) - set(candidate_ids):
            raise RequirementStructuringError("Classification references an unknown candidate")
        if set(candidate_ids) - set(result_ids):
            raise RequirementStructuringError("A candidate classification is missing")
        if result_ids != candidate_ids:
            raise RequirementStructuringError("Classification ordering is inconsistent")
        for candidate, classification in zip(candidates, results, strict=True):
            self._validate_candidate(candidate, candidate_set)
            if classification.candidate_identity != candidate.candidate_identity:
                raise RequirementStructuringError(
                    "Classification candidate identity is inconsistent"
                )

    @staticmethod
    def _validate_candidate(candidate: RequirementCandidate, candidate_set) -> None:
        if (
            candidate.agent_project_id != candidate_set.agent_project_id
            or candidate.n2_execution_id != candidate_set.n2_execution_id
            or candidate.chunk_set_digest != candidate_set.chunk_set_digest
        ):
            raise RequirementStructuringError(
                "Candidate belongs to another discovery input"
            )
        identity = stable_json_sha256(
            {
                "agent_project_id": candidate_set.agent_project_id,
                "candidate_contract_version": CANDIDATE_CONTRACT_VERSION,
                "discovery_input_identity": candidate_set.discovery_input_identity,
                "chunk_id": candidate.chunk_id,
                "span": [candidate.start_offset, candidate.end_offset],
                "text": candidate.text,
            }
        )
        if (
            candidate.candidate_identity != identity
            or candidate.candidate_id != f"RC-{identity[:16].upper()}"
        ):
            raise RequirementStructuringError("Candidate identity is invalid")

    @staticmethod
    def _requirement_identity(candidate, label, agent_project_id: str) -> str:
        return stable_json_sha256(
            {
                "agent_project_id": agent_project_id,
                "requirement_identity_version": REQUIREMENT_IDENTITY_VERSION,
                "structuring_contract_version": STRUCTURING_CONTRACT_VERSION,
                "candidate_id": candidate.candidate_id,
                "classification_label": label.value,
                "statement": candidate.text,
            }
        )
