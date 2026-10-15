from fastapi import UploadFile

from app.common.status import AgentType
from app.modules.agents.implementation.schemas import (
    ImplementationArtifactType,
    ImplementationInputSourceType,
    UploadedFileMetadata,
)
from app.modules.agents.implementation.storage import ImplementationUploadStorage
from app.modules.auth.schemas import UserPublicResponse
from app.modules.standalone.service import StandaloneService


class WrongAgentProjectTypeError(ValueError):
    pass


def require_implementation_project(
    standalone_service: StandaloneService,
    agent_project_id: str,
    current_user: UserPublicResponse,
):
    project = standalone_service.require_active_project(
        current_user.user_id, agent_project_id
    )
    if project.agent_type is not AgentType.IMPLEMENTATION:
        raise WrongAgentProjectTypeError(
            "Agent project must have agent_type IMPLEMENTATION"
        )
    return project


class ImplementationInputService:
    def __init__(
        self,
        standalone_service: StandaloneService,
        storage: ImplementationUploadStorage,
    ) -> None:
        self._standalone = standalone_service
        self._storage = storage

    async def upload(
        self,
        agent_project_id: str,
        current_user: UserPublicResponse,
        source_type: ImplementationInputSourceType,
        artifact_type: ImplementationArtifactType,
        label: str | None,
        upload: UploadFile,
    ) -> UploadedFileMetadata:
        project = require_implementation_project(
            self._standalone, agent_project_id, current_user
        )
        if source_type is ImplementationInputSourceType.TEXT:
            raise ValueError("TEXT inputs do not use the file upload endpoint")
        normalized_label = label.strip() or None if label is not None else None
        return await self._storage.store(
            agent_project_id=project.agent_project_id,
            owner_user_id=current_user.user_id,
            source_type=source_type,
            artifact_type=artifact_type,
            label=normalized_label,
            upload=upload,
        )

    def delete(
        self,
        agent_project_id: str,
        upload_id: str,
        current_user: UserPublicResponse,
    ) -> None:
        project = require_implementation_project(
            self._standalone, agent_project_id, current_user
        )
        self._storage.delete(
            agent_project_id=project.agent_project_id,
            owner_user_id=current_user.user_id,
            upload_id=upload_id,
        )
