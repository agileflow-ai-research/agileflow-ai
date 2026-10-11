from collections.abc import Callable
from datetime import datetime, timezone

from pydantic import ValidationError

from app.common.id_generator import generate_id
from app.common.status import EventType, WorkflowStage
from app.modules.auth.authorization import (
    ProjectAccessNotFoundError,
    authorize_project_access,
)
from app.modules.auth.schemas import UserPublicResponse
from app.modules.orchestrator.policy import (
    ORCHESTRATOR_COMPONENT,
    TransitionDefinition,
    get_stage_owner,
    get_transition,
)
from app.modules.orchestrator.repository import (
    OrchestratorRepository,
    OrchestratorRepositoryError,
)
from app.modules.orchestrator.schemas import (
    WorkflowSnapshot,
    WorkflowTransitionResult,
)
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


class OrchestratorServiceError(RuntimeError):
    """Raised when a workflow transition cannot be completed safely."""


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class OrchestratorService:
    """Core workflow reads and the first executable transition."""

    def __init__(
        self,
        repository: OrchestratorRepository,
        clock: Callable[[], datetime] = utc_now,
    ) -> None:
        self._repository = repository
        self._clock = clock

    def _prerequisites_satisfied(
        self,
        project_id: str,
        transition: TransitionDefinition,
    ) -> bool:
        if transition.source_stage is WorkflowStage.PROJECT_CREATED:
            return self._repository.has_client_input(project_id)
        return False

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
            available = (
                transition is not None
                and transition.executable
                and self._prerequisites_satisfied(project_id, transition)
            )
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
            if not self._prerequisites_satisfied(project_id, transition):
                raise MissingClientInputError(
                    "At least one ClientInput is required before starting requirements"
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
                target_component=transition.responsible_component,
                stage_before=stage_before,
                stage_after=stage_after,
                message=(
                    "Project advanced from PROJECT_CREATED to "
                    "REQUIREMENTS_IN_PROGRESS."
                ),
                metadata={},
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
            OrchestratorServiceError,
        ):
            raise
        except (OrchestratorRepositoryError, ValidationError) as exc:
            raise OrchestratorServiceError(
                "Workflow transition failed"
            ) from exc


OrchestratorProjectNotFoundError = ProjectAccessNotFoundError
