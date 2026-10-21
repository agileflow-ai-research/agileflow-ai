from datetime import datetime, timezone

import pytest

from app.modules.agents.requirements.contracts.schemas import RequirementSourceType
from app.modules.agents.requirements.discovery.dependencies import build_discovery_input_loader
from app.modules.agents.requirements.discovery.input import DiscoveryInputError, DiscoveryInputErrorCode
from app.modules.agents.requirements.infrastructure.artifact_paths import RequirementArtifactKind
from app.modules.agents.requirements.infrastructure.artifact_store import JsonArtifactStore
from app.modules.agents.requirements.processing.preparation.schemas import (
    ChunkerConfiguration, EvidenceChunk, EvidenceChunkResult,
    EvidencePreparationRecord, EvidencePreparationStatus, NormalizedProvenanceSpan,
)
from app.modules.agents.requirements.workflow.contracts.n1 import RequirementN1Confirmation, RequirementOutputCode
from app.modules.agents.requirements.workflow.contracts.n2 import (
    RequirementN2Execution, RequirementN2ResultSummary, RequirementN2SourceProgress,
    RequirementN2SourceSnapshot, RequirementN2SourceStatus, RequirementN2Status,
)
from app.modules.agents.requirements.workflow.contracts.record import RequirementWorkflowRecord
from app.modules.agents.requirements.workflow.orchestration.identity import chunk_source_identity, n2_chunk_set_digest
from app.modules.agents.requirements.workflow.storage import RequirementWorkflowStorage


NOW = datetime(2026, 10, 20, tzinfo=timezone.utc)
CHUNKER = ChunkerConfiguration(chunker_version="1", target_chars=100, max_chars=200,
    overlap_sentences=1, sentence_segmenter="test", sentence_segmenter_version="1", fingerprint="c" * 64)


def build_context(tmp_path, *, status=RequirementN2Status.COMPLETE, source_type=RequirementSourceType.DOCUMENT):
    project, owner, source_id = "AGP-020", "USR-001", {RequirementSourceType.DOCUMENT:"DOC-001", RequirementSourceType.AUDIO:"AUD-001", RequirementSourceType.VIDEO:"VID-001"}[source_type]
    source = RequirementN2SourceSnapshot(source_id=source_id, source_type=source_type, sha256="a" * 64)
    provenance = NormalizedProvenanceSpan(normalized_start_offset=0, normalized_end_offset=5,
        parent_start_offset=0, parent_end_offset=5, page_numbers=[1] if source_type is RequirementSourceType.DOCUMENT else [])
    chunk = EvidenceChunk(chunk_id="CHK-0123456789ABCDEF", content="shall", normalized_start_offset=0,
        normalized_end_offset=5, provenance=[provenance])
    result = EvidenceChunkResult(source_id=source_id, agent_project_id=project, source_type=source_type,
        source_sha256=source.sha256, parent_result_fingerprint="b" * 64, normalizer_version="1",
        chunker=CHUNKER, chunks=[chunk], created_at=NOW)
    prep = EvidencePreparationRecord(source_id=source_id, agent_project_id=project, source_type=source_type,
        source_sha256=source.sha256, parent_result_fingerprint="b" * 64, normalizer_version="1",
        chunker=CHUNKER, status=EvidencePreparationStatus.COMPLETED, started_at=NOW, completed_at=NOW)
    source_digest, selection_digest = "d" * 64, "e" * 64
    digest = n2_chunk_set_digest(source_digest, [chunk_source_identity(source, result)])
    execution = RequirementN2Execution(node_version="1", execution_id="N2-AAAAAAAAAAAAAAAA-001",
        attempt_id="ATT-001", execution_key="f" * 64, attempt_number=1, status=status,
        confirmed_source_set_digest=source_digest, confirmed_selection_digest=selection_digest,
        input_sources=[source], source_progress=[RequirementN2SourceProgress(source_id=source_id,
            processing_status=RequirementN2SourceStatus.COMPLETE, preparation_status=RequirementN2SourceStatus.COMPLETE,
            chunk_count=1)], created_at=NOW, started_at=NOW,
        completed_at=NOW if status is RequirementN2Status.COMPLETE else None,
        result_summary=RequirementN2ResultSummary(source_count=1, completed_source_count=1, chunk_count=1),
        chunk_set_digest=digest)
    record = RequirementWorkflowRecord(schema_version="2", workflow_version="W2", agent_project_id=project,
        owner_user_id=owner, selected_outputs=[RequirementOutputCode.SRS], selection_revision=1,
        selection_digest=selection_digest, source_set_digest=source_digest,
        n1_confirmation=RequirementN1Confirmation(source_set_digest=source_digest,
            selection_digest=selection_digest, confirmed_at=NOW), n2_executions=[execution],
        current_n2_execution_id=execution.execution_id, created_at=NOW, updated_at=NOW)
    RequirementWorkflowStorage(tmp_path).save(record)
    artifacts = JsonArtifactStore(tmp_path)
    artifacts.save(agent_project_id=project, source_id=source_id, kind=RequirementArtifactKind.EVIDENCE_PREPARATION, value=prep)
    artifacts.save(agent_project_id=project, source_id=source_id, kind=RequirementArtifactKind.CHUNK_RESULT, value=result)
    return project, owner, record, execution, prep, result


def test_loads_complete_n2_deterministically_without_raw_upload(tmp_path):
    project, owner, *_ = build_context(tmp_path)
    loader = build_discovery_input_loader(tmp_path)
    first, second = loader.load(agent_project_id=project, owner_user_id=owner), loader.load(agent_project_id=project, owner_user_id=owner)
    assert first == second
    assert [item.chunk.chunk_id for item in first.chunks] == ["CHK-0123456789ABCDEF"]
    assert first.chunks[0].chunk.provenance[0].page_numbers == [1]
    assert not list(tmp_path.rglob("*.pdf")) and not list(tmp_path.rglob("*.mp4"))


@pytest.mark.parametrize("status", [RequirementN2Status.RUNNING, RequirementN2Status.FAILED, RequirementN2Status.BLOCKED])
def test_rejects_non_complete_current_n2(tmp_path, status):
    project, owner, *_ = build_context(tmp_path, status=status)
    with pytest.raises(DiscoveryInputError) as error:
        build_discovery_input_loader(tmp_path).load(agent_project_id=project, owner_user_id=owner)
    assert error.value.code is DiscoveryInputErrorCode.N2_NOT_COMPLETE


def test_rejects_stale_confirmation_and_old_execution(tmp_path):
    project, owner, record, execution, *_ = build_context(tmp_path)
    record.source_set_digest = "1" * 64
    RequirementWorkflowStorage(tmp_path).save(record)
    with pytest.raises(DiscoveryInputError) as error:
        build_discovery_input_loader(tmp_path).load(agent_project_id=project, owner_user_id=owner)
    assert error.value.code is DiscoveryInputErrorCode.N1_CONFIRMATION_STALE
    record.source_set_digest = "d" * 64
    record.current_n2_execution_id = "N2-BBBBBBBBBBBBBBBB-002"
    RequirementWorkflowStorage(tmp_path).save(record)
    with pytest.raises(DiscoveryInputError) as error:
        build_discovery_input_loader(tmp_path).load(agent_project_id=project, owner_user_id=owner)
    assert error.value.code is DiscoveryInputErrorCode.N2_EXECUTION_UNAVAILABLE


def test_rejects_missing_modified_empty_and_sha_mismatched_chunks(tmp_path):
    project, owner, record, execution, prep, result = build_context(tmp_path)
    paths = JsonArtifactStore(tmp_path)
    paths.remove(agent_project_id=project, source_id=result.source_id, kind=RequirementArtifactKind.CHUNK_RESULT)
    loader = build_discovery_input_loader(tmp_path)
    with pytest.raises(DiscoveryInputError) as error:
        loader.load(agent_project_id=project, owner_user_id=owner)
    assert error.value.code is DiscoveryInputErrorCode.EVIDENCE_ARTIFACT_UNAVAILABLE
    result.chunks[0].chunk_id = "CHK-FEDCBA9876543210"
    paths.save(agent_project_id=project, source_id=result.source_id, kind=RequirementArtifactKind.CHUNK_RESULT, value=result)
    with pytest.raises(DiscoveryInputError) as error:
        loader.load(agent_project_id=project, owner_user_id=owner)
    assert error.value.code is DiscoveryInputErrorCode.CHUNK_SET_DIGEST_MISMATCH
    result.source_sha256 = "9" * 64
    paths.save(agent_project_id=project, source_id=result.source_id, kind=RequirementArtifactKind.CHUNK_RESULT, value=result)
    with pytest.raises(DiscoveryInputError) as error:
        loader.load(agent_project_id=project, owner_user_id=owner)
    assert error.value.code is DiscoveryInputErrorCode.EVIDENCE_ARTIFACT_INCOMPATIBLE
