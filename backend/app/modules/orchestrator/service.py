from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone

from pydantic import ValidationError

from app.common.id_generator import generate_id
from app.common.status import ApprovalDecision, EventType, WorkflowStage
from app.modules.auth.authorization import (
    ProjectAccessNotFoundError,
    authorize_project_access,
)
from app.modules.auth.schemas import UserPublicResponse
from app.modules.orchestrator.policy import (
    HUMAN_REVIEWER_COMPONENT,
    ORCHESTRATOR_COMPONENT,
    TransitionDefinition,
    TransitionPrerequisite,
    get_stage_owner,
    get_transition,
)
from app.modules.orchestrator.repository import (
    OrchestratorRepository,
    OrchestratorRepositoryError,
)
from app.modules.orchestrator.readiness import (
    SpecialistHandoffEvaluation,
    evaluate_specialist_handoff,
)
from app.modules.orchestrator.schemas import (
    WorkflowSnapshot,
    WorkflowTransitionResult,
)
from app.schemas.approval import Approval
from app.schemas.project import Project
from app.schemas.workflow import WorkflowEvent


class UnsupportedWorkflowStageError(ValueError):
    """Raised when this foundation cannot advance the current stage."""

    def __init__(self, current_stage: WorkflowStage) -> None:
        self.current_stage = current_stage
        super().__init__(
            f"Transition from {current_stage.value} is not supported"
        )


class MissingClientInputError(ValueError):
    """Raised when the first transition has no project ClientInput."""


class ApprovalPrerequisiteError(ValueError):
    """Raised when the effective gate decision does not allow progression."""

    def __init__(self, current_stage: WorkflowStage, detail: str) -> None:
        self.current_stage = current_stage
        super().__init__(detail)


class SpecialistHandoffPrerequisiteError(ValueError):
    """Raised when specialist readiness evidence is incomplete."""

    def __init__(self, current_stage: WorkflowStage, detail: str) -> None:
        self.current_stage = current_stage
        super().__init__(detail)


class OrchestratorServiceError(RuntimeError):
    """Raised when a workflow transition cannot be completed safely."""


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True, slots=True)
class PrerequisiteEvaluation:
    satisfied: bool
    approval: Approval | None = None
    specialist_handoff: SpecialistHandoffEvaluation | None = None
    detail: str | None = None


class OrchestratorService:
    """Core workflow reads and the first executable transition."""

    def __init__(
        self,
        repository: OrchestratorRepository,
        clock: Callable[[], datetime] = utc_now,
    ) -> None:
        self._repository = repository
        self._clock = clock

    def _client_input_prerequisite(
        self,
        project_id: str,
        transition: TransitionDefinition,
    ) -> PrerequisiteEvaluation:
        del transition
        satisfied = self._repository.has_client_input(project_id)
        return PrerequisiteEvaluation(
            satisfied=satisfied,
            detail=(
                None
                if satisfied
                else "At least one ClientInput is required before starting requirements"
            ),
        )

    def _effective_approval_prerequisite(
        self,
        project_id: str,
        transition: TransitionDefinition,
    ) -> PrerequisiteEvaluation:
        if transition.approval_gate is None:
            return PrerequisiteEvaluation(
                satisfied=False,
                detail="The transition has no matching approval gate",
            )
        document = self._repository.get_effective_approval(
            project_id,
            transition.approval_gate,
        )
        if document is None:
            return PrerequisiteEvaluation(
                satisfied=False,
                detail=(
                    f"{transition.approval_gate.value} approval is required "
                    "before progression"
                ),
            )
        approval = Approval.model_validate(document)
        if approval.decision is not ApprovalDecision.APPROVE:
            return PrerequisiteEvaluation(
                satisfied=False,
                approval=approval,
                detail=(
                    f"Effective {transition.approval_gate.value} decision "
                    "does not permit progression"
                ),
            )
        if approval.next_stage is not transition.target_stage:
            return PrerequisiteEvaluation(
                satisfied=False,
                approval=approval,
                detail=(
                    f"Effective {transition.approval_gate.value} approval "
                    "does not match the canonical next stage"
                ),
            )
        return PrerequisiteEvaluation(satisfied=True, approval=approval)

    def _specialist_handoff_prerequisite(
        self,
        project_id: str,
        transition: TransitionDefinition,
    ) -> PrerequisiteEvaluation:
        evaluation = evaluate_specialist_handoff(
            self._repository,
            project_id,
            transition.source_stage,
        )
        return PrerequisiteEvaluation(
            satisfied=evaluation.ready,
            specialist_handoff=evaluation,
            detail=evaluation.detail,
        )

    def _evaluate_prerequisite(
        self,
        project_id: str,
        transition: TransitionDefinition,
    ) -> PrerequisiteEvaluation:
        handlers = {
            TransitionPrerequisite.CLIENT_INPUT: self._client_input_prerequisite,
            TransitionPrerequisite.SPECIALIST_HANDOFF: (
                self._specialist_handoff_prerequisite
            ),
            TransitionPrerequisite.EFFECTIVE_APPROVAL: (
                self._effective_approval_prerequisite
            ),
        }
        handler = handlers.get(transition.prerequisite)
        if handler is None:
            return PrerequisiteEvaluation(
                satisfied=False,
                detail="The transition prerequisite is not implemented",
            )
        return handler(project_id, transition)

    def get_workflow_snapshot(
        self,
        project_id: str,
        current_user: UserPublicResponse,
    ) -> WorkflowSnapshot:
        try:
            project = authorize_project_access(
                project_id,
                current_user,
                self._repository,
            )
            transition = get_transition(project.current_stage)
            available = False
            if transition is not None and transition.executable:
                available = self._evaluate_prerequisite(
                    project_id,
                    transition,
                ).satisfied
            return WorkflowSnapshot(
                project_id=project.project_id,
                current_stage=project.current_stage,
                current_stage_owner=get_stage_owner(project.current_stage),
                next_stage=(
                    transition.target_stage if transition is not None else None
                ),
                next_stage_owner=(
                    transition.responsible_component
                    if transition is not None
                    else None
                ),
                next_transition_available=available,
                approval_gate=(
                    transition.approval_gate if transition is not None else None
                ),
            )
        except ProjectAccessNotFoundError:
            raise
        except (OrchestratorRepositoryError, ValidationError) as exc:
            raise OrchestratorServiceError(
                "Workflow snapshot retrieval failed"
            ) from exc

    def list_workflow_events(
        self,
        project_id: str,
        current_user: UserPublicResponse,
    ) -> list[WorkflowEvent]:
        try:
            authorize_project_access(project_id, current_user, self._repository)
            events = [
                WorkflowEvent.model_validate(document)
                for document in self._repository.list_workflow_events(project_id)
            ]
            return sorted(
                events,
                key=lambda event: (event.created_at, event.event_id),
            )
        except ProjectAccessNotFoundError:
            raise
        except (OrchestratorRepositoryError, ValidationError) as exc:
            raise OrchestratorServiceError(
                "Workflow event retrieval failed"
            ) from exc

    def next_step(
        self,
        project_id: str,
        current_user: UserPublicResponse,
    ) -> WorkflowTransitionResult:
        try:
            project = authorize_project_access(
                project_id,
                current_user,
                self._repository,
            )
            transition = get_transition(project.current_stage)
            if transition is None or not transition.executable:
                raise UnsupportedWorkflowStageError(project.current_stage)
            prerequisite = self._evaluate_prerequisite(project_id, transition)
            if not prerequisite.satisfied:
                if transition.prerequisite is TransitionPrerequisite.CLIENT_INPUT:
                    raise MissingClientInputError(prerequisite.detail or "")
                if (
                    transition.prerequisite
                    is TransitionPrerequisite.SPECIALIST_HANDOFF
                ):
                    raise SpecialistHandoffPrerequisiteError(
                        project.current_stage,
                        prerequisite.detail
                        or "Specialist handoff readiness is required",
                    )
                raise ApprovalPrerequisiteError(
                    project.current_stage,
                    prerequisite.detail
                    or "An effective approval is required before progression",
                )

            stage_before = transition.source_stage
            stage_after = transition.target_stage
            now = self._clock()
            event = WorkflowEvent(
                event_id=generate_id(
                    "EVT",
                    self._repository.next_event_sequence(),
                ),
                project_id=project_id,
                event_type=EventType.STAGE_CHANGED,
                source_component=ORCHESTRATOR_COMPONENT,
                target_component=(
                    HUMAN_REVIEWER_COMPONENT
                    if transition.prerequisite
                    is TransitionPrerequisite.SPECIALIST_HANDOFF
                    else transition.responsible_component
                ),
                stage_before=stage_before,
                stage_after=stage_after,
                message=(
                    f"Project advanced from {stage_before.value} to "
                    f"{stage_after.value}."
                ),
                metadata=(
                    {
                        "approval_id": prerequisite.approval.approval_id,
                        "gate_id": prerequisite.approval.gate_id.value,
                    }
                    if prerequisite.approval is not None
                    else (
                        {
                            "readiness_event_id": (
                                prerequisite.specialist_handoff.readiness_event.event_id
                            ),
                            "artifact_version": (
                                prerequisite.specialist_handoff.readiness_event.metadata[
                                    "artifact_version"
                                ]
                            ),
                        }
                        if prerequisite.specialist_handoff is not None
                        and prerequisite.specialist_handoff.readiness_event
                        is not None
                        else {}
                    )
                ),
                created_at=now,
            )

            updated_project = self._repository.persist_stage_change(
                project_id=project_id,
                owner_user_id=current_user.user_id,
                stage_before=stage_before,
                stage_after=stage_after,
                updated_at=now,
                event=event,
            )
            if updated_project is None:
                raise OrchestratorServiceError(
                    "Project stage changed before the transition was persisted"
                )
            Project.model_validate(updated_project)

            return WorkflowTransitionResult(
                project_id=project_id,
                stage_before=stage_before,
                stage_after=stage_after,
            )
        except (
            ProjectAccessNotFoundError,
            UnsupportedWorkflowStageError,
            MissingClientInputError,
            SpecialistHandoffPrerequisiteError,
            ApprovalPrerequisiteError,
            OrchestratorServiceError,
        ):
            raise
        except (OrchestratorRepositoryError, ValidationError) as exc:
            raise OrchestratorServiceError(
                "Workflow transition failed"
            ) from exc


OrchestratorProjectNotFoundError = ProjectAccessNotFoundError
