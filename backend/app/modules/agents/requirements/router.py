from fastapi import APIRouter

from app.modules.agents.requirements.api.source_routes import router as source_router
from app.modules.agents.requirements.api.processing_routes import router as processing_router
from app.modules.agents.requirements.api.preparation_routes import router as preparation_router
from app.modules.agents.requirements.api.workflow_routes import router as workflow_router
from app.modules.agents.requirements.api.discovery_routes import router as discovery_router


router = APIRouter(prefix="/agents/requirements", tags=["requirements-agent"])
router.include_router(source_router)
router.include_router(processing_router)
router.include_router(preparation_router)
router.include_router(workflow_router)
router.include_router(discovery_router)
