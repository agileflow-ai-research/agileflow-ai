from dataclasses import dataclass
from types import MappingProxyType
from typing import Protocol

from pydantic import ValidationError

from app.common.status import EventType, WorkflowStage
from app.database.collections import (
    BACKLOG_ITEMS,
    DESIGN_ARTIFACTS,
    EXECUTION_LOGS,
    IMPLEMENTATION_ARTIFACTS,
    REQUIREMENTS,
    TEST_CASES,
    TEST_RESULTS,
)
from app.modules.orchestrator.policy import (
    DESIGN_COMPONENT,
    IMPLEMENTATION_COMPONENT,
    ORCHESTRATOR_COMPONENT,
    REQUIREMENTS_COMPONENT,
    TESTING_COMPONENT,
)
from app.schemas.workflow import WorkflowEvent


@dataclass(frozen=True, slots=True)
class SpecialistHandoffRule:
    source_stage: WorkflowStage
    target_stage: WorkflowStage
    specialist_component: str
    evidence_collections: tuple[str, ...]


SPECIALIST_HANDOFF_RULES = MappingProxyType(
    {
        WorkflowStage.REQUIREMENTS_IN_PROGRESS: SpecialistHandoffRule(
            WorkflowStage.REQUIREMENTS_IN_PROGRESS,
            WorkflowStage.H1_WAITING_APPROVAL,
            REQUIREMENTS_COMPONENT,
            (REQUIREMENTS,),
        ),
        WorkflowStage.DESIGN_IN_PROGRESS: SpecialistHandoffRule(
            WorkflowStage.DESIGN_IN_PROGRESS,
            WorkflowStage.H2_WAITING_APPROVAL,
            DESIGN_COMPONENT,
            (DESIGN_ARTIFACTS, BACKLOG_ITEMS),
        ),
        WorkflowStage.TEST_PLANNING_IN_PROGRESS: SpecialistHandoffRule(
            WorkflowStage.TEST_PLANNING_IN_PROGRESS,
            WorkflowStage.H3_WAITING_APPROVAL,
            TESTING_COMPONENT,
            (TEST_CASES,),
        ),
        WorkflowStage.IMPLEMENTATION_IN_PROGRESS: SpecialistHandoffRule(
            WorkflowStage.IMPLEMENTATION_IN_PROGRESS,
            WorkflowStage.H4_WAITING_APPROVAL,
            IMPLEMENTATION_COMPONENT,
            (IMPLEMENTATION_ARTIFACTS, EXECUTION_LOGS),
        ),
        WorkflowStage.VALIDATION_IN_PROGRESS: SpecialistHandoffRule(
            WorkflowStage.VALIDATION_IN_PROGRESS,
            WorkflowStage.H5_WAITING_APPROVAL,
            TESTING_COMPONENT,
            (TEST_RESULTS,),
        ),
    }
)


class SpecialistReadinessRepository(Protocol):
    def list_artifact_generated_events(
        self,
        project_id: str,
    ) -> list[dict[str, object]]: ...

    def missing_project_evidence(
        self,
        project_id: str,
        collection_names: tuple[str, ...],
    ) -> tuple[str, ...]: ...


@dataclass(frozen=True, slots=True)
class SpecialistHandoffEvaluation:
    ready: bool
    readiness_event: WorkflowEvent | None
    missing_evidence: tuple[str, ...]
    detail: str | None = None


def _matching_readiness_event(
    document: dict[str, object],
    project_id: str,
    rule: SpecialistHandoffRule,
) -> WorkflowEvent | None:
    metadata = document.get("metadata")
    if not isinstance(metadata, dict):
        return None
    artifact_version = metadata.get("artifact_version")
    if type(artifact_version) is not int or artifact_version <= 0:
        return None
    if (
        document.get("project_id") != project_id
        or document.get("event_type")
        not in (EventType.ARTIFACT_GENERATED, EventType.ARTIFACT_GENERATED.value)
        or document.get("source_component") != rule.specialist_component
        or document.get("target_component") != ORCHESTRATOR_COMPONENT
        or metadata.get("handoff_ready") is not True
        or metadata.get("source_stage") != rule.source_stage.value
        or metadata.get("target_stage") != rule.target_stage.value
    ):
        return None
    try:
        return WorkflowEvent.model_validate(document)
    except ValidationError:
        return None


def evaluate_specialist_handoff(
    repository: SpecialistReadinessRepository,
    project_id: str,
    current_stage: WorkflowStage,
) -> SpecialistHandoffEvaluation:
    """Evaluate the canonical marker and evidence for one specialist handoff."""
    rule = SPECIALIST_HANDOFF_RULES.get(current_stage)
    if rule is None:
        return SpecialistHandoffEvaluation(
            ready=False,
            readiness_event=None,
            missing_evidence=(),
            detail="The current stage has no specialist handoff rule",
        )

    valid_events = [
        event
        for document in repository.list_artifact_generated_events(project_id)
        if (event := _matching_readiness_event(document, project_id, rule))
        is not None
    ]
    readiness_event = (
        max(valid_events, key=lambda event: (event.created_at, event.event_id))
        if valid_events
        else None
    )
    missing_evidence = repository.missing_project_evidence(
        project_id,
        rule.evidence_collections,
    )
    ready = readiness_event is not None and not missing_evidence
    if ready:
        detail = None
    elif readiness_event is None and missing_evidence:
        detail = (
            "A valid specialist readiness event and minimum persisted evidence "
            "are required"
        )
    elif readiness_event is None:
        detail = "A valid specialist readiness event is required"
    else:
        detail = (
            "Minimum persisted evidence is missing from: "
            + ", ".join(missing_evidence)
        )
    return SpecialistHandoffEvaluation(
        ready=ready,
        readiness_event=readiness_event,
        missing_evidence=missing_evidence,
        detail=detail,
    )
