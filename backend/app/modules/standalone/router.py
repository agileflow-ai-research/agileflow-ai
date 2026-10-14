from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import JSONResponse

from app.common.id_generator import validate_id
from app.common.response import ErrorDetail, ErrorResponse, SuccessResponse
from app.modules.auth.dependencies import get_current_user
from app.modules.auth.schemas import UserPublicResponse
from app.modules.standalone.repository import (
    AgentProjectRepository,
    AgentRunRepository,
)
from app.modules.standalone.schemas import (
    AgentProject,
    AgentProjectCreateRequest,
    AgentProjectStatus,
    AgentProjectUpdateRequest,
    AgentRun,
    AgentType,
)
from app.modules.standalone.service import (
    AgentProjectNotFoundError,
    AgentRunNotFoundError,
    StandaloneService,
    StandaloneServiceError,
)


router = APIRouter(prefix="/agent-projects", tags=["standalone-agents"])


def get_agent_project_repository() -> AgentProjectRepository:
    return AgentProjectRepository()


def get_agent_run_repository() -> AgentRunRepository:
    return AgentRunRepository()


def get_standalone_service(
    project_repository: Annotated[
        AgentProjectRepository,
        Depends(get_agent_project_repository),
    ],
    run_repository: Annotated[
        AgentRunRepository,
        Depends(get_agent_run_repository),
    ],
) -> StandaloneService:
    return StandaloneService(project_repository, run_repository)


StandaloneServiceDependency = Annotated[
    StandaloneService,
    Depends(get_standalone_service),
]
CurrentUserDependency = Annotated[
    UserPublicResponse,
    Depends(get_current_user),
]


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
    response_model=SuccessResponse[AgentProject],
    status_code=status.HTTP_201_CREATED,
)
def create_agent_project(
    request: AgentProjectCreateRequest,
    service: StandaloneServiceDependency,
    current_user: CurrentUserDependency,
) -> SuccessResponse[AgentProject] | JSONResponse:
    try:
        project = service.create_project(request, current_user)
    except StandaloneServiceError:
        return _error_response(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Agent project creation failed",
            "database",
            "Standalone project storage is unavailable",
        )
    return SuccessResponse(
        message="Agent project created successfully",
        data=project,
    )


@router.get("", response_model=SuccessResponse[list[AgentProject]])
def list_agent_projects(
    service: StandaloneServiceDependency,
    current_user: CurrentUserDependency,
    agent_type: AgentType | None = None,
    status_filter: Annotated[
        AgentProjectStatus | None,
        Query(alias="status"),
    ] = None,
) -> SuccessResponse[list[AgentProject]] | JSONResponse:
    try:
        projects = service.list_projects(
            current_user,
            agent_type=agent_type,
            status=status_filter,
        )
    except StandaloneServiceError:
        return _error_response(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Agent project listing failed",
            "database",
            "Standalone project storage is unavailable",
        )
    return SuccessResponse(
        message="Agent projects retrieved successfully",
        data=projects,
    )


@router.get(
    "/{agent_project_id}/runs",
    response_model=SuccessResponse[list[AgentRun]],
)
def list_agent_runs(
    agent_project_id: str,
    service: StandaloneServiceDependency,
    current_user: CurrentUserDependency,
) -> SuccessResponse[list[AgentRun]] | JSONResponse:
    try:
        runs = service.list_runs(agent_project_id, current_user)
    except ValueError as exc:
        return _error_response(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "Validation failed",
            "agent_project_id",
            str(exc),
        )
    except AgentProjectNotFoundError:
        return _error_response(
            status.HTTP_404_NOT_FOUND,
            "Agent project not found",
            "agent_project_id",
            "Agent project not found",
        )
    except StandaloneServiceError:
        return _error_response(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Agent run listing failed",
            "database",
            "Standalone run storage is unavailable",
        )
    return SuccessResponse(
        message="Agent runs retrieved successfully",
        data=runs,
    )


@router.get(
    "/{agent_project_id}/runs/{run_id}",
    response_model=SuccessResponse[AgentRun],
)
def get_agent_run(
    agent_project_id: str,
    run_id: str,
    service: StandaloneServiceDependency,
    current_user: CurrentUserDependency,
) -> SuccessResponse[AgentRun] | JSONResponse:
    try:
        validate_id(agent_project_id, "AGP")
    except ValueError as exc:
        return _error_response(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "Validation failed",
            "agent_project_id",
            str(exc),
        )
    try:
        validate_id(run_id, "RUN")
    except ValueError as exc:
        return _error_response(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "Validation failed",
            "run_id",
            str(exc),
        )
    try:
        run = service.get_run(agent_project_id, run_id, current_user)
    except AgentProjectNotFoundError:
        return _error_response(
            status.HTTP_404_NOT_FOUND,
            "Agent project not found",
            "agent_project_id",
            "Agent project not found",
        )
    except AgentRunNotFoundError:
        return _error_response(
            status.HTTP_404_NOT_FOUND,
            "Agent run not found",
            "run_id",
            "Agent run not found",
        )
    except StandaloneServiceError:
        return _error_response(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Agent run retrieval failed",
            "database",
            "Standalone run storage is unavailable",
        )
    return SuccessResponse(
        message="Agent run retrieved successfully",
        data=run,
    )


@router.get(
    "/{agent_project_id}",
    response_model=SuccessResponse[AgentProject],
)
def get_agent_project(
    agent_project_id: str,
    service: StandaloneServiceDependency,
    current_user: CurrentUserDependency,
) -> SuccessResponse[AgentProject] | JSONResponse:
    try:
        project = service.get_project(agent_project_id, current_user)
    except ValueError as exc:
        return _error_response(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "Validation failed",
            "agent_project_id",
            str(exc),
        )
    except AgentProjectNotFoundError:
        return _error_response(
            status.HTTP_404_NOT_FOUND,
            "Agent project not found",
            "agent_project_id",
            "Agent project not found",
        )
    except StandaloneServiceError:
        return _error_response(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Agent project retrieval failed",
            "database",
            "Standalone project storage is unavailable",
        )
    return SuccessResponse(
        message="Agent project retrieved successfully",
        data=project,
    )


@router.patch(
    "/{agent_project_id}",
    response_model=SuccessResponse[AgentProject],
)
def update_agent_project(
    agent_project_id: str,
    request: AgentProjectUpdateRequest,
    service: StandaloneServiceDependency,
    current_user: CurrentUserDependency,
) -> SuccessResponse[AgentProject] | JSONResponse:
    try:
        project = service.update_project(
            agent_project_id,
            request,
            current_user,
        )
    except ValueError as exc:
        return _error_response(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "Validation failed",
            "agent_project_id",
            str(exc),
        )
    except AgentProjectNotFoundError:
        return _error_response(
            status.HTTP_404_NOT_FOUND,
            "Agent project not found",
            "agent_project_id",
            "Agent project not found",
        )
    except StandaloneServiceError:
        return _error_response(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Agent project update failed",
            "database",
            "Standalone project storage is unavailable",
        )
    return SuccessResponse(
        message="Agent project updated successfully",
        data=project,
    )
