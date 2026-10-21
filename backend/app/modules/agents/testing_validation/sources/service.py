from fastapi import UploadFile

from app.common.id_generator import validate_id
from app.common.status import AgentStage, AgentType
from app.modules.agents.testing_validation.contracts.sources import (
    TestGenerationInputArtifactType,
    TestGenerationInputDescriptor,
    TestGenerationInputOriginAgent,
    TestGenerationInputProvenance,
    TestGenerationInputSourceType,
)
from app.modules.agents.testing_validation.sources.schemas import (
    TestGenerationSourceRecord,
    TestGenerationTextSourceCreate,
)
from app.modules.agents.testing_validation.sources.storage import Agent4SourceStorage
from app.modules.agents.testing_validation.workflow.service import (
    Agent4SetupConfirmedError,
    Agent4WorkflowStageError,
    WrongAgent4WorkflowProjectError,
)
from app.modules.agents.testing_validation.workflow.storage import (
    AGENT4_WORKFLOW_STATE_LOCK,
    Agent4WorkflowStorage,
)
from app.modules.auth.schemas import UserPublicResponse
from app.modules.standalone.service import StandaloneService


class Agent4SourceService:
    def __init__(
        self,
        standalone_service: StandaloneService,
        storage: Agent4SourceStorage,
        workflow_storage: Agent4WorkflowStorage,
    ) -> None:
        self._standalone = standalone_service
        self._storage = storage
        self._workflow = workflow_storage

    def create_text(
        self,
        agent_project_id: str,
        request: TestGenerationTextSourceCreate,
        current_user: UserPublicResponse,
    ) -> TestGenerationSourceRecord:
        with AGENT4_WORKFLOW_STATE_LOCK:
            project = self._require_project(agent_project_id, current_user)
            self._require_editable(project.agent_project_id, current_user.user_id)
            return self._storage.create_text(
                agent_project_id=project.agent_project_id,
                owner_user_id=current_user.user_id,
                artifact_type=request.artifact_type,
                normally_supplied_by=request.normally_supplied_by,
                label=request.label,
                content=request.content,
            )

    async def create_file(
        self,
        agent_project_id: str,
        *,
        artifact_type: TestGenerationInputArtifactType,
        source_type: TestGenerationInputSourceType,
        normally_supplied_by: TestGenerationInputOriginAgent,
        label: str | None,
        upload: UploadFile,
        current_user: UserPublicResponse,
    ) -> TestGenerationSourceRecord:
        with AGENT4_WORKFLOW_STATE_LOCK:
            project = self._require_project(agent_project_id, current_user)
            self._require_editable(project.agent_project_id, current_user.user_id)
            normalized_label = label.strip() or None if label is not None else None
            TestGenerationInputDescriptor(
                artifact_type=artifact_type,
                source_type=source_type,
                provenance=TestGenerationInputProvenance(
                    normally_supplied_by=normally_supplied_by
                ),
                label=normalized_label,
            )
            return await self._storage.create_file(
                agent_project_id=project.agent_project_id,
                owner_user_id=current_user.user_id,
                artifact_type=artifact_type,
                source_type=source_type,
                normally_supplied_by=normally_supplied_by,
                label=normalized_label,
                upload=upload,
            )

    def list(
        self, agent_project_id: str, current_user: UserPublicResponse
    ) -> list[TestGenerationSourceRecord]:
        project = self._require_project(agent_project_id, current_user)
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
        with AGENT4_WORKFLOW_STATE_LOCK:
            project = self._require_project(agent_project_id, current_user)
            self._require_editable(project.agent_project_id, current_user.user_id)
            self._storage.delete(
                agent_project_id=project.agent_project_id,
                owner_user_id=current_user.user_id,
                source_id=source_id,
            )

    def _require_editable(self, agent_project_id: str, owner_user_id: str) -> None:
        workflow = self._workflow.load(
            agent_project_id=agent_project_id,
            owner_user_id=owner_user_id,
        )
        if workflow is not None and workflow.n1_confirmation is not None:
            raise Agent4SetupConfirmedError(
                "Input and output setup has already been confirmed."
            )

    def _require_project(
        self, agent_project_id: str, current_user: UserPublicResponse
    ):
        try:
            validate_id(agent_project_id, "AGP")
        except (TypeError, ValueError) as exc:
            raise Agent4SourceProjectIdError(agent_project_id) from exc
        project = self._standalone.require_active_project(
            current_user.user_id, agent_project_id
        )
        if project.agent_type is not AgentType.TESTING_VALIDATION:
            raise WrongAgent4WorkflowProjectError(
                "Agent project must have agent_type TESTING_VALIDATION"
            )
        if project.agent_stage is not AgentStage.TEST_GENERATION:
            raise Agent4WorkflowStageError(
                "Agent project must have agent_stage TEST_GENERATION"
            )
        return project


class Agent4SourceProjectIdError(ValueError):
    pass
