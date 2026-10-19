"""TEST_GENERATION input collection.

Every operation verifies the authenticated owner, the AgentProject type, and (for writes)
that the project is ACTIVE. Choosing a mode or adding inputs never creates an AgentRun.
"""

from fastapi import UploadFile

from app.common.status import AgentType
from app.modules.agents.testing_validation.contracts.enums import (
    Agent4ArtifactType,
    Agent4InputSourceType,
    InputOriginAgent,
)
from app.modules.agents.testing_validation.inputs import catalog
from app.modules.agents.testing_validation.inputs.constants import (
    MAX_SOURCES_PER_PROJECT,
    MAX_TOTAL_TEXT_CHARACTERS,
    UPLOAD_SOURCE_PREFIX,
    TEXT_SOURCE_PREFIX,
)
from app.modules.agents.testing_validation.inputs.schemas import TestGenerationSource, TextSourceCreateRequest
from app.modules.agents.testing_validation.inputs.storage import (
    InputValidationError,
    TestGenerationInputStorage,
    new_source_id,
    utc_now,
)
from app.modules.auth.schemas import UserPublicResponse
from app.modules.standalone.schemas import AgentProject
from app.modules.standalone.service import StandaloneService

_PUBLIC_FIELDS = frozenset(TestGenerationSource.model_fields)


class WrongAgentProjectTypeError(ValueError):
    pass


class TestGenerationInputService:
    def __init__(
        self,
        standalone_service: StandaloneService,
        storage: TestGenerationInputStorage,
        *,
        clock=utc_now,
    ) -> None:
        self._standalone = standalone_service
        self._storage = storage
        self._clock = clock

    def list_sources(self, agent_project_id: str, current_user: UserPublicResponse) -> list[TestGenerationSource]:
        project = self._require_project(agent_project_id, current_user, active=False)
        return [self._public(record) for record in self._records(project, current_user)]

    def add_text(
        self,
        agent_project_id: str,
        current_user: UserPublicResponse,
        request: TextSourceCreateRequest,
    ) -> TestGenerationSource:
        project = self._require_project(agent_project_id, current_user, active=True)
        origin = catalog.resolve_origin(request.artifact_type, request.origin_agent)
        records = self._records(project, current_user)
        self._check_capacity(records, added_text_characters=len(request.content))
        source = TestGenerationSource(
            source_id=new_source_id(TEXT_SOURCE_PREFIX),
            agent_project_id=project.agent_project_id,
            artifact_type=request.artifact_type,
            source_type=Agent4InputSourceType.TEXT,
            normally_supplied_by=origin,
            label=request.label,
            processing_status=catalog.processing_status_for(Agent4InputSourceType.TEXT),
            text_content=request.content,
            created_at=self._clock(),
        )
        self._storage.write_record(
            project.agent_project_id, current_user.user_id, source.model_dump(mode="json")
        )
        return source

    async def add_file(
        self,
        agent_project_id: str,
        current_user: UserPublicResponse,
        artifact_type: Agent4ArtifactType,
        source_type: Agent4InputSourceType,
        origin_agent: InputOriginAgent | None,
        label: str | None,
        upload: UploadFile,
    ) -> TestGenerationSource:
        if source_type is Agent4InputSourceType.TEXT:
            raise InputValidationError("TEXT sources are entered directly, not uploaded")
        project = self._require_project(agent_project_id, current_user, active=True)
        origin = catalog.resolve_origin(artifact_type, origin_agent)
        catalog.validate_source_type(artifact_type, source_type)
        self._check_capacity(self._records(project, current_user), added_text_characters=0)

        source_id = new_source_id(UPLOAD_SOURCE_PREFIX)
        file_info = await self._storage.store_file(
            agent_project_id=project.agent_project_id,
            source_id=source_id,
            source_type=source_type,
            upload=upload,
        )
        source = TestGenerationSource(
            source_id=source_id,
            agent_project_id=project.agent_project_id,
            artifact_type=artifact_type,
            source_type=source_type,
            normally_supplied_by=origin,
            label=(label or "").strip() or None,
            processing_status=catalog.processing_status_for(source_type),
            original_filename=file_info["original_filename"],
            mime_type=file_info["mime_type"],
            size_bytes=file_info["size_bytes"],
            sha256=file_info["sha256"],
            created_at=self._clock(),
        )
        try:
            self._storage.write_record(
                project.agent_project_id,
                current_user.user_id,
                {**source.model_dump(mode="json"), "storage_extension": file_info["storage_extension"]},
            )
        except Exception:
            self._storage.delete_file(project.agent_project_id, source_id, file_info["storage_extension"])
            raise
        return source

    def delete_source(self, agent_project_id: str, current_user: UserPublicResponse, source_id: str) -> None:
        project = self._require_project(agent_project_id, current_user, active=True)
        self._storage.delete(project.agent_project_id, current_user.user_id, source_id)

    # --- helpers --------------------------------------------------------------

    def _require_project(
        self,
        agent_project_id: str,
        current_user: UserPublicResponse,
        *,
        active: bool,
    ) -> AgentProject:
        if active:
            project = self._standalone.require_active_project(current_user.user_id, agent_project_id)
        else:
            project = self._standalone.get_project(agent_project_id, current_user)
        if project.agent_type is not AgentType.TESTING_VALIDATION:
            raise WrongAgentProjectTypeError("Agent project must have agent_type TESTING_VALIDATION")
        return project

    def _records(self, project: AgentProject, current_user: UserPublicResponse) -> list[dict]:
        return self._storage.list_records(project.agent_project_id, current_user.user_id)

    @staticmethod
    def _check_capacity(records: list[dict], *, added_text_characters: int) -> None:
        if len(records) >= MAX_SOURCES_PER_PROJECT:
            raise InputValidationError(f"A project can hold at most {MAX_SOURCES_PER_PROJECT} sources")
        existing_text = sum(len(item.get("text_content") or "") for item in records)
        if existing_text + added_text_characters > MAX_TOTAL_TEXT_CHARACTERS:
            raise InputValidationError("Manual text sources exceed the project total size limit")

    @staticmethod
    def _public(record: dict) -> TestGenerationSource:
        return TestGenerationSource.model_validate({k: v for k, v in record.items() if k in _PUBLIC_FIELDS})
