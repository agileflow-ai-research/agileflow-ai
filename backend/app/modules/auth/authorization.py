from typing import Any, Protocol

from app.common.id_generator import validate_id
from app.schemas.project import Project


class ProjectAccessNotFoundError(LookupError):
    """Raised when a project is missing or is not owned by the current user."""


class ProjectIdentity(Protocol):
    user_id: str


class ProjectLookup(Protocol):
    def get_project(self, project_id: str) -> dict[str, Any] | None: ...


def authorize_project_access(
    project_id: str,
    current_user: ProjectIdentity,
    repository: ProjectLookup,
) -> Project:
    """Return an owned Project without revealing foreign project existence."""
    validate_id(project_id, "PRJ")
    document = repository.get_project(project_id)
    if (
        document is None
        or document.get("owner_user_id") != current_user.user_id
    ):
        raise ProjectAccessNotFoundError(project_id)
    return Project.model_validate(document)
