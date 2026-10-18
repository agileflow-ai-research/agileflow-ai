import json
from datetime import datetime, timezone
from threading import Lock

from fastapi import UploadFile
from pydantic import ValidationError

from app.common.status import AgentType
from app.modules.auth.schemas import UserPublicResponse
from app.modules.standalone.artifact_inputs.extraction.constants import EXTRACTOR_VERSION
from app.modules.standalone.artifact_inputs.extraction.docx_extractor import extract_docx
from app.modules.standalone.artifact_inputs.extraction.pdf_extractor import extract_pdf
from app.modules.standalone.artifact_inputs.extraction.schemas import (
    DocumentExtractionResult,
    DocumentType,
    ExtractionStatus,
    ExtractionWarning,
    ExtractionWarningCode,
    MarkdownContent,
    DOCXContent,
    DOCXMetrics,
    PDFContent,
    PDFMetrics,
    StructuredContent,
    StructuredMetrics,
    TextContent,
    TextMetrics,
)
from app.modules.standalone.artifact_inputs.extraction.structured_extractors import (
    extract_structured,
    extract_text,
)
from app.modules.standalone.artifact_inputs.schemas import (
    PENDING_STATUS_BY_SOURCE,
    ArtifactExtractionResponse,
    ArtifactExtractionWarning,
    ArtifactSourceType,
    ArtifactUploadResponse,
)
from app.modules.standalone.artifact_inputs.storage import (
    ArtifactUploadStorage,
    StagedArtifactUpload,
)
from app.modules.standalone.service import StandaloneService


# Artifact types each agent may receive as manual standalone uploads. This registry is the only
# agent-specific knowledge in the shared layer; add an agent here to open its uploads.
ARTIFACT_TYPES_BY_AGENT: dict[AgentType, frozenset[str]] = {
    AgentType.TESTING_VALIDATION: frozenset({
        "REQUIREMENTS", "USER_STORIES", "ACCEPTANCE_CRITERIA", "SRS",
        "SYSTEM_ARCHITECTURE", "API_SPECIFICATION", "DATABASE_SCHEMA",
        "UI_SPECIFICATION", "TECHNOLOGY_STACK",
        "EXISTING_SOURCE_CODE",
    }),
}

DOCUMENT_TYPES = {
    ".pdf": DocumentType.PDF,
    ".docx": DocumentType.DOCX,
    ".txt": DocumentType.TXT,
    ".md": DocumentType.MD,
    ".json": DocumentType.JSON,
    ".yaml": DocumentType.YAML,
    ".yml": DocumentType.YAML,
}


class ArtifactAgentTypeError(ValueError):
    pass


class UnsupportedArtifactTypeError(ValueError):
    pass


class UnsupportedExtractionSourceError(ValueError):
    pass


class ExtractionNotFoundError(LookupError):
    pass


class ExtractionStorageError(RuntimeError):
    pass


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _extracted_text(content) -> str:
    if isinstance(content, StructuredContent):
        return content.normalized_text
    return content.combined_text


class StandaloneArtifactService:
    _extraction_lock = Lock()

    def __init__(
        self,
        standalone_service: StandaloneService,
        storage: ArtifactUploadStorage,
        *,
        clock=utc_now,
    ) -> None:
        self._standalone = standalone_service
        self._storage = storage
        self._clock = clock

    async def upload(
        self,
        agent_project_id: str,
        current_user: UserPublicResponse,
        *,
        source_type: str,
        artifact_type: str,
        label: str | None,
        upload: UploadFile,
    ) -> ArtifactUploadResponse:
        project = self._require_project(agent_project_id, current_user)
        self._require_artifact_type(project.agent_type, artifact_type)
        source = ArtifactSourceType(source_type)
        metadata = await self._storage.store(
            agent_project_id=project.agent_project_id,
            owner_user_id=current_user.user_id,
            source_type=source,
            artifact_type=artifact_type,
            label=label,
            upload=upload,
        )
        return ArtifactUploadResponse(
            upload_id=metadata.upload_id,
            source_type=metadata.source_type,
            artifact_type=metadata.artifact_type,
            label=metadata.label,
            original_filename=metadata.original_filename,
            mime_type=metadata.mime_type,
            size_bytes=metadata.size_bytes,
            created_at=metadata.created_at,
            processing_status=PENDING_STATUS_BY_SOURCE[source],
        )

    def delete(self, agent_project_id: str, current_user: UserPublicResponse, upload_id: str) -> None:
        project = self._require_project(agent_project_id, current_user)
        self._storage.delete(
            agent_project_id=project.agent_project_id,
            owner_user_id=current_user.user_id,
            upload_id=upload_id,
        )

    def extract(
        self,
        agent_project_id: str,
        current_user: UserPublicResponse,
        upload_id: str,
        *,
        force: bool = False,
    ) -> ArtifactExtractionResponse:
        project = self._require_project(agent_project_id, current_user)
        staged = self._locate_document(project.agent_project_id, current_user, upload_id)
        with self._extraction_lock:
            if not force:
                cached = self._load_valid_cache(staged, project.agent_project_id)
                if cached is not None:
                    return self._response(cached)
            document_type = DOCUMENT_TYPES[staged.metadata.extension]
            try:
                status, content, metrics, warnings = self._dispatch(staged, document_type)
            except Exception:
                status, content, metrics, warnings = self._failed_payload(document_type)
            result = DocumentExtractionResult(
                upload_id=staged.metadata.upload_id,
                agent_project_id=project.agent_project_id,
                artifact_type=staged.metadata.artifact_type,
                original_filename=staged.metadata.original_filename,
                document_type=document_type,
                status=status,
                extractor_version=EXTRACTOR_VERSION,
                source_sha256=staged.metadata.sha256,
                content=content,
                metrics=metrics,
                warnings=warnings,
                extracted_at=self._clock(),
            )
            self._persist(staged, result)
            return self._response(result)

    def get_existing(
        self,
        agent_project_id: str,
        current_user: UserPublicResponse,
        upload_id: str,
    ) -> ArtifactExtractionResponse:
        project = self._require_project(agent_project_id, current_user)
        staged = self._locate_document(project.agent_project_id, current_user, upload_id)
        cached = self._load_valid_cache(staged, project.agent_project_id)
        if cached is None:
            raise ExtractionNotFoundError(upload_id)
        return self._response(cached)

    def _require_project(self, agent_project_id: str, current_user: UserPublicResponse):
        # Foreign and missing projects both raise AgentProjectNotFoundError here.
        project = self._standalone.require_active_project(current_user.user_id, agent_project_id)
        if project.agent_type not in ARTIFACT_TYPES_BY_AGENT:
            raise ArtifactAgentTypeError("Standalone artifact uploads are not supported for this agent type")
        return project

    @staticmethod
    def _require_artifact_type(agent_type: AgentType, artifact_type: str) -> None:
        if artifact_type not in ARTIFACT_TYPES_BY_AGENT[agent_type]:
            raise UnsupportedArtifactTypeError(f"{artifact_type} is not an accepted artifact type for this agent")

    def _locate_document(self, agent_project_id: str, current_user: UserPublicResponse, upload_id: str) -> StagedArtifactUpload:
        staged = self._storage.locate(
            agent_project_id=agent_project_id,
            owner_user_id=current_user.user_id,
            upload_id=upload_id,
        )
        if staged.metadata.source_type is ArtifactSourceType.IMAGE:
            raise UnsupportedExtractionSourceError(
                "Image understanding is not implemented. Uploaded images are preserved but not analyzed."
            )
        if staged.metadata.extension not in DOCUMENT_TYPES:
            raise UnsupportedExtractionSourceError("This document type is not supported for extraction")
        return staged

    @staticmethod
    def _dispatch(staged: StagedArtifactUpload, document_type: DocumentType):
        if document_type is DocumentType.PDF:
            return extract_pdf(staged.file_path)
        if document_type is DocumentType.DOCX:
            return extract_docx(staged.file_path)
        if document_type is DocumentType.TXT:
            return extract_text(staged.file_path)
        if document_type is DocumentType.MD:
            return extract_text(staged.file_path, markdown=True)
        if document_type is DocumentType.JSON:
            return extract_structured(staged.file_path)
        return extract_structured(staged.file_path, yaml_document=True)

    @staticmethod
    def _failed_payload(document_type: DocumentType):
        warning = ExtractionWarning(
            code=ExtractionWarningCode.EXTRACTION_ERROR,
            message="The document could not be extracted safely.",
        )
        if document_type is DocumentType.PDF:
            return (
                ExtractionStatus.FAILED,
                PDFContent(pages=[], combined_text=""),
                PDFMetrics(page_count=0, processed_page_count=0, pages_with_text=0, pages_without_text=0, extracted_character_count=0),
                [warning],
            )
        if document_type is DocumentType.DOCX:
            return (
                ExtractionStatus.FAILED,
                DOCXContent(blocks=[], combined_text=""),
                DOCXMetrics(block_count=0, paragraph_count=0, heading_count=0, table_count=0, extracted_character_count=0),
                [warning],
            )
        if document_type is DocumentType.MD:
            content = MarkdownContent(markdown="", combined_text="")
            metrics = TextMetrics(extracted_character_count=0, line_count=0)
        elif document_type is DocumentType.TXT:
            content = TextContent(text="", combined_text="")
            metrics = TextMetrics(extracted_character_count=0, line_count=0)
        else:
            content = StructuredContent(structured_content=None, normalized_text="")
            metrics = StructuredMetrics(root_type="NULL", extracted_character_count=0)
        return ExtractionStatus.FAILED, content, metrics, [warning]

    @staticmethod
    def _load_valid_cache(staged: StagedArtifactUpload, agent_project_id: str) -> DocumentExtractionResult | None:
        try:
            raw = json.loads(staged.extraction_path.read_text(encoding="utf-8"))
            result = DocumentExtractionResult.model_validate(raw)
        except (FileNotFoundError, OSError, json.JSONDecodeError, ValidationError):
            return None
        if (
            result.upload_id != staged.metadata.upload_id
            or result.agent_project_id != agent_project_id
            or result.source_sha256 != staged.metadata.sha256
            or result.extractor_version != EXTRACTOR_VERSION
            or result.artifact_type != staged.metadata.artifact_type
            or result.original_filename != staged.metadata.original_filename
            or result.document_type is not DOCUMENT_TYPES[staged.metadata.extension]
        ):
            return None
        return result

    @staticmethod
    def _persist(staged: StagedArtifactUpload, result: DocumentExtractionResult) -> None:
        try:
            staged.extraction_partial_path.write_text(
                json.dumps(result.model_dump(mode="json"), ensure_ascii=False, separators=(",", ":")),
                encoding="utf-8",
            )
            staged.extraction_partial_path.replace(staged.extraction_path)
        except (OSError, TypeError, ValueError) as exc:
            try:
                staged.extraction_partial_path.unlink(missing_ok=True)
            except OSError:
                pass
            raise ExtractionStorageError("Document extraction could not be cached") from exc

    @staticmethod
    def _response(result: DocumentExtractionResult) -> ArtifactExtractionResponse:
        text = _extracted_text(result.content)
        return ArtifactExtractionResponse(
            upload_id=result.upload_id,
            artifact_type=result.artifact_type,
            original_filename=result.original_filename,
            document_type=result.document_type.value,
            status=result.status.value,
            # PARTIAL is usable but incomplete, matching the Agent 3 readiness rule. The status is
            # never rewritten to SUCCESS, so the caller can keep showing the partial-extraction warning.
            usable_as_context=result.status in (ExtractionStatus.SUCCESS, ExtractionStatus.PARTIAL) and bool(text.strip()),
            extracted_text=text,
            warnings=[
                ArtifactExtractionWarning(code=warning.code.value, message=warning.message)
                for warning in result.warnings
            ],
            extractor_version=result.extractor_version,
            extracted_at=result.extracted_at,
        )
