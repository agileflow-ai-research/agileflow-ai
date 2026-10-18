"""Project specification automation and semantic approval routes."""

from typing import Annotated

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse

from app.common.response import SuccessResponse
from app.modules.agents.implementation.api.dependencies import (
    get_project_specification_service,
    get_project_specification_storage,
    get_semantic_review_service,
)
from app.modules.agents.implementation.api.errors import _error
from app.modules.agents.implementation.infrastructure.storage import (
    UploadNotFoundError,
    UploadStorageError,
)
from app.modules.agents.implementation.inputs.upload.service import (
    WrongAgentProjectTypeError,
)
from app.modules.agents.implementation.preparation.canonical.service import (
    CanonicalArtifactStorageError,
    CanonicalArtifactsNotFoundError,
    HumanVerificationRequiredError,
    StaleHumanVerificationError,
)
from app.modules.agents.implementation.preparation.semantic_extraction.artifact_service import (
    SemanticArtifactStorageError,
    SemanticArtifactsNotFoundError,
)
from app.modules.agents.implementation.preparation.specification.review_service import (
    FinalTrustedArtifactsNotFoundError,
    FinalTrustedArtifactsNotReadyError,
    SemanticDecisionNotFoundError,
    SemanticDecisionValidationError,
    SemanticReviewNotFoundError,
    SemanticReviewService,
    SemanticReviewStorageError,
    StaleSemanticReviewError,
)
from app.modules.agents.implementation.preparation.specification.schemas import (
    DocumentFinalTrustedArtifacts,
    DocumentSemanticReviewState,
    ProjectSpecificationStatusResponse,
    SemanticDecisionUpdate,
)
from app.modules.agents.implementation.preparation.specification.service import (
    ProjectSpecificationService,
)
from app.modules.agents.implementation.preparation.specification.storage import (
    ProjectSpecificationStorage,
    ProjectSpecificationStorageError,
)
from app.modules.auth.dependencies import get_current_user
from app.modules.auth.schemas import UserPublicResponse
from app.modules.standalone.service import (
    AgentProjectNotFoundError,
    ArchivedAgentProjectError,
    StandaloneServiceError,
)


router = APIRouter()


def _common_error(exc: Exception) -> JSONResponse:
    if isinstance(exc, AgentProjectNotFoundError):
        return _error(404, "Agent project not found", "agent_project_id",
                      "Agent project not found")
    if isinstance(exc, ArchivedAgentProjectError):
        return _error(409, "Agent project is archived", "agent_project_id",
                      "Reactivate the project before preparing its specification")
    if isinstance(exc, WrongAgentProjectTypeError):
        return _error(422, "Wrong agent project type", "agent_project_id",
                      str(exc))
    if isinstance(exc, UploadNotFoundError):
        return _error(404, "Upload not found", "upload_id",
                      "Staged upload not found")
    if isinstance(exc, (HumanVerificationRequiredError,
                        StaleHumanVerificationError)):
        return _error(409, "Specification preparation unavailable",
                      "specification", "HUMAN_VERIFICATION_REQUIRED")
    if isinstance(exc, (CanonicalArtifactsNotFoundError,
                        SemanticArtifactsNotFoundError)):
        return _error(409, "Specification preparation unavailable",
                      "specification", "SPECIFICATION_PREPARATION_REQUIRED")
    if isinstance(exc, SemanticReviewNotFoundError):
        return _error(409, "Semantic review unavailable",
                      "semantic_review", "SEMANTIC_REVIEW_NOT_READY")
    return _error(503, "Specification preparation unavailable",
                  "specification", "Specification storage is unavailable")


@router.post(
    "/{agent_project_id}/specification/start",
    response_model=SuccessResponse[ProjectSpecificationStatusResponse],
    status_code=status.HTTP_202_ACCEPTED,
)
def start_project_specification(
    agent_project_id: str,
    service: Annotated[
        ProjectSpecificationService,
        Depends(get_project_specification_service),
    ],
    current_user: Annotated[UserPublicResponse, Depends(get_current_user)],
) -> SuccessResponse[ProjectSpecificationStatusResponse] | JSONResponse:
    try:
        result = service.start(agent_project_id, current_user)
    except (
        AgentProjectNotFoundError,
        ArchivedAgentProjectError,
        WrongAgentProjectTypeError,
        StandaloneServiceError,
        UploadStorageError,
        ProjectSpecificationStorageError,
    ) as exc:
        return _common_error(exc)
    return SuccessResponse(message="Specification preparation started", data=result)


@router.get(
    "/{agent_project_id}/specification/status",
    response_model=SuccessResponse[ProjectSpecificationStatusResponse],
)
def get_project_specification_status(
    agent_project_id: str,
    service: Annotated[
        ProjectSpecificationService,
        Depends(get_project_specification_service),
    ],
    current_user: Annotated[UserPublicResponse, Depends(get_current_user)],
) -> SuccessResponse[ProjectSpecificationStatusResponse] | JSONResponse:
    try:
        result = service.get_status(agent_project_id, current_user)
    except (
        AgentProjectNotFoundError,
        ArchivedAgentProjectError,
        WrongAgentProjectTypeError,
        StandaloneServiceError,
        UploadStorageError,
        ProjectSpecificationStorageError,
    ) as exc:
        return _common_error(exc)
    return SuccessResponse(message="Specification status retrieved", data=result)


@router.get(
    "/{agent_project_id}/input-files/{upload_id}/semantic-reviews",
    response_model=SuccessResponse[DocumentSemanticReviewState],
)
def get_semantic_reviews(
    agent_project_id: str,
    upload_id: str,
    service: Annotated[SemanticReviewService, Depends(get_semantic_review_service)],
    current_user: Annotated[UserPublicResponse, Depends(get_current_user)],
) -> SuccessResponse[DocumentSemanticReviewState] | JSONResponse:
    try:
        result = service.get_state(agent_project_id, upload_id, current_user)
    except Exception as exc:
        if isinstance(exc, (
            AgentProjectNotFoundError, ArchivedAgentProjectError,
            WrongAgentProjectTypeError, UploadNotFoundError,
            HumanVerificationRequiredError, StaleHumanVerificationError,
            CanonicalArtifactsNotFoundError, SemanticArtifactsNotFoundError,
            StandaloneServiceError, UploadStorageError,
            CanonicalArtifactStorageError, SemanticArtifactStorageError,
            SemanticReviewStorageError,
            SemanticReviewNotFoundError,
        )):
            return _common_error(exc)
        raise
    return SuccessResponse(message="Semantic review retrieved", data=result)


@router.put(
    "/{agent_project_id}/input-files/{upload_id}/semantic-reviews/{decision_id}",
    response_model=SuccessResponse[DocumentSemanticReviewState],
)
def save_semantic_decision(
    agent_project_id: str,
    upload_id: str,
    decision_id: str,
    request: SemanticDecisionUpdate,
    review_service: Annotated[
        SemanticReviewService, Depends(get_semantic_review_service)
    ],
    specification_service: Annotated[
        ProjectSpecificationService,
        Depends(get_project_specification_service),
    ],
    specification_storage: Annotated[
        ProjectSpecificationStorage,
        Depends(get_project_specification_storage),
    ],
    current_user: Annotated[UserPublicResponse, Depends(get_current_user)],
) -> SuccessResponse[DocumentSemanticReviewState] | JSONResponse:
    try:
        result = review_service.save_decision(
            agent_project_id, upload_id, decision_id, request, current_user
        )
        specification = specification_storage.load(
            agent_project_id=agent_project_id,
            owner_user_id=current_user.user_id,
        )
        if specification is not None:
            specification_service.start(agent_project_id, current_user)
    except SemanticDecisionNotFoundError:
        return _error(404, "Semantic decision not found", "decision_id",
                      "Current semantic decision not found")
    except StaleSemanticReviewError:
        return _error(409, "Semantic review is stale", "semantic_review",
                      "STALE_SEMANTIC_REVIEW")
    except SemanticDecisionValidationError as exc:
        return _error(422, "Invalid semantic decision", "action", str(exc))
    except Exception as exc:
        if isinstance(exc, (
            AgentProjectNotFoundError, ArchivedAgentProjectError,
            WrongAgentProjectTypeError, UploadNotFoundError,
            HumanVerificationRequiredError, StaleHumanVerificationError,
            CanonicalArtifactsNotFoundError, SemanticArtifactsNotFoundError,
            StandaloneServiceError, UploadStorageError,
            CanonicalArtifactStorageError, SemanticArtifactStorageError,
            SemanticReviewStorageError, ProjectSpecificationStorageError,
            SemanticReviewNotFoundError,
        )):
            return _common_error(exc)
        raise
    return SuccessResponse(message="Semantic decision saved", data=result)


@router.get(
    "/{agent_project_id}/input-files/{upload_id}/trusted-artifacts",
    response_model=SuccessResponse[DocumentFinalTrustedArtifacts],
)
def get_final_trusted_artifacts(
    agent_project_id: str,
    upload_id: str,
    service: Annotated[SemanticReviewService, Depends(get_semantic_review_service)],
    current_user: Annotated[UserPublicResponse, Depends(get_current_user)],
) -> SuccessResponse[DocumentFinalTrustedArtifacts] | JSONResponse:
    try:
        result = service.get_final(agent_project_id, upload_id, current_user)
    except (FinalTrustedArtifactsNotFoundError,
            FinalTrustedArtifactsNotReadyError):
        return _error(404, "Trusted artifacts not found", "trusted_artifacts",
                      "No current final trusted artifact result exists")
    except Exception as exc:
        if isinstance(exc, (
            AgentProjectNotFoundError, ArchivedAgentProjectError,
            WrongAgentProjectTypeError, UploadNotFoundError,
            HumanVerificationRequiredError, StaleHumanVerificationError,
            StandaloneServiceError, UploadStorageError,
            CanonicalArtifactStorageError, SemanticArtifactStorageError,
            SemanticReviewStorageError,
        )):
            return _common_error(exc)
        raise
    return SuccessResponse(message="Final trusted artifacts retrieved", data=result)
