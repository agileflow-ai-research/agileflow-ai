from collections.abc import Callable
from datetime import datetime, timezone

from pydantic import ValidationError

from app.common.id_generator import generate_id, validate_id
from app.common.status import ArtifactStatus, WorkflowStage
from app.modules.projects.repository import (
    ProjectRepository,
    ProjectRepositoryError,
)
from app.modules.projects.schemas import ProjectCreateRequest, ProjectUpdateRequest
from app.schemas.project import Project


class ProjectNotFoundError(LookupError):
    """Raised when a requested project does not exist."""


class ProjectServiceError(RuntimeError):
    """Raised when a project operation cannot be completed safely."""


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ProjectService:
    """Project creation and metadata update rules."""

    def __init__(
        self,
        repository: ProjectRepository,
        clock: Callable[[], datetime] = utc_now,
    ) -> None:
        self._repository = repository
        self._clock = clock

    def create_project(self, request: ProjectCreateRequest) -> Project:
        try:
            sequence = self._repository.next_project_sequence()
            now = self._clock()
            project = Project(
                project_id=generate_id("PRJ", sequence),
                name=request.name,
                domain=request.domain,
                description=request.description,
                current_stage=WorkflowStage.PROJECT_CREATED,
                status=ArtifactStatus.IN_PROGRESS,
                created_by=request.created_by,
                created_at=now,
                updated_at=now,
            )
            document = self._repository.create_project(project)
            return Project.model_validate(document)
        except (ProjectRepositoryError, ValidationError) as exc:
            raise ProjectServiceError("Project creation failed") from exc

    def list_projects(self) -> list[Project]:
        try:
            return [
                Project.model_validate(document)
                for document in self._repository.list_projects()
            ]
        except (ProjectRepositoryError, ValidationError) as exc:
            raise ProjectServiceError("Project listing failed") from exc

    def get_project(self, project_id: str) -> Project:
        validate_id(project_id, "PRJ")
        try:
            document = self._repository.get_project(project_id)
            if document is None:
                raise ProjectNotFoundError(project_id)
            return Project.model_validate(document)
        except ProjectNotFoundError:
            raise
        except (ProjectRepositoryError, ValidationError) as exc:
            raise ProjectServiceError("Project retrieval failed") from exc

    def update_project(
        self,
        project_id: str,
        request: ProjectUpdateRequest,
    ) -> Project:
        validate_id(project_id, "PRJ")
        updates = request.model_dump(exclude_unset=True)
        updates["updated_at"] = self._clock()
        try:
            document = self._repository.update_project(project_id, updates)
            if document is None:
                raise ProjectNotFoundError(project_id)
            return Project.model_validate(document)
        except ProjectNotFoundError:
            raise
        except (ProjectRepositoryError, ValidationError) as exc:
            raise ProjectServiceError("Project update failed") from exc
