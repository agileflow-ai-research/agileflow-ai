from datetime import datetime

from app.modules.agents.requirements.workflow.contracts.n3 import (
    RequirementN3Error, RequirementN3Execution, RequirementN3ResultSummary,
    RequirementN3Status,
)


def n3_execution_by_id(record, execution_id):
    return next((item for item in record.n3_executions if item.execution_id == execution_id), None)


def current_n3_execution(record):
    return n3_execution_by_id(record, record.current_n3_execution_id) if record.current_n3_execution_id else None


def queue_n3(record, execution, *, updated_at):
    record.n3_executions.append(execution)
    record.current_n3_execution_id = execution.execution_id
    record.updated_at = updated_at


def mark_n3_running(record, execution, *, started_at, updated_at):
    execution.status = RequirementN3Status.RUNNING
    execution.started_at = started_at
    record.updated_at = updated_at


def mark_n3_complete(record, execution, summary: RequirementN3ResultSummary, *, completed_at, updated_at):
    execution.status = RequirementN3Status.COMPLETE
    execution.completed_at = completed_at
    execution.retryable = False
    execution.result_summary = summary
    record.updated_at = updated_at


def mark_n3_failed(record, execution, code, message, *, failed_at, updated_at, retryable=True):
    execution.status = RequirementN3Status.FAILED
    execution.failed_at = failed_at
    execution.retryable = retryable
    execution.error = RequirementN3Error(code=code, message=message)
    record.updated_at = updated_at


def mark_n3_blocked(record, execution, *, failed_at, updated_at):
    execution.status = RequirementN3Status.BLOCKED
    execution.failed_at = failed_at
    execution.retryable = False
    execution.error = RequirementN3Error(
        code="N3_INPUT_STALE",
        message="The authoritative N2 input changed before discovery completed.",
    )
    record.updated_at = updated_at


def mark_n3_interrupted(record, execution, *, failed_at, updated_at):
    mark_n3_failed(
        record, execution, "N3_EXECUTION_INTERRUPTED",
        "Requirement discovery was interrupted and can be retried safely.",
        failed_at=failed_at, updated_at=updated_at,
    )
