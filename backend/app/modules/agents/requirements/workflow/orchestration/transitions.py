"""Deterministic mutations of persisted N2 workflow state."""

from datetime import datetime

from app.modules.agents.requirements.workflow.contracts.n2 import (
    RequirementN2Error,
    RequirementN2Execution,
    RequirementN2ResultSummary,
    RequirementN2SourceStatus,
    RequirementN2Status,
)
from app.modules.agents.requirements.workflow.contracts.record import (
    RequirementWorkflowRecord,
)


def execution_by_id(
    record: RequirementWorkflowRecord, execution_id: str
) -> RequirementN2Execution | None:
    return next(
        (
            execution
            for execution in record.n2_executions
            if execution.execution_id == execution_id
        ),
        None,
    )


def current_execution(
    record: RequirementWorkflowRecord,
) -> RequirementN2Execution | None:
    if record.current_n2_execution_id is None:
        return None
    return execution_by_id(record, record.current_n2_execution_id)


def queue_execution(
    record: RequirementWorkflowRecord,
    execution: RequirementN2Execution,
    *,
    updated_at: datetime,
) -> None:
    record.n2_executions.append(execution)
    record.current_n2_execution_id = execution.execution_id
    record.updated_at = updated_at


def mark_running(
    record: RequirementWorkflowRecord,
    execution: RequirementN2Execution,
    *,
    started_at: datetime,
    updated_at: datetime,
) -> None:
    execution.status = RequirementN2Status.RUNNING
    execution.started_at = started_at
    record.updated_at = updated_at


def update_source_progress(
    record: RequirementWorkflowRecord,
    execution: RequirementN2Execution,
    source_id: str,
    *,
    updated_at: datetime,
    processing_status: RequirementN2SourceStatus | None = None,
    preparation_status: RequirementN2SourceStatus | None = None,
    chunk_count: int | None = None,
) -> None:
    progress = next(
        item for item in execution.source_progress if item.source_id == source_id
    )
    if processing_status is not None:
        progress.processing_status = processing_status
    if preparation_status is not None:
        progress.preparation_status = preparation_status
    if chunk_count is not None:
        progress.chunk_count = chunk_count
    record.updated_at = updated_at


def mark_failed(
    record: RequirementWorkflowRecord,
    execution: RequirementN2Execution,
    error: RequirementN2Error,
    *,
    failed_at: datetime,
    updated_at: datetime,
) -> None:
    execution.status = RequirementN2Status.FAILED
    execution.failed_at = failed_at
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
    record.updated_at = updated_at


def fail_source(
    record: RequirementWorkflowRecord,
    execution: RequirementN2Execution,
    source_id: str,
    error: RequirementN2Error,
    *,
    processing: bool,
    failed_at: datetime,
    updated_at: datetime,
) -> None:
    progress = next(
        item for item in execution.source_progress if item.source_id == source_id
    )
    if processing:
        progress.processing_status = RequirementN2SourceStatus.FAILED
    else:
        progress.preparation_status = RequirementN2SourceStatus.FAILED
    progress.error = error
    mark_failed(
        record,
        execution,
        error,
        failed_at=failed_at,
        updated_at=updated_at,
    )


def mark_blocked(
    record: RequirementWorkflowRecord,
    execution: RequirementN2Execution,
    *,
    failed_at: datetime,
    updated_at: datetime,
) -> None:
    execution.status = RequirementN2Status.BLOCKED
    execution.failed_at = failed_at
    execution.retryable = False
    execution.error = RequirementN2Error(
        code="N2_INPUT_STALE",
        message="The confirmed source set changed before evidence processing began.",
    )
    record.updated_at = updated_at


def mark_interrupted(
    record: RequirementWorkflowRecord,
    execution: RequirementN2Execution,
    *,
    failed_at: datetime,
    updated_at: datetime,
) -> None:
    execution.status = RequirementN2Status.FAILED
    execution.failed_at = failed_at
    execution.retryable = True
    execution.error = RequirementN2Error(
        code="N2_EXECUTION_INTERRUPTED",
        message="Evidence processing was interrupted and can be retried safely.",
    )
    record.updated_at = updated_at


def mark_complete(
    record: RequirementWorkflowRecord,
    execution: RequirementN2Execution,
    *,
    chunk_count: int,
    chunk_set_digest: str,
    completed_at: datetime,
    updated_at: datetime,
) -> None:
    execution.status = RequirementN2Status.COMPLETE
    execution.completed_at = completed_at
    execution.retryable = False
    execution.result_summary = RequirementN2ResultSummary(
        source_count=len(execution.input_sources),
        completed_source_count=len(execution.input_sources),
        chunk_count=chunk_count,
    )
    execution.chunk_set_digest = chunk_set_digest
    record.updated_at = updated_at
