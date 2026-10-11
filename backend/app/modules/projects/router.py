from typing import Annotated, Any

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse

from app.common.response import ErrorDetail, ErrorResponse, SuccessResponse
from app.modules.auth.dependencies import get_current_user
from app.modules.auth.schemas import UserPublicResponse
from app.modules.projects.repository import ProjectRepository
from app.modules.projects.schemas import ProjectCreateRequest, ProjectUpdateRequest
from app.modules.projects.service import (
    ProjectNotFoundError,
    ProjectService,
    ProjectServiceError,
)
from app.schemas.project import Project


router = APIRouter(prefix="/projects", tags=["projects"])


def get_project_repository() -> ProjectRepository:
    return ProjectRepository()


def get_project_service(
    repository: Annotated[ProjectRepository, Depends(get_project_repository)],
) -> ProjectService:
    return ProjectService(repository)


ProjectServiceDependency = Annotated[ProjectService, Depends(get_project_service)]
CurrentUserDependency = Annotated[UserPublicResponse, Depends(get_current_user)]


def _error_response(
    status_code: int,
    message: str,
    field: str,
    detail: str,
) -> JSONResponse:
    payload = ErrorResponse(
        message=message,
        errors=[ErrorDetail(field=field, message=detail)],
    )
    return JSONResponse(
        status_code=status_code,
        content=payload.model_dump(mode="json"),
    )


@router.post(
    "",
    response_model=SuccessResponse[Project],
    status_code=status.HTTP_201_CREATED,
)
def create_project(
    request: ProjectCreateRequest,
    service: ProjectServiceDependency,
    current_user: CurrentUserDependency,
) -> SuccessResponse[Project] | JSONResponse:
    try:
        project = service.create_project(request, current_user)
    except ProjectServiceError:
        return _error_response(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Project creation failed",
            "database",
            "Project storage is unavailable",
        )
    return SuccessResponse(
        message="Project created successfully",
        data=project,
        workflow_stage=project.current_stage,
    )


@router.get("", response_model=SuccessResponse[list[Project]])
def list_projects(
    service: ProjectServiceDependency,
    current_user: CurrentUserDependency,
) -> SuccessResponse[list[Project]] | JSONResponse:
    try:
        projects = service.list_projects(current_user)
    except ProjectServiceError:
        return _error_response(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Project listing failed",
            "database",
            "Project storage is unavailable",
        )
    return SuccessResponse(
        message="Projects retrieved successfully",
        data=projects,
    )


@router.get("/{project_id}", response_model=SuccessResponse[Project])
def get_project(
    project_id: str,
    service: ProjectServiceDependency,
    current_user: CurrentUserDependency,
) -> SuccessResponse[Project] | JSONResponse:
    try:
        project = service.get_project(project_id, current_user)
    except ValueError as exc:
        return _error_response(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "Validation failed",
            "project_id",
            str(exc),
        )
    except ProjectNotFoundError:
        return _error_response(
            status.HTTP_404_NOT_FOUND,
            "Project not found",
            "project_id",
            "Project not found",
        )
    except ProjectServiceError:
        return _error_response(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Project retrieval failed",
            "database",
            "Project storage is unavailable",
        )
    return SuccessResponse(
        message="Project retrieved successfully",
        data=project,
        workflow_stage=project.current_stage,
    )


@router.patch("/{project_id}", response_model=SuccessResponse[Project])
def update_project(
    project_id: str,
    request: ProjectUpdateRequest,
    service: ProjectServiceDependency,
    current_user: CurrentUserDependency,
) -> SuccessResponse[Project] | JSONResponse:
    try:
        project = service.update_project(project_id, request, current_user)
    except ValueError as exc:
        return _error_response(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "Validation failed",
            "project_id",
            str(exc),
        )
    except ProjectNotFoundError:
        return _error_response(
            status.HTTP_404_NOT_FOUND,
            "Project not found",
            "project_id",
            "Project not found",
        )
    except ProjectServiceError:
        return _error_response(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Project update failed",
            "database",
            "Project storage is unavailable",
        )
    return SuccessResponse(
        message="Project updated successfully",
        data=project,
        workflow_stage=project.current_stage,
    )
