from collections.abc import Callable
from datetime import datetime, timezone

from pydantic import ValidationError

from app.common.id_generator import generate_id
from app.common.status import ArtifactStatus, WorkflowStage
from app.modules.auth.authorization import (
    ProjectAccessNotFoundError,
    authorize_project_access,
)
from app.modules.auth.schemas import UserPublicResponse
from app.modules.projects.repository import (
    ProjectRepository,
    ProjectRepositoryError,
)
from app.modules.projects.schemas import ProjectCreateRequest, ProjectUpdateRequest
from app.schemas.project import Project


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

    def create_project(
        self,
        request: ProjectCreateRequest,
        current_user: UserPublicResponse,
    ) -> Project:
        try:
            sequence = self._repository.next_project_sequence()
            now = self._clock()
            project = Project(
                project_id=generate_id("PRJ", sequence),
                owner_user_id=current_user.user_id,
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

    def list_projects(self, current_user: UserPublicResponse) -> list[Project]:
        try:
            return [
                Project.model_validate(document)
                for document in self._repository.list_projects(
                    current_user.user_id
                )
            ]
        except (ProjectRepositoryError, ValidationError) as exc:
            raise ProjectServiceError("Project listing failed") from exc

    def get_project(
        self,
        project_id: str,
        current_user: UserPublicResponse,
    ) -> Project:
        try:
            return authorize_project_access(
                project_id,
                current_user,
                self._repository,
            )
        except ProjectAccessNotFoundError:
            raise
        except (ProjectRepositoryError, ValidationError) as exc:
            raise ProjectServiceError("Project retrieval failed") from exc

    def update_project(
        self,
        project_id: str,
        request: ProjectUpdateRequest,
        current_user: UserPublicResponse,
    ) -> Project:
        updates = request.model_dump(exclude_unset=True)
        updates["updated_at"] = self._clock()
        try:
            authorize_project_access(project_id, current_user, self._repository)
            document = self._repository.update_project(
                project_id,
                current_user.user_id,
                updates,
            )
            if document is None:
                raise ProjectAccessNotFoundError(project_id)
            return Project.model_validate(document)
        except ProjectAccessNotFoundError:
            raise
        except (ProjectRepositoryError, ValidationError) as exc:
            raise ProjectServiceError("Project update failed") from exc


ProjectNotFoundError = ProjectAccessNotFoundError
