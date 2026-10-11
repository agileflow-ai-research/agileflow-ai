from typing import Annotated

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse

from app.common.response import ErrorDetail, ErrorResponse, SuccessResponse
from app.common.status import WorkflowStage
from app.modules.auth.dependencies import get_current_user
from app.modules.auth.schemas import UserPublicResponse
from app.modules.orchestrator.repository import OrchestratorRepository
from app.modules.orchestrator.schemas import (
    WorkflowSnapshot,
    WorkflowTransitionResult,
)
from app.modules.orchestrator.service import (
    MissingClientInputError,
    OrchestratorProjectNotFoundError,
    OrchestratorService,
    OrchestratorServiceError,
    UnsupportedWorkflowStageError,
)
from app.schemas.workflow import WorkflowEvent


router = APIRouter(
    prefix="/projects/{project_id}",
    tags=["orchestrator"],
)


def get_orchestrator_repository() -> OrchestratorRepository:
    return OrchestratorRepository()


def get_orchestrator_service(
    repository: Annotated[
        OrchestratorRepository,
        Depends(get_orchestrator_repository),
    ],
) -> OrchestratorService:
    return OrchestratorService(repository)


OrchestratorServiceDependency = Annotated[
    OrchestratorService,
    Depends(get_orchestrator_service),
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


@router.get(
    "/workflow",
    response_model=SuccessResponse[WorkflowSnapshot],
)
def get_workflow_snapshot(
    project_id: str,
    service: OrchestratorServiceDependency,
    current_user: CurrentUserDependency,
) -> SuccessResponse[WorkflowSnapshot] | JSONResponse:
    try:
        snapshot = service.get_workflow_snapshot(project_id, current_user)
    except ValueError as exc:
        return _error_response(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "Validation failed",
            "project_id",
            str(exc),
        )
    except OrchestratorProjectNotFoundError:
        return _error_response(
            status.HTTP_404_NOT_FOUND,
            "Project not found",
            "project_id",
            "Project not found",
        )
    except OrchestratorServiceError:
        return _error_response(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Workflow retrieval failed",
            "database",
            "Workflow storage is unavailable",
        )

    return SuccessResponse(
        message="Workflow snapshot retrieved successfully",
        data=snapshot,
        workflow_stage=snapshot.current_stage,
    )


@router.get(
    "/events",
    response_model=SuccessResponse[list[WorkflowEvent]],
)
def list_workflow_events(
    project_id: str,
    service: OrchestratorServiceDependency,
    current_user: CurrentUserDependency,
) -> SuccessResponse[list[WorkflowEvent]] | JSONResponse:
    try:
        events = service.list_workflow_events(project_id, current_user)
    except ValueError as exc:
        return _error_response(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "Validation failed",
            "project_id",
            str(exc),
        )
    except OrchestratorProjectNotFoundError:
        return _error_response(
            status.HTTP_404_NOT_FOUND,
            "Project not found",
            "project_id",
            "Project not found",
        )
    except OrchestratorServiceError:
        return _error_response(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Workflow event retrieval failed",
            "database",
            "Workflow storage is unavailable",
        )

    return SuccessResponse(
        message="Workflow events retrieved successfully",
        data=events,
    )


@router.post(
    "/orchestrator/next-step",
    response_model=SuccessResponse[WorkflowTransitionResult],
)
def next_step(
    project_id: str,
    service: OrchestratorServiceDependency,
    current_user: CurrentUserDependency,
) -> SuccessResponse[WorkflowTransitionResult] | JSONResponse:
    try:
        transition = service.next_step(project_id, current_user)
    except MissingClientInputError as exc:
        return _error_response(
            status.HTTP_409_CONFLICT,
            "Workflow prerequisite is not satisfied",
            "client_input",
            str(exc),
            workflow_stage=WorkflowStage.PROJECT_CREATED,
        )
    except UnsupportedWorkflowStageError as exc:
        return _error_response(
            status.HTTP_409_CONFLICT,
            "Workflow transition is not allowed",
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
    except OrchestratorProjectNotFoundError:
        return _error_response(
            status.HTTP_404_NOT_FOUND,
            "Project not found",
            "project_id",
            "Project not found",
        )
    except OrchestratorServiceError:
        return _error_response(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Workflow transition failed",
            "database",
            "Workflow storage is unavailable or inconsistent",
        )

    return SuccessResponse(
        message="Workflow stage updated successfully",
        data=transition,
        workflow_stage=transition.stage_after,
    )
