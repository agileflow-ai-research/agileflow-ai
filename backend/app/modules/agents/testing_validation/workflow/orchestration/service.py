from collections.abc import Callable
from concurrent.futures import Executor
from datetime import datetime, timezone
from threading import Lock
from uuid import uuid4

from app.modules.agents.testing_validation.contracts.sources import (
    TestGenerationInputSourceType,
)
from app.modules.agents.testing_validation.preparation.chunking.service import (
    Agent4ChunkingService,
)
from app.modules.agents.testing_validation.preparation.extraction.schemas import (
    Agent4ExtractionStatus,
)
from app.modules.agents.testing_validation.preparation.extraction.service import (
    Agent4DocumentExtractionService,
)
from app.modules.agents.testing_validation.preparation.normalization.schemas import (
    NormalizationStatus,
)
from app.modules.agents.testing_validation.preparation.normalization.service import (
    Agent4NormalizationService,
)
from app.modules.agents.testing_validation.sources.storage import Agent4SourceStorage
from app.modules.agents.testing_validation.workflow.orchestration.executor import (
    AGENT4_N2_EXECUTOR,
)
from app.modules.agents.testing_validation.workflow.digests import source_set_digest
from app.modules.agents.testing_validation.workflow.projection import (
    build_agent4_workflow_response,
)
from app.modules.agents.testing_validation.workflow.schemas import (
    Agent4N2Execution,
    Agent4N2ExecutionStatus,
    Agent4N2Message,
    Agent4N2SourceExecution,
    Agent4N2SourceStatus,
    Agent4PipelineStatus,
    Agent4TestGenerationNodeId,
    Agent4TestGenerationWorkflowRecord,
    Agent4TestGenerationWorkflowResponse,
    Agent4WorkflowNodeStatus,
)
from app.modules.agents.testing_validation.workflow.service import (
    Agent4WorkflowGateError,
    Agent4WorkflowService,
)
from app.modules.agents.testing_validation.workflow.storage import (
    AGENT4_WORKFLOW_STATE_LOCK,
    Agent4WorkflowStorage,
)
from app.modules.auth.schemas import UserPublicResponse


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


ACTIVE_EXECUTION_STATES = {
    Agent4N2ExecutionStatus.QUEUED,
    Agent4N2ExecutionStatus.RUNNING,
}


class Agent4N2OrchestrationService:
    _active_lock = Lock()
    _active_execution_ids: set[str] = set()

    def __init__(
        self,
        workflow_service: Agent4WorkflowService,
        workflow_storage: Agent4WorkflowStorage,
        source_storage: Agent4SourceStorage,
        extraction_service: Agent4DocumentExtractionService,
        normalization_service: Agent4NormalizationService,
        chunking_service: Agent4ChunkingService,
        *,
        executor: Executor = AGENT4_N2_EXECUTOR,
        clock: Callable[[], datetime] = utc_now,
    ) -> None:
        self._workflow_service = workflow_service
        self._workflow = workflow_storage
        self._sources = source_storage
        self._extraction = extraction_service
        self._normalization = normalization_service
        self._chunking = chunking_service
        self._executor = executor
        self._clock = clock

    def get(
        self, agent_project_id: str, current_user: UserPublicResponse
    ) -> Agent4TestGenerationWorkflowResponse:
        self._workflow_service.get(agent_project_id, current_user)
        with AGENT4_WORKFLOW_STATE_LOCK:
            record = self._require_record(agent_project_id, current_user.user_id)
            execution = self._current_execution(record)
            if execution and execution.status in ACTIVE_EXECUTION_STATES:
                with self._active_lock:
                    active = execution.execution_id in self._active_execution_ids
                if not active:
                    now = self._clock()
                    execution.status = Agent4N2ExecutionStatus.INTERRUPTED
                    execution.failed_at = now
                    execution.updated_at = now
                    execution.retryable = True
                    execution.error = Agent4N2Message(
                        code="N2_EXECUTION_INTERRUPTED",
                        message=(
                            "Input preparation was interrupted and can be retried "
                            "safely."
                        ),
                    )
                    for source in execution.sources:
                        if source.status in {
                            Agent4N2SourceStatus.QUEUED,
                            Agent4N2SourceStatus.EXTRACTING,
                            Agent4N2SourceStatus.NORMALIZING,
                            Agent4N2SourceStatus.CHUNKING,
                        }:
                            source.status = Agent4N2SourceStatus.FAILED
                            source.updated_at = now
                            source.error = Agent4N2Message(
                                code="N2_EXECUTION_INTERRUPTED",
                                message="Preparation for this source was interrupted.",
                            )
                    self._mark_n2_failed(record, now)
                    self._workflow.save(record)
            return build_agent4_workflow_response(record)

    def confirm_n1_and_start(
        self, agent_project_id: str, current_user: UserPublicResponse
    ) -> Agent4TestGenerationWorkflowResponse:
        self._workflow_service.confirm_n1(agent_project_id, current_user)
        return self._start(agent_project_id, current_user, "N1_CONFIRMATION")

    def start(
        self, agent_project_id: str, current_user: UserPublicResponse
    ) -> Agent4TestGenerationWorkflowResponse:
        self._workflow_service.get(agent_project_id, current_user)
        return self._start(agent_project_id, current_user, "LEGACY_START")

    def retry_source(
        self,
        agent_project_id: str,
        source_id: str,
        current_user: UserPublicResponse,
    ) -> Agent4TestGenerationWorkflowResponse:
        self._workflow_service.get(agent_project_id, current_user)
        with AGENT4_WORKFLOW_STATE_LOCK:
            record = self._require_record(agent_project_id, current_user.user_id)
            previous = self._current_execution(record)
            if previous is None or previous.status not in {
                Agent4N2ExecutionStatus.FAILED,
                Agent4N2ExecutionStatus.INTERRUPTED,
            }:
                raise Agent4WorkflowGateError(
                    "Input Preparation does not have a retryable execution."
                )
            target = next(
                (item for item in previous.sources if item.source_id == source_id),
                None,
            )
            if target is None or target.status is not Agent4N2SourceStatus.FAILED:
                raise Agent4WorkflowGateError(
                    "Only a failed confirmed source can be retried."
                )
            confirmation = self._require_confirmation(record)
            if (
                previous.confirmation_id != confirmation.confirmation_id
                or previous.source_set_digest != confirmation.source_set_digest
                or previous.selection_digest != confirmation.selection_digest
            ):
                raise Agent4WorkflowGateError(
                    "The confirmed setup no longer matches this execution."
                )
            persisted = self._sources.list_for_project(
                agent_project_id=agent_project_id,
                owner_user_id=current_user.user_id,
            )
            if source_set_digest(persisted) != confirmation.source_set_digest:
                raise Agent4WorkflowGateError(
                    "The confirmed source evidence is no longer current."
                )
            now = self._clock()
            sources = [item.model_copy(deep=True) for item in previous.sources]
            retry_target = next(item for item in sources if item.source_id == source_id)
            retry_target.status = Agent4N2SourceStatus.QUEUED
            retry_target.error = None
            retry_target.started_at = None
            retry_target.completed_at = None
            retry_target.chunk_count = 0
            retry_target.warnings = []
            retry_target.updated_at = now
            execution = self._new_execution(
                record,
                confirmation,
                sources,
                trigger="SOURCE_RETRY",
                retry_source_id=source_id,
                now=now,
            )
            self._queue(record, execution, now)
            self._workflow.save(record)
        self._submit(record, execution, current_user)
        current = self._require_record(agent_project_id, current_user.user_id)
        return build_agent4_workflow_response(current)

    def _start(self, agent_project_id, current_user, trigger):
        with AGENT4_WORKFLOW_STATE_LOCK:
            record = self._require_record(agent_project_id, current_user.user_id)
            confirmation = self._require_confirmation(record)
            current = self._current_execution(record)
            if current is not None:
                return build_agent4_workflow_response(record)
            n2 = self._node(record, Agent4TestGenerationNodeId.INPUT_PREPARATION)
            if n2.status is not Agent4WorkflowNodeStatus.NOT_STARTED:
                raise Agent4WorkflowGateError(
                    "Input Preparation cannot be started from its current state."
                )
            persisted = self._sources.list_for_project(
                agent_project_id=agent_project_id,
                owner_user_id=current_user.user_id,
            )
            by_id = {source.source_id: source for source in persisted}
            if set(by_id) != set(confirmation.source_ids):
                raise Agent4WorkflowGateError(
                    "The confirmed source snapshot is no longer current."
                )
            if source_set_digest(persisted) != confirmation.source_set_digest:
                raise Agent4WorkflowGateError(
                    "The confirmed source evidence is no longer current."
                )
            now = self._clock()
            sources = [
                Agent4N2SourceExecution(
                    source_id=source_id,
                    artifact_type=by_id[source_id].artifact_type,
                    source_type=by_id[source_id].source_type,
                    label=by_id[source_id].label,
                    original_filename=by_id[source_id].original_filename,
                    status=Agent4N2SourceStatus.QUEUED,
                    updated_at=now,
                )
                for source_id in confirmation.source_ids
            ]
            execution = self._new_execution(
                record, confirmation, sources, trigger=trigger, now=now
            )
            self._queue(record, execution, now)
            self._workflow.save(record)
        self._submit(record, execution, current_user)
        current = self._require_record(agent_project_id, current_user.user_id)
        return build_agent4_workflow_response(current)

    def _submit(self, record, execution, current_user):
        with self._active_lock:
            if execution.execution_id in self._active_execution_ids:
                return
            self._active_execution_ids.add(execution.execution_id)
        try:
            self._executor.submit(
                self._run,
                record.agent_project_id,
                record.owner_user_id,
                execution.execution_id,
                current_user,
            )
        except RuntimeError:
            with self._active_lock:
                self._active_execution_ids.discard(execution.execution_id)
            self._fail_execution(
                record.agent_project_id,
                record.owner_user_id,
                execution.execution_id,
                "N2_EXECUTOR_UNAVAILABLE",
                "Input preparation could not be started and can be retried safely.",
            )

    def _run(self, agent_project_id, owner_user_id, execution_id, current_user):
        try:
            self._mark_running(agent_project_id, owner_user_id, execution_id)
            record = self._require_record(agent_project_id, owner_user_id)
            execution = self._execution(record, execution_id)
            for source in execution.sources:
                if source.status is not Agent4N2SourceStatus.QUEUED:
                    continue
                self._process_source(
                    agent_project_id,
                    owner_user_id,
                    execution_id,
                    source.source_id,
                    current_user,
                )
            self._finish(agent_project_id, owner_user_id, execution_id)
        except Exception:
            self._fail_execution(
                agent_project_id,
                owner_user_id,
                execution_id,
                "N2_EXECUTION_FAILED",
                "Input preparation could not be completed and can be retried safely.",
            )
        finally:
            with self._active_lock:
                self._active_execution_ids.discard(execution_id)

    def _process_source(
        self, project_id, owner_id, execution_id, source_id, current_user
    ):
        record = self._require_record(project_id, owner_id)
        progress = self._source(self._execution(record, execution_id), source_id)
        try:
            if progress.source_type is TestGenerationInputSourceType.DOCUMENT:
                self._advance(
                    project_id,
                    owner_id,
                    execution_id,
                    source_id,
                    Agent4N2SourceStatus.EXTRACTING,
                )
                extraction = self._extraction.extract(
                    project_id, source_id, current_user
                )
                self._update_source(
                    project_id,
                    owner_id,
                    execution_id,
                    source_id,
                    extraction_status=extraction.status.value,
                    warnings=[
                        Agent4N2Message(code=item.code, message=item.message)
                        for item in extraction.warnings
                    ],
                )
                if extraction.status is Agent4ExtractionStatus.FAILED:
                    code = extraction.error.code.value if extraction.error else "EXTRACTION_FAILED"
                    message = (
                        extraction.error.message
                        if extraction.error
                        else "The document could not be extracted."
                    )
                    self._fail_source(
                        project_id, owner_id, execution_id, source_id, code, message
                    )
                    return

            self._advance(
                project_id,
                owner_id,
                execution_id,
                source_id,
                Agent4N2SourceStatus.NORMALIZING,
            )
            normalized = self._normalization.normalize(
                project_id, source_id, current_user
            )
            self._update_source(
                project_id,
                owner_id,
                execution_id,
                source_id,
                normalization_status=normalized.normalization_status.value,
            )
            if progress.source_type is TestGenerationInputSourceType.IMAGE:
                self._pending_image(project_id, owner_id, execution_id, source_id)
                return
            if (
                not normalized.textual_context_usable
                or normalized.normalization_status is NormalizationStatus.FAILED
            ):
                self._fail_source(
                    project_id,
                    owner_id,
                    execution_id,
                    source_id,
                    "NORMALIZATION_FAILED",
                    "The source did not produce usable normalized text.",
                )
                return

            self._advance(
                project_id,
                owner_id,
                execution_id,
                source_id,
                Agent4N2SourceStatus.CHUNKING,
            )
            chunks = self._chunking.build(project_id, source_id, current_user)
            self._complete_source(
                project_id,
                owner_id,
                execution_id,
                source_id,
                len(chunks.chunks),
            )
        except Exception:
            self._fail_source(
                project_id,
                owner_id,
                execution_id,
                source_id,
                "SOURCE_PREPARATION_FAILED",
                "This source could not be prepared at its current stage.",
            )

    def _mark_running(self, project_id, owner_id, execution_id):
        with AGENT4_WORKFLOW_STATE_LOCK:
            record = self._require_record(project_id, owner_id)
            execution = self._execution(record, execution_id)
            if execution.status is not Agent4N2ExecutionStatus.QUEUED:
                return
            now = self._clock()
            execution.status = Agent4N2ExecutionStatus.RUNNING
            execution.started_at = now
            execution.updated_at = now
            self._node(record, Agent4TestGenerationNodeId.INPUT_PREPARATION).status = (
                Agent4WorkflowNodeStatus.RUNNING
            )
            record.updated_at = now
            self._workflow.save(record)

    def _advance(self, project_id, owner_id, execution_id, source_id, status):
        with AGENT4_WORKFLOW_STATE_LOCK:
            record = self._require_record(project_id, owner_id)
            source = self._source(self._execution(record, execution_id), source_id)
            now = self._clock()
            source.status = status
            source.started_at = source.started_at or now
            source.updated_at = now
            source.error = None
            execution = self._execution(record, execution_id)
            execution.updated_at = now
            record.updated_at = now
            self._workflow.save(record)

    def _update_source(self, project_id, owner_id, execution_id, source_id, **updates):
        with AGENT4_WORKFLOW_STATE_LOCK:
            record = self._require_record(project_id, owner_id)
            source = self._source(self._execution(record, execution_id), source_id)
            for key, value in updates.items():
                setattr(source, key, value)
            now = self._clock()
            source.updated_at = now
            self._execution(record, execution_id).updated_at = now
            record.updated_at = now
            self._workflow.save(record)

    def _complete_source(
        self, project_id, owner_id, execution_id, source_id, chunk_count
    ):
        with AGENT4_WORKFLOW_STATE_LOCK:
            record = self._require_record(project_id, owner_id)
            source = self._source(self._execution(record, execution_id), source_id)
            now = self._clock()
            source.status = Agent4N2SourceStatus.COMPLETE
            source.chunk_count = chunk_count
            source.completed_at = now
            source.updated_at = now
            source.error = None
            self._execution(record, execution_id).updated_at = now
            record.updated_at = now
            self._workflow.save(record)

    def _pending_image(self, project_id, owner_id, execution_id, source_id):
        warning = Agent4N2Message(
            code="IMAGE_ANALYSIS_NOT_IMPLEMENTED",
            message=(
                "Image understanding is not implemented; this source remains "
                "pending analysis."
            ),
        )
        with AGENT4_WORKFLOW_STATE_LOCK:
            record = self._require_record(project_id, owner_id)
            execution = self._execution(record, execution_id)
            source = self._source(execution, source_id)
            now = self._clock()
            source.status = Agent4N2SourceStatus.PENDING_ANALYSIS
            source.warnings = [*source.warnings, warning]
            source.completed_at = now
            source.updated_at = now
            if not any(item.code == warning.code for item in execution.warnings):
                execution.warnings.append(warning)
            execution.updated_at = now
            record.updated_at = now
            self._workflow.save(record)

    def _fail_source(
        self, project_id, owner_id, execution_id, source_id, code, message
    ):
        with AGENT4_WORKFLOW_STATE_LOCK:
            record = self._require_record(project_id, owner_id)
            source = self._source(self._execution(record, execution_id), source_id)
            now = self._clock()
            source.status = Agent4N2SourceStatus.FAILED
            source.error = Agent4N2Message(code=code, message=message)
            source.completed_at = now
            source.updated_at = now
            self._execution(record, execution_id).updated_at = now
            record.updated_at = now
            self._workflow.save(record)

    def _finish(self, project_id, owner_id, execution_id):
        with AGENT4_WORKFLOW_STATE_LOCK:
            record = self._require_record(project_id, owner_id)
            execution = self._execution(record, execution_id)
            now = self._clock()
            execution.total_chunks = sum(item.chunk_count for item in execution.sources)
            failed = [
                item for item in execution.sources
                if item.status is Agent4N2SourceStatus.FAILED
            ]
            if failed or execution.total_chunks == 0:
                execution.status = Agent4N2ExecutionStatus.FAILED
                execution.failed_at = now
                execution.retryable = bool(failed)
                execution.error = Agent4N2Message(
                    code=("SOURCE_PREPARATION_FAILED" if failed else "NO_USABLE_CHUNKS"),
                    message=(
                        "One or more confirmed sources could not be prepared."
                        if failed
                        else "Input preparation produced no usable textual chunks."
                    ),
                )
                self._mark_n2_failed(record, now)
            else:
                execution.status = Agent4N2ExecutionStatus.COMPLETED
                execution.completed_at = now
                execution.retryable = False
                n2 = self._node(record, Agent4TestGenerationNodeId.INPUT_PREPARATION)
                n3 = self._node(record, Agent4TestGenerationNodeId.TESTING_INTELLIGENCE)
                n2.status = Agent4WorkflowNodeStatus.COMPLETED
                n2.updated_at = now
                n3.status = Agent4WorkflowNodeStatus.NOT_STARTED
                n3.updated_at = now
                record.current_node_id = Agent4TestGenerationNodeId.TESTING_INTELLIGENCE
                record.pipeline_status = Agent4PipelineStatus.RUNNING
            execution.updated_at = now
            record.updated_at = now
            self._workflow.save(record)

    def _fail_execution(self, project_id, owner_id, execution_id, code, message):
        with AGENT4_WORKFLOW_STATE_LOCK:
            record = self._require_record(project_id, owner_id)
            execution = self._execution(record, execution_id)
            if execution.status in {
                Agent4N2ExecutionStatus.COMPLETED,
                Agent4N2ExecutionStatus.FAILED,
                Agent4N2ExecutionStatus.INTERRUPTED,
            }:
                return
            now = self._clock()
            execution.status = Agent4N2ExecutionStatus.FAILED
            execution.failed_at = now
            execution.updated_at = now
            execution.retryable = True
            execution.error = Agent4N2Message(code=code, message=message)
            self._mark_n2_failed(record, now)
            self._workflow.save(record)

    def _mark_n2_failed(self, record, now):
        node = self._node(record, Agent4TestGenerationNodeId.INPUT_PREPARATION)
        node.status = Agent4WorkflowNodeStatus.FAILED
        node.updated_at = now
        record.pipeline_status = Agent4PipelineStatus.FAILED
        record.current_node_id = Agent4TestGenerationNodeId.INPUT_PREPARATION
        record.updated_at = now

    @staticmethod
    def _node(record, node_id):
        return next(node for node in record.nodes if node.node_id is node_id)

    @staticmethod
    def _source(execution, source_id):
        return next(source for source in execution.sources if source.source_id == source_id)

    @staticmethod
    def _execution(record, execution_id):
        execution = next(
            (item for item in record.n2_executions if item.execution_id == execution_id),
            None,
        )
        if execution is None:
            raise Agent4WorkflowGateError("Input Preparation execution is unavailable.")
        return execution

    @staticmethod
    def _current_execution(record):
        if record.current_n2_execution_id is None:
            return None
        return Agent4N2OrchestrationService._execution(
            record, record.current_n2_execution_id
        )

    @staticmethod
    def _require_confirmation(record):
        if record.n1_confirmation is None:
            raise Agent4WorkflowGateError(
                "Confirm Input and Output Setup before starting preparation."
            )
        return record.n1_confirmation

    def _require_record(self, project_id, owner_id):
        record = self._workflow.load(
            agent_project_id=project_id, owner_user_id=owner_id
        )
        if record is None:
            raise Agent4WorkflowGateError("Test Generation workflow is unavailable.")
        return record

    def _new_execution(
        self,
        record,
        confirmation,
        sources,
        *,
        trigger,
        now,
        retry_source_id=None,
    ):
        return Agent4N2Execution(
            execution_id=f"A4N2E-{uuid4().hex}",
            attempt_number=len(record.n2_executions) + 1,
            trigger=trigger,
            retry_source_id=retry_source_id,
            status=Agent4N2ExecutionStatus.QUEUED,
            confirmation_id=confirmation.confirmation_id,
            source_set_digest=confirmation.source_set_digest,
            selection_digest=confirmation.selection_digest,
            confirmed_source_ids=confirmation.source_ids,
            sources=sources,
            created_at=now,
            queued_at=now,
            updated_at=now,
        )

    def _queue(self, record, execution, now):
        record.n2_executions.append(execution)
        record.current_n2_execution_id = execution.execution_id
        record.pipeline_status = Agent4PipelineStatus.RUNNING
        record.current_node_id = Agent4TestGenerationNodeId.INPUT_PREPARATION
        node = self._node(record, Agent4TestGenerationNodeId.INPUT_PREPARATION)
        node.status = Agent4WorkflowNodeStatus.QUEUED
        node.updated_at = now
        record.updated_at = now
