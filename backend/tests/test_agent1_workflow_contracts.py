import json
from copy import deepcopy

import pytest

from app.modules.agents.requirements.workflow.contracts.n1 import (
    RequirementN1State,
    RequirementOutputCode,
)
from app.modules.agents.requirements.workflow.contracts.n2 import (
    RequirementN2SourceStatus,
    RequirementN2Status,
)
from app.modules.agents.requirements.workflow.contracts.record import (
    RequirementWorkflowRecord,
)
from app.modules.agents.requirements.workflow.projection import (
    build_workflow_response,
    confirmation_is_current,
)
from app.modules.agents.requirements.workflow.storage import RequirementWorkflowStorage


NOW = "2026-10-20T12:30:00Z"


def execution_payload(status: str, attempt: int) -> dict[str, object]:
    terminal = status in {"COMPLETE", "FAILED", "BLOCKED"}
    return {
        "node_id": "PROCESSING_AND_CHUNKING",
        "node_version": "1",
        "execution_id": f"N2-ABCDEF012345678{attempt}-{attempt:03d}",
        "attempt_id": f"ATT-{attempt:03d}",
        "execution_key": "c" * 64,
        "attempt_number": attempt,
        "status": status,
        "confirmed_source_set_digest": "a" * 64,
        "confirmed_selection_digest": "b" * 64,
        "input_sources": [
            {
                "source_id": "AUD-001",
                "source_type": "AUDIO",
                "sha256": "d" * 64,
            }
        ],
        "source_progress": [
            {
                "source_id": "AUD-001",
                "processing_status": "COMPLETE",
                "preparation_status": "COMPLETE",
                "chunk_count": 7,
                "error": None,
            }
        ],
        "created_at": NOW,
        "started_at": NOW if status != "QUEUED" else None,
        "completed_at": NOW if status == "COMPLETE" else None,
        "failed_at": NOW if status in {"FAILED", "BLOCKED"} else None,
        "error": (
            {
                "code": "N2_TEST_FAILURE",
                "message": "Fixed compatibility failure",
                "affected_source_ids": ["AUD-001"],
            }
            if status in {"FAILED", "BLOCKED"}
            else None
        ),
        "retryable": status in {"FAILED", "BLOCKED"},
        "result_summary": (
            {"source_count": 1, "completed_source_count": 1, "chunk_count": 7}
            if status == "COMPLETE"
            else None
        ),
        "chunk_set_digest": "e" * 64 if status == "COMPLETE" else None,
    }


def record_payload(
    *,
    executions: list[dict[str, object]] | None = None,
    current_execution_id: str | None = None,
) -> dict[str, object]:
    return {
        "schema_version": "2",
        "workflow_version": "W2",
        "agent_project_id": "AGP-020",
        "owner_user_id": "USR-001",
        "selected_outputs": ["SRS"],
        "selection_revision": 1,
        "selection_digest": "b" * 64,
        "source_set_digest": "a" * 64,
        "n1_confirmation": {
            "source_set_digest": "a" * 64,
            "selection_digest": "b" * 64,
            "confirmed_at": NOW,
        },
        "n2_executions": executions or [],
        "current_n2_execution_id": current_execution_id,
        "created_at": NOW,
        "updated_at": NOW,
    }


def test_pre_r2_persisted_record_parses_and_dumps_with_identical_shape():
    failed = execution_payload("FAILED", 1)
    complete = execution_payload("COMPLETE", 2)
    payload = record_payload(
        executions=[failed, complete],
        current_execution_id=str(complete["execution_id"]),
    )

    record = RequirementWorkflowRecord.model_validate(payload)

    assert record.model_dump(mode="json") == payload


def test_existing_w1_and_w2_history_load_without_migration(tmp_path):
    failed = execution_payload("FAILED", 1)
    blocked = execution_payload("BLOCKED", 2)
    payload = record_payload(
        executions=[failed, blocked],
        current_execution_id=str(blocked["execution_id"]),
    )
    path = tmp_path / "AGP-020" / "workflow.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")

    loaded = RequirementWorkflowStorage(tmp_path).load(
        agent_project_id="AGP-020", owner_user_id="USR-001"
    )

    assert loaded is not None
    assert loaded.model_dump(mode="json") == payload
    assert loaded.current_n2_execution_id == blocked["execution_id"]
    assert [item.attempt_number for item in loaded.n2_executions] == [1, 2]

    w1_payload = record_payload()
    w1_payload.update(
        {
            "schema_version": "1",
            "workflow_version": "W1",
            "n1_confirmation": {
                "source_set_digest": "f" * 64,
                "selection_digest": "b" * 64,
                "confirmed_at": NOW,
            },
        }
    )
    w1_path = tmp_path / "AGP-021" / "workflow.json"
    w1_path.parent.mkdir(parents=True)
    w1_payload["agent_project_id"] = "AGP-021"
    w1_path.write_text(json.dumps(w1_payload), encoding="utf-8")
    w1 = RequirementWorkflowStorage(tmp_path).load(
        agent_project_id="AGP-021", owner_user_id="USR-001"
    )
    assert w1 is not None
    assert w1.model_dump(mode="json") == w1_payload
    assert confirmation_is_current(w1) is False


def test_enum_values_remain_exactly_compatible():
    assert [item.value for item in RequirementOutputCode] == [
        "FUNCTIONAL_REQUIREMENTS",
        "NON_FUNCTIONAL_REQUIREMENTS",
        "USER_STORIES",
        "ACCEPTANCE_CRITERIA",
        "PERSONAS",
        "SRS",
    ]
    assert [item.value for item in RequirementN1State] == [
        "NOT_STARTED",
        "WAITING_FOR_HUMAN",
        "COMPLETE",
    ]
    assert [item.value for item in RequirementN2Status] == [
        "QUEUED",
        "RUNNING",
        "COMPLETE",
        "FAILED",
        "BLOCKED",
    ]
    assert [item.value for item in RequirementN2SourceStatus] == [
        "READY",
        "RUNNING",
        "COMPLETE",
        "FAILED",
    ]


def test_projection_without_n2_preserves_fixed_public_response_shape():
    payload = record_payload()
    record = RequirementWorkflowRecord.model_validate(payload)

    response = build_workflow_response(record, source_count=1)

    assert response.model_dump(mode="json") == {
        "schema_version": "2",
        "workflow_version": "W2",
        "agent_project_id": "AGP-020",
        "selected_outputs": ["SRS"],
        "selection_revision": 1,
        "selection_digest": "b" * 64,
        "source_set_digest": "a" * 64,
        "source_count": 1,
        "n1_state": "COMPLETE",
        "n1_confirmation_current": True,
        "confirmed_source_set_digest": "a" * 64,
        "confirmed_selection_digest": "b" * 64,
        "confirmed_at": NOW,
        "n2_execution": None,
        "n2_is_current": False,
        "n2_execution_count": 0,
        "created_at": NOW,
        "updated_at": NOW,
    }


@pytest.mark.parametrize(
    "status",
    ["QUEUED", "RUNNING", "COMPLETE", "FAILED", "BLOCKED"],
)
def test_projection_is_pure_for_each_n2_status(status):
    execution = execution_payload(status, 1)
    payload = record_payload(
        executions=[execution],
        current_execution_id=str(execution["execution_id"]),
    )
    record = RequirementWorkflowRecord.model_validate(payload)
    before = deepcopy(record.model_dump(mode="json"))

    response = build_workflow_response(record, source_count=1)

    assert response.n2_execution is not None
    assert response.n2_execution.status.value == status
    assert response.n2_is_current is True
    assert record.model_dump(mode="json") == before


def test_projection_selects_current_execution_from_history():
    first = execution_payload("FAILED", 1)
    second = execution_payload("BLOCKED", 2)
    record = RequirementWorkflowRecord.model_validate(
        record_payload(
            executions=[first, second],
            current_execution_id=str(first["execution_id"]),
        )
    )

    response = build_workflow_response(record, source_count=1)

    assert response.n2_execution is not None
    assert response.n2_execution.execution_id == first["execution_id"]
    assert response.n2_execution_count == 2


def test_projection_reports_not_started_and_stale_confirmation():
    no_sources = RequirementWorkflowRecord.model_validate(record_payload())
    assert build_workflow_response(no_sources, source_count=0).n1_state.value == "NOT_STARTED"

    stale_payload = record_payload()
    stale_payload["n1_confirmation"] = {
        "source_set_digest": "f" * 64,
        "selection_digest": "b" * 64,
        "confirmed_at": NOW,
    }
    stale = RequirementWorkflowRecord.model_validate(stale_payload)
    response = build_workflow_response(stale, source_count=1)

    assert response.n1_state.value == "WAITING_FOR_HUMAN"
    assert response.n1_confirmation_current is False
    assert response.n2_is_current is False


def test_pre_r2_schema_module_remains_an_identity_compatible_shim():
    from app.modules.agents.requirements.workflow.schemas import (
        RequirementN2Execution as LegacyExecution,
    )
    from app.modules.agents.requirements.workflow.schemas import (
        RequirementOutputCode as LegacyOutputCode,
    )
    from app.modules.agents.requirements.workflow.schemas import (
        RequirementWorkflowRecord as LegacyRecord,
    )

    from app.modules.agents.requirements.workflow.contracts.n2 import (
        RequirementN2Execution,
    )

    assert LegacyOutputCode is RequirementOutputCode
    assert LegacyExecution is RequirementN2Execution
    assert LegacyRecord is RequirementWorkflowRecord
