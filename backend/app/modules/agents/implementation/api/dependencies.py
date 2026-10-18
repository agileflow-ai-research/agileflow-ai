"""Dependency factories shared by Agent 3 route modules."""

from typing import Annotated
from fastapi import APIRouter, Depends, File, Form, Query, UploadFile, status
from app.core.config import settings
from app.modules.agents.implementation.inputs.extraction.service import (
    DocumentExtractionService,
    ExtractionNotFoundError,
    ExtractionStorageError,
    UnsupportedExtractionSourceError,
)
from app.modules.agents.implementation.github.auth import (
    GitHubAppAuthenticationError,
    GitHubAppAuthenticator,
    GitHubAppPermissionError,
    GitHubExternalServiceError,
    GitHubInstallationRevokedError,
    GitHubPrivateKeyError,
)
from app.modules.agents.implementation.github.repository_service import (
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
from app.modules.agents.implementation.github.connection_service import (
    GitHubApiClient,
    GitHubCallbackError,
    GitHubConfiguration,
    GitHubConfigurationError,
    GitHubConnectionService,
    GitHubStateError,
    GitHubStateStore,
)
from app.modules.agents.implementation.github.repository import (
    GitHubConnectionRepository,
    GitHubConnectionRepositoryError,
    GitHubRepositoryBindingRepository,
    GitHubRepositoryBindingRepositoryError,
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
from app.modules.agents.implementation.preparation.classification.zero_shot.classifier import (
    ZeroShotClassifier,
)
from app.modules.agents.implementation.preparation.classification.zero_shot.service import (
    ZeroShotDetectionNotFoundError,
    ZeroShotDetectionService,
    ZeroShotDetectionStorageError,
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
from app.modules.agents.implementation.preparation.orchestration.service import (
    ProjectPreparationService,
)
from app.modules.agents.implementation.preparation.orchestration.storage import (
    ProjectPreparationStorage,
)
from app.modules.agents.implementation.preparation.semantic_extraction.artifact_service import (
    CanonicalArtifactsRequiredError,
    SemanticArtifactService,
    SemanticArtifactsNotFoundError,
    SemanticArtifactStorageError,
)
from app.modules.agents.implementation.preparation.semantic_extraction.local_model.adapter import (
    LocalSemanticExtractorAdapter,
)
from app.modules.agents.implementation.infrastructure.storage import (
    ImplementationUploadStorage,
    UploadNotFoundError,
    UploadStorageError,
    UploadValidationError,
)
from app.modules.standalone.router import get_standalone_service
from app.modules.standalone.service import (
    AgentProjectNotFoundError,
    ArchivedAgentProjectError,
    StandaloneService,
    StandaloneServiceError,
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


def get_project_preparation_storage() -> ProjectPreparationStorage:
    return ProjectPreparationStorage(settings.agent3_upload_root)


def get_project_preparation_service(
    standalone_service: Annotated[
        StandaloneService, Depends(get_standalone_service)
    ],
    upload_storage: Annotated[
        ImplementationUploadStorage,
        Depends(get_implementation_upload_storage),
    ],
    state_storage: Annotated[
        ProjectPreparationStorage,
        Depends(get_project_preparation_storage),
    ],
    extraction_service: Annotated[
        DocumentExtractionService,
        Depends(get_document_extraction_service),
    ],
    chunking_service: Annotated[
        SemanticChunkingService,
        Depends(get_semantic_chunking_service),
    ],
    rule_service: Annotated[
        RuleDetectionService,
        Depends(get_rule_detection_service),
    ],
    zero_shot_service: Annotated[
        ZeroShotDetectionService,
        Depends(get_zero_shot_detection_service),
    ],
    hybrid_service: Annotated[
        HybridDetectionService,
        Depends(get_hybrid_detection_service),
    ],
    human_review_service: Annotated[
        HumanReviewService,
        Depends(get_human_review_service),
    ],
) -> ProjectPreparationService:
    return ProjectPreparationService(
        standalone_service,
        upload_storage,
        state_storage,
        extraction_service,
        chunking_service,
        rule_service,
        zero_shot_service,
        hybrid_service,
        human_review_service,
    )


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

