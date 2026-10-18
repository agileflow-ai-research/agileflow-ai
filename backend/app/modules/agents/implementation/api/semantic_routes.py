"""Agent 3 HTTP routes grouped by responsibility."""

from typing import Annotated
from fastapi import APIRouter, Depends, File, Form, Query, UploadFile, status
from fastapi.responses import JSONResponse, RedirectResponse
from app.common.response import ErrorDetail, ErrorResponse, SuccessResponse
from app.modules.agents.implementation.inputs.extraction.service import (
    DocumentExtractionService,
    ExtractionNotFoundError,
    ExtractionStorageError,
    UnsupportedExtractionSourceError,
)
from app.modules.agents.implementation.github.repository import (
    GitHubConnectionRepository,
    GitHubConnectionRepositoryError,
    GitHubRepositoryBindingRepository,
    GitHubRepositoryBindingRepositoryError,
)
from app.modules.agents.implementation.preparation.readiness.schemas import (
    ReadinessEvaluationRequest,
    ReadinessEvaluationResult,
)
from app.modules.agents.implementation.preparation.readiness.service import (
    ImplementationReadinessService,
    ReadinessResolutionError,
    ReadinessUploadTypeError,
    StaleReadinessResolutionError,
)
from app.modules.agents.implementation.inputs.upload.service import (
    ImplementationInputService,
    WrongAgentProjectTypeError,
)
from app.modules.agents.implementation.preparation.service import (
    ChunkingNotFoundError,
    ChunkingStorageError,
    ChunkingUnavailableError,
    RuleDetectionNotFoundError,
    RuleDetectionService,
    RuleDetectionStorageError,
    SemanticChunkingService,
)
from app.modules.agents.implementation.preparation.hybrid.service import (
    HybridDetectionNotFoundError,
    HybridDetectionService,
    HybridDetectionStorageError,
    RuleDetectionRequiredError,
    StaleClassificationInputError,
    ZeroShotDetectionRequiredError,
)
from app.modules.agents.implementation.preparation.human_review.service import (
    HumanReviewService,
    HumanReviewStorageError,
    HumanReviewValidationError,
    HybridReviewRequiredError,
    StaleHumanReviewError,
)
from app.modules.agents.implementation.preparation.canonical.service import (
    CanonicalArtifactService,
    CanonicalArtifactStorageError,
    CanonicalArtifactsNotFoundError,
    HumanVerificationRequiredError,
    SemanticChunksRequiredError,
    StaleHumanVerificationError,
)
from app.modules.agents.implementation.preparation.semantic_extraction.artifact_service import (
    CanonicalArtifactsRequiredError,
    SemanticArtifactService,
    SemanticArtifactsNotFoundError,
    SemanticArtifactStorageError,
)
from app.modules.agents.implementation.preparation.semantic_extraction.local_model.model_loader import (
    SemanticModelUnavailableError,
)
from app.modules.agents.implementation.preparation.semantic_extraction.schemas import (
    DocumentSemanticArtifactResult,
)
from app.modules.agents.implementation.infrastructure.storage import (
    ImplementationUploadStorage,
    UploadNotFoundError,
    UploadStorageError,
    UploadValidationError,
)
from app.modules.auth.dependencies import get_current_user
from app.modules.auth.schemas import UserPublicResponse
from app.modules.standalone.service import (
    AgentProjectNotFoundError,
    ArchivedAgentProjectError,
    StandaloneService,
    StandaloneServiceError,
)
from app.modules.agents.implementation.api.dependencies import (
    get_implementation_readiness_service,
    get_semantic_artifact_service,
)
from app.modules.agents.implementation.api.errors import (
    _error,
)


router = APIRouter()


def _semantic_artifact_error(
    status_code: int, message: str, detail: str,
) -> JSONResponse:
    return _error(status_code, message, "semantic_artifacts", detail)


@router.post(
    "/{agent_project_id}/input-files/{upload_id}/semantic-artifacts",
    response_model=SuccessResponse[DocumentSemanticArtifactResult],
)
def build_implementation_semantic_artifacts(
    agent_project_id: str,
    upload_id: str,
    service: Annotated[SemanticArtifactService, Depends(get_semantic_artifact_service)],
    current_user: Annotated[UserPublicResponse, Depends(get_current_user)],
    force: Annotated[bool, Query()] = False,
) -> SuccessResponse[DocumentSemanticArtifactResult] | JSONResponse:
    try:
        result = service.build(agent_project_id, upload_id, current_user, force=force)
    except AgentProjectNotFoundError:
        return _error(404, "Agent project not found", "agent_project_id", "Agent project not found")
    except ArchivedAgentProjectError:
        return _error(409, "Agent project is archived", "agent_project_id", "Reactivate the agent project before semantic extraction")
    except WrongAgentProjectTypeError as exc:
        return _error(422, "Wrong agent project type", "agent_project_id", str(exc))
    except UploadNotFoundError:
        return _semantic_artifact_error(404, "Upload not found", "Staged upload not found")
    except SemanticChunksRequiredError:
        return _semantic_artifact_error(409, "Semantic extraction unavailable", "SEMANTIC_CHUNKS_REQUIRED")
    except HumanVerificationRequiredError:
        return _semantic_artifact_error(409, "Semantic extraction unavailable", "HUMAN_VERIFICATION_REQUIRED")
    except StaleHumanVerificationError:
        return _semantic_artifact_error(409, "Semantic extraction unavailable", "STALE_HUMAN_VERIFICATION")
    except CanonicalArtifactsRequiredError:
        return _semantic_artifact_error(409, "Semantic extraction unavailable", "CANONICAL_ARTIFACTS_REQUIRED")
    except SemanticModelUnavailableError:
        return _semantic_artifact_error(503, "Semantic extraction unavailable", "SEMANTIC_MODEL_UNAVAILABLE")
    except (RuleDetectionRequiredError, ZeroShotDetectionRequiredError,
            HybridReviewRequiredError):
        return _semantic_artifact_error(409, "Semantic extraction unavailable", "HUMAN_VERIFICATION_REQUIRED")
    except StaleClassificationInputError:
        return _semantic_artifact_error(409, "Semantic extraction unavailable", "STALE_HUMAN_VERIFICATION")
    except (ExtractionNotFoundError, ChunkingNotFoundError):
        return _semantic_artifact_error(409, "Semantic extraction unavailable", "SEMANTIC_CHUNKS_REQUIRED")
    except (StandaloneServiceError, UploadStorageError,
            CanonicalArtifactStorageError, HumanReviewStorageError,
            SemanticArtifactStorageError):
        return _semantic_artifact_error(503, "Semantic extraction unavailable", "Semantic artifact storage is unavailable")
    return SuccessResponse(message="Semantic artifact proposals prepared", data=result)


@router.get(
    "/{agent_project_id}/input-files/{upload_id}/semantic-artifacts",
    response_model=SuccessResponse[DocumentSemanticArtifactResult],
)
def get_implementation_semantic_artifacts(
    agent_project_id: str,
    upload_id: str,
    service: Annotated[SemanticArtifactService, Depends(get_semantic_artifact_service)],
    current_user: Annotated[UserPublicResponse, Depends(get_current_user)],
) -> SuccessResponse[DocumentSemanticArtifactResult] | JSONResponse:
    try:
        result = service.get_existing(agent_project_id, upload_id, current_user)
    except AgentProjectNotFoundError:
        return _error(404, "Agent project not found", "agent_project_id", "Agent project not found")
    except ArchivedAgentProjectError:
        return _error(409, "Agent project is archived", "agent_project_id", "Reactivate the agent project before reviewing semantic artifacts")
    except WrongAgentProjectTypeError as exc:
        return _error(422, "Wrong agent project type", "agent_project_id", str(exc))
    except UploadNotFoundError:
        return _semantic_artifact_error(404, "Upload not found", "Staged upload not found")
    except SemanticChunksRequiredError:
        return _semantic_artifact_error(409, "Semantic extraction unavailable", "SEMANTIC_CHUNKS_REQUIRED")
    except HumanVerificationRequiredError:
        return _semantic_artifact_error(409, "Semantic extraction unavailable", "HUMAN_VERIFICATION_REQUIRED")
    except StaleHumanVerificationError:
        return _semantic_artifact_error(409, "Semantic extraction unavailable", "STALE_HUMAN_VERIFICATION")
    except CanonicalArtifactsRequiredError:
        return _semantic_artifact_error(409, "Semantic extraction unavailable", "CANONICAL_ARTIFACTS_REQUIRED")
    except SemanticArtifactsNotFoundError:
        return _semantic_artifact_error(404, "Semantic artifacts not found", "No current semantic artifact result exists for this upload")
    except (RuleDetectionRequiredError, ZeroShotDetectionRequiredError,
            HybridReviewRequiredError):
        return _semantic_artifact_error(409, "Semantic extraction unavailable", "HUMAN_VERIFICATION_REQUIRED")
    except StaleClassificationInputError:
        return _semantic_artifact_error(409, "Semantic extraction unavailable", "STALE_HUMAN_VERIFICATION")
    except (ExtractionNotFoundError, ChunkingNotFoundError):
        return _semantic_artifact_error(409, "Semantic extraction unavailable", "SEMANTIC_CHUNKS_REQUIRED")
    except (StandaloneServiceError, UploadStorageError,
            CanonicalArtifactStorageError, HumanReviewStorageError,
            SemanticArtifactStorageError):
        return _semantic_artifact_error(503, "Semantic extraction unavailable", "Semantic artifact storage is unavailable")
    return SuccessResponse(message="Semantic artifact proposals retrieved", data=result)


@router.post(
    "/{agent_project_id}/readiness/evaluate",
    response_model=SuccessResponse[ReadinessEvaluationResult],
)
def evaluate_implementation_readiness(
    agent_project_id: str,
    request: ReadinessEvaluationRequest,
    service: Annotated[
        ImplementationReadinessService,
        Depends(get_implementation_readiness_service),
    ],
    current_user: Annotated[UserPublicResponse, Depends(get_current_user)],
) -> SuccessResponse[ReadinessEvaluationResult] | JSONResponse:
    try:
        result = service.evaluate(agent_project_id, request, current_user)
    except AgentProjectNotFoundError:
        return _error(
            404,
            "Agent project not found",
            "agent_project_id",
            "Agent project not found",
        )
    except ArchivedAgentProjectError:
        return _error(
            409,
            "Agent project is archived",
            "agent_project_id",
            "Reactivate the agent project before evaluating readiness",
        )
    except WrongAgentProjectTypeError as exc:
        return _error(
            422, "Wrong agent project type", "agent_project_id", str(exc)
        )
    except UploadNotFoundError:
        return _error(
            404, "Upload not found", "upload_id", "Staged upload not found"
        )
    except StaleReadinessResolutionError as exc:
        return _error(409, "Readiness result is stale", "input_fingerprint", str(exc))
    except (ReadinessResolutionError, ReadinessUploadTypeError) as exc:
        return _error(422, "Readiness request is invalid", "readiness", str(exc))
    except (
        StandaloneServiceError,
        UploadStorageError,
        GitHubRepositoryBindingRepositoryError,
    ):
        return _error(
            503,
            "Readiness evaluation unavailable",
            "readiness",
            "Readiness dependencies are unavailable",
        )
    return SuccessResponse(
        message="Implementation readiness evaluated", data=result
    )


