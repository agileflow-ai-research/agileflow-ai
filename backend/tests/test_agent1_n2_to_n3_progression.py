from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from threading import Lock
from types import SimpleNamespace

import pytest

from app.modules.agents.requirements.contracts.schemas import RequirementSourceType
from app.modules.agents.requirements.workflow.contracts.n1 import (
    RequirementN1Confirmation,
    RequirementOutputCode,
)
from app.modules.agents.requirements.workflow.contracts.n2 import RequirementN2Status
from app.modules.agents.requirements.workflow.contracts.n3 import (
    RequirementN3Execution,
    RequirementN3Status,
)
from app.modules.agents.requirements.workflow.contracts.record import (
    RequirementWorkflowRecord,
)
from app.modules.agents.requirements.workflow.orchestration.identity import (
    build_queued_execution,
    n2_execution_key,
)
from app.modules.agents.requirements.workflow.orchestration.progression import (
    RequirementProgressionError,
    WorkflowProgressionCoordinator,
)
from app.modules.agents.requirements.workflow.orchestration.transitions import mark_complete
from app.modules.agents.requirements.workflow.service import source_set_digest
from app.modules.agents.requirements.workflow.storage import RequirementWorkflowStorage


NOW = datetime(2026, 10, 21, tzinfo=timezone.utc)


class IdempotentN3:
    def __init__(self, *, failure=False):
        self.failure = failure
        self.calls = 0
        self.logical_ids = set()
        self.lock = Lock()

    def start(self, project, owner):
        with self.lock:
            self.calls += 1
            if self.failure:
                raise RuntimeError("private provider detail")
            self.logical_ids.add((project, owner))


def complete_record():
    source = SimpleNamespace(
        source_id="DOC-001",
        source_type=RequirementSourceType.DOCUMENT,
        sha256="a" * 64,
    )
    source_digest = source_set_digest([source])
    selection_digest = "b" * 64
    execution = build_queued_execution(
        key=n2_execution_key("AGP-020", source_digest, selection_digest),
        confirmed_source_set_digest=source_digest,
        confirmed_selection_digest=selection_digest,
        sources=[source],
        attempt_number=1,
        created_at=NOW,
    )
    record = RequirementWorkflowRecord(
        schema_version="3",
        workflow_version="W3",
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
    mark_complete(
        record,
        execution,
        chunk_count=2,
        chunk_set_digest="c" * 64,
        completed_at=NOW,
        updated_at=NOW,
    )
    return record, execution


def coordinator(tmp_path, record, service=None):
    storage = RequirementWorkflowStorage(tmp_path)
    storage.save(record)
    n3 = service or IdempotentN3()
    return WorkflowProgressionCoordinator(storage, n3), n3


def test_complete_current_n2_advances_and_repeated_calls_are_logically_idempotent(tmp_path):
    record, execution = complete_record()
    progression, n3 = coordinator(tmp_path, record)

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(
            pool.map(
                lambda _: progression.advance_after_n2_complete(
                    record.agent_project_id, record.owner_user_id, execution.execution_id
                ),
                range(16),
            )
        )

    assert all(results)
    assert n3.logical_ids == {(record.agent_project_id, record.owner_user_id)}


@pytest.mark.parametrize(
    "invalid",
    ["queued", "missing_summary", "missing_digest", "stale_n1", "superseded"],
)
def test_progression_rejects_non_authoritative_or_incomplete_n2(tmp_path, invalid):
    record, execution = complete_record()
    if invalid == "queued":
        execution.status = RequirementN2Status.QUEUED
    elif invalid == "missing_summary":
        execution.result_summary = None
    elif invalid == "missing_digest":
        execution.chunk_set_digest = None
    elif invalid == "stale_n1":
        record.selection_digest = "d" * 64
    else:
        record.current_n2_execution_id = "N2-FFFFFFFFFFFFFFFF-999"
    progression, n3 = coordinator(tmp_path, record)

    assert progression.advance_after_n2_complete(
        record.agent_project_id, record.owner_user_id, execution.execution_id
    ) is False
    assert n3.calls == 0


@pytest.mark.parametrize("status", [RequirementN3Status.FAILED, RequirementN3Status.BLOCKED])
def test_failed_or_blocked_n3_is_not_automatically_retried(tmp_path, status):
    record, execution = complete_record()
    n3_execution = RequirementN3Execution(
        node_version="1",
        execution_id="N3-1111111111111111-001",
        attempt_id="ATT-001",
        execution_key="1" * 64,
        attempt_number=1,
        status=status,
        n2_execution_id=execution.execution_id,
        chunk_set_digest=execution.chunk_set_digest,
        discovery_input_identity="2" * 64,
        candidate_detector_fingerprint="3" * 64,
        classifier_configuration_fingerprint="4" * 64,
        structuring_contract_version="1",
        created_at=NOW,
        failed_at=NOW,
    )
    record.n3_executions = [n3_execution]
    record.current_n3_execution_id = n3_execution.execution_id
    progression, n3 = coordinator(tmp_path, record)

    assert progression.advance_after_n2_complete(
        record.agent_project_id, record.owner_user_id, execution.execution_id
    ) is False
    assert n3.calls == 0


def test_n3_start_failure_is_safe_and_leaves_n2_complete(tmp_path):
    record, execution = complete_record()
    progression, _ = coordinator(tmp_path, record, IdempotentN3(failure=True))

    with pytest.raises(RequirementProgressionError) as error:
        progression.advance_after_n2_complete(
            record.agent_project_id, record.owner_user_id, execution.execution_id
        )

    assert str(error.value) == "Automatic requirement discovery could not be started."
    persisted = progression._states.load(
        agent_project_id=record.agent_project_id, owner_user_id=record.owner_user_id
    )
    assert persisted.n2_executions[0].status is RequirementN2Status.COMPLETE
