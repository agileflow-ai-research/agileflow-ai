"""Fail-closed adaptation of the authoritative current N3 result for N4."""

from enum import StrEnum

from app.modules.agents.requirements.discovery.contracts import (
    RequirementClassificationLabel,
    StructuredRequirementType,
)
from app.modules.agents.requirements.discovery.input import DiscoveryInputError
from app.modules.agents.requirements.discovery.storage import DiscoveryStorageError
from app.modules.agents.requirements.discovery.structuring import (
    RequirementStructuringError,
    RequirementStructuringService,
)
from app.modules.agents.requirements.infrastructure.digests import stable_json_sha256
from app.modules.agents.requirements.quality.contracts import (
    QualityRequirement,
    ValidatedQualityInput,
)
from app.modules.agents.requirements.quality.identity import (
    QUALITY_INPUT_CONTRACT_VERSION,
    quality_input_identity,
)
from app.modules.agents.requirements.workflow.contracts.n3 import RequirementN3Status
from app.modules.agents.requirements.workflow.orchestration.n3_identity import n3_execution_key
from app.modules.agents.requirements.workflow.storage import RequirementWorkflowStorageError


class QualityInputErrorCode(StrEnum):
    QUALITY_INPUT_UNAVAILABLE = "QUALITY_INPUT_UNAVAILABLE"
    QUALITY_N3_NOT_COMPLETE = "QUALITY_N3_NOT_COMPLETE"
    QUALITY_INPUT_STALE = "QUALITY_INPUT_STALE"
    QUALITY_ARTIFACT_UNAVAILABLE = "QUALITY_ARTIFACT_UNAVAILABLE"
    QUALITY_ARTIFACT_INVALID = "QUALITY_ARTIFACT_INVALID"
    QUALITY_ARTIFACT_DIGEST_MISMATCH = "QUALITY_ARTIFACT_DIGEST_MISMATCH"
    QUALITY_TRACEABILITY_INVALID = "QUALITY_TRACEABILITY_INVALID"
    QUALITY_INPUT_IDENTITY_INVALID = "QUALITY_INPUT_IDENTITY_INVALID"


class QualityInputError(RuntimeError):
    def __init__(self, code: QualityInputErrorCode, message: str) -> None:
        self.code = code
        super().__init__(message)


class QualityInputLoader:
    def __init__(self, workflows, discovery_inputs, discovery_storage) -> None:
        self._workflows = workflows
        self._discovery_inputs = discovery_inputs
        self._artifacts = discovery_storage

    def load(self, *, agent_project_id: str, owner_user_id: str) -> ValidatedQualityInput:
        record = self._load_workflow(agent_project_id, owner_user_id)
        execution = next(
            (item for item in record.n3_executions
             if item.execution_id == record.current_n3_execution_id), None,
        )
        if execution is None:
            self._reject(QualityInputErrorCode.QUALITY_INPUT_UNAVAILABLE,
                         "Current N3 execution is unavailable")
        if execution.status is not RequirementN3Status.COMPLETE:
            self._reject(QualityInputErrorCode.QUALITY_N3_NOT_COMPLETE,
                         "Current N3 execution is not complete")
        if execution.result_summary is None:
            self._reject(QualityInputErrorCode.QUALITY_ARTIFACT_INVALID,
                         "N3 result summary is unavailable")

        upstream = self._revalidate_upstream(agent_project_id, owner_user_id)
        if (upstream.reference.n2_execution_id != execution.n2_execution_id
                or upstream.reference.chunk_set_digest != execution.chunk_set_digest
                or upstream.input_identity != execution.discovery_input_identity):
            self._reject(QualityInputErrorCode.QUALITY_INPUT_STALE,
                         "N3 input no longer matches authoritative upstream evidence")
        # Re-read after upstream validation so a concurrently moved N3 pointer fails closed.
        current = self._load_workflow(agent_project_id, owner_user_id)
        if current.current_n3_execution_id != execution.execution_id:
            self._reject(QualityInputErrorCode.QUALITY_INPUT_STALE,
                         "Current N3 execution changed during validation")

        candidates, classifications, structured = self._load_artifacts(
            agent_project_id, execution.execution_id
        )
        summary = execution.result_summary
        digests = tuple(stable_json_sha256(value.model_dump(mode="json")) for value in (
            candidates, classifications, structured,
        ))
        expected = (summary.candidate_artifact_digest,
                    summary.classification_artifact_digest,
                    summary.structured_artifact_digest)
        if digests != expected:
            self._reject(QualityInputErrorCode.QUALITY_ARTIFACT_DIGEST_MISMATCH,
                         "Persisted N3 artifact digest does not match its result summary")

        self._validate_context(agent_project_id, execution, candidates,
                               classifications, structured)
        requirements = self._validate_traceability(
            execution, upstream, candidates, classifications, structured
        )
        identity = quality_input_identity(
            agent_project_id=agent_project_id,
            n3_execution_id=execution.execution_id,
            n3_attempt=execution.attempt_number,
            discovery_input_identity=execution.discovery_input_identity,
            chunk_set_digest=execution.chunk_set_digest,
            candidate_artifact_digest=digests[0],
            classification_artifact_digest=digests[1],
            structured_artifact_digest=digests[2],
            structured_set_identity=structured.structured_set_identity,
            classifier_configuration_fingerprint=execution.classifier_configuration_fingerprint,
            ordered_requirement_ids=tuple(item.requirement_id for item in requirements),
        )
        return ValidatedQualityInput(
            contract_version=QUALITY_INPUT_CONTRACT_VERSION,
            agent_project_id=agent_project_id,
            n3_execution_id=execution.execution_id,
            n3_attempt=execution.attempt_number,
            n2_execution_id=execution.n2_execution_id,
            discovery_input_identity=execution.discovery_input_identity,
            chunk_set_digest=execution.chunk_set_digest,
            candidate_artifact_digest=digests[0],
            classification_artifact_digest=digests[1],
            structured_artifact_digest=digests[2],
            structured_set_identity=structured.structured_set_identity,
            classifier_configuration_fingerprint=execution.classifier_configuration_fingerprint,
            requirements=requirements,
            input_identity=identity,
        )

    def _load_workflow(self, project, owner):
        try:
            record = self._workflows.load(agent_project_id=project, owner_user_id=owner)
        except RequirementWorkflowStorageError as exc:
            raise QualityInputError(QualityInputErrorCode.QUALITY_INPUT_UNAVAILABLE,
                                    "Requirement workflow is unavailable") from exc
        if record is None:
            self._reject(QualityInputErrorCode.QUALITY_INPUT_UNAVAILABLE,
                         "Requirement workflow is unavailable")
        return record

    def _revalidate_upstream(self, project, owner):
        try:
            return self._discovery_inputs.load(agent_project_id=project,
                                               owner_user_id=owner)
        except DiscoveryInputError as exc:
            raise QualityInputError(QualityInputErrorCode.QUALITY_INPUT_STALE,
                                    "Authoritative upstream evidence is no longer valid") from exc

    def _load_artifacts(self, project, execution_id):
        try:
            return (
                self._artifacts.load_candidates(project, execution_id),
                self._artifacts.load_classifications(project, execution_id),
                self._artifacts.load_structured_requirements(project, execution_id),
            )
        except DiscoveryStorageError as exc:
            raise QualityInputError(QualityInputErrorCode.QUALITY_ARTIFACT_UNAVAILABLE,
                                    "A persisted N3 artifact is unavailable or invalid") from exc

    def _validate_context(self, project, execution, candidates, classifications, structured):
        summary = execution.result_summary
        expected_execution_key = n3_execution_key(
            agent_project_id=project,
            n2_execution_id=execution.n2_execution_id,
            chunk_set_digest=execution.chunk_set_digest,
            discovery_input_identity=execution.discovery_input_identity,
            candidate_detector_fingerprint=execution.candidate_detector_fingerprint,
            classifier_configuration_fingerprint=execution.classifier_configuration_fingerprint,
            structuring_contract_version=execution.structuring_contract_version,
        )
        compatible = (
            execution.execution_key == expected_execution_key
            and
            candidates.agent_project_id == project == structured.agent_project_id
            and candidates.n2_execution_id == execution.n2_execution_id
            and candidates.chunk_set_digest == execution.chunk_set_digest == structured.chunk_set_digest
            and candidates.discovery_input_identity == execution.discovery_input_identity == structured.discovery_input_identity
            and classifications.candidate_set == candidates
            and classifications.model.configuration_fingerprint == execution.classifier_configuration_fingerprint
            and structured.classifier_configuration_fingerprint == execution.classifier_configuration_fingerprint
            and summary.structured_set_identity == structured.structured_set_identity
            and summary.classifier_configuration_fingerprint == execution.classifier_configuration_fingerprint
            and summary.candidate_count == len(candidates.candidates)
            and summary.functional_requirement_count == len(structured.functional_requirements)
            and summary.non_functional_requirement_count == len(structured.non_functional_requirements)
            and summary.excluded_candidate_count == len(structured.excluded_candidates)
        )
        if not compatible:
            self._reject(QualityInputErrorCode.QUALITY_INPUT_IDENTITY_INVALID,
                         "N3 artifact identity is inconsistent with its execution")
        try:
            expected = RequirementStructuringService().structure(classifications)
        except RequirementStructuringError as exc:
            raise QualityInputError(QualityInputErrorCode.QUALITY_ARTIFACT_INVALID,
                                    "N3 artifacts are internally invalid") from exc
        if expected.structured_set_identity != structured.structured_set_identity:
            self._reject(QualityInputErrorCode.QUALITY_INPUT_IDENTITY_INVALID,
                         "Structured requirement set identity is invalid")

    def _validate_traceability(self, execution, upstream, candidates,
                               classifications, structured):
        classification_by_id = {item.candidate_id: item for item in classifications.classifications}
        if len(classification_by_id) != len(classifications.classifications):
            self._traceability_reject()
        promoted = {
            item.candidate_id: item
            for item in (*structured.functional_requirements,
                         *structured.non_functional_requirements)
        }
        if len(promoted) != (len(structured.functional_requirements)
                             + len(structured.non_functional_requirements)):
            self._traceability_reject()
        chunks = {item.chunk.chunk_id: item for item in upstream.chunks}
        ordered: list[QualityRequirement] = []
        for candidate in candidates.candidates:
            requirement = promoted.get(candidate.candidate_id)
            if requirement is None:
                continue
            classification = classification_by_id.get(candidate.candidate_id)
            chunk = chunks.get(candidate.chunk_id)
            expected_label = (RequirementClassificationLabel.FUNCTIONAL
                              if requirement.requirement_type is StructuredRequirementType.FUNCTIONAL
                              else RequirementClassificationLabel.NON_FUNCTIONAL)
            if (classification is None or classification.label is not expected_label
                    or classification.candidate_identity != candidate.candidate_identity
                    or requirement.statement != candidate.text
                    or requirement.candidate_identity != candidate.candidate_identity
                    or requirement.chunk_id != candidate.chunk_id
                    or requirement.source_id != candidate.source_id
                    or requirement.source_type is not candidate.source_type
                    or requirement.start_offset != candidate.start_offset
                    or requirement.end_offset != candidate.end_offset
                    or requirement.provenance != candidate.provenance
                    or requirement.classification_confidence != classification.confidence
                    or requirement.classifier_configuration_fingerprint
                       != execution.classifier_configuration_fingerprint
                    or chunk is None or chunk.source_id != candidate.source_id
                    or chunk.source_type is not candidate.source_type
                    or candidate.provenance != tuple(chunk.chunk.provenance)):
                self._traceability_reject()
            ordered.append(QualityRequirement(
                requirement_id=requirement.requirement_id,
                requirement_type=requirement.requirement_type,
                statement=requirement.statement,
                candidate_id=requirement.candidate_id,
                candidate_identity=requirement.candidate_identity,
                chunk_id=requirement.chunk_id,
                source_id=requirement.source_id,
                source_type=requirement.source_type,
                start_offset=requirement.start_offset,
                end_offset=requirement.end_offset,
                provenance=requirement.provenance,
                classification_confidence=requirement.classification_confidence,
                classifier_configuration_fingerprint=requirement.classifier_configuration_fingerprint,
            ))
        if len(ordered) != len(promoted):
            self._traceability_reject()
        return tuple(ordered)

    @staticmethod
    def _traceability_reject():
        raise QualityInputError(QualityInputErrorCode.QUALITY_TRACEABILITY_INVALID,
                                "N3 requirement traceability is invalid")

    @staticmethod
    def _reject(code, message):
        raise QualityInputError(code, message)
