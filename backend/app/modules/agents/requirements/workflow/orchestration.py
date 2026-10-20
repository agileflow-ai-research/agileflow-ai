from concurrent.futures import Executor
from datetime import datetime, timezone
from threading import Lock

from app.modules.agents.requirements.infrastructure.digests import stable_json_sha256
from app.modules.agents.requirements.infrastructure.storage import RequirementSourceStorage
from app.modules.agents.requirements.inputs.upload.service import require_requirements_project
from app.modules.agents.requirements.processing.facade import RequirementProcessingService
from app.modules.agents.requirements.processing.preparation.service import EvidencePreparationService
from app.modules.agents.requirements.workflow.constants import (
    N2_CHUNK_SET_CONTRACT_VERSION,
    N2_NODE_ID,
    N2_NODE_VERSION,
    N2_ORCHESTRATION_CONTRACT_VERSION,
)
from app.modules.agents.requirements.workflow.executor import AGENT1_N2_EXECUTOR
from app.modules.agents.requirements.workflow.schemas import (
    RequirementN2Error,
    RequirementN2Execution,
    RequirementN2ResultSummary,
    RequirementN2SourceProgress,
    RequirementN2SourceSnapshot,
    RequirementN2SourceStatus,
    RequirementN2Status,
    RequirementWorkflowRecord,
    RequirementWorkflowResponse,
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


def _canonical_digest(payload: dict[str, object]) -> str:
    return stable_json_sha256(payload)


def n2_execution_key(
    agent_project_id: str,
    confirmed_source_set_digest: str,
    confirmed_selection_digest: str,
) -> str:
    return _canonical_digest(
        {
            "agent_project_id": agent_project_id,
            "contract_version": N2_ORCHESTRATION_CONTRACT_VERSION,
            "node_id": N2_NODE_ID,
            "node_version": N2_NODE_VERSION,
            "source_set_digest": confirmed_source_set_digest,
            "selection_digest": confirmed_selection_digest,
        }
    )


def n2_chunk_set_digest(
    confirmed_source_set_digest: str,
    source_chunks: list[dict[str, object]],
) -> str:
    return _canonical_digest(
        {
            "contract_version": N2_CHUNK_SET_CONTRACT_VERSION,
            "node_version": N2_NODE_VERSION,
            "source_set_digest": confirmed_source_set_digest,
            "sources": sorted(source_chunks, key=lambda item: str(item["source_id"])),
        }
    )


class RequirementN2OrchestrationService:
    """Sequential, resumable orchestration over the frozen N2 services."""

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
        clock=utc_now,
    ) -> None:
        self._standalone = standalone_service
        self._sources = source_storage
        self._states = workflow_storage
        self._workflow = workflow_service
        self._processing = processing_service
        self._preparation = preparation_service
        self._executor = executor
        self._clock = clock

    def get_workflow(
        self, agent_project_id: str, current_user: UserPublicResponse
    ) -> RequirementWorkflowResponse:
        self._workflow.get(agent_project_id, current_user)
        with WORKFLOW_STATE_LOCK:
            record, source_count = self._load_record(agent_project_id, current_user)
            execution = self._current_execution(record)
            if execution and execution.status in {
                RequirementN2Status.QUEUED,
                RequirementN2Status.RUNNING,
            }:
                with self._active_lock:
                    active = execution.execution_id in self._active_execution_ids
                if not active:
                    execution.status = RequirementN2Status.FAILED
                    execution.failed_at = self._clock()
                    execution.retryable = True
                    execution.error = RequirementN2Error(
                        code="N2_EXECUTION_INTERRUPTED",
                        message="Evidence processing was interrupted and can be retried safely.",
                    )
                    record.updated_at = self._clock()
                    self._states.save(record)
            return self._workflow._response(record, source_count)

    def continue_n1_and_start(
        self, agent_project_id: str, current_user: UserPublicResponse
    ) -> RequirementWorkflowResponse:
        with WORKFLOW_STATE_LOCK:
            self._workflow.continue_n1(agent_project_id, current_user)
            record, source_count = self._load_record(agent_project_id, current_user)
            confirmation = record.n1_confirmation
            if not confirmation or not self._workflow._confirmation_current(record):
                raise RequirementWorkflowGateError(
                    "N1 confirmation is stale; confirm the current inputs before starting N2"
                )
            key = n2_execution_key(
                agent_project_id,
                confirmation.source_set_digest,
                confirmation.selection_digest,
            )
            existing = next(
                (item for item in reversed(record.n2_executions) if item.execution_key == key),
                None,
            )
            if existing is not None:
                record.current_n2_execution_id = existing.execution_id
                self._states.save(record)
                return self._workflow._response(record, source_count)
            sources = self._sources.list_for_project(
                agent_project_id=agent_project_id,
                owner_user_id=current_user.user_id,
            )
            if source_set_digest(sources) != confirmation.source_set_digest:
                raise RequirementWorkflowGateError(
                    "The confirmed source set is stale; reconfirm N1 before starting N2"
                )
            execution = self._new_execution(key, confirmation, sources, attempt_number=1)
            record.n2_executions.append(execution)
            record.current_n2_execution_id = execution.execution_id
            record.updated_at = self._clock()
            self._states.save(record)
            self._submit(record, execution, current_user)
            return self._workflow._response(record, source_count)

    def retry(
        self, agent_project_id: str, current_user: UserPublicResponse
    ) -> RequirementWorkflowResponse:
        with WORKFLOW_STATE_LOCK:
            self._workflow.get(agent_project_id, current_user)
            record, source_count = self._load_record(agent_project_id, current_user)
            previous = self._current_execution(record)
            if previous is None:
                raise RequirementWorkflowGateError("No N2 execution is available to retry")
            confirmation = record.n1_confirmation
            if (
                not confirmation
                or not self._workflow._confirmation_current(record)
                or previous.confirmed_source_set_digest != confirmation.source_set_digest
                or previous.confirmed_selection_digest != confirmation.selection_digest
            ):
                raise RequirementWorkflowGateError(
                    "N1 inputs changed; reconfirm N1 before starting a new N2 execution"
                )
            if previous.status in {
                RequirementN2Status.QUEUED,
                RequirementN2Status.RUNNING,
                RequirementN2Status.COMPLETE,
            }:
                return self._workflow._response(record, source_count)
            sources = self._sources.list_for_project(
                agent_project_id=agent_project_id,
                owner_user_id=current_user.user_id,
            )
            if source_set_digest(sources) != previous.confirmed_source_set_digest:
                raise RequirementWorkflowGateError(
                    "The confirmed source set changed; reconfirm N1 before retrying N2"
                )
            execution = self._new_execution(
                previous.execution_key,
                confirmation,
                sources,
                attempt_number=previous.attempt_number + 1,
            )
            record.n2_executions.append(execution)
            record.current_n2_execution_id = execution.execution_id
            record.updated_at = self._clock()
            self._states.save(record)
            self._submit(record, execution, current_user)
            return self._workflow._response(record, source_count)

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
            self._fail_execution(
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
            with WORKFLOW_STATE_LOCK:
                record = self._states.load(
                    agent_project_id=agent_project_id,
                    owner_user_id=owner_user_id,
                )
                if record is None:
                    return
                execution = self._execution(record, execution_id)
                sources = self._sources.list_for_project(
                    agent_project_id=agent_project_id,
                    owner_user_id=owner_user_id,
                )
                if (
                    source_set_digest(sources) != execution.confirmed_source_set_digest
                    or self._snapshot(sources) != execution.input_sources
                ):
                    self._mark_blocked(record, execution)
                    return
                execution.status = RequirementN2Status.RUNNING
                execution.started_at = self._clock()
                record.updated_at = self._clock()
                self._states.save(record)

            chunk_sources: list[dict[str, object]] = []
            total_chunks = 0
            for source in execution.input_sources:
                self._set_source_progress(
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
                self._set_source_progress(
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
                chunk_sources.append(
                    {
                        "source_id": source.source_id,
                        "source_sha256": source.sha256,
                        "parent_result_fingerprint": chunks.parent_result_fingerprint,
                        "normalizer_version": chunks.normalizer_version,
                        "chunker_fingerprint": chunks.chunker.fingerprint,
                        "chunk_ids": sorted(chunk.chunk_id for chunk in chunks.chunks),
                    }
                )
                self._set_source_progress(
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
                execution = self._execution(record, execution_id)
                execution.status = RequirementN2Status.COMPLETE
                execution.completed_at = self._clock()
                execution.retryable = False
                execution.result_summary = RequirementN2ResultSummary(
                    source_count=len(execution.input_sources),
                    completed_source_count=len(execution.input_sources),
                    chunk_count=total_chunks,
                )
                execution.chunk_set_digest = n2_chunk_set_digest(
                    execution.confirmed_source_set_digest, chunk_sources
                )
                record.updated_at = self._clock()
                self._states.save(record)
        except Exception:
            self._fail_execution(
                agent_project_id,
                owner_user_id,
                execution_id,
                "N2_EXECUTION_FAILED",
                "Evidence processing could not be completed and can be retried safely.",
            )
        finally:
            with self._active_lock:
                self._active_execution_ids.discard(execution_id)

    def _new_execution(self, key, confirmation, sources, *, attempt_number):
        now = self._clock()
        snapshot = self._snapshot(sources)
        return RequirementN2Execution(
            node_version=N2_NODE_VERSION,
            execution_id=f"N2-{key[:16].upper()}-{attempt_number:03d}",
            attempt_id=f"ATT-{attempt_number:03d}",
            execution_key=key,
            attempt_number=attempt_number,
            status=RequirementN2Status.QUEUED,
            confirmed_source_set_digest=confirmation.source_set_digest,
            confirmed_selection_digest=confirmation.selection_digest,
            input_sources=snapshot,
            source_progress=[
                RequirementN2SourceProgress(source_id=source.source_id)
                for source in snapshot
            ],
            created_at=now,
        )

    @staticmethod
    def _snapshot(sources):
        return sorted(
            [
                RequirementN2SourceSnapshot(
                    source_id=source.source_id,
                    source_type=source.source_type.value,
                    sha256=source.sha256,
                )
                for source in sources
            ],
            key=lambda source: source.source_id,
        )

    def _load_record(self, agent_project_id, current_user):
        project = require_requirements_project(
            self._standalone, agent_project_id, current_user
        )
        sources = self._sources.list_for_project(
            agent_project_id=project.agent_project_id,
            owner_user_id=current_user.user_id,
        )
        return self._require_record(project.agent_project_id, current_user.user_id), len(sources)

    def _require_record(self, agent_project_id, owner_user_id):
        record = self._states.load(
            agent_project_id=agent_project_id, owner_user_id=owner_user_id
        )
        if record is None:
            raise RequirementWorkflowGateError("Requirements workflow is unavailable")
        return record

    @staticmethod
    def _execution(record, execution_id):
        for execution in record.n2_executions:
            if execution.execution_id == execution_id:
                return execution
        raise RequirementWorkflowGateError("N2 execution is unavailable")

    def _current_execution(self, record):
        if record.current_n2_execution_id is None:
            return None
        return self._execution(record, record.current_n2_execution_id)

    def _set_source_progress(
        self,
        agent_project_id,
        owner_user_id,
        execution_id,
        source_id,
        *,
        processing_status=None,
        preparation_status=None,
        chunk_count=None,
    ):
        with WORKFLOW_STATE_LOCK:
            record = self._require_record(agent_project_id, owner_user_id)
            execution = self._execution(record, execution_id)
            progress = next(item for item in execution.source_progress if item.source_id == source_id)
            if processing_status is not None:
                progress.processing_status = processing_status
            if preparation_status is not None:
                progress.preparation_status = preparation_status
            if chunk_count is not None:
                progress.chunk_count = chunk_count
            record.updated_at = self._clock()
            self._states.save(record)

    def _fail_source(
        self,
        agent_project_id,
        owner_user_id,
        execution_id,
        source_id,
        code,
        message,
        *,
        processing=False,
    ):
        with WORKFLOW_STATE_LOCK:
            record = self._require_record(agent_project_id, owner_user_id)
            execution = self._execution(record, execution_id)
            error = RequirementN2Error(
                code=code, message=message, affected_source_ids=[source_id]
            )
            progress = next(item for item in execution.source_progress if item.source_id == source_id)
            if processing:
                progress.processing_status = RequirementN2SourceStatus.FAILED
            else:
                progress.preparation_status = RequirementN2SourceStatus.FAILED
            progress.error = error
            self._mark_failed(record, execution, error)

    def _fail_execution(
        self, agent_project_id, owner_user_id, execution_id, code, message
    ):
        try:
            with WORKFLOW_STATE_LOCK:
                record = self._require_record(agent_project_id, owner_user_id)
                execution = self._execution(record, execution_id)
                if execution.status in {
                    RequirementN2Status.COMPLETE,
                    RequirementN2Status.FAILED,
                    RequirementN2Status.BLOCKED,
                }:
                    return
                self._mark_failed(
                    record,
                    execution,
                    RequirementN2Error(code=code, message=message),
                )
        except Exception:
            return

    def _mark_failed(self, record, execution, error):
        execution.status = RequirementN2Status.FAILED
        execution.failed_at = self._clock()
        execution.retryable = True
        execution.error = error
        execution.result_summary = RequirementN2ResultSummary(
            source_count=len(execution.input_sources),
            completed_source_count=sum(
                item.preparation_status is RequirementN2SourceStatus.COMPLETE
                for item in execution.source_progress
            ),
            chunk_count=sum(item.chunk_count for item in execution.source_progress),
        )
        record.updated_at = self._clock()
        self._states.save(record)

    def _mark_blocked(self, record, execution):
        execution.status = RequirementN2Status.BLOCKED
        execution.failed_at = self._clock()
        execution.retryable = False
        execution.error = RequirementN2Error(
            code="N2_INPUT_STALE",
            message="The confirmed source set changed before evidence processing began.",
        )
        record.updated_at = self._clock()
        self._states.save(record)
