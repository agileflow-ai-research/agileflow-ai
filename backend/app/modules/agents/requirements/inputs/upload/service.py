from fastapi import UploadFile

from app.common.status import AgentType
from app.modules.agents.requirements.contracts.schemas import (
    RequirementSourceMetadata,
    RequirementSourceType,
)
from app.modules.agents.requirements.infrastructure.storage import RequirementSourceStorage
from app.modules.agents.requirements.service import WrongAgentProjectTypeError
from app.modules.auth.schemas import UserPublicResponse
from app.modules.standalone.service import StandaloneService


def require_requirements_project(
    standalone_service: StandaloneService,
    agent_project_id: str,
    current_user: UserPublicResponse,
):
    project = standalone_service.require_active_project(
        current_user.user_id, agent_project_id
    )
    if project.agent_type is not AgentType.REQUIREMENTS:
        raise WrongAgentProjectTypeError(
            "Agent project must have agent_type REQUIREMENTS"
        )
    return project


class RequirementSourceService:
    def __init__(
        self,
        standalone_service: StandaloneService,
        storage: RequirementSourceStorage,
    ) -> None:
        self._standalone = standalone_service
        self._storage = storage

    async def upload(
        self,
        agent_project_id: str,
        current_user: UserPublicResponse,
        source_type: RequirementSourceType,
        upload: UploadFile,
    ) -> RequirementSourceMetadata:
        project = require_requirements_project(
            self._standalone, agent_project_id, current_user
        )
        return await self._storage.store(
            agent_project_id=project.agent_project_id,
            owner_user_id=current_user.user_id,
            source_type=source_type,
            upload=upload,
        )

    def list(
        self,
        agent_project_id: str,
        current_user: UserPublicResponse,
    ) -> list[RequirementSourceMetadata]:
        project = require_requirements_project(
            self._standalone, agent_project_id, current_user
        )
        return self._storage.list_for_project(
            agent_project_id=project.agent_project_id,
            owner_user_id=current_user.user_id,
        )

    def delete(
        self,
        agent_project_id: str,
        source_id: str,
        current_user: UserPublicResponse,
    ) -> None:
        project = require_requirements_project(
            self._standalone, agent_project_id, current_user
        )
        self._storage.delete(
            agent_project_id=project.agent_project_id,
            owner_user_id=current_user.user_id,
            source_id=source_id,
        )

