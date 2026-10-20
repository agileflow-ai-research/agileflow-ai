from fastapi import APIRouter

from app.modules.agents.requirements.api.source_routes import router as source_router
from app.modules.agents.requirements.api.processing_routes import router as processing_router


router = APIRouter(prefix="/agents/requirements", tags=["requirements-agent"])
router.include_router(source_router)
router.include_router(processing_router)
