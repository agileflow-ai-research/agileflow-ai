"""Pure Testing Intelligence sub-stage progression and status derivation."""

from app.modules.agents.testing_validation.workflow.schemas import (
    Agent4N3ExecutionStatus,
    Agent4N3SubStageName,
    Agent4N3SubStageProgress,
    Agent4N3SubStageStatus,
)


N3_SUB_STAGE_ORDER = tuple(Agent4N3SubStageName)
SUCCESSFUL_SUB_STAGE_STATUSES = {
    Agent4N3SubStageStatus.COMPLETED,
    Agent4N3SubStageStatus.NOT_APPLICABLE,
}
ACTIVE_SUB_STAGE_STATUSES = {
    Agent4N3SubStageStatus.QUEUED,
    Agent4N3SubStageStatus.RUNNING,
}


def new_n3_sub_stages() -> list[Agent4N3SubStageProgress]:
    return [Agent4N3SubStageProgress(stage=stage) for stage in N3_SUB_STAGE_ORDER]


def get_next_n3_substage(
    stages: list[Agent4N3SubStageProgress],
) -> Agent4N3SubStageName | None:
    """Return the first non-success checkpoint in canonical dependency order."""
    by_name = {item.stage: item for item in stages}
    for name in N3_SUB_STAGE_ORDER:
        item = by_name.get(name)
        if item is None or item.status not in SUCCESSFUL_SUB_STAGE_STATUSES:
            return name
    return None


def derive_n3_execution_status(
    stages: list[Agent4N3SubStageProgress],
) -> Agent4N3ExecutionStatus:
    statuses = {item.status for item in stages}
    if Agent4N3SubStageStatus.FAILED in statuses:
        return Agent4N3ExecutionStatus.FAILED
    if Agent4N3SubStageStatus.INTERRUPTED in statuses:
        return Agent4N3ExecutionStatus.INTERRUPTED
    if Agent4N3SubStageStatus.WAITING_FOR_HUMAN in statuses:
        return Agent4N3ExecutionStatus.WAITING_FOR_HUMAN
    if Agent4N3SubStageStatus.RUNNING in statuses:
        return Agent4N3ExecutionStatus.RUNNING
    if Agent4N3SubStageStatus.QUEUED in statuses:
        return Agent4N3ExecutionStatus.QUEUED
    if stages and all(
        item.status in SUCCESSFUL_SUB_STAGE_STATUSES for item in stages
    ):
        return Agent4N3ExecutionStatus.COMPLETED
    return Agent4N3ExecutionStatus.QUEUED
