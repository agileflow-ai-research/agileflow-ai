"""Sequential background runtime for one persisted N2 execution attempt."""

from collections.abc import Callable
from datetime import datetime

from app.modules.agents.requirements.infrastructure.storage import RequirementSourceStorage
from app.modules.agents.requirements.processing.facade import RequirementProcessingService
from app.modules.agents.requirements.processing.preparation.service import (
    EvidencePreparationService,
)
from app.modules.agents.requirements.workflow.contracts.n2 import (
    RequirementN2Error,
    RequirementN2Execution,
    RequirementN2SourceStatus,
    RequirementN2Status,
)
from app.modules.agents.requirements.workflow.contracts.record import (
    RequirementWorkflowRecord,
)
from app.modules.agents.requirements.workflow.orchestration.identity import (
    chunk_source_identity,
    n2_chunk_set_digest,
    snapshot_sources,
)
from app.modules.agents.requirements.workflow.orchestration.progression import (
    N2CompletionProgression,
    NoOpN2CompletionProgression,
)
from app.modules.agents.requirements.workflow.orchestration.transitions import (
    execution_by_id,
    fail_source,
    mark_blocked,
    mark_complete,
    mark_failed,
    mark_running,
    update_source_progress,
)
from app.modules.agents.requirements.workflow.service import (
    RequirementWorkflowGateError,
    source_set_digest,
)
from app.modules.agents.requirements.workflow.storage import (
    WORKFLOW_STATE_LOCK,
    RequirementWorkflowStorage,
)
from app.modules.auth.schemas import UserPublicResponse


class RequirementN2Runner:
    def __init__(
        self,
        source_storage: RequirementSourceStorage,
        workflow_storage: RequirementWorkflowStorage,
        processing_service: RequirementProcessingService,
        preparation_service: EvidencePreparationService,
        *,
        clock: Callable[[], datetime],
        progression: N2CompletionProgression | None = None,
    ) -> None:
        self._sources = source_storage
        self._states = workflow_storage
        self._processing = processing_service
        self._preparation = preparation_service
        self._clock = clock
        self._progression = progression or NoOpN2CompletionProgression()

    def run(
        self,
        agent_project_id: str,
        owner_user_id: str,
        execution_id: str,
        current_user: UserPublicResponse,
    ) -> None:
        try:
            execution = self._start(
                agent_project_id, owner_user_id, execution_id
            )
            if execution is None:
                return
            chunk_sources: list[dict[str, object]] = []
            total_chunks = 0
            for source in execution.input_sources:
                self._update_progress(
                    agent_project_id,
                    owner_user_id,
                    execution_id,
                    source.source_id,
                    processing_status=RequirementN2SourceStatus.RUNNING,
                )
                processing = self._processing.process(
                    agent_project_id, source.source_id, current_user, force=False
                )
                if processing.status.value != "COMPLETED":
                    self._fail_source(
                        agent_project_id,
                        owner_user_id,
                        execution_id,
                        source.source_id,
                        "SOURCE_PROCESSING_FAILED",
                        "A confirmed source could not be processed.",
                        processing=True,
                    )
                    return
                self._update_progress(
                    agent_project_id,
                    owner_user_id,
                    execution_id,
                    source.source_id,
                    processing_status=RequirementN2SourceStatus.COMPLETE,
                    preparation_status=RequirementN2SourceStatus.RUNNING,
                )
                preparation = self._preparation.prepare(
                    agent_project_id, source.source_id, current_user, force=False
                )
                if preparation.status.value != "COMPLETED":
                    self._fail_source(
                        agent_project_id,
                        owner_user_id,
                        execution_id,
                        source.source_id,
                        "EVIDENCE_PREPARATION_FAILED",
                        "Processed source evidence could not be prepared.",
                    )
                    return
                try:
                    chunks = self._preparation.get_chunks(
                        agent_project_id, source.source_id, current_user
                    )
                except Exception:
                    self._fail_source(
                        agent_project_id,
                        owner_user_id,
                        execution_id,
                        source.source_id,
                        "N2_RESULT_INVALID",
                        "Prepared evidence is missing or incompatible.",
                    )
                    return
                if not chunks.chunks:
                    self._fail_source(
                        agent_project_id,
                        owner_user_id,
                        execution_id,
                        source.source_id,
                        "N2_RESULT_INVALID",
                        "Prepared evidence did not contain any valid chunks.",
                    )
                    return
                chunk_count = len(chunks.chunks)
                total_chunks += chunk_count
                chunk_sources.append(chunk_source_identity(source, chunks))
                self._update_progress(
                    agent_project_id,
                    owner_user_id,
                    execution_id,
                    source.source_id,
                    processing_status=RequirementN2SourceStatus.COMPLETE,
                    preparation_status=RequirementN2SourceStatus.COMPLETE,
                    chunk_count=chunk_count,
                )
            with WORKFLOW_STATE_LOCK:
                record = self._require_record(agent_project_id, owner_user_id)
                persisted = self._require_execution(record, execution_id)
                mark_complete(
                    record,
                    persisted,
                    chunk_count=total_chunks,
                    chunk_set_digest=n2_chunk_set_digest(
                        persisted.confirmed_source_set_digest, chunk_sources
                    ),
                    completed_at=self._clock(),
                    updated_at=self._clock(),
                )
                self._states.save(record)
            try:
                self._progression.advance_after_n2_complete(
                    agent_project_id, owner_user_id, execution_id
                )
            except Exception:
                # N2 is already durable and must not be rolled back by N3 startup.
                pass
        except Exception:
            self.fail_execution(
                agent_project_id,
                owner_user_id,
                execution_id,
                "N2_EXECUTION_FAILED",
                "Evidence processing could not be completed and can be retried safely.",
            )

    def fail_execution(
        self,
        agent_project_id: str,
        owner_user_id: str,
        execution_id: str,
        code: str,
        message: str,
    ) -> None:
        with WORKFLOW_STATE_LOCK:
            record = self._require_record(agent_project_id, owner_user_id)
            execution = self._require_execution(record, execution_id)
            if execution.status in {
                RequirementN2Status.COMPLETE,
                RequirementN2Status.FAILED,
                RequirementN2Status.BLOCKED,
            }:
                return
            mark_failed(
                record,
                execution,
                RequirementN2Error(code=code, message=message),
                failed_at=self._clock(),
                updated_at=self._clock(),
            )
            self._states.save(record)

    def _start(
        self, agent_project_id: str, owner_user_id: str, execution_id: str
    ) -> RequirementN2Execution | None:
        with WORKFLOW_STATE_LOCK:
            record = self._states.load(
                agent_project_id=agent_project_id,
                owner_user_id=owner_user_id,
            )
            if record is None:
                return None
            execution = self._require_execution(record, execution_id)
            sources = self._sources.list_for_project(
                agent_project_id=agent_project_id,
                owner_user_id=owner_user_id,
            )
            if (
                source_set_digest(sources) != execution.confirmed_source_set_digest
                or snapshot_sources(sources) != execution.input_sources
            ):
                mark_blocked(
                    record,
                    execution,
                    failed_at=self._clock(),
                    updated_at=self._clock(),
                )
                self._states.save(record)
                return None
            mark_running(
                record,
                execution,
                started_at=self._clock(),
                updated_at=self._clock(),
            )
            self._states.save(record)
            return execution

    def _update_progress(
        self,
        agent_project_id: str,
        owner_user_id: str,
        execution_id: str,
        source_id: str,
        *,
        processing_status: RequirementN2SourceStatus | None = None,
        preparation_status: RequirementN2SourceStatus | None = None,
        chunk_count: int | None = None,
    ) -> None:
        with WORKFLOW_STATE_LOCK:
            record = self._require_record(agent_project_id, owner_user_id)
            execution = self._require_execution(record, execution_id)
            update_source_progress(
                record,
                execution,
                source_id,
                processing_status=processing_status,
                preparation_status=preparation_status,
                chunk_count=chunk_count,
                updated_at=self._clock(),
            )
            self._states.save(record)

    def _fail_source(
        self,
        agent_project_id: str,
        owner_user_id: str,
        execution_id: str,
        source_id: str,
        code: str,
        message: str,
        *,
        processing: bool = False,
    ) -> None:
        with WORKFLOW_STATE_LOCK:
            record = self._require_record(agent_project_id, owner_user_id)
            execution = self._require_execution(record, execution_id)
            fail_source(
                record,
                execution,
                source_id,
                RequirementN2Error(
                    code=code,
                    message=message,
                    affected_source_ids=[source_id],
                ),
                processing=processing,
                failed_at=self._clock(),
                updated_at=self._clock(),
            )
            self._states.save(record)

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

    @staticmethod
    def _require_execution(
        record: RequirementWorkflowRecord, execution_id: str
    ) -> RequirementN2Execution:
        execution = execution_by_id(record, execution_id)
        if execution is None:
            raise RequirementWorkflowGateError("N2 execution is unavailable")
        return execution
