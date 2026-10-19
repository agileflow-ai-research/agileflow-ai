import json
from datetime import datetime, timezone
from threading import Lock

from pydantic import ValidationError

from app.common.document_extraction.constants import ExtractionLimits
from app.common.document_extraction.dispatch import DOCUMENT_TYPES, failed_outcome
from app.common.document_extraction.docx_extractor import extract_docx
from app.common.document_extraction.pdf_extractor import extract_pdf
from app.common.document_extraction.structured_extractors import extract_structured, extract_text
from app.modules.agents.implementation.inputs.extraction import constants
from app.modules.agents.implementation.inputs.extraction.constants import EXTRACTOR_VERSION
from app.modules.agents.implementation.inputs.extraction.schemas import (
    DocumentExtractionResult,
    DocumentType,
    ExtractionStatus,
)
from app.modules.agents.implementation.contracts.schemas import ImplementationInputSourceType
from app.modules.agents.implementation.inputs.upload.service import require_implementation_project
from app.modules.agents.implementation.infrastructure.storage import (
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


def _current_limits() -> ExtractionLimits:
    # Read at call time so tuned Agent 3 constants apply without re-importing the shared package.
    return ExtractionLimits(
        max_pdf_pages=constants.MAX_PDF_PAGES,
        max_extracted_characters=constants.MAX_EXTRACTED_CHARACTERS,
        max_docx_uncompressed_bytes=constants.MAX_DOCX_UNCOMPRESSED_BYTES,
        max_docx_archive_entries=constants.MAX_DOCX_ARCHIVE_ENTRIES,
    )


def utc_now() -> datetime:
    return datetime.now(timezone.utc)




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
        limits = _current_limits()
        if document_type is DocumentType.PDF:
            return extract_pdf(staged.file_path, limits=limits)
        if document_type is DocumentType.DOCX:
            return extract_docx(staged.file_path, limits=limits)
        if document_type is DocumentType.TXT:
            return extract_text(staged.file_path, limits=limits)
        if document_type is DocumentType.MD:
            return extract_text(staged.file_path, markdown=True, limits=limits)
        if document_type is DocumentType.JSON:
            return extract_structured(staged.file_path, limits=limits)
        return extract_structured(staged.file_path, yaml_document=True, limits=limits)

    @staticmethod
    def _failed_payload(document_type: DocumentType):
        return failed_outcome(document_type)

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
