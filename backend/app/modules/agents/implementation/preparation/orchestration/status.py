from app.modules.agents.implementation.contracts.enums import (
    ImplementationInputSourceType,
)
from .constants import ProjectPreparationStatus, SourcePreparationStatus
from .schemas import (
    PersistedPreparationSource,
    PreparationSourceStatus,
    ProjectPreparationRecord,
    ProjectPreparationStatusResponse,
)


ACTIVE_SOURCE_STATES = frozenset(
    {
        SourcePreparationStatus.EXTRACTING,
        SourcePreparationStatus.CHUNKING,
        SourcePreparationStatus.CLASSIFYING_RULES,
        SourcePreparationStatus.CLASSIFYING_MODEL,
        SourcePreparationStatus.BUILDING_HYBRID,
    }
)
COMPLETED_SOURCE_STATES = frozenset(
    {
        SourcePreparationStatus.READY,
        SourcePreparationStatus.WAITING_FOR_HUMAN,
    }
)
PROCESSED_SOURCE_STATES = COMPLETED_SOURCE_STATES | {
    SourcePreparationStatus.FAILED,
    SourcePreparationStatus.SKIPPED,
}


def derive_project_status(
    sources: list[PersistedPreparationSource],
) -> ProjectPreparationStatus:
    eligible = [
        source
        for source in sources
        if source.source_kind is not ImplementationInputSourceType.IMAGE
    ]
    if any(source.status in ACTIVE_SOURCE_STATES for source in eligible):
        return ProjectPreparationStatus.RUNNING
    failed = sum(
        source.status is SourcePreparationStatus.FAILED for source in eligible
    )
    usable = sum(source.status in COMPLETED_SOURCE_STATES for source in eligible)
    if failed and usable:
        return ProjectPreparationStatus.PARTIAL_FAILURE
    if failed and failed == len(eligible):
        return ProjectPreparationStatus.FAILED
    if any(
        source.status is SourcePreparationStatus.WAITING_FOR_HUMAN
        for source in eligible
    ):
        return ProjectPreparationStatus.WAITING_FOR_HUMAN
    if eligible and all(
        source.status is SourcePreparationStatus.READY for source in eligible
    ):
        return ProjectPreparationStatus.ANALYSIS_READY
    return ProjectPreparationStatus.NOT_STARTED


def public_status(
    record: ProjectPreparationRecord,
) -> ProjectPreparationStatusResponse:
    sources = [
        PreparationSourceStatus.model_validate(
            source.model_dump(exclude={"text_content"})
        )
        for source in record.sources
    ]
    eligible = [
        source
        for source in sources
        if source.source_kind is not ImplementationInputSourceType.IMAGE
    ]
    return ProjectPreparationStatusResponse(
        agent_project_id=record.agent_project_id,
        status=record.status,
        source_count=len(sources),
        eligible_source_count=len(eligible),
        processed_source_count=sum(
            source.status in PROCESSED_SOURCE_STATES for source in eligible
        ),
        completed_source_count=sum(
            source.status in COMPLETED_SOURCE_STATES for source in eligible
        ),
        active_source_count=sum(
            source.status in ACTIVE_SOURCE_STATES for source in eligible
        ),
        failed_source_count=sum(
            source.status is SourcePreparationStatus.FAILED
            for source in eligible
        ),
        sources=sources,
        requires_human_review=any(
            source.status is SourcePreparationStatus.WAITING_FOR_HUMAN
            for source in eligible
        ),
        human_review_source_count=sum(
            source.status is SourcePreparationStatus.WAITING_FOR_HUMAN
            for source in eligible
        ),
        started_at=record.started_at,
        updated_at=record.updated_at,
    )
