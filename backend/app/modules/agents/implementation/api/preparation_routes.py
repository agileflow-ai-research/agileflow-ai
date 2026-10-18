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
from app.modules.agents.implementation.inputs.upload.service import (
    ImplementationInputService,
    WrongAgentProjectTypeError,
)
from app.modules.agents.implementation.preparation.schemas import (
    DocumentChunkingResult,
    DocumentRuleDetectionResult,
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
from app.modules.agents.implementation.preparation.classification.zero_shot.schemas import (
    DocumentZeroShotDetectionResult,
)
from app.modules.agents.implementation.preparation.classification.zero_shot.service import (
    ZeroShotDetectionNotFoundError,
    ZeroShotDetectionService,
    ZeroShotDetectionStorageError,
)
from app.modules.agents.implementation.preparation.hybrid.schemas import (
    DocumentHybridDetectionResult,
)
from app.modules.agents.implementation.preparation.hybrid.service import (
    HybridDetectionNotFoundError,
    HybridDetectionService,
    HybridDetectionStorageError,
    RuleDetectionRequiredError,
    StaleClassificationInputError,
    ZeroShotDetectionRequiredError,
)
from app.modules.agents.implementation.preparation.human_review.schemas import (
    ChunkHumanReviewUpdate,
    DocumentReviewStatus,
    HumanReviewStateResponse,
)
from app.modules.agents.implementation.preparation.specification.service import (
    ProjectSpecificationService,
)
from app.modules.agents.implementation.preparation.orchestration.storage import (
    ProjectPreparationStorage,
)
from app.modules.agents.implementation.preparation.human_review.service import (
    HumanReviewService,
    HumanReviewStorageError,
    HumanReviewValidationError,
    HybridReviewRequiredError,
    StaleHumanReviewError,
)
from app.modules.agents.implementation.preparation.canonical.schemas import (
    DocumentCanonicalArtifactResult,
)
from app.modules.agents.implementation.preparation.canonical.service import (
    CanonicalArtifactService,
    CanonicalArtifactStorageError,
    CanonicalArtifactsNotFoundError,
    HumanVerificationRequiredError,
    SemanticChunksRequiredError,
    StaleHumanVerificationError,
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
    get_canonical_artifact_service,
    get_human_review_service,
    get_hybrid_detection_service,
    get_project_specification_service,
    get_project_preparation_storage,
    get_rule_detection_service,
    get_semantic_chunking_service,
    get_zero_shot_detection_service,
)
from app.modules.agents.implementation.api.errors import (
    _error,
)


router = APIRouter()


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
    specification_service: Annotated[
        ProjectSpecificationService,
        Depends(get_project_specification_service),
    ],
    preparation_storage: Annotated[
        ProjectPreparationStorage,
        Depends(get_project_preparation_storage),
    ],
    current_user: Annotated[UserPublicResponse, Depends(get_current_user)],
) -> SuccessResponse[HumanReviewStateResponse] | JSONResponse:
    try:
        result = service.save_chunk(
            agent_project_id, upload_id, chunk_id, request, current_user
        )
        preparation = preparation_storage.load(
            agent_project_id=agent_project_id,
            owner_user_id=current_user.user_id,
        )
        if (
            preparation is not None
            and result.review.review_status is DocumentReviewStatus.COMPLETE
        ):
            specification_service.start(agent_project_id, current_user)
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


