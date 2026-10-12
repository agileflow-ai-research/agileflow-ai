from typing import Annotated

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse

from app.common.response import ErrorDetail, ErrorResponse, SuccessResponse
from app.common.status import ApprovalGate, WorkflowStage
from app.modules.approvals.repository import ApprovalRepository
from app.modules.approvals.schemas import ApprovalCreateRequest
from app.modules.approvals.service import (
    ApprovalProjectNotFoundError,
    ApprovalService,
    ApprovalServiceError,
    ApprovalStageConflictError,
)
from app.modules.auth.dependencies import get_current_user
from app.modules.auth.schemas import UserPublicResponse
from app.schemas.approval import Approval


router = APIRouter(
    prefix="/projects/{project_id}/approvals",
    tags=["approvals"],
)


def get_approval_repository() -> ApprovalRepository:
    return ApprovalRepository()


def get_approval_service(
    repository: Annotated[
        ApprovalRepository,
        Depends(get_approval_repository),
    ],
) -> ApprovalService:
    return ApprovalService(repository)


ApprovalServiceDependency = Annotated[
    ApprovalService,
    Depends(get_approval_service),
]
CurrentUserDependency = Annotated[UserPublicResponse, Depends(get_current_user)]


def _error_response(
    status_code: int,
    message: str,
    field: str,
    detail: str,
    workflow_stage: WorkflowStage | None = None,
) -> JSONResponse:
    payload = ErrorResponse(
        message=message,
        errors=[ErrorDetail(field=field, message=detail)],
        workflow_stage=workflow_stage,
    )
    return JSONResponse(
        status_code=status_code,
        content=payload.model_dump(mode="json"),
    )


def _create_approval(
    project_id: str,
    gate_id: ApprovalGate,
    request: ApprovalCreateRequest,
    service: ApprovalService,
    current_user: UserPublicResponse,
) -> SuccessResponse[Approval] | JSONResponse:
    try:
        approval = service.create_approval(
            project_id,
            gate_id,
            request,
            current_user,
        )
    except ApprovalStageConflictError as exc:
        return _error_response(
            status.HTTP_409_CONFLICT,
            "Approval decision is not allowed at the current stage",
            "current_stage",
            str(exc),
            workflow_stage=exc.current_stage,
        )
    except ValueError as exc:
        return _error_response(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "Validation failed",
            "project_id",
            str(exc),
        )
    except ApprovalProjectNotFoundError:
        return _error_response(
            status.HTTP_404_NOT_FOUND,
            "Project not found",
            "project_id",
            "Project not found",
        )
    except ApprovalServiceError:
        return _error_response(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Approval decision failed",
            "database",
            "Approval storage is unavailable or inconsistent",
        )

    return SuccessResponse(
        message="Approval decision recorded successfully",
        data=approval,
    )


@router.post(
    "/h1",
    response_model=SuccessResponse[Approval],
    status_code=status.HTTP_201_CREATED,
)
def create_h1_approval(
    project_id: str,
    request: ApprovalCreateRequest,
    service: ApprovalServiceDependency,
    current_user: CurrentUserDependency,
) -> SuccessResponse[Approval] | JSONResponse:
    return _create_approval(
        project_id, ApprovalGate.H1, request, service, current_user
    )


@router.post(
    "/h2",
    response_model=SuccessResponse[Approval],
    status_code=status.HTTP_201_CREATED,
)
def create_h2_approval(
    project_id: str,
    request: ApprovalCreateRequest,
    service: ApprovalServiceDependency,
    current_user: CurrentUserDependency,
) -> SuccessResponse[Approval] | JSONResponse:
    return _create_approval(
        project_id, ApprovalGate.H2, request, service, current_user
    )


@router.post(
    "/h3",
    response_model=SuccessResponse[Approval],
    status_code=status.HTTP_201_CREATED,
)
def create_h3_approval(
    project_id: str,
    request: ApprovalCreateRequest,
    service: ApprovalServiceDependency,
    current_user: CurrentUserDependency,
) -> SuccessResponse[Approval] | JSONResponse:
    return _create_approval(
        project_id, ApprovalGate.H3, request, service, current_user
    )


@router.post(
    "/h4",
    response_model=SuccessResponse[Approval],
    status_code=status.HTTP_201_CREATED,
)
def create_h4_approval(
    project_id: str,
    request: ApprovalCreateRequest,
    service: ApprovalServiceDependency,
    current_user: CurrentUserDependency,
) -> SuccessResponse[Approval] | JSONResponse:
    return _create_approval(
        project_id, ApprovalGate.H4, request, service, current_user
    )


@router.post(
    "/h5",
    response_model=SuccessResponse[Approval],
    status_code=status.HTTP_201_CREATED,
)
def create_h5_approval(
    project_id: str,
    request: ApprovalCreateRequest,
    service: ApprovalServiceDependency,
    current_user: CurrentUserDependency,
) -> SuccessResponse[Approval] | JSONResponse:
    return _create_approval(
        project_id, ApprovalGate.H5, request, service, current_user
    )
