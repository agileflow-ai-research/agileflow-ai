from typing import Annotated

from fastapi import Depends

from app.core.config import settings
from app.modules.agents.requirements.infrastructure.storage import RequirementSourceStorage
from app.modules.agents.requirements.inputs.upload.service import RequirementSourceService
from app.modules.agents.requirements.processing.service import DocumentProcessingService
from app.modules.standalone.router import get_standalone_service
from app.modules.standalone.service import StandaloneService


def get_requirement_source_storage() -> RequirementSourceStorage:
    return RequirementSourceStorage(settings.agent1_source_root)


def get_requirement_source_service(
    standalone_service: Annotated[
        StandaloneService, Depends(get_standalone_service)
    ],
    storage: Annotated[
        RequirementSourceStorage, Depends(get_requirement_source_storage)
    ],
) -> RequirementSourceService:
    return RequirementSourceService(standalone_service, storage)


def get_document_processing_service(
    standalone_service: Annotated[
        StandaloneService, Depends(get_standalone_service)
    ],
    storage: Annotated[
        RequirementSourceStorage, Depends(get_requirement_source_storage)
    ],
) -> DocumentProcessingService:
    return DocumentProcessingService(standalone_service, storage)

