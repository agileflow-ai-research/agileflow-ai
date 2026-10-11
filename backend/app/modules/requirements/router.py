from typing import Annotated

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse

from app.common.response import ErrorDetail, ErrorResponse, SuccessResponse
from app.modules.auth.dependencies import get_current_user
from app.modules.auth.schemas import UserPublicResponse
from app.modules.requirements.repository import ClientInputRepository
from app.modules.requirements.schemas import (
    ClientInputCreateRequest,
    ClientInputResponse,
)
from app.modules.requirements.service import (
    ClientInputProjectNotFoundError,
    ClientInputService,
    ClientInputServiceError,
)


router = APIRouter(
    prefix="/projects/{project_id}/inputs",
    tags=["requirements"],
)


def get_client_input_repository() -> ClientInputRepository:
    return ClientInputRepository()


def get_client_input_service(
    repository: Annotated[
        ClientInputRepository,
        Depends(get_client_input_repository),
    ],
) -> ClientInputService:
    return ClientInputService(repository)


ClientInputServiceDependency = Annotated[
    ClientInputService,
    Depends(get_client_input_service),
]
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
    response_model=SuccessResponse[ClientInputResponse],
    status_code=status.HTTP_201_CREATED,
)
def create_client_input(
    project_id: str,
    request: ClientInputCreateRequest,
    service: ClientInputServiceDependency,
    current_user: CurrentUserDependency,
) -> SuccessResponse[ClientInputResponse] | JSONResponse:
    try:
        client_input = service.create_client_input(
            project_id,
            request,
            current_user,
        )
    except ValueError as exc:
        return _error_response(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "Validation failed",
            "project_id",
            str(exc),
        )
    except ClientInputProjectNotFoundError:
        return _error_response(
            status.HTTP_404_NOT_FOUND,
            "Project not found",
            "project_id",
            "Project not found",
        )
    except ClientInputServiceError:
        return _error_response(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Client input creation failed",
            "database",
            "Client input storage is unavailable",
        )

    return SuccessResponse(
        message="Client input created successfully",
        data=client_input,
    )


@router.get("", response_model=SuccessResponse[list[ClientInputResponse]])
def list_client_inputs(
    project_id: str,
    service: ClientInputServiceDependency,
    current_user: CurrentUserDependency,
) -> SuccessResponse[list[ClientInputResponse]] | JSONResponse:
    try:
        client_inputs = service.list_client_inputs(project_id, current_user)
    except ValueError as exc:
        return _error_response(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "Validation failed",
            "project_id",
            str(exc),
        )
    except ClientInputProjectNotFoundError:
        return _error_response(
            status.HTTP_404_NOT_FOUND,
            "Project not found",
            "project_id",
            "Project not found",
        )
    except ClientInputServiceError:
        return _error_response(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Client input listing failed",
            "database",
            "Client input storage is unavailable",
        )

    return SuccessResponse(
        message="Client inputs retrieved successfully",
        data=client_inputs,
    )
