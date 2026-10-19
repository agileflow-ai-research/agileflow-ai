"""Agent 4 DOCUMENT extraction: ownership, source resolution, cache, and persistence.

Extraction is project-level preparation. It never creates an AgentRun and never
normalizes or classifies the extracted text.
"""

from datetime import datetime, timezone
from threading import Lock

from pydantic import ValidationError

from app.common.document_extraction.constants import EXTRACTOR_VERSION
from app.common.document_extraction.dispatch import document_type_for_extension, extract_document_safely
from app.common.status import AgentType
from app.modules.agents.testing_validation.contracts.enums import Agent4InputSourceType
from app.modules.agents.testing_validation.extraction.schemas import TestGenerationExtractionResult
from app.modules.agents.testing_validation.inputs.storage import (
    InputNotFoundError,
    TestGenerationInputStorage,
)
from app.modules.auth.schemas import UserPublicResponse
from app.modules.standalone.schemas import AgentProject
from app.modules.standalone.service import StandaloneService


class UnsupportedExtractionSourceError(ValueError):
    pass


class WrongAgentProjectTypeError(ValueError):
    pass


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class TestGenerationExtractionService:
    _extraction_lock = Lock()

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

    def extract(
        self,
        agent_project_id: str,
        source_id: str,
        current_user: UserPublicResponse,
        *,
        force: bool = False,
    ) -> TestGenerationExtractionResult:
        project = self._require_project(agent_project_id, current_user, active=True)
        record = self._document_record(project, current_user, source_id)
        with self._extraction_lock:
            if not force:
                cached = self._load_valid_cache(project, record)
                if cached is not None:
                    return cached
            document_type = document_type_for_extension(record["storage_extension"])
            path = self._storage.document_file_path(project.agent_project_id, source_id, record["storage_extension"])
            status, content, metrics, warnings = extract_document_safely(path, document_type)
            result = TestGenerationExtractionResult(
                source_id=source_id,
                agent_project_id=project.agent_project_id,
                artifact_type=record["artifact_type"],
                original_filename=record["original_filename"],
                document_type=document_type,
                status=status,
                extractor_version=EXTRACTOR_VERSION,
                source_sha256=record["sha256"],
                content=content,
                metrics=metrics,
                warnings=warnings,
                extracted_at=self._clock(),
            )
            self._storage.write_extraction(
                project.agent_project_id, source_id, result.model_dump(mode="json")
            )
            return result

    def get_existing(
        self,
        agent_project_id: str,
        source_id: str,
        current_user: UserPublicResponse,
    ) -> TestGenerationExtractionResult:
        project = self._require_project(agent_project_id, current_user, active=False)
        record = self._document_record(project, current_user, source_id)
        cached = self._load_valid_cache(project, record)
        if cached is None:
            raise InputNotFoundError(source_id)
        return cached

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

    def _document_record(self, project: AgentProject, current_user: UserPublicResponse, source_id: str) -> dict:
        record = self._storage.load_record(project.agent_project_id, current_user.user_id, source_id)
        if record is None:
            raise InputNotFoundError(source_id)
        if record["source_type"] != Agent4InputSourceType.DOCUMENT.value:
            if record["source_type"] == Agent4InputSourceType.IMAGE.value:
                raise UnsupportedExtractionSourceError(
                    "Images are pending analysis and cannot be extracted in this step"
                )
            raise UnsupportedExtractionSourceError("Only DOCUMENT sources can be extracted")
        if document_type_for_extension(record.get("storage_extension", "")) is None:
            raise UnsupportedExtractionSourceError("This document type is not supported for extraction")
        return record

    def _load_valid_cache(self, project: AgentProject, record: dict) -> TestGenerationExtractionResult | None:
        raw = self._storage.read_extraction(project.agent_project_id, record["source_id"])
        if raw is None:
            return None
        try:
            result = TestGenerationExtractionResult.model_validate(raw)
        except ValidationError:
            return None
        expected_type = document_type_for_extension(record["storage_extension"])
        if (
            result.source_id != record["source_id"]
            or result.agent_project_id != project.agent_project_id
            or result.source_sha256 != record["sha256"]
            or result.extractor_version != EXTRACTOR_VERSION
            or result.artifact_type.value != record["artifact_type"]
            or result.original_filename != record["original_filename"]
            or result.document_type is not expected_type
        ):
            return None
        return result
