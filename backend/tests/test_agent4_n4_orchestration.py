from types import SimpleNamespace

import pytest

from app.modules.agents.testing_validation.context_testability.context_decision.constants import (
    ContextDecisionStatus,
)
from app.modules.agents.testing_validation.context_testability.context_decision.storage import (
    Agent4ContextDecisionStorage,
)
from app.modules.agents.testing_validation.context_testability.feasibility.storage import (
    Agent4FeasibilityStorage,
)
from app.modules.agents.testing_validation.context_testability.testability.storage import (
    Agent4TestabilityStorage,
)
from app.modules.agents.testing_validation.context_testability.traceability.storage import (
    Agent4TraceabilityStorage,
)
from app.modules.agents.testing_validation.workflow.orchestration.n4_service import (
    Agent4N4OrchestrationService,
    Agent4N4ReviewError,
)
from app.modules.agents.testing_validation.workflow.schemas import (
    Agent4N4ExecutionStatus,
    Agent4N4StageStatus,
    Agent4N4WarningAcknowledgementRequest,
    Agent4WorkflowNodeStatus,
)
from app.modules.agents.testing_validation.workflow.service import Agent4WorkflowGateError
from app.modules.agents.testing_validation.workflow.storage import Agent4WorkflowStorage
from test_agent4_context_decision import decision_service
from test_agent4_feasibility import feasibility_service
from test_agent4_n2_orchestration import ControlledExecutor, create_project, load, n2_context
from test_agent4_traceability import completed_project
from test_standalone_foundation import user


class RecordingService:
    def __init__(self, name, service, method, order, *, replacement=None, failure=None):
        self.name = name
        self.service = service
        self.method = method
        self.order = order
        self.replacement = replacement
        self.failure = failure

    def run(self, project_id, current_user, *, force=False):
        assert force is False
        self.order.append(self.name)
        if self.failure:
            raise self.failure
        value = getattr(self.service, self.method)(project_id, current_user, force=force)
        return self.replacement(value) if self.replacement else value


class RejectingExecutor:
    def submit(self, *_args, **_kwargs):
        raise RuntimeError("executor unavailable")


def setup_n4(context, *, decision=None, failure_stage=None, executor=None, prebuild=True):
    project_id = completed_project(context)
    feasibility, traceability, testability = feasibility_service(context)
    context_service = decision_service(context)
    if prebuild:
        traceability.build(project_id, user())
        testability.evaluate(project_id, user())
        feasibility.evaluate(project_id, user())
        context_service.evaluate(project_id, user())
    order = []

    def replacement(value):
        return value.model_copy(update={"overall_decision": decision}) if decision else value

    stages = {
        "TR1": RecordingService("TR1", traceability, "build", order),
        "TB1": RecordingService("TB1", testability, "evaluate", order),
        "FB1": RecordingService("FB1", feasibility, "evaluate", order),
        "CD1": RecordingService("CD1", context_service, "evaluate", order, replacement=replacement),
    }
    if failure_stage:
        stages[failure_stage].failure = RuntimeError("unsafe internal details")
    root = context[3]
    worker = executor or ControlledExecutor()
    service = Agent4N4OrchestrationService(
        context[1]._workflow_service,
        Agent4WorkflowStorage(root),
        SimpleNamespace(build=stages["TR1"].run),
        SimpleNamespace(evaluate=stages["TB1"].run),
        SimpleNamespace(evaluate=stages["FB1"].run),
        SimpleNamespace(evaluate=stages["CD1"].run),
        Agent4TraceabilityStorage(root),
        Agent4TestabilityStorage(root),
        Agent4FeasibilityStorage(root),
        Agent4ContextDecisionStorage(root),
        executor=worker,
    )
    return project_id, service, worker, order


def workflow_record(context, project_id):
    return Agent4WorkflowStorage(context[3]).load(
        agent_project_id=project_id, owner_user_id=user().user_id
    )


def test_legacy_start_is_idempotent_ordered_cache_aware_and_waits_for_warnings(n2_context):
    project_id, service, executor, order = setup_n4(n2_context)
    first = service.start(project_id, user())
    second = service.start(project_id, user())
    assert first.n4_execution.status is Agent4N4ExecutionStatus.QUEUED
    assert second.n4_execution_count == 1 and len(executor.tasks) == 1
    executor.drain()
    result = service.get(project_id, user())
    assert order == ["TR1", "TB1", "FB1", "CD1"]
    assert result.n4_execution.status is Agent4N4ExecutionStatus.WAITING_FOR_HUMAN
    assert [item.status for item in result.n4_execution.stages] == [Agent4N4StageStatus.COMPLETE] * 4
    assert result.pipeline_status.value == "WAITING_FOR_HUMAN"
    assert result.nodes[6].status is Agent4WorkflowNodeStatus.LOCKED
    assert result.n4_acknowledgement_count == 0
    assert n2_context[5].documents == {}


def test_pipeline_builds_missing_tr1_tb1_fb1_and_cd1_artifacts_in_order(n2_context):
    project_id, service, executor, order = setup_n4(n2_context, prebuild=False)
    service.start(project_id, user())
    executor.drain()
    result = service.get(project_id, user())
    assert result.n4_execution.status is Agent4N4ExecutionStatus.WAITING_FOR_HUMAN
    assert order == ["TR1", "TB1", "FB1", "CD1"]
    root = n2_context[3] / project_id / "context-testability"
    assert all(
        (root / name).is_file()
        for name in ("traceability.json", "testability.json", "feasibility.json", "context-decision.json")
    )


def test_new_n3_completion_handoff_queues_once_and_submission_failure_is_retryable(n2_context):
    project_id, service, executor, _ = setup_n4(n2_context)
    record = workflow_record(n2_context, project_id)
    n3 = record.n3_executions[-1]
    service.start_after_n3(project_id, user().user_id, n3.execution_id, user())
    service.start_after_n3(project_id, user().user_id, n3.execution_id, user())
    current = workflow_record(n2_context, project_id)
    assert current.n3_executions[-1].status.value == "COMPLETED"
    assert len(current.n4_executions) == 1 and len(executor.tasks) == 1

    other_id, failing, _, _ = setup_n4(n2_context, executor=RejectingExecutor())
    failing.start(other_id, user())
    failed = workflow_record(n2_context, other_id)
    assert failed.n3_executions[-1].status.value == "COMPLETED"
    assert failed.n4_executions[-1].status is Agent4N4ExecutionStatus.FAILED
    assert failed.n4_executions[-1].retryable


def test_n4_handoff_reserves_execution_before_publishing_queued_state(
    n2_context, monkeypatch,
):
    project_id, service, executor, _ = setup_n4(n2_context)
    record = workflow_record(n2_context, project_id)
    n3 = record.n3_executions[-1]
    original_save = service._workflow.save
    queued_saves = []

    def checked_save(current_record):
        current = (
            current_record.n4_executions[-1]
            if current_record.n4_executions else None
        )
        if current is not None and current.status is Agent4N4ExecutionStatus.QUEUED:
            queued_saves.append(current.execution_id)
            assert (
                current.execution_id
                in Agent4N4OrchestrationService._active_execution_ids
            )
        result = original_save(current_record)
        if current is not None and current.status is Agent4N4ExecutionStatus.QUEUED:
            concurrent_projection = service.get(project_id, user())
            assert (
                concurrent_projection.n4_execution.status
                is Agent4N4ExecutionStatus.QUEUED
            )
        return result

    monkeypatch.setattr(service._workflow, "save", checked_save)
    service.start_after_n3(
        project_id, user().user_id, n3.execution_id, user()
    )

    assert len(queued_saves) == 1
    assert len(executor.tasks) == 1
    executor.drain()


def test_proceed_completes_n4_and_unlocks_but_does_not_start_n5(n2_context):
    project_id, service, executor, _ = setup_n4(
        n2_context, decision=ContextDecisionStatus.PROCEED
    )
    service.start(project_id, user())
    executor.drain()
    workflow = service.get(project_id, user())
    assert workflow.n4_execution.status is Agent4N4ExecutionStatus.COMPLETED
    assert [item.status.value for item in workflow.nodes] == [
        "COMPLETED", "COMPLETED", "COMPLETED", "COMPLETED", "COMPLETED", "COMPLETED", "NOT_STARTED", "LOCKED",
    ]
    assert workflow.current_node_id.value == "TEST_PLANNING_REVIEW"
    assert workflow.pipeline_status.value == "RUNNING"
    assert workflow.n4_acknowledgement_count == 0


def test_warning_acknowledgement_is_snapshot_bound_append_only_and_immutable(n2_context):
    project_id, service, executor, _ = setup_n4(n2_context)
    service.start(project_id, user())
    executor.drain()
    root = n2_context[3]
    project_root = root / project_id
    immutable_paths = [
        path for path in project_root.rglob("*")
        if path.is_file() and path.name != "workflow.json"
    ]
    before = {path: path.read_bytes() for path in immutable_paths}
    waiting = service.get(project_id, user())
    assert waiting.n4_execution.warning_snapshot_fingerprint == service._warning_snapshot(
        Agent4ContextDecisionStorage(root).load(
            agent_project_id=project_id, owner_user_id=user().user_id,
        )
    )
    with pytest.raises(Agent4N4ReviewError, match="stale"):
        service.acknowledge(
            project_id,
            Agent4N4WarningAcknowledgementRequest(warning_snapshot_fingerprint="0" * 64),
            user(),
        )
    completed = service.acknowledge(
        project_id,
        Agent4N4WarningAcknowledgementRequest(
            warning_snapshot_fingerprint=waiting.n4_execution.warning_snapshot_fingerprint,
            optional_note="  Reviewed limitations.  ",
        ),
        user(),
    )
    assert completed.n4_execution.status is Agent4N4ExecutionStatus.COMPLETED
    assert completed.nodes[6].status is Agent4WorkflowNodeStatus.NOT_STARTED
    record = workflow_record(n2_context, project_id)
    assert len(record.n4_acknowledgement_history) == 1
    assert record.n4_acknowledgement_history[0].optional_note == "Reviewed limitations."
    assert record.n4_acknowledgement_history[0].reviewer_user_id == user().user_id
    assert record.n4_acknowledgement_history[0].warning_ids
    assert all(path.read_bytes() == content for path, content in before.items())
    with pytest.raises(Agent4N4ReviewError, match="not waiting"):
        service.acknowledge(
            project_id,
            Agent4N4WarningAcknowledgementRequest(
                warning_snapshot_fingerprint=waiting.n4_execution.warning_snapshot_fingerprint,
            ),
            user(),
        )


def test_blocked_stops_pipeline_cannot_acknowledge_or_retry_and_preserves_selection(n2_context):
    project_id, service, executor, _ = setup_n4(
        n2_context, decision=ContextDecisionStatus.BLOCKED
    )
    selected = list(workflow_record(n2_context, project_id).selected_outputs)
    service.start(project_id, user())
    executor.drain()
    workflow = service.get(project_id, user())
    assert workflow.n4_execution.status is Agent4N4ExecutionStatus.BLOCKED
    assert workflow.pipeline_status.value == "BLOCKED"
    assert workflow.current_node_id.value == "CONTEXT_TESTABILITY"
    assert workflow.nodes[6].status is Agent4WorkflowNodeStatus.LOCKED
    assert workflow.selected_outputs == selected
    with pytest.raises(Agent4WorkflowGateError, match="no retryable"):
        service.retry(project_id, user())
    with pytest.raises(Agent4N4ReviewError, match="not waiting"):
        service.acknowledge(
            project_id,
            Agent4N4WarningAcknowledgementRequest(warning_snapshot_fingerprint="0" * 64),
            user(),
        )


@pytest.mark.parametrize(
    ("failure_stage", "expected_order"),
    (
        ("TR1", ["TR1"]),
        ("TB1", ["TR1", "TB1"]),
        ("FB1", ["TR1", "TB1", "FB1"]),
        ("CD1", ["TR1", "TB1", "FB1", "CD1"]),
    ),
)
def test_operational_failures_stop_downstream_and_expose_only_safe_retryable_error(
    n2_context, failure_stage, expected_order,
):
    project_id, service, executor, order = setup_n4(n2_context, failure_stage=failure_stage)
    service.start(project_id, user())
    executor.drain()
    workflow = service.get(project_id, user())
    assert order == expected_order
    assert workflow.n4_execution.status is Agent4N4ExecutionStatus.FAILED
    assert workflow.n4_execution.retryable
    assert workflow.n4_execution.error.message == "Context analysis could not complete safely."
    assert "unsafe internal details" not in workflow.model_dump_json()


def test_retry_is_append_only_and_reuses_cached_artifacts(n2_context):
    project_id, service, executor, order = setup_n4(n2_context, failure_stage="CD1")
    service.start(project_id, user())
    executor.drain()
    assert service.get(project_id, user()).n4_execution.status is Agent4N4ExecutionStatus.FAILED
    service._context_decision.evaluate = RecordingService(
        "CD1", decision_service(n2_context), "evaluate", order
    ).run
    retried = service.retry(project_id, user())
    assert retried.n4_execution_count == 2 and retried.n4_execution.attempt_number == 2
    with pytest.raises(Agent4WorkflowGateError, match="no retryable"):
        service.retry(project_id, user())
    executor.drain()
    assert service.get(project_id, user()).n4_execution.status is Agent4N4ExecutionStatus.WAITING_FOR_HUMAN
    assert order == ["TR1", "TB1", "FB1", "CD1", "TR1", "TB1", "FB1", "CD1"]


@pytest.mark.parametrize("status", (Agent4N4ExecutionStatus.QUEUED, Agent4N4ExecutionStatus.RUNNING))
def test_orphaned_active_execution_becomes_interrupted_but_terminal_states_do_not(n2_context, status):
    project_id, service, _, _ = setup_n4(n2_context)
    service.start(project_id, user())
    storage = Agent4WorkflowStorage(n2_context[3])
    record = workflow_record(n2_context, project_id)
    record.n4_executions[-1].status = status
    storage.save(record)
    service._active_execution_ids.clear()
    recovered = service.get(project_id, user())
    assert recovered.n4_execution.status is Agent4N4ExecutionStatus.INTERRUPTED
    assert recovered.n4_execution.retryable


@pytest.mark.parametrize(
    "status",
    (
        Agent4N4ExecutionStatus.WAITING_FOR_HUMAN,
        Agent4N4ExecutionStatus.BLOCKED,
        Agent4N4ExecutionStatus.COMPLETED,
    ),
)
def test_stale_recovery_leaves_intentional_terminal_n4_states_unchanged(n2_context, status):
    project_id, service, _, _ = setup_n4(n2_context)
    service.start(project_id, user())
    record = workflow_record(n2_context, project_id)
    record.n4_executions[-1].status = status
    Agent4WorkflowStorage(n2_context[3]).save(record)
    service._active_execution_ids.clear()
    assert service.get(project_id, user()).n4_execution.status is status


def test_legacy_start_is_rejected_before_n3_completion(n2_context):
    _, service, _, _ = setup_n4(n2_context)
    incomplete_project = create_project(n2_context[0])
    with pytest.raises(Agent4WorkflowGateError, match="cannot be started"):
        service.start(incomplete_project, user())


def test_result_projection_is_safe_and_contains_output_decisions(n2_context):
    project_id, service, executor, _ = setup_n4(n2_context)
    service.start(project_id, user())
    executor.drain()
    result = service.result(project_id, user())
    assert result.outputs
    assert result.outputs[0].recommended_representation in {
        "SPECIFICATION", "EXECUTABLE_CODE", "STRUCTURED_ARTIFACT",
    }
    assert isinstance(result.outputs[0].planning_allowed, bool)
    serialized = result.model_dump_json().casefold()
    assert "reviewer_user_id" not in serialized
    assert "storage" not in serialized and "technical_evidence_inventory" not in serialized
    assert "clarification" not in serialized
