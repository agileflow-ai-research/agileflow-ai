from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from app.modules.agents.requirements.contracts.schemas import RequirementSourceType
from app.modules.agents.requirements.workflow.contracts.n1 import (
    RequirementN1Confirmation,
    RequirementOutputCode,
)
from app.modules.agents.requirements.workflow.contracts.n2 import (
    RequirementN2Error,
    RequirementN2SourceStatus,
    RequirementN2Status,
)
from app.modules.agents.requirements.workflow.contracts.record import (
    RequirementWorkflowRecord,
)
from app.modules.agents.requirements.workflow.orchestration.identity import (
    build_queued_execution,
    n2_chunk_set_digest,
    n2_execution_key,
    snapshot_sources,
)
from app.modules.agents.requirements.workflow.orchestration.n2_runner import (
    RequirementN2Runner,
)
from app.modules.agents.requirements.workflow.orchestration.transitions import (
    fail_source,
    mark_blocked,
    mark_complete,
    mark_failed,
    mark_interrupted,
    mark_running,
    update_source_progress,
)
from app.modules.agents.requirements.workflow.service import source_set_digest
from app.modules.agents.requirements.workflow.storage import RequirementWorkflowStorage


NOW = datetime(2026, 10, 20, 12, 30, tzinfo=timezone.utc)
LATER = NOW + timedelta(seconds=1)


def source(source_id: str, source_type: RequirementSourceType, digest: str):
    return SimpleNamespace(source_id=source_id, source_type=source_type, sha256=digest)


def queued_record(sources=None):
    sources = sources or [source("DOC-001", RequirementSourceType.DOCUMENT, "d" * 64)]
    source_digest = source_set_digest(sources)
    selection_digest = "b" * 64
    key = n2_execution_key("AGP-020", source_digest, selection_digest)
    execution = build_queued_execution(
        key=key,
        confirmed_source_set_digest=source_digest,
        confirmed_selection_digest=selection_digest,
        sources=sources,
        attempt_number=1,
        created_at=NOW,
    )
    record = RequirementWorkflowRecord(
        schema_version="2",
        workflow_version="W2",
        agent_project_id="AGP-020",
        owner_user_id="USR-001",
        selected_outputs=[RequirementOutputCode.SRS],
        selection_revision=1,
        selection_digest=selection_digest,
        source_set_digest=source_digest,
        n1_confirmation=RequirementN1Confirmation(
            source_set_digest=source_digest,
            selection_digest=selection_digest,
            confirmed_at=NOW,
        ),
        n2_executions=[execution],
        current_n2_execution_id=execution.execution_id,
        created_at=NOW,
        updated_at=NOW,
    )
    return record, execution


def test_identity_module_preserves_fixed_hashes_and_attempt_identity():
    assert n2_execution_key("AGP-020", "a" * 64, "b" * 64) == (
        "145b2d2a493922b50143ed867cbbd7ec00836bd42b2f5b61d4434fd3364cfe2c"
    )
    chunks = [
        {
            "source_id": "DOC-002",
            "chunk_count": 2,
            "chunk_set_digest": "d" * 64,
        },
        {
            "source_id": "AUD-001",
            "chunk_count": 7,
            "chunk_set_digest": "c" * 64,
        },
    ]
    assert n2_chunk_set_digest("a" * 64, chunks) == (
        "321f1959cc83c331b0c26802fc43dad5c454a428fd4f588f2446ea1c43820bdf"
    )
    sources = [
        source("VID-002", RequirementSourceType.VIDEO, "2" * 64),
        source("AUD-001", RequirementSourceType.AUDIO, "1" * 64),
    ]
    execution = build_queued_execution(
        key="f" * 64,
        confirmed_source_set_digest="a" * 64,
        confirmed_selection_digest="b" * 64,
        sources=sources,
        attempt_number=2,
        created_at=NOW,
    )

    assert execution.execution_id == "N2-FFFFFFFFFFFFFFFF-002"
    assert execution.attempt_id == "ATT-002"
    assert [item.source_id for item in execution.input_sources] == ["AUD-001", "VID-002"]
    assert snapshot_sources(sources) == execution.input_sources


def test_transitions_cover_running_progress_and_complete():
    record, execution = queued_record()

    mark_running(record, execution, started_at=NOW, updated_at=LATER)
    update_source_progress(
        record,
        execution,
        "DOC-001",
        processing_status=RequirementN2SourceStatus.COMPLETE,
        preparation_status=RequirementN2SourceStatus.COMPLETE,
        chunk_count=3,
        updated_at=LATER,
    )
    mark_complete(
        record,
        execution,
        chunk_count=3,
        chunk_set_digest="e" * 64,
        completed_at=LATER,
        updated_at=LATER,
    )

    assert execution.status is RequirementN2Status.COMPLETE
    assert execution.started_at == NOW
    assert execution.completed_at == LATER
    assert execution.retryable is False
    assert execution.source_progress[0].chunk_count == 3
    assert execution.result_summary is not None
    assert execution.result_summary.chunk_count == 3
    assert execution.chunk_set_digest == "e" * 64


def test_transitions_cover_failed_source_and_general_failure():
    record, execution = queued_record()
    error = RequirementN2Error(
        code="SOURCE_PROCESSING_FAILED",
        message="A confirmed source could not be processed.",
        affected_source_ids=["DOC-001"],
    )

    fail_source(
        record,
        execution,
        "DOC-001",
        error,
        processing=True,
        failed_at=NOW,
        updated_at=LATER,
    )

    assert execution.status is RequirementN2Status.FAILED
    assert execution.source_progress[0].processing_status is RequirementN2SourceStatus.FAILED
    assert execution.source_progress[0].error == error
    assert execution.retryable is True

    other_record, other_execution = queued_record()
    general = RequirementN2Error(code="N2_EXECUTION_FAILED", message="Safe failure")
    mark_failed(
        other_record,
        other_execution,
        general,
        failed_at=NOW,
        updated_at=LATER,
    )
    assert other_execution.error == general
    assert other_execution.result_summary is not None


def test_transitions_cover_stale_and_interrupted_execution():
    stale_record, stale = queued_record()
    mark_blocked(stale_record, stale, failed_at=NOW, updated_at=LATER)
    assert stale.status is RequirementN2Status.BLOCKED
    assert stale.retryable is False
    assert stale.error is not None
    assert stale.error.code == "N2_INPUT_STALE"

    interrupted_record, interrupted = queued_record()
    mark_interrupted(
        interrupted_record,
        interrupted,
        failed_at=NOW,
        updated_at=LATER,
    )
    assert interrupted.status is RequirementN2Status.FAILED
    assert interrupted.retryable is True
    assert interrupted.error is not None
    assert interrupted.error.code == "N2_EXECUTION_INTERRUPTED"
    assert interrupted.result_summary is None


class FakeSourceStorage:
    def __init__(self, sources):
        self.sources = sources

    def list_for_project(self, **_kwargs):
        return list(self.sources)


class FakeProcessingService:
    def __init__(self, *, status="COMPLETED", raises=False):
        self.status = status
        self.raises = raises
        self.calls = []

    def process(self, project_id, source_id, current_user, *, force=False):
        self.calls.append(source_id)
        if self.raises:
            raise RuntimeError("provider details")
        return SimpleNamespace(status=SimpleNamespace(value=self.status))


class FakePreparationService:
    def __init__(self, *, status="COMPLETED", empty=False, raises=False):
        self.status = status
        self.empty = empty
        self.raises = raises
        self.prepare_calls = []
        self.chunk_calls = []

    def prepare(self, project_id, source_id, current_user, *, force=False):
        self.prepare_calls.append(source_id)
        return SimpleNamespace(status=SimpleNamespace(value=self.status))

    def get_chunks(self, project_id, source_id, current_user):
        self.chunk_calls.append(source_id)
        if self.raises:
            raise RuntimeError("storage details")
        chunks = [] if self.empty else [SimpleNamespace(chunk_id=f"CHK-{source_id}-001")]
        return SimpleNamespace(
            chunks=chunks,
            parent_result_fingerprint=f"parent-{source_id}",
            normalizer_version="1",
            chunker=SimpleNamespace(fingerprint=f"chunker-{source_id}"),
        )


def runner_context(tmp_path, sources, *, processing=None, preparation=None):
    storage = RequirementWorkflowStorage(tmp_path)
    record, execution = queued_record(sources)
    storage.save(record)
    processing = processing or FakeProcessingService()
    preparation = preparation or FakePreparationService()
    runner = RequirementN2Runner(
        FakeSourceStorage(sources),
        storage,
        processing,
        preparation,
        clock=lambda: LATER,
    )
    return runner, storage, execution, processing, preparation


def load_execution(storage):
    record = storage.load(agent_project_id="AGP-020", owner_user_id="USR-001")
    assert record is not None
    return record.n2_executions[0]


def test_runner_processes_mixed_sources_in_deterministic_order(tmp_path):
    sources = [
        source("VID-001", RequirementSourceType.VIDEO, "3" * 64),
        source("DOC-001", RequirementSourceType.DOCUMENT, "1" * 64),
        source("AUD-001", RequirementSourceType.AUDIO, "2" * 64),
    ]
    runner, storage, execution, processing, preparation = runner_context(tmp_path, sources)

    runner.run("AGP-020", "USR-001", execution.execution_id, SimpleNamespace())

    completed = load_execution(storage)
    expected_order = ["AUD-001", "DOC-001", "VID-001"]
    assert processing.calls == expected_order
    assert preparation.prepare_calls == expected_order
    assert preparation.chunk_calls == expected_order
    assert completed.status is RequirementN2Status.COMPLETE
    assert completed.result_summary is not None
    assert completed.result_summary.chunk_count == 3
    assert completed.chunk_set_digest == n2_chunk_set_digest(
        completed.confirmed_source_set_digest,
        [
            {
                "source_id": source_id,
                "source_sha256": next(
                    item.sha256 for item in completed.input_sources if item.source_id == source_id
                ),
                "parent_result_fingerprint": f"parent-{source_id}",
                "normalizer_version": "1",
                "chunker_fingerprint": f"chunker-{source_id}",
                "chunk_ids": [f"CHK-{source_id}-001"],
            }
            for source_id in expected_order
        ],
    )


@pytest.mark.parametrize(
    ("processing", "preparation", "expected_code"),
    [
        (FakeProcessingService(status="FAILED"), FakePreparationService(), "SOURCE_PROCESSING_FAILED"),
        (FakeProcessingService(), FakePreparationService(status="FAILED"), "EVIDENCE_PREPARATION_FAILED"),
        (FakeProcessingService(), FakePreparationService(empty=True), "N2_RESULT_INVALID"),
        (FakeProcessingService(), FakePreparationService(raises=True), "N2_RESULT_INVALID"),
        (FakeProcessingService(raises=True), FakePreparationService(), "N2_EXECUTION_FAILED"),
    ],
)
def test_runner_preserves_safe_failure_mapping(
    tmp_path, processing, preparation, expected_code
):
    sources = [source("DOC-001", RequirementSourceType.DOCUMENT, "d" * 64)]
    runner, storage, execution, _, _ = runner_context(
        tmp_path,
        sources,
        processing=processing,
        preparation=preparation,
    )

    runner.run("AGP-020", "USR-001", execution.execution_id, SimpleNamespace())

    failed = load_execution(storage)
    assert failed.status is RequirementN2Status.FAILED
    assert failed.error is not None
    assert failed.error.code == expected_code
    assert "details" not in failed.error.message


def test_runner_blocks_stale_source_snapshot(tmp_path):
    confirmed = [source("DOC-001", RequirementSourceType.DOCUMENT, "d" * 64)]
    runner, storage, execution, _, _ = runner_context(tmp_path, confirmed)
    runner._sources.sources = [
        source("DOC-001", RequirementSourceType.DOCUMENT, "e" * 64)
    ]

    runner.run("AGP-020", "USR-001", execution.execution_id, SimpleNamespace())

    blocked = load_execution(storage)
    assert blocked.status is RequirementN2Status.BLOCKED
    assert blocked.error is not None
    assert blocked.error.code == "N2_INPUT_STALE"
