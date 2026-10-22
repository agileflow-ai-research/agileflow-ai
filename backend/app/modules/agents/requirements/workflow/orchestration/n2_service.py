"""Commands, replay rules, and executor ownership for N2 orchestration."""

from collections.abc import Callable
from concurrent.futures import Executor
from datetime import datetime, timezone
from threading import Lock

from app.modules.agents.requirements.infrastructure.storage import RequirementSourceStorage
from app.modules.agents.requirements.inputs.upload.service import require_requirements_project
from app.modules.agents.requirements.processing.facade import RequirementProcessingService
from app.modules.agents.requirements.processing.preparation.service import (
    EvidencePreparationService,
)
from app.modules.agents.requirements.workflow.contracts.n2 import (
    RequirementN2Execution,
    RequirementN2Status,
)
from app.modules.agents.requirements.workflow.contracts.record import (
    RequirementWorkflowRecord,
)
from app.modules.agents.requirements.workflow.contracts.responses import (
    RequirementWorkflowResponse,
)
from app.modules.agents.requirements.workflow.executor import AGENT1_N2_EXECUTOR
from app.modules.agents.requirements.workflow.orchestration.identity import (
    build_queued_execution,
    n2_execution_key,
)
from app.modules.agents.requirements.workflow.orchestration.n2_runner import (
    RequirementN2Runner,
)
from app.modules.agents.requirements.workflow.orchestration.progression import (
    N2CompletionProgression,
    NoOpN2CompletionProgression,
)
from app.modules.agents.requirements.workflow.orchestration.transitions import (
    current_execution,
    mark_interrupted,
    queue_execution,
)
from app.modules.agents.requirements.workflow.projection import (
    build_workflow_response,
    confirmation_is_current,
)
from app.modules.agents.requirements.workflow.service import (
    RequirementWorkflowGateError,
    RequirementWorkflowService,
    source_set_digest,
)
from app.modules.agents.requirements.workflow.storage import (
    WORKFLOW_STATE_LOCK,
    RequirementWorkflowStorage,
)
from app.modules.auth.schemas import UserPublicResponse
from app.modules.standalone.service import StandaloneService


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class RequirementN2OrchestrationService:
    """Coordinate N2 commands while the runner owns source execution."""

    _active_lock = Lock()
    _active_execution_ids: set[str] = set()

    def __init__(
        self,
        standalone_service: StandaloneService,
        source_storage: RequirementSourceStorage,
        workflow_storage: RequirementWorkflowStorage,
        workflow_service: RequirementWorkflowService,
        processing_service: RequirementProcessingService,
        preparation_service: EvidencePreparationService,
        *,
        executor: Executor = AGENT1_N2_EXECUTOR,
        clock: Callable[[], datetime] = utc_now,
        progression: N2CompletionProgression | None = None,
    ) -> None:
        self._standalone = standalone_service
        self._sources = source_storage
        self._states = workflow_storage
        self._workflow = workflow_service
        self._executor = executor
        self._clock = clock
        self._progression = progression or NoOpN2CompletionProgression()
        self._runner = RequirementN2Runner(
            source_storage,
            workflow_storage,
            processing_service,
            preparation_service,
            clock=clock,
            progression=self._progression,
        )

    def get_workflow(
        self, agent_project_id: str, current_user: UserPublicResponse
    ) -> RequirementWorkflowResponse:
        self._workflow.get(agent_project_id, current_user)
        with WORKFLOW_STATE_LOCK:
            record, source_count = self._load_record(agent_project_id, current_user)
            execution = current_execution(record)
            if execution and execution.status in {
                RequirementN2Status.QUEUED,
                RequirementN2Status.RUNNING,
            }:
                with self._active_lock:
                    active = execution.execution_id in self._active_execution_ids
                if not active:
                    mark_interrupted(
                        record,
                        execution,
                        failed_at=self._clock(),
                        updated_at=self._clock(),
                    )
                    self._states.save(record)
            completed_execution_id = (
                execution.execution_id
                if execution and execution.status is RequirementN2Status.COMPLETE
                else None
            )
        if completed_execution_id:
            try:
                self._progression.advance_after_n2_complete(
                    agent_project_id, current_user.user_id, completed_execution_id
                )
            except Exception:
                pass
        with WORKFLOW_STATE_LOCK:
            record, source_count = self._load_record(agent_project_id, current_user)
            return build_workflow_response(record, source_count)

    def continue_n1_and_start(
        self, agent_project_id: str, current_user: UserPublicResponse
    ) -> RequirementWorkflowResponse:
        with WORKFLOW_STATE_LOCK:
            self._workflow.continue_n1(agent_project_id, current_user)
            record, source_count = self._load_record(agent_project_id, current_user)
            confirmation = record.n1_confirmation
            if not confirmation or not confirmation_is_current(record):
                raise RequirementWorkflowGateError(
                    "N1 confirmation is stale; confirm the current inputs before starting N2"
                )
            key = n2_execution_key(
                agent_project_id,
                confirmation.source_set_digest,
                confirmation.selection_digest,
            )
            existing = next(
                (
                    item
                    for item in reversed(record.n2_executions)
                    if item.execution_key == key
                ),
                None,
            )
            if existing is not None:
                record.current_n2_execution_id = existing.execution_id
                self._states.save(record)
                return build_workflow_response(record, source_count)
            sources = self._sources.list_for_project(
                agent_project_id=agent_project_id,
                owner_user_id=current_user.user_id,
            )
            if source_set_digest(sources) != confirmation.source_set_digest:
                raise RequirementWorkflowGateError(
                    "The confirmed source set is stale; reconfirm N1 before starting N2"
                )
            execution = build_queued_execution(
                key=key,
                confirmed_source_set_digest=confirmation.source_set_digest,
                confirmed_selection_digest=confirmation.selection_digest,
                sources=sources,
                attempt_number=1,
                created_at=self._clock(),
            )
            queue_execution(record, execution, updated_at=self._clock())
            self._states.save(record)
            self._submit(record, execution, current_user)
            return build_workflow_response(record, source_count)

    def retry(
        self, agent_project_id: str, current_user: UserPublicResponse
    ) -> RequirementWorkflowResponse:
        with WORKFLOW_STATE_LOCK:
            self._workflow.get(agent_project_id, current_user)
            record, source_count = self._load_record(agent_project_id, current_user)
            previous = current_execution(record)
            if previous is None:
                raise RequirementWorkflowGateError("No N2 execution is available to retry")
            confirmation = record.n1_confirmation
            if (
                not confirmation
                or not confirmation_is_current(record)
                or previous.confirmed_source_set_digest
                != confirmation.source_set_digest
                or previous.confirmed_selection_digest
                != confirmation.selection_digest
            ):
                raise RequirementWorkflowGateError(
                    "N1 inputs changed; reconfirm N1 before starting a new N2 execution"
                )
            if previous.status in {
                RequirementN2Status.QUEUED,
                RequirementN2Status.RUNNING,
                RequirementN2Status.COMPLETE,
            }:
                return build_workflow_response(record, source_count)
            sources = self._sources.list_for_project(
                agent_project_id=agent_project_id,
                owner_user_id=current_user.user_id,
            )
            if source_set_digest(sources) != previous.confirmed_source_set_digest:
                raise RequirementWorkflowGateError(
                    "The confirmed source set changed; reconfirm N1 before retrying N2"
                )
            execution = build_queued_execution(
                key=previous.execution_key,
                confirmed_source_set_digest=confirmation.source_set_digest,
                confirmed_selection_digest=confirmation.selection_digest,
                sources=sources,
                attempt_number=previous.attempt_number + 1,
                created_at=self._clock(),
            )
            queue_execution(record, execution, updated_at=self._clock())
            self._states.save(record)
            self._submit(record, execution, current_user)
            return build_workflow_response(record, source_count)

    def _submit(
        self,
        record: RequirementWorkflowRecord,
        execution: RequirementN2Execution,
        current_user: UserPublicResponse,
    ) -> None:
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
            self._runner.fail_execution(
                record.agent_project_id,
                record.owner_user_id,
                execution.execution_id,
                "N2_EXECUTOR_UNAVAILABLE",
                "Evidence processing could not be started and can be retried safely.",
            )

    def _run(
        self,
        agent_project_id: str,
        owner_user_id: str,
        execution_id: str,
        current_user: UserPublicResponse,
    ) -> None:
        try:
            self._runner.run(
                agent_project_id,
                owner_user_id,
                execution_id,
                current_user,
            )
        finally:
            with self._active_lock:
                self._active_execution_ids.discard(execution_id)

    def _load_record(
        self, agent_project_id: str, current_user: UserPublicResponse
    ) -> tuple[RequirementWorkflowRecord, int]:
        project = require_requirements_project(
            self._standalone, agent_project_id, current_user
        )
        sources = self._sources.list_for_project(
            agent_project_id=project.agent_project_id,
            owner_user_id=current_user.user_id,
        )
        return (
            self._require_record(project.agent_project_id, current_user.user_id),
            len(sources),
        )

    def _require_record(
        self, agent_project_id: str, owner_user_id: str
    ) -> RequirementWorkflowRecord:
        record = self._states.load(
            agent_project_id=agent_project_id,
            owner_user_id=owner_user_id,
        )
        if record is None:
            raise RequirementWorkflowGateError("Requirements workflow is unavailable")
        return record

