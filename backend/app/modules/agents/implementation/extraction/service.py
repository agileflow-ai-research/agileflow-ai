import json
from datetime import datetime, timezone
from threading import Lock

from pydantic import ValidationError

from app.modules.agents.implementation.extraction.constants import EXTRACTOR_VERSION
from app.modules.agents.implementation.extraction.docx_extractor import extract_docx
from app.modules.agents.implementation.extraction.pdf_extractor import extract_pdf
from app.modules.agents.implementation.extraction.schemas import (
    DOCXContent,
    DOCXMetrics,
    DocumentExtractionResult,
    DocumentType,
    ExtractionStatus,
    ExtractionWarning,
    ExtractionWarningCode,
    MarkdownContent,
    PDFContent,
    PDFMetrics,
    StructuredContent,
    StructuredMetrics,
    TextContent,
    TextMetrics,
)
from app.modules.agents.implementation.extraction.structured_extractors import (
    extract_structured,
    extract_text,
)
from app.modules.agents.implementation.schemas import ImplementationInputSourceType
from app.modules.agents.implementation.service import require_implementation_project
from app.modules.agents.implementation.storage import (
    ImplementationUploadStorage,
    StagedUpload,
)
from app.modules.auth.schemas import UserPublicResponse
from app.modules.standalone.service import StandaloneService


class ExtractionNotFoundError(LookupError):
    pass


class UnsupportedExtractionSourceError(ValueError):
    pass


class ExtractionStorageError(RuntimeError):
    pass


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


DOCUMENT_TYPES = {
    ".pdf": DocumentType.PDF,
    ".docx": DocumentType.DOCX,
    ".txt": DocumentType.TXT,
    ".md": DocumentType.MD,
    ".json": DocumentType.JSON,
    ".yaml": DocumentType.YAML,
    ".yml": DocumentType.YAML,
}


class DocumentExtractionService:
    _extraction_lock = Lock()

    def __init__(
        self,
        standalone_service: StandaloneService,
        storage: ImplementationUploadStorage,
        *,
        clock=utc_now,
    ) -> None:
        self._standalone = standalone_service
        self._storage = storage
        self._clock = clock

    def extract(
        self,
        agent_project_id: str,
        upload_id: str,
        current_user: UserPublicResponse,
        *,
        force: bool = False,
    ) -> DocumentExtractionResult:
        project = require_implementation_project(
            self._standalone, agent_project_id, current_user
        )
        staged = self._storage.locate(
            agent_project_id=project.agent_project_id,
            owner_user_id=current_user.user_id,
            upload_id=upload_id,
        )
        self._require_document(staged)
        with self._extraction_lock:
            if not force:
                cached = self._load_valid_cache(staged, project.agent_project_id)
                if cached is not None:
                    return cached
            document_type = DOCUMENT_TYPES[staged.metadata.extension]
            try:
                status, content, metrics, warnings = self._dispatch(
                    staged, document_type
                )
            except Exception:
                status, content, metrics, warnings = self._failed_payload(
                    document_type
                )
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
            return result

    def get_existing(
        self,
        agent_project_id: str,
        upload_id: str,
        current_user: UserPublicResponse,
    ) -> DocumentExtractionResult:
        project = require_implementation_project(
            self._standalone, agent_project_id, current_user
        )
        staged = self._storage.locate(
            agent_project_id=project.agent_project_id,
            owner_user_id=current_user.user_id,
            upload_id=upload_id,
        )
        self._require_document(staged)
        cached = self._load_valid_cache(staged, project.agent_project_id)
        if cached is None:
            raise ExtractionNotFoundError(upload_id)
        return cached

    @staticmethod
    def _require_document(staged: StagedUpload) -> None:
        if staged.metadata.source_type is ImplementationInputSourceType.IMAGE:
            raise UnsupportedExtractionSourceError(
                "Image understanding is not implemented in the current document extraction step."
            )
        if staged.metadata.source_type is not ImplementationInputSourceType.DOCUMENT:
            raise UnsupportedExtractionSourceError(
                "Only uploaded DOCUMENT inputs can be extracted"
            )
        if staged.metadata.extension not in DOCUMENT_TYPES:
            raise UnsupportedExtractionSourceError(
                "This document type is not supported for extraction"
            )

    @staticmethod
    def _dispatch(staged: StagedUpload, document_type: DocumentType):
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
                PDFMetrics(
                    page_count=0,
                    processed_page_count=0,
                    pages_with_text=0,
                    pages_without_text=0,
                    extracted_character_count=0,
                ),
                [warning],
            )
        if document_type is DocumentType.DOCX:
            return (
                ExtractionStatus.FAILED,
                DOCXContent(blocks=[], combined_text=""),
                DOCXMetrics(
                    block_count=0,
                    paragraph_count=0,
                    heading_count=0,
                    table_count=0,
                    extracted_character_count=0,
                ),
                [warning],
            )
        if document_type is DocumentType.MD:
            content = MarkdownContent(markdown="", combined_text="")
            metrics = TextMetrics(extracted_character_count=0, line_count=0)
        elif document_type is DocumentType.TXT:
            content = TextContent(text="", combined_text="")
            metrics = TextMetrics(extracted_character_count=0, line_count=0)
        else:
            content = StructuredContent(
                structured_content=None, normalized_text=""
            )
            metrics = StructuredMetrics(
                root_type="NULL", extracted_character_count=0
            )
        return ExtractionStatus.FAILED, content, metrics, [warning]

    @staticmethod
    def _load_valid_cache(
        staged: StagedUpload, agent_project_id: str
    ) -> DocumentExtractionResult | None:
        try:
            raw = json.loads(staged.extraction_path.read_text(encoding="utf-8"))
            result = DocumentExtractionResult.model_validate(raw)
        except (
            FileNotFoundError,
            OSError,
            json.JSONDecodeError,
            ValidationError,
        ):
            return None
        if (
            result.upload_id != staged.metadata.upload_id
            or result.agent_project_id != agent_project_id
            or result.source_sha256 != staged.metadata.sha256
            or result.extractor_version != EXTRACTOR_VERSION
            or result.artifact_type is not staged.metadata.artifact_type
            or result.original_filename != staged.metadata.original_filename
            or result.document_type is not DOCUMENT_TYPES[staged.metadata.extension]
        ):
            return None
        return result

    @staticmethod
    def _persist(
        staged: StagedUpload, result: DocumentExtractionResult
    ) -> None:
        try:
            staged.extraction_partial_path.write_text(
                json.dumps(
                    result.model_dump(mode="json"),
                    ensure_ascii=False,
                    separators=(",", ":"),
                ),
                encoding="utf-8",
            )
            staged.extraction_partial_path.replace(staged.extraction_path)
        except (OSError, TypeError, ValueError) as exc:
            try:
                staged.extraction_partial_path.unlink(missing_ok=True)
            except OSError:
                pass
            raise ExtractionStorageError(
                "Document extraction could not be cached"
            ) from exc
