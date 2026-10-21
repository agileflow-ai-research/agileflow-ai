"""Read-only validation boundary from authoritative N2 output into N3."""

from enum import StrEnum

from app.modules.agents.requirements.discovery.contracts import (
    DiscoveryInputReference, ValidatedDiscoveryChunk, ValidatedDiscoveryInput,
)
from app.modules.agents.requirements.discovery.identity import (
    DISCOVERY_INPUT_CONTRACT_VERSION, discovery_input_identity,
)
from app.modules.agents.requirements.discovery.storage import DiscoveryStorage, DiscoveryStorageError
from app.modules.agents.requirements.processing.preparation.schemas import EvidencePreparationStatus
from app.modules.agents.requirements.workflow.contracts.n2 import RequirementN2Status
from app.modules.agents.requirements.workflow.orchestration.identity import chunk_source_identity, n2_chunk_set_digest
from app.modules.agents.requirements.workflow.projection import confirmation_is_current
from app.modules.agents.requirements.workflow.storage import RequirementWorkflowStorage, RequirementWorkflowStorageError


class DiscoveryInputErrorCode(StrEnum):
    WORKFLOW_UNAVAILABLE = "WORKFLOW_UNAVAILABLE"
    N2_EXECUTION_UNAVAILABLE = "N2_EXECUTION_UNAVAILABLE"
    N2_NOT_COMPLETE = "N2_NOT_COMPLETE"
    N1_CONFIRMATION_STALE = "N1_CONFIRMATION_STALE"
    N2_RESULT_INVALID = "N2_RESULT_INVALID"
    EVIDENCE_ARTIFACT_UNAVAILABLE = "EVIDENCE_ARTIFACT_UNAVAILABLE"
    EVIDENCE_ARTIFACT_INCOMPATIBLE = "EVIDENCE_ARTIFACT_INCOMPATIBLE"
    CHUNK_SET_DIGEST_MISMATCH = "CHUNK_SET_DIGEST_MISMATCH"


class DiscoveryInputError(RuntimeError):
    def __init__(self, code: DiscoveryInputErrorCode, message: str) -> None:
        self.code = code
        super().__init__(message)


class DiscoveryInputLoader:
    def __init__(self, workflows: RequirementWorkflowStorage, storage: DiscoveryStorage) -> None:
        self._workflows = workflows
        self._storage = storage

    def load(self, *, agent_project_id: str, owner_user_id: str) -> ValidatedDiscoveryInput:
        record = self._load_workflow(agent_project_id, owner_user_id)
        execution = next(
            (item for item in record.n2_executions if item.execution_id == record.current_n2_execution_id),
            None,
        )
        if execution is None:
            self._reject(DiscoveryInputErrorCode.N2_EXECUTION_UNAVAILABLE, "Current N2 execution is unavailable")
        if execution.status is not RequirementN2Status.COMPLETE:
            self._reject(DiscoveryInputErrorCode.N2_NOT_COMPLETE, "Current N2 execution is not complete")
        if not confirmation_is_current(record):
            self._reject(DiscoveryInputErrorCode.N1_CONFIRMATION_STALE, "N1 confirmation is stale")
        confirmation = record.n1_confirmation
        if (confirmation is None
            or execution.confirmed_source_set_digest != confirmation.source_set_digest
            or execution.confirmed_selection_digest != confirmation.selection_digest):
            self._reject(DiscoveryInputErrorCode.N1_CONFIRMATION_STALE, "N2 input confirmation is stale")
        if execution.chunk_set_digest is None or execution.result_summary is None:
            self._reject(DiscoveryInputErrorCode.N2_RESULT_INVALID, "N2 result summary is incomplete")
        expected_sources = len(execution.input_sources)
        if (execution.result_summary.source_count != expected_sources
            or execution.result_summary.completed_source_count != expected_sources
            or execution.result_summary.chunk_count <= 0):
            self._reject(DiscoveryInputErrorCode.N2_RESULT_INVALID, "N2 result summary is invalid")

        validated: list[ValidatedDiscoveryChunk] = []
        source_identities: list[dict[str, object]] = []
        for source in execution.input_sources:
            preparation, chunks = self._load_source(agent_project_id, source.source_id)
            compatible = (
                preparation.status is EvidencePreparationStatus.COMPLETED
                and preparation.agent_project_id == agent_project_id == chunks.agent_project_id
                and preparation.source_id == source.source_id == chunks.source_id
                and preparation.source_type is source.source_type is chunks.source_type
                and preparation.source_sha256 == source.sha256 == chunks.source_sha256
                and preparation.parent_result_fingerprint == chunks.parent_result_fingerprint
                and preparation.normalizer_version == chunks.normalizer_version
                and preparation.chunker == chunks.chunker
                and bool(chunks.chunks)
            )
            if not compatible:
                self._reject(DiscoveryInputErrorCode.EVIDENCE_ARTIFACT_INCOMPATIBLE, "Prepared evidence is incompatible")
            source_identities.append(chunk_source_identity(source, chunks))
            for chunk in chunks.chunks:
                validated.append(ValidatedDiscoveryChunk(
                    source_id=source.source_id, source_type=source.source_type,
                    source_sha256=source.sha256,
                    parent_result_fingerprint=chunks.parent_result_fingerprint,
                    normalizer_version=chunks.normalizer_version,
                    chunker_fingerprint=chunks.chunker.fingerprint, chunk=chunk,
                ))
        if len(validated) != execution.result_summary.chunk_count:
            self._reject(DiscoveryInputErrorCode.N2_RESULT_INVALID, "N2 chunk count is inconsistent")
        recomputed = n2_chunk_set_digest(execution.confirmed_source_set_digest, source_identities)
        if recomputed != execution.chunk_set_digest:
            self._reject(DiscoveryInputErrorCode.CHUNK_SET_DIGEST_MISMATCH, "N2 chunk identity does not match")
        reference = DiscoveryInputReference(
            n2_execution_id=execution.execution_id, n2_attempt=execution.attempt_number,
            chunk_set_digest=execution.chunk_set_digest,
            confirmed_source_set_digest=execution.confirmed_source_set_digest,
        )
        return ValidatedDiscoveryInput(
            contract_version=DISCOVERY_INPUT_CONTRACT_VERSION,
            agent_project_id=agent_project_id, reference=reference,
            chunks=tuple(validated),
            input_identity=discovery_input_identity(
                agent_project_id=agent_project_id, n2_execution_id=execution.execution_id,
                n2_attempt=execution.attempt_number, chunk_set_digest=execution.chunk_set_digest,
            ),
        )

    def _load_workflow(self, agent_project_id, owner_user_id):
        try:
            record = self._workflows.load(agent_project_id=agent_project_id, owner_user_id=owner_user_id)
        except RequirementWorkflowStorageError as exc:
            raise DiscoveryInputError(DiscoveryInputErrorCode.WORKFLOW_UNAVAILABLE, "Requirement workflow is unavailable") from exc
        if record is None:
            self._reject(DiscoveryInputErrorCode.WORKFLOW_UNAVAILABLE, "Requirement workflow is unavailable")
        return record

    def _load_source(self, agent_project_id, source_id):
        try:
            preparation = self._storage.load_preparation(agent_project_id, source_id)
            chunks = self._storage.load_chunks(agent_project_id, source_id)
        except DiscoveryStorageError as exc:
            raise DiscoveryInputError(DiscoveryInputErrorCode.EVIDENCE_ARTIFACT_UNAVAILABLE, "Prepared evidence is unavailable") from exc
        if preparation is None or chunks is None:
            self._reject(DiscoveryInputErrorCode.EVIDENCE_ARTIFACT_UNAVAILABLE, "Prepared evidence is unavailable")
        return preparation, chunks

    @staticmethod
    def _reject(code: DiscoveryInputErrorCode, message: str):
        raise DiscoveryInputError(code, message)
