"""Composition root for the Implementation and Git Automation Agent API."""

from fastapi import APIRouter

from app.modules.agents.implementation.api.github_routes import (
    router as github_router,
)
from app.modules.agents.implementation.api.input_routes import (
    router as input_router,
)
from app.modules.agents.implementation.api.preparation_routes import (
    router as preparation_router,
)
from app.modules.agents.implementation.api.project_preparation_routes import (
    router as project_preparation_router,
)
from app.modules.agents.implementation.api.semantic_routes import (
    router as semantic_router,
)
from app.modules.agents.implementation.api.specification_routes import (
    router as specification_router,
)
from app.modules.agents.implementation.api.dependencies import (
    get_canonical_artifact_service,
    get_document_extraction_service,
    get_github_connection_repository,
    get_github_connection_service,
    get_github_repository_binding_repository,
    get_github_repository_service,
    get_human_review_service,
    get_hybrid_detection_service,
    get_implementation_input_service,
    get_implementation_readiness_service,
    get_implementation_upload_storage,
    get_project_preparation_service,
    get_project_preparation_storage,
    get_rule_detection_service,
    get_semantic_artifact_service,
    get_semantic_chunking_service,
    get_zero_shot_detection_service,
)


router = APIRouter(
    prefix="/agents/implementation",
    tags=["implementation-agent"],
)
router.include_router(input_router)
router.include_router(preparation_router)
router.include_router(project_preparation_router)
router.include_router(semantic_router)
router.include_router(specification_router)
router.include_router(github_router)


__all__ = [
    "get_canonical_artifact_service",
    "get_document_extraction_service",
    "get_github_connection_repository",
    "get_github_connection_service",
    "get_github_repository_binding_repository",
    "get_github_repository_service",
    "get_human_review_service",
    "get_hybrid_detection_service",
    "get_implementation_input_service",
    "get_implementation_readiness_service",
    "get_implementation_upload_storage",
    "get_project_preparation_service",
    "get_project_preparation_storage",
    "get_rule_detection_service",
    "get_semantic_artifact_service",
    "get_semantic_chunking_service",
    "get_zero_shot_detection_service",
    "router",
]
