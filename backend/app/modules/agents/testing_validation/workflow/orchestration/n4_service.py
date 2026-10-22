from collections.abc import Callable
from concurrent.futures import Executor
from datetime import datetime, timezone
from threading import Lock
from uuid import uuid4

from app.modules.agents.testing_validation.context_testability.context_decision.constants import (
    CONTEXT_DECISION_POLICY_VERSION,
    ContextDecisionStatus,
)
from app.modules.agents.testing_validation.context_testability.context_decision.service import (
    _result_fingerprint as context_decision_fingerprint,
)
from app.modules.agents.testing_validation.context_testability.feasibility.schemas import (
    RepresentationRecommendation,
)
from app.modules.agents.testing_validation.context_testability.feasibility.service import (
    testability_result_fingerprint,
)
from app.modules.agents.testing_validation.context_testability.traceability.canonicalization import (
    fingerprint,
)
from app.modules.agents.testing_validation.context_testability.testability.service import (
    traceability_manifest_fingerprint,
)
from app.modules.agents.testing_validation.workflow.orchestration.executor import (
    AGENT4_N4_EXECUTOR,
)
from app.modules.agents.testing_validation.workflow.projection import (
    build_agent4_workflow_response,
)
from app.modules.agents.testing_validation.workflow.schemas import (
    Agent4N2Message,
    Agent4N3ExecutionStatus,
    Agent4N4Execution,
    Agent4N4ExecutionStatus,
    Agent4N4OutputResult,
    Agent4N4ResultFinding,
    Agent4N4ResultProjection,
    Agent4N4StageName,
    Agent4N4StageProgress,
    Agent4N4StageStatus,
    Agent4N4WarningAcknowledgement,
    Agent4N4WarningAcknowledgementRequest,
    Agent4PipelineStatus,
    Agent4TestGenerationNodeId,
    Agent4WorkflowNodeStatus,
)
from app.modules.agents.testing_validation.workflow.service import Agent4WorkflowGateError
from app.modules.agents.testing_validation.workflow.storage import AGENT4_WORKFLOW_STATE_LOCK


def utc_now():
    return datetime.now(timezone.utc)


ACTIVE_N4_STATES = {Agent4N4ExecutionStatus.QUEUED, Agent4N4ExecutionStatus.RUNNING}


class Agent4N4ReviewError(ValueError):
    pass


class Agent4N4OrchestrationService:
    _active_lock = Lock()
    _active_execution_ids: set[str] = set()

    def __init__(
        self, workflow_service, workflow_storage, traceability_service,
        testability_service, feasibility_service, context_decision_service,
        traceability_storage, testability_storage, feasibility_storage,
        context_decision_storage, *, executor: Executor = AGENT4_N4_EXECUTOR,
        clock: Callable[[], datetime] = utc_now,
    ):
        self._workflow_service = workflow_service
        self._workflow = workflow_storage
        self._traceability = traceability_service
        self._testability = testability_service
        self._feasibility = feasibility_service
        self._context_decision = context_decision_service
        self._traceability_storage = traceability_storage
        self._testability_storage = testability_storage
        self._feasibility_storage = feasibility_storage
        self._context_storage = context_decision_storage
        self._executor = executor
        self._clock = clock

    def get(self, project_id, user):
        self._workflow_service.get(project_id, user)
        with AGENT4_WORKFLOW_STATE_LOCK:
            record = self._require_record(project_id, user.user_id)
            current = self._current(record)
            if current and current.status in ACTIVE_N4_STATES:
                with self._active_lock:
                    active = current.execution_id in self._active_execution_ids
                if not active:
                    now = self._clock()
                    current.status = Agent4N4ExecutionStatus.INTERRUPTED
                    current.interrupted_at = now
                    current.updated_at = now
                    current.retryable = True
                    current.error = Agent4N2Message(
                        code="N4_EXECUTION_INTERRUPTED",
                        message="Context analysis was interrupted and can be retried safely.",
                    )
                    self._mark_operational_failure(record, now, interrupted=True)
                    self._workflow.save(record)
            return build_agent4_workflow_response(record)

    def start(self, project_id, user):
        self._workflow_service.get(project_id, user)
        with AGENT4_WORKFLOW_STATE_LOCK:
            record = self._require_record(project_id, user.user_id)
            current = self._current(record)
            if current is not None:
                return build_agent4_workflow_response(record)
            n3 = self._current_n3(record)
            node = self._node(record, Agent4TestGenerationNodeId.CONTEXT_TESTABILITY)
            if (
                n3 is None or n3.status is not Agent4N3ExecutionStatus.COMPLETED
                or node.status is not Agent4WorkflowNodeStatus.NOT_STARTED
                or record.current_node_id is not Agent4TestGenerationNodeId.CONTEXT_TESTABILITY
            ):
                raise Agent4WorkflowGateError("Context & Testability cannot be started from its current state.")
            execution = self._new_execution(record, n3.execution_id, "LEGACY_START", self._clock())
            self._queue(record, execution)
            self._reserve_and_save(record, execution)
        self._submit(project_id, execution, user)
        return build_agent4_workflow_response(self._require_record(project_id, user.user_id))

    def start_after_n3(self, project_id, owner_id, n3_execution_id, user):
        with AGENT4_WORKFLOW_STATE_LOCK:
            record = self._require_record(project_id, owner_id)
            if self._current(record) is not None:
                return
            n3 = self._current_n3(record)
            if n3 is None or n3.execution_id != n3_execution_id or n3.status is not Agent4N3ExecutionStatus.COMPLETED:
                return
            execution = self._new_execution(record, n3_execution_id, "N3_COMPLETION", self._clock())
            self._queue(record, execution)
            self._reserve_and_save(record, execution)
        self._submit(project_id, execution, user)

    def retry(self, project_id, user):
        self._workflow_service.get(project_id, user)
        with AGENT4_WORKFLOW_STATE_LOCK:
            record = self._require_record(project_id, user.user_id)
            previous = self._current(record)
            if previous is None or previous.status not in {
                Agent4N4ExecutionStatus.FAILED, Agent4N4ExecutionStatus.INTERRUPTED,
            } or not previous.retryable:
                raise Agent4WorkflowGateError("Context analysis has no retryable operational failure.")
            execution = self._new_execution(
                record, previous.n3_execution_id, "RETRY", self._clock()
            )
            self._queue(record, execution)
            self._reserve_and_save(record, execution)
        self._submit(project_id, execution, user)
        return build_agent4_workflow_response(self._require_record(project_id, user.user_id))

    def result(self, project_id, user):
        self._workflow_service.get(project_id, user)
        with AGENT4_WORKFLOW_STATE_LOCK:
            record = self._require_record(project_id, user.user_id)
            execution = self._current(record)
            if execution is None or execution.overall_decision is None:
                raise Agent4WorkflowGateError("Context decision result is not available.")
            result = self._context_storage.load(
                agent_project_id=project_id, owner_user_id=user.user_id
            )
            if result is None:
                raise Agent4WorkflowGateError("Current context decision result is unavailable.")
            result_fp = context_decision_fingerprint(result)
            stage = self._stage(execution, Agent4N4StageName.CONTEXT_DECISION)
            if stage.artifact_fingerprint != result_fp:
                raise Agent4WorkflowGateError("Context decision result is stale.")
            findings = {item.consolidated_finding_id: item for item in result.consolidated_findings}
            outputs = []
            for profile in result.output_profiles:
                def public(ids):
                    return [
                        Agent4N4ResultFinding(
                            finding_id=findings[item].consolidated_finding_id,
                            reason_code=findings[item].reason_code,
                            message=findings[item].display_message,
                        ) for item in ids
                    ]
                outputs.append(Agent4N4OutputResult(
                    output_code=profile.output_code,
                    testability_status=profile.testability_status.value,
                    feasibility_status=profile.feasibility_status.value,
                    recommended_representation=(
                        profile.recommended_representation.value
                        if profile.recommended_representation else None
                    ),
                    decision=profile.decision.value,
                    planning_allowed=profile.planning_allowed,
                    blockers=public(profile.blocking_finding_ids),
                    warnings=public(profile.warning_finding_ids),
                    evidence_node_count=len(profile.evidence_node_ids),
                    evidence_link_count=len(profile.evidence_link_ids),
                    semantic_fact_count=len(profile.semantic_fact_ids),
                    execution_status=profile.execution_status,
                ))
            return Agent4N4ResultProjection(
                execution_id=execution.execution_id,
                overall_testability=execution.overall_testability,
                overall_feasibility=execution.overall_feasibility,
                overall_decision=execution.overall_decision,
                warning_snapshot_fingerprint=execution.warning_snapshot_fingerprint,
                outputs=outputs,
                planning_allowed_count=result.planning_allowed_output_count,
                blocked_output_count=result.blocked_output_count,
                warning_count=result.warning_count,
                executable_output_count=result.executable_output_count,
                specification_output_count=result.specification_output_count,
                structured_artifact_count=result.structured_artifact_count,
            )

    def acknowledge(self, project_id, request: Agent4N4WarningAcknowledgementRequest, user):
        self._workflow_service.get(project_id, user)
        with AGENT4_WORKFLOW_STATE_LOCK:
            record = self._require_record(project_id, user.user_id)
            execution = self._current(record)
            if execution is None or execution.status is not Agent4N4ExecutionStatus.WAITING_FOR_HUMAN:
                raise Agent4N4ReviewError("Context analysis is not waiting for warning acknowledgement.")
            result = self._context_storage.load(
                agent_project_id=project_id, owner_user_id=user.user_id
            )
            if result is None or result.overall_decision is not ContextDecisionStatus.PROCEED_WITH_WARNINGS:
                raise Agent4N4ReviewError("Current warning evidence is unavailable.")
            snapshot = self._warning_snapshot(result)
            if (
                request.warning_snapshot_fingerprint != snapshot
                or execution.warning_snapshot_fingerprint != snapshot
            ):
                raise Agent4N4ReviewError("Warning acknowledgement snapshot is stale.")
            if execution.acknowledgement_id is not None:
                raise Agent4N4ReviewError("Warnings have already been acknowledged.")
            now = self._clock()
            event = Agent4N4WarningAcknowledgement(
                acknowledgement_id=f"A4N4A-{uuid4().hex}",
                n4_execution_id=execution.execution_id,
                context_decision_fingerprint=context_decision_fingerprint(result),
                warning_snapshot_fingerprint=snapshot,
                warning_ids=sorted(
                    item.consolidated_finding_id for item in result.consolidated_findings
                    if item.severity.value == "WARNING"
                ),
                optional_note=request.optional_note,
                acknowledged_at=now,
                reviewer_user_id=user.user_id,
            )
            record.n4_acknowledgement_history.append(event)
            execution.acknowledgement_id = event.acknowledgement_id
            self._complete_to_n5(record, execution, now)
            self._workflow.save(record)
            return build_agent4_workflow_response(record)

    def _reserve_and_save(self, record, execution):
        """Publish QUEUED only after stale recovery can see scheduled work."""
        with self._active_lock:
            if execution.execution_id in self._active_execution_ids:
                raise Agent4WorkflowGateError(
                    "Context analysis execution is already scheduled"
                )
            self._active_execution_ids.add(execution.execution_id)
        try:
            self._workflow.save(record)
        except Exception:
            with self._active_lock:
                self._active_execution_ids.discard(execution.execution_id)
            raise

    def _submit(self, project_id, execution, user):
        with self._active_lock:
            if execution.execution_id not in self._active_execution_ids:
                return
        try:
            self._executor.submit(self._run, project_id, execution.execution_id, user)
        except Exception:
            with self._active_lock:
                self._active_execution_ids.discard(execution.execution_id)
            self._fail_submission(project_id, execution.execution_id, user.user_id)

    def _run(self, project_id, execution_id, user):
        try:
            with AGENT4_WORKFLOW_STATE_LOCK:
                record = self._require_record(project_id, user.user_id)
                execution = self._execution(record, execution_id)
                if execution.status is not Agent4N4ExecutionStatus.QUEUED:
                    return
                now = self._clock()
                execution.status = Agent4N4ExecutionStatus.RUNNING
                execution.started_at = now
                execution.updated_at = now
                node = self._node(record, Agent4TestGenerationNodeId.CONTEXT_TESTABILITY)
                node.status = Agent4WorkflowNodeStatus.RUNNING
                node.updated_at = now
                record.pipeline_status = Agent4PipelineStatus.RUNNING
                record.updated_at = now
                self._workflow.save(record)

            graph = self._run_stage(
                project_id, user, execution_id, Agent4N4StageName.TRACEABILITY,
                self._traceability.build,
                lambda value: (
                    traceability_manifest_fingerprint(value),
                    {"node_count": value.counts.node_count, "link_count": value.counts.link_count},
                ),
            )
            testability = self._run_stage(
                project_id, user, execution_id, Agent4N4StageName.TESTABILITY,
                self._testability.evaluate,
                lambda value: (
                    testability_result_fingerprint(value),
                    {"overall_status": value.overall_status.value,
                     "blocking_count": value.blocking_finding_count,
                     "warning_count": value.warning_count},
                ),
            )
            feasibility = self._run_stage(
                project_id, user, execution_id, Agent4N4StageName.FEASIBILITY,
                self._feasibility.evaluate,
                lambda value: (
                    fingerprint(value.model_dump(mode="json", exclude={"evaluated_at"})),
                    {"overall_feasibility": value.overall_feasibility.value},
                ),
            )
            decision = self._run_stage(
                project_id, user, execution_id, Agent4N4StageName.CONTEXT_DECISION,
                self._context_decision.evaluate,
                lambda value: (
                    context_decision_fingerprint(value),
                    {"overall_decision": value.overall_decision.value,
                     "planning_allowed_count": value.planning_allowed_output_count,
                     "blocked_output_count": value.blocked_output_count,
                     "warning_count": value.warning_count},
                ),
            )
            self._finish(project_id, user.user_id, execution_id, testability, feasibility, decision)
        except Exception:
            self._fail_execution(project_id, user.user_id, execution_id)
        finally:
            with self._active_lock:
                self._active_execution_ids.discard(execution_id)

    def _run_stage(self, project_id, user, execution_id, stage_name, operation, summarize):
        self._set_stage(project_id, user.user_id, execution_id, stage_name, Agent4N4StageStatus.RUNNING)
        try:
            value = operation(project_id, user, force=False)
        except Exception:
            self._set_stage(
                project_id, user.user_id, execution_id, stage_name,
                Agent4N4StageStatus.FAILED,
                error=Agent4N2Message(
                    code=f"N4_{stage_name.value}_FAILED",
                    message=f"{stage_name.value.replace('_', ' ').title()} could not complete safely.",
                ),
            )
            raise
        artifact_fp, summary = summarize(value)
        self._set_stage(
            project_id, user.user_id, execution_id, stage_name,
            Agent4N4StageStatus.COMPLETE, artifact_fingerprint=artifact_fp,
            summary=summary,
        )
        return value

    def _finish(self, project_id, owner_id, execution_id, testability, feasibility, decision):
        with AGENT4_WORKFLOW_STATE_LOCK:
            record = self._require_record(project_id, owner_id)
            execution = self._execution(record, execution_id)
            now = self._clock()
            execution.overall_testability = testability.overall_status.value
            execution.overall_feasibility = feasibility.overall_feasibility.value
            execution.overall_decision = decision.overall_decision.value
            execution.planning_allowed_count = decision.planning_allowed_output_count
            execution.blocked_output_count = decision.blocked_output_count
            execution.warning_count = decision.warning_count
            execution.executable_output_count = decision.executable_output_count
            execution.specification_output_count = decision.specification_output_count
            execution.structured_artifact_count = decision.structured_artifact_count
            node = self._node(record, Agent4TestGenerationNodeId.CONTEXT_TESTABILITY)
            if decision.overall_decision is ContextDecisionStatus.PROCEED:
                self._complete_to_n5(record, execution, now)
            elif decision.overall_decision is ContextDecisionStatus.PROCEED_WITH_WARNINGS:
                execution.status = Agent4N4ExecutionStatus.WAITING_FOR_HUMAN
                execution.waiting_at = now
                execution.retryable = False
                execution.warning_snapshot_fingerprint = self._warning_snapshot(decision)
                node.status = Agent4WorkflowNodeStatus.WAITING_FOR_HUMAN
                node.updated_at = now
                record.pipeline_status = Agent4PipelineStatus.WAITING_FOR_HUMAN
                record.current_node_id = Agent4TestGenerationNodeId.CONTEXT_TESTABILITY
            else:
                execution.status = Agent4N4ExecutionStatus.BLOCKED
                execution.blocked_at = now
                execution.retryable = False
                node.status = Agent4WorkflowNodeStatus.BLOCKED
                node.updated_at = now
                record.pipeline_status = Agent4PipelineStatus.BLOCKED
                record.current_node_id = Agent4TestGenerationNodeId.CONTEXT_TESTABILITY
            execution.updated_at = now
            record.updated_at = now
            self._workflow.save(record)

    def _complete_to_n5(self, record, execution, now):
        execution.status = Agent4N4ExecutionStatus.COMPLETED
        execution.completed_at = now
        execution.retryable = False
        n4 = self._node(record, Agent4TestGenerationNodeId.CONTEXT_TESTABILITY)
        n5 = self._node(record, Agent4TestGenerationNodeId.TEST_PLANNING_REVIEW)
        n6 = self._node(record, Agent4TestGenerationNodeId.TEST_GENERATION_RESULTS)
        n4.status = Agent4WorkflowNodeStatus.COMPLETED
        n5.status = Agent4WorkflowNodeStatus.NOT_STARTED
        n6.status = Agent4WorkflowNodeStatus.LOCKED
        n4.updated_at = n5.updated_at = n6.updated_at = now
        record.current_node_id = Agent4TestGenerationNodeId.TEST_PLANNING_REVIEW
        record.pipeline_status = Agent4PipelineStatus.RUNNING
        execution.updated_at = record.updated_at = now

    def _set_stage(self, project_id, owner_id, execution_id, stage_name, status,
                   *, artifact_fingerprint=None, summary=None, error=None):
        with AGENT4_WORKFLOW_STATE_LOCK:
            record = self._require_record(project_id, owner_id)
            execution = self._execution(record, execution_id)
            stage = self._stage(execution, stage_name)
            now = self._clock()
            stage.status = status
            stage.updated_at = now
            stage.artifact_fingerprint = artifact_fingerprint
            stage.summary = summary or {}
            stage.error = error
            execution.updated_at = record.updated_at = now
            self._workflow.save(record)

    def _fail_submission(self, project_id, execution_id, owner_id):
        with AGENT4_WORKFLOW_STATE_LOCK:
            record = self._require_record(project_id, owner_id)
            execution = self._execution(record, execution_id)
            now = self._clock()
            execution.status = Agent4N4ExecutionStatus.FAILED
            execution.failed_at = now
            execution.updated_at = now
            execution.retryable = True
            execution.error = Agent4N2Message(
                code="N4_EXECUTOR_UNAVAILABLE",
                message="Context analysis could not be queued and can be retried.",
            )
            self._mark_operational_failure(record, now)
            self._workflow.save(record)

    def _fail_execution(self, project_id, owner_id, execution_id):
        with AGENT4_WORKFLOW_STATE_LOCK:
            record = self._require_record(project_id, owner_id)
            execution = self._execution(record, execution_id)
            if execution.status not in ACTIVE_N4_STATES:
                return
            now = self._clock()
            execution.status = Agent4N4ExecutionStatus.FAILED
            execution.failed_at = now
            execution.updated_at = now
            execution.retryable = True
            execution.error = Agent4N2Message(
                code="N4_EXECUTION_FAILED",
                message="Context analysis could not complete safely.",
            )
            self._mark_operational_failure(record, now)
            self._workflow.save(record)

    def _mark_operational_failure(self, record, now, interrupted=False):
        node = self._node(record, Agent4TestGenerationNodeId.CONTEXT_TESTABILITY)
        node.status = Agent4WorkflowNodeStatus.FAILED
        node.updated_at = now
        record.pipeline_status = Agent4PipelineStatus.FAILED
        record.current_node_id = Agent4TestGenerationNodeId.CONTEXT_TESTABILITY
        record.updated_at = now

    def _new_execution(self, record, n3_execution_id, trigger, now):
        return Agent4N4Execution(
            execution_id=f"A4N4E-{uuid4().hex}",
            attempt_number=len(record.n4_executions) + 1,
            trigger=trigger,
            status=Agent4N4ExecutionStatus.QUEUED,
            n3_execution_id=n3_execution_id,
            stages=[
                Agent4N4StageProgress(
                    stage=stage, status=Agent4N4StageStatus.NOT_RUN, updated_at=now
                ) for stage in Agent4N4StageName
            ],
            selected_output_count=len(record.selected_outputs),
            queued_at=now,
            updated_at=now,
        )

    def _queue(self, record, execution):
        record.n4_executions.append(execution)
        record.current_n4_execution_id = execution.execution_id
        node = self._node(record, Agent4TestGenerationNodeId.CONTEXT_TESTABILITY)
        node.status = Agent4WorkflowNodeStatus.QUEUED
        node.updated_at = execution.queued_at
        record.current_node_id = Agent4TestGenerationNodeId.CONTEXT_TESTABILITY
        record.pipeline_status = Agent4PipelineStatus.RUNNING
        record.updated_at = execution.queued_at

    @staticmethod
    def _warning_snapshot(result):
        return fingerprint({
            "policy": CONTEXT_DECISION_POLICY_VERSION,
            "context_decision": context_decision_fingerprint(result),
            "selected_outputs": [item.value for item in result.selected_outputs],
            "warnings": sorted(
                item.consolidated_finding_id for item in result.consolidated_findings
                if item.severity.value == "WARNING"
            ),
            "decisions": [
                (item.output_code.value, item.decision.value)
                for item in result.output_profiles
            ],
        })

    def _require_record(self, project_id, owner_id):
        record = self._workflow.load(agent_project_id=project_id, owner_user_id=owner_id)
        if record is None:
            raise Agent4WorkflowGateError("Test Generation workflow is unavailable")
        return record

    @staticmethod
    def _node(record, node_id):
        return next(item for item in record.nodes if item.node_id is node_id)

    @staticmethod
    def _stage(execution, name):
        return next(item for item in execution.stages if item.stage is name)

    @staticmethod
    def _execution(record, execution_id):
        item = next((item for item in record.n4_executions if item.execution_id == execution_id), None)
        if item is None:
            raise Agent4WorkflowGateError("Context analysis execution is unavailable")
        return item

    @staticmethod
    def _current(record):
        if record.current_n4_execution_id is None:
            return None
        return Agent4N4OrchestrationService._execution(record, record.current_n4_execution_id)

    @staticmethod
    def _current_n3(record):
        return next(
            (item for item in record.n3_executions if item.execution_id == record.current_n3_execution_id),
            None,
        )
