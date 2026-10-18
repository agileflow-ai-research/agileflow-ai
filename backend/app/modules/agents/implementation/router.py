from typing import Annotated
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile, status
from fastapi.responses import JSONResponse, RedirectResponse

from app.common.response import ErrorDetail, ErrorResponse, SuccessResponse
from app.core.config import settings
from app.modules.agents.implementation.extraction.schemas import (
    DocumentExtractionResult,
)
from app.modules.agents.implementation.extraction.service import (
    DocumentExtractionService,
    ExtractionNotFoundError,
    ExtractionStorageError,
    UnsupportedExtractionSourceError,
)
from app.modules.agents.implementation.schemas import (
    GitHubConnectionStatus,
    GitHubConnectResponse,
    GitHubRepositoryCreateRequest,
    GitHubRepositoryStatus,
    ImplementationArtifactType,
    ImplementationInputSourceType,
    UploadedFileMetadata,
)
from app.modules.agents.implementation.github_auth import (
    GitHubAppAuthenticationError,
    GitHubAppAuthenticator,
    GitHubAppPermissionError,
    GitHubExternalServiceError,
    GitHubInstallationRevokedError,
    GitHubPrivateKeyError,
)
from app.modules.agents.implementation.github_repository_service import (
    GitHubConnectionRequiredError,
    GitHubOrganizationConnectionError,
    GitHubRepositoryAlreadyBoundError,
    GitHubRepositoryAuthenticationError,
    GitHubRepositoryClient,
    GitHubRepositoryExternalError,
    GitHubRepositoryNameConflictError,
    GitHubRepositoryPartialFailureError,
    GitHubRepositoryPermissionError,
    GitHubRepositoryService,
    GitHubRepositoryValidationError,
)
from app.modules.agents.implementation.github import (
    GitHubApiClient,
    GitHubCallbackError,
    GitHubConfiguration,
    GitHubConfigurationError,
    GitHubConnectionService,
    GitHubStateError,
    GitHubStateStore,
)
from app.modules.agents.implementation.repository import (
    GitHubConnectionRepository,
    GitHubConnectionRepositoryError,
    GitHubRepositoryBindingRepository,
    GitHubRepositoryBindingRepositoryError,
)
from app.modules.agents.implementation.readiness.schemas import (
    ReadinessEvaluationRequest,
    ReadinessEvaluationResult,
)
from app.modules.agents.implementation.readiness.service import (
    ImplementationReadinessService,
    ReadinessResolutionError,
    ReadinessUploadTypeError,
    StaleReadinessResolutionError,
)
from app.modules.agents.implementation.service import (
    ImplementationInputService,
    WrongAgentProjectTypeError,
)
from app.modules.agents.implementation.semantic_discovery.schemas import (
    DocumentChunkingResult,
    DocumentRuleDetectionResult,
)
from app.modules.agents.implementation.semantic_discovery.service import (
    ChunkingNotFoundError,
    ChunkingStorageError,
    ChunkingUnavailableError,
    RuleDetectionNotFoundError,
    RuleDetectionService,
    RuleDetectionStorageError,
    SemanticChunkingService,
)
from app.modules.agents.implementation.semantic_discovery.zero_shot.classifier import (
    ZeroShotClassifier,
)
from app.modules.agents.implementation.semantic_discovery.zero_shot.schemas import (
    DocumentZeroShotDetectionResult,
)
from app.modules.agents.implementation.semantic_discovery.zero_shot.service import (
    ZeroShotDetectionNotFoundError,
    ZeroShotDetectionService,
    ZeroShotDetectionStorageError,
)
from app.modules.agents.implementation.semantic_discovery.hybrid.schemas import (
    DocumentHybridDetectionResult,
)
from app.modules.agents.implementation.semantic_discovery.hybrid.service import (
    HybridDetectionNotFoundError,
    HybridDetectionService,
    HybridDetectionStorageError,
    RuleDetectionRequiredError,
    StaleClassificationInputError,
    ZeroShotDetectionRequiredError,
)
from app.modules.agents.implementation.semantic_discovery.human_review.schemas import (
    ChunkHumanReviewUpdate,
    HumanReviewStateResponse,
)
from app.modules.agents.implementation.semantic_discovery.human_review.service import (
    HumanReviewService,
    HumanReviewStorageError,
    HumanReviewValidationError,
    HybridReviewRequiredError,
    StaleHumanReviewError,
)
from app.modules.agents.implementation.semantic_discovery.canonical.schemas import (
    DocumentCanonicalArtifactResult,
)
from app.modules.agents.implementation.semantic_discovery.canonical.service import (
    CanonicalArtifactService,
    CanonicalArtifactStorageError,
    CanonicalArtifactsNotFoundError,
    HumanVerificationRequiredError,
    SemanticChunksRequiredError,
    StaleHumanVerificationError,
)
from app.modules.agents.implementation.semantic_discovery.semantic_extraction.artifact_service import (
    CanonicalArtifactsRequiredError,
    SemanticArtifactService,
    SemanticArtifactsNotFoundError,
    SemanticArtifactStorageError,
)
from app.modules.agents.implementation.semantic_discovery.semantic_extraction.local_model.adapter import (
    LocalSemanticExtractorAdapter,
)
from app.modules.agents.implementation.semantic_discovery.semantic_extraction.local_model.model_loader import (
    SemanticModelUnavailableError,
)
from app.modules.agents.implementation.semantic_discovery.semantic_extraction.schemas import (
    DocumentSemanticArtifactResult,
)
from app.modules.agents.implementation.storage import (
    ImplementationUploadStorage,
    UploadNotFoundError,
    UploadStorageError,
    UploadValidationError,
)
from app.modules.auth.dependencies import get_current_user
from app.modules.auth.schemas import UserPublicResponse
from app.modules.standalone.router import get_standalone_service
from app.modules.standalone.service import (
    AgentProjectNotFoundError,
    ArchivedAgentProjectError,
    StandaloneService,
    StandaloneServiceError,
)


router = APIRouter(
    prefix="/agents/implementation", tags=["implementation-agent"]
)

_github_states = GitHubStateStore()


def get_implementation_upload_storage() -> ImplementationUploadStorage:
    return ImplementationUploadStorage(settings.agent3_upload_root)


def get_implementation_input_service(
    standalone_service: Annotated[
        StandaloneService, Depends(get_standalone_service)
    ],
    storage: Annotated[
        ImplementationUploadStorage,
        Depends(get_implementation_upload_storage),
    ],
) -> ImplementationInputService:
    return ImplementationInputService(standalone_service, storage)


def get_document_extraction_service(
    standalone_service: Annotated[
        StandaloneService, Depends(get_standalone_service)
    ],
    storage: Annotated[
        ImplementationUploadStorage,
        Depends(get_implementation_upload_storage),
    ],
) -> DocumentExtractionService:
    return DocumentExtractionService(standalone_service, storage)


def get_semantic_chunking_service(
    standalone_service: Annotated[
        StandaloneService, Depends(get_standalone_service)
    ],
    storage: Annotated[
        ImplementationUploadStorage,
        Depends(get_implementation_upload_storage),
    ],
) -> SemanticChunkingService:
    return SemanticChunkingService(standalone_service, storage)


def get_rule_detection_service(
    standalone_service: Annotated[
        StandaloneService, Depends(get_standalone_service)
    ],
    storage: Annotated[
        ImplementationUploadStorage,
        Depends(get_implementation_upload_storage),
    ],
) -> RuleDetectionService:
    return RuleDetectionService(standalone_service, storage)


def get_zero_shot_detection_service(
    standalone_service: Annotated[
        StandaloneService, Depends(get_standalone_service)
    ],
    storage: Annotated[
        ImplementationUploadStorage,
        Depends(get_implementation_upload_storage),
    ],
) -> ZeroShotDetectionService:
    return ZeroShotDetectionService(
        standalone_service,
        storage,
        ZeroShotClassifier(
            local_files_only=settings.agent3_zero_shot_local_files_only
        ),
    )


def get_hybrid_detection_service(
    standalone_service: Annotated[
        StandaloneService, Depends(get_standalone_service)
    ],
    storage: Annotated[
        ImplementationUploadStorage,
        Depends(get_implementation_upload_storage),
    ],
) -> HybridDetectionService:
    return HybridDetectionService(standalone_service, storage)


def get_human_review_service(
    standalone_service: Annotated[
        StandaloneService, Depends(get_standalone_service)
    ],
    storage: Annotated[
        ImplementationUploadStorage,
        Depends(get_implementation_upload_storage),
    ],
) -> HumanReviewService:
    return HumanReviewService(standalone_service, storage)


def get_canonical_artifact_service(
    standalone_service: Annotated[
        StandaloneService, Depends(get_standalone_service)
    ],
    storage: Annotated[
        ImplementationUploadStorage,
        Depends(get_implementation_upload_storage),
    ],
) -> CanonicalArtifactService:
    return CanonicalArtifactService(standalone_service, storage)


def get_semantic_artifact_service(
    standalone_service: Annotated[
        StandaloneService, Depends(get_standalone_service)
    ],
    storage: Annotated[
        ImplementationUploadStorage,
        Depends(get_implementation_upload_storage),
    ],
) -> SemanticArtifactService:
    adapter = LocalSemanticExtractorAdapter(
        model_id=settings.agent3_semantic_model_id,
        revision=settings.agent3_semantic_model_revision,
        local_files_only=settings.agent3_semantic_local_files_only,
        device=settings.agent3_semantic_device,
    )
    return SemanticArtifactService(standalone_service, storage, adapter)


def get_github_connection_repository() -> GitHubConnectionRepository:
    return GitHubConnectionRepository()


def get_github_connection_service(
    standalone_service: Annotated[
        StandaloneService, Depends(get_standalone_service)
    ],
    repository: Annotated[
        GitHubConnectionRepository,
        Depends(get_github_connection_repository),
    ],
) -> GitHubConnectionService | None:
    try:
        configuration = GitHubConfiguration.from_settings(settings)
    except GitHubConfigurationError:
        return None
    return GitHubConnectionService(
        standalone_service,
        repository,
        _github_states,
        GitHubApiClient(configuration),
        configuration,
    )


def get_github_repository_binding_repository() -> GitHubRepositoryBindingRepository:
    return GitHubRepositoryBindingRepository()


def get_implementation_readiness_service(
    standalone_service: Annotated[
        StandaloneService, Depends(get_standalone_service)
    ],
    storage: Annotated[
        ImplementationUploadStorage,
        Depends(get_implementation_upload_storage),
    ],
    binding_repository: Annotated[
        GitHubRepositoryBindingRepository,
        Depends(get_github_repository_binding_repository),
    ],
) -> ImplementationReadinessService:
    return ImplementationReadinessService(
        standalone_service,
        storage,
        DocumentExtractionService(standalone_service, storage),
        binding_repository,
    )


def get_github_repository_service(
    standalone_service: Annotated[
        StandaloneService, Depends(get_standalone_service)
    ],
    connection_repository: Annotated[
        GitHubConnectionRepository,
        Depends(get_github_connection_repository),
    ],
    binding_repository: Annotated[
        GitHubRepositoryBindingRepository,
        Depends(get_github_repository_binding_repository),
    ],
) -> GitHubRepositoryService:
    return GitHubRepositoryService(
        standalone_service,
        connection_repository,
        binding_repository,
        GitHubAppAuthenticator(settings),
        GitHubRepositoryClient(
            settings.github_api_base_url,
            settings.github_http_timeout_seconds,
        ),
    )


def _error(
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
        status_code=status_code, content=payload.model_dump(mode="json")
    )


def _frontend_callback_url(
    *,
    agent_project_id: str | None = None,
    connected: bool = False,
    reason: str | None = None,
) -> str:
    base = settings.frontend_base_url.rstrip("/")
    path = (
        f"/agent-projects/{agent_project_id}"
        if agent_project_id
        else "/agents/implementation"
    )
    query = {"github": "connected" if connected else "error"}
    if reason and not connected:
        query["reason"] = reason
    return f"{base}{path}?{urlencode(query)}"


@router.post(
    "/{agent_project_id}/input-files",
    response_model=SuccessResponse[UploadedFileMetadata],
    status_code=status.HTTP_201_CREATED,
)
async def upload_implementation_input_file(
    agent_project_id: str,
    source_type: Annotated[ImplementationInputSourceType, Form()],
    artifact_type: Annotated[ImplementationArtifactType, Form()],
    file: Annotated[UploadFile, File()],
    service: Annotated[
        ImplementationInputService,
        Depends(get_implementation_input_service),
    ],
    current_user: Annotated[UserPublicResponse, Depends(get_current_user)],
    label: Annotated[str | None, Form(max_length=200)] = None,
) -> SuccessResponse[UploadedFileMetadata] | JSONResponse:
    try:
        metadata = await service.upload(
            agent_project_id,
            current_user,
            source_type,
            artifact_type,
            label,
            file,
        )
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
            "Reactivate the agent project before uploading files",
        )
    except WrongAgentProjectTypeError as exc:
        return _error(
            422, "Wrong agent project type", "agent_project_id", str(exc)
        )
    except (ValueError, UploadValidationError) as exc:
        return _error(422, "Upload validation failed", "file", str(exc))
    except (StandaloneServiceError, UploadStorageError):
        return _error(
            503,
            "Upload storage failed",
            "storage",
            "The staged upload could not be stored",
        )
    finally:
        await file.close()
    return SuccessResponse(
        message="Implementation input file uploaded", data=metadata
    )


@router.delete(
    "/{agent_project_id}/input-files/{upload_id}",
    response_model=SuccessResponse[dict[str, str]],
    status_code=status.HTTP_200_OK,
)
def delete_implementation_input_file(
    agent_project_id: str,
    upload_id: str,
    service: Annotated[
        ImplementationInputService,
        Depends(get_implementation_input_service),
    ],
    current_user: Annotated[UserPublicResponse, Depends(get_current_user)],
) -> SuccessResponse[dict[str, str]] | JSONResponse:
    try:
        service.delete(agent_project_id, upload_id, current_user)
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
            "Reactivate the agent project before deleting files",
        )
    except WrongAgentProjectTypeError as exc:
        return _error(
            422, "Wrong agent project type", "agent_project_id", str(exc)
        )
    except UploadNotFoundError:
        return _error(
            404, "Upload not found", "upload_id", "Staged upload not found"
        )
    except (StandaloneServiceError, UploadStorageError):
        return _error(
            503,
            "Upload storage failed",
            "storage",
            "The staged upload could not be deleted",
        )
    return SuccessResponse(
        message="Implementation input file deleted",
        data={"upload_id": upload_id},
    )


def _extraction_error(
    status_code: int, message: str, detail: str
) -> JSONResponse:
    return _error(status_code, message, "extraction", detail)


@router.post(
    "/{agent_project_id}/input-files/{upload_id}/extract",
    response_model=SuccessResponse[DocumentExtractionResult],
)
def extract_implementation_document(
    agent_project_id: str,
    upload_id: str,
    service: Annotated[
        DocumentExtractionService, Depends(get_document_extraction_service)
    ],
    current_user: Annotated[UserPublicResponse, Depends(get_current_user)],
    force: Annotated[bool, Query()] = False,
) -> SuccessResponse[DocumentExtractionResult] | JSONResponse:
    try:
        extraction = service.extract(
            agent_project_id,
            upload_id,
            current_user,
            force=force,
        )
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
            "Reactivate the agent project before extracting documents",
        )
    except WrongAgentProjectTypeError as exc:
        return _error(
            422, "Wrong agent project type", "agent_project_id", str(exc)
        )
    except UploadNotFoundError:
        return _extraction_error(404, "Upload not found", "Staged upload not found")
    except UnsupportedExtractionSourceError as exc:
        return _extraction_error(
            422, "Document extraction unavailable", str(exc)
        )
    except (StandaloneServiceError, UploadStorageError, ExtractionStorageError):
        return _extraction_error(
            503,
            "Document extraction unavailable",
            "Document extraction storage is unavailable",
        )
    return SuccessResponse(message="Document extraction completed", data=extraction)


@router.get(
    "/{agent_project_id}/input-files/{upload_id}/extraction",
    response_model=SuccessResponse[DocumentExtractionResult],
)
def get_implementation_document_extraction(
    agent_project_id: str,
    upload_id: str,
    service: Annotated[
        DocumentExtractionService, Depends(get_document_extraction_service)
    ],
    current_user: Annotated[UserPublicResponse, Depends(get_current_user)],
) -> SuccessResponse[DocumentExtractionResult] | JSONResponse:
    try:
        extraction = service.get_existing(
            agent_project_id, upload_id, current_user
        )
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
            "Reactivate the agent project before reviewing extraction",
        )
    except WrongAgentProjectTypeError as exc:
        return _error(
            422, "Wrong agent project type", "agent_project_id", str(exc)
        )
    except (UploadNotFoundError, ExtractionNotFoundError):
        return _extraction_error(
            404,
            "Extraction not found",
            "No valid extraction exists for this upload",
        )
    except UnsupportedExtractionSourceError as exc:
        return _extraction_error(
            422, "Document extraction unavailable", str(exc)
        )
    except (StandaloneServiceError, UploadStorageError):
        return _extraction_error(
            503,
            "Document extraction unavailable",
            "Document extraction storage is unavailable",
        )
    return SuccessResponse(message="Document extraction retrieved", data=extraction)


def _chunking_error(status_code: int, message: str, detail: str) -> JSONResponse:
    return _error(status_code, message, "chunks", detail)


@router.post(
    "/{agent_project_id}/input-files/{upload_id}/chunks",
    response_model=SuccessResponse[DocumentChunkingResult],
)
def build_implementation_document_chunks(
    agent_project_id: str,
    upload_id: str,
    service: Annotated[
        SemanticChunkingService, Depends(get_semantic_chunking_service)
    ],
    current_user: Annotated[UserPublicResponse, Depends(get_current_user)],
    force: Annotated[bool, Query()] = False,
) -> SuccessResponse[DocumentChunkingResult] | JSONResponse:
    try:
        result = service.build(agent_project_id, upload_id, current_user, force=force)
    except AgentProjectNotFoundError:
        return _error(404, "Agent project not found", "agent_project_id", "Agent project not found")
    except ArchivedAgentProjectError:
        return _error(409, "Agent project is archived", "agent_project_id", "Reactivate the agent project before preparing semantic chunks")
    except WrongAgentProjectTypeError as exc:
        return _error(422, "Wrong agent project type", "agent_project_id", str(exc))
    except UploadNotFoundError:
        return _chunking_error(404, "Upload not found", "Staged upload not found")
    except ExtractionNotFoundError:
        return _chunking_error(409, "Semantic preparation unavailable", "A valid trusted extraction must exist before chunking")
    except (UnsupportedExtractionSourceError, ChunkingUnavailableError) as exc:
        return _chunking_error(422, "Semantic preparation unavailable", str(exc))
    except (StandaloneServiceError, UploadStorageError, ChunkingStorageError):
        return _chunking_error(503, "Semantic preparation unavailable", "Semantic chunk storage is unavailable")
    return SuccessResponse(message="Semantic chunks prepared", data=result)


@router.get(
    "/{agent_project_id}/input-files/{upload_id}/chunks",
    response_model=SuccessResponse[DocumentChunkingResult],
)
def get_implementation_document_chunks(
    agent_project_id: str,
    upload_id: str,
    service: Annotated[
        SemanticChunkingService, Depends(get_semantic_chunking_service)
    ],
    current_user: Annotated[UserPublicResponse, Depends(get_current_user)],
) -> SuccessResponse[DocumentChunkingResult] | JSONResponse:
    try:
        result = service.get_existing(agent_project_id, upload_id, current_user)
    except AgentProjectNotFoundError:
        return _error(404, "Agent project not found", "agent_project_id", "Agent project not found")
    except ArchivedAgentProjectError:
        return _error(409, "Agent project is archived", "agent_project_id", "Reactivate the agent project before reviewing semantic chunks")
    except WrongAgentProjectTypeError as exc:
        return _error(422, "Wrong agent project type", "agent_project_id", str(exc))
    except UploadNotFoundError:
        return _chunking_error(404, "Upload not found", "Staged upload not found")
    except (ExtractionNotFoundError, ChunkingNotFoundError):
        return _chunking_error(404, "Semantic chunks not found", "No current semantic chunk result exists for this upload")
    except (UnsupportedExtractionSourceError, ChunkingUnavailableError) as exc:
        return _chunking_error(422, "Semantic preparation unavailable", str(exc))
    except (StandaloneServiceError, UploadStorageError):
        return _chunking_error(503, "Semantic preparation unavailable", "Semantic chunk storage is unavailable")
    return SuccessResponse(message="Semantic chunks retrieved", data=result)


def _rule_detection_error(
    status_code: int, message: str, detail: str
) -> JSONResponse:
    return _error(status_code, message, "rule_detections", detail)


@router.post(
    "/{agent_project_id}/input-files/{upload_id}/rule-detections",
    response_model=SuccessResponse[DocumentRuleDetectionResult],
)
def build_implementation_rule_detections(
    agent_project_id: str,
    upload_id: str,
    service: Annotated[
        RuleDetectionService, Depends(get_rule_detection_service)
    ],
    current_user: Annotated[UserPublicResponse, Depends(get_current_user)],
    force: Annotated[bool, Query()] = False,
) -> SuccessResponse[DocumentRuleDetectionResult] | JSONResponse:
    try:
        result = service.build(
            agent_project_id, upload_id, current_user, force=force
        )
    except AgentProjectNotFoundError:
        return _error(404, "Agent project not found", "agent_project_id", "Agent project not found")
    except ArchivedAgentProjectError:
        return _error(409, "Agent project is archived", "agent_project_id", "Reactivate the agent project before running rule detection")
    except WrongAgentProjectTypeError as exc:
        return _error(422, "Wrong agent project type", "agent_project_id", str(exc))
    except UploadNotFoundError:
        return _rule_detection_error(404, "Upload not found", "Staged upload not found")
    except (ExtractionNotFoundError, ChunkingNotFoundError):
        return _rule_detection_error(409, "Rule detection unavailable", "Current trusted semantic chunks must exist before rule detection")
    except (UnsupportedExtractionSourceError, ChunkingUnavailableError) as exc:
        return _rule_detection_error(422, "Rule detection unavailable", str(exc))
    except (StandaloneServiceError, UploadStorageError, RuleDetectionStorageError):
        return _rule_detection_error(503, "Rule detection unavailable", "Rule-detection storage is unavailable")
    return SuccessResponse(message="Rule-based artifact detection completed", data=result)


@router.get(
    "/{agent_project_id}/input-files/{upload_id}/rule-detections",
    response_model=SuccessResponse[DocumentRuleDetectionResult],
)
def get_implementation_rule_detections(
    agent_project_id: str,
    upload_id: str,
    service: Annotated[
        RuleDetectionService, Depends(get_rule_detection_service)
    ],
    current_user: Annotated[UserPublicResponse, Depends(get_current_user)],
) -> SuccessResponse[DocumentRuleDetectionResult] | JSONResponse:
    try:
        result = service.get_existing(agent_project_id, upload_id, current_user)
    except AgentProjectNotFoundError:
        return _error(404, "Agent project not found", "agent_project_id", "Agent project not found")
    except ArchivedAgentProjectError:
        return _error(409, "Agent project is archived", "agent_project_id", "Reactivate the agent project before reviewing rule detection")
    except WrongAgentProjectTypeError as exc:
        return _error(422, "Wrong agent project type", "agent_project_id", str(exc))
    except UploadNotFoundError:
        return _rule_detection_error(404, "Upload not found", "Staged upload not found")
    except (ExtractionNotFoundError, ChunkingNotFoundError, RuleDetectionNotFoundError):
        return _rule_detection_error(404, "Rule detections not found", "No current rule-detection result exists for this upload")
    except (UnsupportedExtractionSourceError, ChunkingUnavailableError) as exc:
        return _rule_detection_error(422, "Rule detection unavailable", str(exc))
    except (StandaloneServiceError, UploadStorageError):
        return _rule_detection_error(503, "Rule detection unavailable", "Rule-detection storage is unavailable")
    return SuccessResponse(message="Rule-based artifact detections retrieved", data=result)


def _zero_shot_error(
    status_code: int, message: str, detail: str
) -> JSONResponse:
    return _error(status_code, message, "zero_shot_detections", detail)


@router.post(
    "/{agent_project_id}/input-files/{upload_id}/zero-shot-detections",
    response_model=SuccessResponse[DocumentZeroShotDetectionResult],
)
def build_implementation_zero_shot_detections(
    agent_project_id: str,
    upload_id: str,
    service: Annotated[
        ZeroShotDetectionService, Depends(get_zero_shot_detection_service)
    ],
    current_user: Annotated[UserPublicResponse, Depends(get_current_user)],
    force: Annotated[bool, Query()] = False,
) -> SuccessResponse[DocumentZeroShotDetectionResult] | JSONResponse:
    try:
        result = service.build(
            agent_project_id, upload_id, current_user, force=force
        )
    except AgentProjectNotFoundError:
        return _error(404, "Agent project not found", "agent_project_id", "Agent project not found")
    except ArchivedAgentProjectError:
        return _error(409, "Agent project is archived", "agent_project_id", "Reactivate the agent project before running zero-shot classification")
    except WrongAgentProjectTypeError as exc:
        return _error(422, "Wrong agent project type", "agent_project_id", str(exc))
    except UploadNotFoundError:
        return _zero_shot_error(404, "Upload not found", "Staged upload not found")
    except (ExtractionNotFoundError, ChunkingNotFoundError):
        return _zero_shot_error(409, "Zero-shot classification unavailable", "Current trusted semantic chunks must exist before zero-shot classification")
    except (UnsupportedExtractionSourceError, ChunkingUnavailableError) as exc:
        return _zero_shot_error(422, "Zero-shot classification unavailable", str(exc))
    except (StandaloneServiceError, UploadStorageError, ZeroShotDetectionStorageError):
        return _zero_shot_error(503, "Zero-shot classification unavailable", "Zero-shot result storage is unavailable")
    return SuccessResponse(message="Zero-shot artifact classification completed", data=result)


@router.get(
    "/{agent_project_id}/input-files/{upload_id}/zero-shot-detections",
    response_model=SuccessResponse[DocumentZeroShotDetectionResult],
)
def get_implementation_zero_shot_detections(
    agent_project_id: str,
    upload_id: str,
    service: Annotated[
        ZeroShotDetectionService, Depends(get_zero_shot_detection_service)
    ],
    current_user: Annotated[UserPublicResponse, Depends(get_current_user)],
) -> SuccessResponse[DocumentZeroShotDetectionResult] | JSONResponse:
    try:
        result = service.get_existing(agent_project_id, upload_id, current_user)
    except AgentProjectNotFoundError:
        return _error(404, "Agent project not found", "agent_project_id", "Agent project not found")
    except ArchivedAgentProjectError:
        return _error(409, "Agent project is archived", "agent_project_id", "Reactivate the agent project before reviewing zero-shot classification")
    except WrongAgentProjectTypeError as exc:
        return _error(422, "Wrong agent project type", "agent_project_id", str(exc))
    except UploadNotFoundError:
        return _zero_shot_error(404, "Upload not found", "Staged upload not found")
    except (ExtractionNotFoundError, ChunkingNotFoundError, ZeroShotDetectionNotFoundError):
        return _zero_shot_error(404, "Zero-shot detections not found", "No current zero-shot result exists for this upload")
    except (UnsupportedExtractionSourceError, ChunkingUnavailableError) as exc:
        return _zero_shot_error(422, "Zero-shot classification unavailable", str(exc))
    except (StandaloneServiceError, UploadStorageError):
        return _zero_shot_error(503, "Zero-shot classification unavailable", "Zero-shot result storage is unavailable")
    return SuccessResponse(message="Zero-shot artifact classifications retrieved", data=result)


def _hybrid_error(status_code: int, message: str, detail: str) -> JSONResponse:
    return _error(status_code, message, "hybrid_detections", detail)


@router.post(
    "/{agent_project_id}/input-files/{upload_id}/hybrid-detections",
    response_model=SuccessResponse[DocumentHybridDetectionResult],
)
def build_implementation_hybrid_detections(
    agent_project_id: str,
    upload_id: str,
    service: Annotated[HybridDetectionService, Depends(get_hybrid_detection_service)],
    current_user: Annotated[UserPublicResponse, Depends(get_current_user)],
    force: Annotated[bool, Query()] = False,
) -> SuccessResponse[DocumentHybridDetectionResult] | JSONResponse:
    try:
        result = service.build(agent_project_id, upload_id, current_user, force=force)
    except AgentProjectNotFoundError:
        return _error(404, "Agent project not found", "agent_project_id", "Agent project not found")
    except ArchivedAgentProjectError:
        return _error(409, "Agent project is archived", "agent_project_id", "Reactivate the agent project before building hybrid candidates")
    except WrongAgentProjectTypeError as exc:
        return _error(422, "Wrong agent project type", "agent_project_id", str(exc))
    except UploadNotFoundError:
        return _hybrid_error(404, "Upload not found", "Staged upload not found")
    except RuleDetectionRequiredError:
        return _hybrid_error(409, "Hybrid detection unavailable", "RULE_DETECTION_REQUIRED")
    except ZeroShotDetectionRequiredError:
        return _hybrid_error(409, "Hybrid detection unavailable", "ZERO_SHOT_DETECTION_REQUIRED")
    except StaleClassificationInputError:
        return _hybrid_error(409, "Hybrid detection unavailable", "STALE_CLASSIFICATION_INPUT")
    except (ExtractionNotFoundError, ChunkingNotFoundError):
        return _hybrid_error(409, "Hybrid detection unavailable", "Current trusted semantic chunks are required")
    except (UnsupportedExtractionSourceError, ChunkingUnavailableError) as exc:
        return _hybrid_error(422, "Hybrid detection unavailable", str(exc))
    except (StandaloneServiceError, UploadStorageError, HybridDetectionStorageError):
        return _hybrid_error(503, "Hybrid detection unavailable", "Hybrid result storage is unavailable")
    return SuccessResponse(message="Hybrid artifact candidates built", data=result)


@router.get(
    "/{agent_project_id}/input-files/{upload_id}/hybrid-detections",
    response_model=SuccessResponse[DocumentHybridDetectionResult],
)
def get_implementation_hybrid_detections(
    agent_project_id: str,
    upload_id: str,
    service: Annotated[HybridDetectionService, Depends(get_hybrid_detection_service)],
    current_user: Annotated[UserPublicResponse, Depends(get_current_user)],
) -> SuccessResponse[DocumentHybridDetectionResult] | JSONResponse:
    try:
        result = service.get_existing(agent_project_id, upload_id, current_user)
    except AgentProjectNotFoundError:
        return _error(404, "Agent project not found", "agent_project_id", "Agent project not found")
    except ArchivedAgentProjectError:
        return _error(409, "Agent project is archived", "agent_project_id", "Reactivate the agent project before reviewing hybrid candidates")
    except WrongAgentProjectTypeError as exc:
        return _error(422, "Wrong agent project type", "agent_project_id", str(exc))
    except UploadNotFoundError:
        return _hybrid_error(404, "Upload not found", "Staged upload not found")
    except RuleDetectionRequiredError:
        return _hybrid_error(409, "Hybrid detection unavailable", "RULE_DETECTION_REQUIRED")
    except ZeroShotDetectionRequiredError:
        return _hybrid_error(409, "Hybrid detection unavailable", "ZERO_SHOT_DETECTION_REQUIRED")
    except StaleClassificationInputError:
        return _hybrid_error(409, "Hybrid detection unavailable", "STALE_CLASSIFICATION_INPUT")
    except (ExtractionNotFoundError, ChunkingNotFoundError, HybridDetectionNotFoundError):
        return _hybrid_error(404, "Hybrid detections not found", "No current hybrid result exists for this upload")
    except (UnsupportedExtractionSourceError, ChunkingUnavailableError) as exc:
        return _hybrid_error(422, "Hybrid detection unavailable", str(exc))
    except (StandaloneServiceError, UploadStorageError):
        return _hybrid_error(503, "Hybrid detection unavailable", "Hybrid result storage is unavailable")
    return SuccessResponse(message="Hybrid artifact candidates retrieved", data=result)


def _human_review_error(status_code: int, message: str, detail: str) -> JSONResponse:
    return _error(status_code, message, "human_reviews", detail)


@router.get(
    "/{agent_project_id}/input-files/{upload_id}/human-reviews",
    response_model=SuccessResponse[HumanReviewStateResponse],
)
def get_implementation_human_reviews(
    agent_project_id: str,
    upload_id: str,
    service: Annotated[HumanReviewService, Depends(get_human_review_service)],
    current_user: Annotated[UserPublicResponse, Depends(get_current_user)],
) -> SuccessResponse[HumanReviewStateResponse] | JSONResponse:
    try:
        result = service.get_state(agent_project_id, upload_id, current_user)
    except AgentProjectNotFoundError:
        return _error(404, "Agent project not found", "agent_project_id", "Agent project not found")
    except ArchivedAgentProjectError:
        return _error(409, "Agent project is archived", "agent_project_id", "Reactivate the agent project before human verification")
    except WrongAgentProjectTypeError as exc:
        return _error(422, "Wrong agent project type", "agent_project_id", str(exc))
    except UploadNotFoundError:
        return _human_review_error(404, "Upload not found", "Staged upload not found")
    except HybridReviewRequiredError:
        return _human_review_error(409, "Human verification unavailable", "HYBRID_DETECTION_REQUIRED")
    except RuleDetectionRequiredError:
        return _human_review_error(409, "Human verification unavailable", "RULE_DETECTION_REQUIRED")
    except ZeroShotDetectionRequiredError:
        return _human_review_error(409, "Human verification unavailable", "ZERO_SHOT_DETECTION_REQUIRED")
    except StaleClassificationInputError:
        return _human_review_error(409, "Human verification unavailable", "STALE_CLASSIFICATION_INPUT")
    except (ExtractionNotFoundError, ChunkingNotFoundError):
        return _human_review_error(409, "Human verification unavailable", "Current trusted semantic chunks are required")
    except (UnsupportedExtractionSourceError, ChunkingUnavailableError) as exc:
        return _human_review_error(422, "Human verification unavailable", str(exc))
    except (StandaloneServiceError, UploadStorageError, HumanReviewStorageError):
        return _human_review_error(503, "Human verification unavailable", "Human-review storage is unavailable")
    return SuccessResponse(message="Human artifact verification state retrieved", data=result)


@router.put(
    "/{agent_project_id}/input-files/{upload_id}/human-reviews/{chunk_id}",
    response_model=SuccessResponse[HumanReviewStateResponse],
)
def save_implementation_human_review(
    agent_project_id: str,
    upload_id: str,
    chunk_id: str,
    request: ChunkHumanReviewUpdate,
    service: Annotated[HumanReviewService, Depends(get_human_review_service)],
    current_user: Annotated[UserPublicResponse, Depends(get_current_user)],
) -> SuccessResponse[HumanReviewStateResponse] | JSONResponse:
    try:
        result = service.save_chunk(
            agent_project_id, upload_id, chunk_id, request, current_user
        )
    except AgentProjectNotFoundError:
        return _error(404, "Agent project not found", "agent_project_id", "Agent project not found")
    except ArchivedAgentProjectError:
        return _error(409, "Agent project is archived", "agent_project_id", "Reactivate the agent project before human verification")
    except WrongAgentProjectTypeError as exc:
        return _error(422, "Wrong agent project type", "agent_project_id", str(exc))
    except UploadNotFoundError:
        return _human_review_error(404, "Upload not found", "Staged upload not found")
    except HybridReviewRequiredError:
        return _human_review_error(409, "Human verification unavailable", "HYBRID_DETECTION_REQUIRED")
    except RuleDetectionRequiredError:
        return _human_review_error(409, "Human verification unavailable", "RULE_DETECTION_REQUIRED")
    except ZeroShotDetectionRequiredError:
        return _human_review_error(409, "Human verification unavailable", "ZERO_SHOT_DETECTION_REQUIRED")
    except StaleClassificationInputError:
        return _human_review_error(409, "Human verification unavailable", "STALE_CLASSIFICATION_INPUT")
    except StaleHumanReviewError:
        return _human_review_error(409, "Human verification is stale", "STALE_HUMAN_REVIEW")
    except HumanReviewValidationError as exc:
        return _human_review_error(422, "Invalid human-review decision", str(exc))
    except (ExtractionNotFoundError, ChunkingNotFoundError):
        return _human_review_error(409, "Human verification unavailable", "Current trusted semantic chunks are required")
    except (UnsupportedExtractionSourceError, ChunkingUnavailableError) as exc:
        return _human_review_error(422, "Human verification unavailable", str(exc))
    except (StandaloneServiceError, UploadStorageError, HumanReviewStorageError):
        return _human_review_error(503, "Human verification unavailable", "Human-review storage is unavailable")
    return SuccessResponse(message="Human artifact verification saved", data=result)


def _canonical_error(status_code: int, message: str, detail: str) -> JSONResponse:
    return _error(status_code, message, "canonical_artifacts", detail)


@router.post(
    "/{agent_project_id}/input-files/{upload_id}/canonical-artifacts",
    response_model=SuccessResponse[DocumentCanonicalArtifactResult],
)
def build_implementation_canonical_artifacts(
    agent_project_id: str,
    upload_id: str,
    service: Annotated[CanonicalArtifactService, Depends(get_canonical_artifact_service)],
    current_user: Annotated[UserPublicResponse, Depends(get_current_user)],
    force: Annotated[bool, Query()] = False,
) -> SuccessResponse[DocumentCanonicalArtifactResult] | JSONResponse:
    try:
        result = service.build(agent_project_id, upload_id, current_user, force=force)
    except AgentProjectNotFoundError:
        return _error(404, "Agent project not found", "agent_project_id", "Agent project not found")
    except ArchivedAgentProjectError:
        return _error(409, "Agent project is archived", "agent_project_id", "Reactivate the agent project before canonical extraction")
    except WrongAgentProjectTypeError as exc:
        return _error(422, "Wrong agent project type", "agent_project_id", str(exc))
    except UploadNotFoundError:
        return _canonical_error(404, "Upload not found", "Staged upload not found")
    except SemanticChunksRequiredError:
        return _canonical_error(409, "Canonical extraction unavailable", "SEMANTIC_CHUNKS_REQUIRED")
    except (HumanVerificationRequiredError, RuleDetectionRequiredError,
            ZeroShotDetectionRequiredError, HybridReviewRequiredError):
        return _canonical_error(409, "Canonical extraction unavailable", "HUMAN_VERIFICATION_REQUIRED")
    except (StaleHumanVerificationError, StaleClassificationInputError):
        return _canonical_error(409, "Canonical extraction unavailable", "STALE_HUMAN_VERIFICATION")
    except (ExtractionNotFoundError, ChunkingNotFoundError):
        return _canonical_error(409, "Canonical extraction unavailable", "SEMANTIC_CHUNKS_REQUIRED")
    except (UnsupportedExtractionSourceError, ChunkingUnavailableError) as exc:
        return _canonical_error(422, "Canonical extraction unavailable", str(exc))
    except (StandaloneServiceError, UploadStorageError, HumanReviewStorageError,
            CanonicalArtifactStorageError):
        return _canonical_error(503, "Canonical extraction unavailable", "Canonical artifact storage is unavailable")
    return SuccessResponse(message="Canonical artifacts prepared", data=result)


@router.get(
    "/{agent_project_id}/input-files/{upload_id}/canonical-artifacts",
    response_model=SuccessResponse[DocumentCanonicalArtifactResult],
)
def get_implementation_canonical_artifacts(
    agent_project_id: str,
    upload_id: str,
    service: Annotated[CanonicalArtifactService, Depends(get_canonical_artifact_service)],
    current_user: Annotated[UserPublicResponse, Depends(get_current_user)],
) -> SuccessResponse[DocumentCanonicalArtifactResult] | JSONResponse:
    try:
        result = service.get_existing(agent_project_id, upload_id, current_user)
    except AgentProjectNotFoundError:
        return _error(404, "Agent project not found", "agent_project_id", "Agent project not found")
    except ArchivedAgentProjectError:
        return _error(409, "Agent project is archived", "agent_project_id", "Reactivate the agent project before reviewing canonical artifacts")
    except WrongAgentProjectTypeError as exc:
        return _error(422, "Wrong agent project type", "agent_project_id", str(exc))
    except UploadNotFoundError:
        return _canonical_error(404, "Upload not found", "Staged upload not found")
    except SemanticChunksRequiredError:
        return _canonical_error(409, "Canonical extraction unavailable", "SEMANTIC_CHUNKS_REQUIRED")
    except (HumanVerificationRequiredError, RuleDetectionRequiredError,
            ZeroShotDetectionRequiredError, HybridReviewRequiredError):
        return _canonical_error(409, "Canonical extraction unavailable", "HUMAN_VERIFICATION_REQUIRED")
    except (StaleHumanVerificationError, StaleClassificationInputError):
        return _canonical_error(409, "Canonical extraction unavailable", "STALE_HUMAN_VERIFICATION")
    except CanonicalArtifactsNotFoundError:
        return _canonical_error(404, "Canonical artifacts not found", "No current canonical artifact result exists for this upload")
    except (ExtractionNotFoundError, ChunkingNotFoundError):
        return _canonical_error(409, "Canonical extraction unavailable", "SEMANTIC_CHUNKS_REQUIRED")
    except (UnsupportedExtractionSourceError, ChunkingUnavailableError) as exc:
        return _canonical_error(422, "Canonical extraction unavailable", str(exc))
    except (StandaloneServiceError, UploadStorageError, HumanReviewStorageError,
            CanonicalArtifactStorageError):
        return _canonical_error(503, "Canonical extraction unavailable", "Canonical artifact storage is unavailable")
    return SuccessResponse(message="Canonical artifacts retrieved", data=result)


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


@router.post(
    "/{agent_project_id}/github/connect",
    response_model=SuccessResponse[GitHubConnectResponse],
)
def connect_github(
    agent_project_id: str,
    service: Annotated[
        GitHubConnectionService | None,
        Depends(get_github_connection_service),
    ],
    current_user: Annotated[UserPublicResponse, Depends(get_current_user)],
) -> SuccessResponse[GitHubConnectResponse] | JSONResponse:
    if service is None:
        return _error(
            503,
            "GitHub connection unavailable",
            "github",
            "GitHub App connection is not configured",
        )
    try:
        result = service.begin_connection(agent_project_id, current_user)
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
            "Reactivate the agent project before connecting GitHub",
        )
    except WrongAgentProjectTypeError as exc:
        return _error(
            422, "Wrong agent project type", "agent_project_id", str(exc)
        )
    except StandaloneServiceError:
        return _error(
            503,
            "GitHub connection unavailable",
            "database",
            "Standalone project storage is unavailable",
        )
    return SuccessResponse(message="GitHub installation started", data=result)


@router.get("/github/install-callback", include_in_schema=True)
def github_install_callback(
    service: Annotated[
        GitHubConnectionService | None,
        Depends(get_github_connection_service),
    ],
    state_value: Annotated[str | None, Query(alias="state")] = None,
    installation_id: Annotated[int | None, Query()] = None,
    setup_action: Annotated[str | None, Query()] = None,
) -> RedirectResponse:
    del setup_action
    if service is None:
        return RedirectResponse(
            _frontend_callback_url(reason="configuration_unavailable"),
            status_code=302,
        )
    if not state_value or installation_id is None:
        return RedirectResponse(
            _frontend_callback_url(reason="invalid_state"), status_code=302
        )
    try:
        authorization_url = service.continue_after_installation(
            state_value, installation_id
        )
    except GitHubStateError:
        return RedirectResponse(
            _frontend_callback_url(reason="invalid_state"), status_code=302
        )
    except GitHubCallbackError as exc:
        return RedirectResponse(
            _frontend_callback_url(
                agent_project_id=exc.agent_project_id,
                reason=exc.reason,
            ),
            status_code=302,
        )
    return RedirectResponse(authorization_url, status_code=302)


@router.get("/github/oauth-callback", include_in_schema=True)
def github_oauth_callback(
    service: Annotated[
        GitHubConnectionService | None,
        Depends(get_github_connection_service),
    ],
    state_value: Annotated[str | None, Query(alias="state")] = None,
    code: Annotated[str | None, Query()] = None,
    error: Annotated[str | None, Query()] = None,
    error_description: Annotated[str | None, Query()] = None,
) -> RedirectResponse:
    del error_description
    if service is None:
        return RedirectResponse(
            _frontend_callback_url(reason="configuration_unavailable"),
            status_code=302,
        )
    if not state_value:
        return RedirectResponse(
            _frontend_callback_url(reason="invalid_state"), status_code=302
        )
    try:
        agent_project_id = service.complete_connection(
            state=state_value,
            code=code,
            oauth_error=error,
        )
    except GitHubStateError:
        return RedirectResponse(
            _frontend_callback_url(reason="invalid_state"), status_code=302
        )
    except GitHubCallbackError as exc:
        return RedirectResponse(
            _frontend_callback_url(
                agent_project_id=exc.agent_project_id,
                reason=exc.reason,
            ),
            status_code=302,
        )
    return RedirectResponse(
        _frontend_callback_url(
            agent_project_id=agent_project_id, connected=True
        ),
        status_code=302,
    )


@router.get(
    "/{agent_project_id}/github/connection",
    response_model=SuccessResponse[GitHubConnectionStatus],
    response_model_exclude_none=True,
)
def get_github_connection(
    agent_project_id: str,
    service: Annotated[
        GitHubConnectionService | None,
        Depends(get_github_connection_service),
    ],
    current_user: Annotated[UserPublicResponse, Depends(get_current_user)],
) -> SuccessResponse[GitHubConnectionStatus] | JSONResponse:
    if service is None:
        return _error(
            503,
            "GitHub connection unavailable",
            "github",
            "GitHub App connection is not configured",
        )
    try:
        result = service.connection_status(agent_project_id, current_user)
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
            "Reactivate the agent project before checking GitHub",
        )
    except WrongAgentProjectTypeError as exc:
        return _error(
            422, "Wrong agent project type", "agent_project_id", str(exc)
        )
    except (StandaloneServiceError, GitHubConnectionRepositoryError):
        return _error(
            503,
            "GitHub connection unavailable",
            "database",
            "GitHub connection storage is unavailable",
        )
    return SuccessResponse(message="GitHub connection retrieved", data=result)


def _repository_failure(
    status_code: int,
    message: str,
    detail: str,
    repository: GitHubRepositoryStatus | None = None,
) -> JSONResponse:
    content = ErrorResponse(
        message=message,
        errors=[ErrorDetail(field="repository", message=detail)],
    ).model_dump(mode="json")
    if repository is not None:
        content["data"] = {
            "repository": repository.model_dump(mode="json", exclude_none=True)
        }
    return JSONResponse(status_code=status_code, content=content)


@router.get(
    "/{agent_project_id}/github/repository",
    response_model=SuccessResponse[GitHubRepositoryStatus],
    response_model_exclude_none=True,
)
def get_github_repository(
    agent_project_id: str,
    service: Annotated[
        GitHubRepositoryService, Depends(get_github_repository_service)
    ],
    current_user: Annotated[UserPublicResponse, Depends(get_current_user)],
) -> SuccessResponse[GitHubRepositoryStatus] | JSONResponse:
    try:
        repository = service.get_repository(agent_project_id, current_user)
    except AgentProjectNotFoundError:
        return _error(404, "Agent project not found", "agent_project_id", "Agent project not found")
    except ArchivedAgentProjectError:
        return _error(
            409,
            "Agent project is archived",
            "agent_project_id",
            "Reactivate the agent project before checking its GitHub repository",
        )
    except WrongAgentProjectTypeError as exc:
        return _error(422, "Wrong agent project type", "agent_project_id", str(exc))
    except (StandaloneServiceError, GitHubRepositoryBindingRepositoryError):
        return _repository_failure(
            503,
            "GitHub repository unavailable",
            "Repository binding storage is unavailable",
        )
    return SuccessResponse(message="GitHub repository retrieved", data=repository)


@router.post(
    "/{agent_project_id}/github/repository",
    response_model=SuccessResponse[GitHubRepositoryStatus],
    response_model_exclude_none=True,
    status_code=status.HTTP_201_CREATED,
)
def create_github_repository(
    agent_project_id: str,
    request: GitHubRepositoryCreateRequest,
    service: Annotated[
        GitHubRepositoryService, Depends(get_github_repository_service)
    ],
    current_user: Annotated[UserPublicResponse, Depends(get_current_user)],
) -> SuccessResponse[GitHubRepositoryStatus] | JSONResponse:
    try:
        repository = service.create_repository(
            agent_project_id, current_user, request
        )
    except AgentProjectNotFoundError:
        return _error(404, "Agent project not found", "agent_project_id", "Agent project not found")
    except ArchivedAgentProjectError:
        return _error(
            409,
            "Agent project is archived",
            "agent_project_id",
            "Reactivate the agent project before creating a GitHub repository",
        )
    except WrongAgentProjectTypeError as exc:
        return _error(422, "Wrong agent project type", "agent_project_id", str(exc))
    except GitHubRepositoryAlreadyBoundError as exc:
        return _repository_failure(409, str(exc), str(exc), exc.repository)
    except GitHubConnectionRequiredError as exc:
        return _repository_failure(409, "GitHub connection required", str(exc))
    except GitHubOrganizationConnectionError as exc:
        return _repository_failure(422, "Unsupported GitHub account", str(exc))
    except GitHubPrivateKeyError as exc:
        return _repository_failure(503, "GitHub App configuration unavailable", str(exc))
    except (GitHubInstallationRevokedError, GitHubRepositoryAuthenticationError) as exc:
        return _repository_failure(409, "GitHub reconnection required", str(exc))
    except GitHubAppAuthenticationError as exc:
        return _repository_failure(502, "GitHub App authentication failed", str(exc))
    except (GitHubAppPermissionError, GitHubRepositoryPermissionError) as exc:
        return _repository_failure(403, "GitHub App permission denied", str(exc))
    except GitHubRepositoryNameConflictError as exc:
        return _repository_failure(409, "Repository name unavailable", str(exc))
    except GitHubRepositoryValidationError as exc:
        return _repository_failure(422, "Repository creation rejected", str(exc))
    except GitHubRepositoryPartialFailureError as exc:
        return _repository_failure(
            502,
            "Repository created but binding failed",
            str(exc),
            exc.repository,
        )
    except (GitHubExternalServiceError, GitHubRepositoryExternalError) as exc:
        return _repository_failure(502, "GitHub repository unavailable", str(exc))
    except (
        StandaloneServiceError,
        GitHubConnectionRepositoryError,
        GitHubRepositoryBindingRepositoryError,
    ):
        return _repository_failure(
            503,
            "GitHub repository unavailable",
            "GitHub repository storage is unavailable",
        )
    return SuccessResponse(message="GitHub repository created", data=repository)
