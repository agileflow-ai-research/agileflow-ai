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
from app.modules.orchestrator.repository import (
    OrchestratorRepository,
    OrchestratorRepositoryError,
)
from app.modules.orchestrator.schemas import WorkflowTransitionResult
from app.schemas.project import Project
from app.schemas.workflow import WorkflowEvent


ORCHESTRATOR_COMPONENT = "Central SDLC Orchestrator"
REQUIREMENTS_COMPONENT = "Requirement Gathering and Analysis Agent"


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
    """Rules for the first approved Central SDLC Orchestrator transition."""

    def __init__(
        self,
        repository: OrchestratorRepository,
        clock: Callable[[], datetime] = utc_now,
    ) -> None:
        self._repository = repository
        self._clock = clock

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
            if project.current_stage is not WorkflowStage.PROJECT_CREATED:
                raise UnsupportedWorkflowStageError(project.current_stage)
            if not self._repository.has_client_input(project_id):
                raise MissingClientInputError(
                    "At least one ClientInput is required before starting requirements"
                )

            stage_before = WorkflowStage.PROJECT_CREATED
            stage_after = WorkflowStage.REQUIREMENTS_IN_PROGRESS
            now = self._clock()
            event = WorkflowEvent(
                event_id=generate_id(
                    "EVT",
                    self._repository.next_event_sequence(),
                ),
                project_id=project_id,
                event_type=EventType.STAGE_CHANGED,
                source_component=ORCHESTRATOR_COMPONENT,
                target_component=REQUIREMENTS_COMPONENT,
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
