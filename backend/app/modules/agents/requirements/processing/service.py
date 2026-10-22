import hashlib
import json
from datetime import datetime, timezone
from threading import Lock

from pydantic import ValidationError

from app.modules.agents.requirements.contracts.schemas import RequirementSourceType
from app.modules.agents.requirements.infrastructure.storage import (
    RequirementSourceStorage,
    StoredRequirementSource,
)
from app.modules.agents.requirements.inputs.upload.service import require_requirements_project
from app.modules.agents.requirements.processing.adapters.docx import extract_docx_text
from app.modules.agents.requirements.processing.adapters.pdf import (
    NoMachineReadableTextError,
    extract_pdf_text,
)
from app.modules.agents.requirements.processing.adapters.text import extract_text
from app.modules.agents.requirements.processing.constants import PROCESSOR_VERSION
from app.modules.agents.requirements.processing.schemas import (
    DocumentBlockSpan,
    DocumentBlockType,
    DocumentPageSpan,
    DocumentProcessingError,
    DocumentProcessingErrorCode,
    DocumentProcessingRecord,
    DocumentProcessingResult,
    DocumentProcessingStatus,
    DocumentStructuralProvenance,
    DocumentTextRange,
    DocumentType,
)
from app.modules.auth.schemas import UserPublicResponse
from app.modules.standalone.service import StandaloneService


DOCUMENT_TYPES = {
    ".pdf": DocumentType.PDF,
    ".docx": DocumentType.DOCX,
    ".txt": DocumentType.TXT,
}


class DocumentProcessingNotFoundError(LookupError):
    pass


class UnsupportedDocumentSourceError(ValueError):
    pass


class DocumentProcessingStorageError(RuntimeError):
    pass


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class DocumentProcessingService:
    _processing_lock = Lock()

    def __init__(
        self,
        standalone_service: StandaloneService,
        storage: RequirementSourceStorage,
        *,
        clock=utc_now,
    ) -> None:
        self._standalone = standalone_service
        self._storage = storage
        self._clock = clock

    def process(
        self,
        agent_project_id: str,
        source_id: str,
        current_user: UserPublicResponse,
        *,
        force: bool = False,
    ) -> DocumentProcessingRecord:
        stored = self._require_source(agent_project_id, source_id, current_user)
        with self._processing_lock:
            existing = self._load_valid_record(stored, agent_project_id)
            if (
                not force
                and existing is not None
                and existing.status is DocumentProcessingStatus.COMPLETED
                and self._load_valid_result(stored, agent_project_id) is not None
            ):
                return existing

            started_at = self._clock()
            processing = self._record(
                stored,
                agent_project_id,
                DocumentProcessingStatus.PROCESSING,
                started_at=started_at,
            )
            self._persist_record(stored, processing)
            self._remove_result(stored)
            try:
                actual_sha256 = self._sha256(stored)
                if actual_sha256 != stored.metadata.sha256:
                    raise _SafeProcessingFailure(
                        DocumentProcessingErrorCode.SOURCE_CHECKSUM_MISMATCH,
                        "The source content no longer matches its recorded checksum.",
                    )
                result = self._extract(stored, agent_project_id)
                self._persist_result(stored, result)
                completed = self._record(
                    stored,
                    agent_project_id,
                    DocumentProcessingStatus.COMPLETED,
                    started_at=started_at,
                    completed_at=result.processed_at,
                )
                self._persist_record(stored, completed)
                return completed
            except NoMachineReadableTextError:
                failure = _SafeProcessingFailure(
                    DocumentProcessingErrorCode.NO_MACHINE_READABLE_TEXT,
                    "No machine-readable text was found. OCR is not available in N2A.",
                )
            except _SafeProcessingFailure as exc:
                failure = exc
            except DocumentProcessingStorageError:
                raise
            except Exception:
                failure = _SafeProcessingFailure(
                    DocumentProcessingErrorCode.DOCUMENT_UNREADABLE,
                    "The document could not be read safely.",
                )
            failed = self._record(
                stored,
                agent_project_id,
                DocumentProcessingStatus.FAILED,
                started_at=started_at,
                completed_at=self._clock(),
                error=DocumentProcessingError(
                    code=failure.code,
                    message=failure.message,
                ),
            )
            self._persist_record(stored, failed)
            return failed

    def get_status(
        self,
        agent_project_id: str,
        source_id: str,
        current_user: UserPublicResponse,
    ) -> DocumentProcessingRecord:
        stored = self._require_source(agent_project_id, source_id, current_user)
        with self._processing_lock:
            record = self._load_valid_record(stored, agent_project_id)
            if record is not None:
                return self._reconcile_completed_record(
                    stored, agent_project_id, record
                )
            return self._record(
                stored, agent_project_id, DocumentProcessingStatus.READY
            )

    def get_result(
        self,
        agent_project_id: str,
        source_id: str,
        current_user: UserPublicResponse,
    ) -> DocumentProcessingResult:
        stored = self._require_source(agent_project_id, source_id, current_user)
        with self._processing_lock:
            result = self._load_valid_result(stored, agent_project_id)
            record = self._load_valid_record(stored, agent_project_id)
            if record is not None and record.status is DocumentProcessingStatus.COMPLETED:
                record = self._reconcile_completed_record(
                    stored, agent_project_id, record, result=result
                )
            if (
                result is None
                or record is None
                or record.status is not DocumentProcessingStatus.COMPLETED
            ):
                raise DocumentProcessingNotFoundError(source_id)
            return result

    def _reconcile_completed_record(
        self,
        stored: StoredRequirementSource,
        agent_project_id: str,
        record: DocumentProcessingRecord,
        *,
        result: DocumentProcessingResult | None = None,
    ) -> DocumentProcessingRecord:
        if record.status is not DocumentProcessingStatus.COMPLETED:
            return record
        compatible_result = result or self._load_valid_result(stored, agent_project_id)
        if compatible_result is not None:
            return record
        reconciled = self._record(
            stored,
            agent_project_id,
            DocumentProcessingStatus.FAILED,
            started_at=record.started_at,
            completed_at=self._clock(),
            error=DocumentProcessingError(
                code=DocumentProcessingErrorCode.PROCESSING_RESULT_INVALID,
                message="The completed processing result is missing or incompatible. Retry processing.",
            ),
        )
        self._persist_record(stored, reconciled)
        return reconciled

    def _require_source(
        self,
        agent_project_id: str,
        source_id: str,
        current_user: UserPublicResponse,
    ) -> StoredRequirementSource:
        project = require_requirements_project(
            self._standalone, agent_project_id, current_user
        )
        stored = self._storage.locate(
            agent_project_id=project.agent_project_id,
            owner_user_id=current_user.user_id,
            source_id=source_id,
        )
        if (
            stored.metadata.source_type is not RequirementSourceType.DOCUMENT
            or stored.metadata.extension not in DOCUMENT_TYPES
        ):
            raise UnsupportedDocumentSourceError(
                "N2A supports DOCUMENT sources only"
            )
        return stored

    def _extract(
        self,
        stored: StoredRequirementSource,
        agent_project_id: str,
    ) -> DocumentProcessingResult:
        document_type = DOCUMENT_TYPES[stored.metadata.extension]
        page_count = None
        paragraph_count = None
        table_count = None
        provenance = DocumentStructuralProvenance()
        if document_type is DocumentType.PDF:
            text, page_count, pages = extract_pdf_text(stored.file_path)
            provenance = DocumentStructuralProvenance(
                pages=[
                    DocumentPageSpan(
                        page_number=page_number,
                        text=page_text,
                        start_offset=start_offset,
                        end_offset=end_offset,
                    )
                    for page_number, page_text, start_offset, end_offset in pages
                ]
            )
        elif document_type is DocumentType.DOCX:
            text, paragraph_count, table_count, blocks = extract_docx_text(
                stored.file_path
            )
            provenance = DocumentStructuralProvenance(
                blocks=[
                    DocumentBlockSpan(
                        block_index=block_index,
                        block_type=DocumentBlockType(block_type),
                        text=block_text,
                        start_offset=start_offset,
                        end_offset=end_offset,
                    )
                    for block_index, block_type, block_text, start_offset, end_offset in blocks
                ]
            )
        else:
            text = extract_text(stored.file_path)
            provenance = DocumentStructuralProvenance(
                text_ranges=[
                    DocumentTextRange(
                        text=text,
                        start_offset=0,
                        end_offset=len(text),
                    )
                ]
            )
        if not text.strip():
            raise NoMachineReadableTextError()
        return DocumentProcessingResult(
            source_id=stored.metadata.source_id,
            agent_project_id=agent_project_id,
            source_sha256=stored.metadata.sha256,
            processor_version=PROCESSOR_VERSION,
            document_type=document_type,
            text=text,
            character_count=len(text),
            page_count=page_count,
            paragraph_count=paragraph_count,
            table_count=table_count,
            structural_provenance=provenance,
            processed_at=self._clock(),
        )

    @staticmethod
    def _sha256(stored: StoredRequirementSource) -> str:
        digest = hashlib.sha256()
        with stored.file_path.open("rb") as source:
            while chunk := source.read(64 * 1024):
                digest.update(chunk)
        return digest.hexdigest()

    @staticmethod
    def _record(
        stored: StoredRequirementSource,
        agent_project_id: str,
        status: DocumentProcessingStatus,
        *,
        started_at: datetime | None = None,
        completed_at: datetime | None = None,
        error: DocumentProcessingError | None = None,
    ) -> DocumentProcessingRecord:
        return DocumentProcessingRecord(
            source_id=stored.metadata.source_id,
            agent_project_id=agent_project_id,
            source_sha256=stored.metadata.sha256,
            processor_version=PROCESSOR_VERSION,
            status=status,
            started_at=started_at,
            completed_at=completed_at,
            error=error,
        )

    @staticmethod
    def _load_valid_record(
        stored: StoredRequirementSource,
        agent_project_id: str,
    ) -> DocumentProcessingRecord | None:
        try:
            record = DocumentProcessingRecord.model_validate_json(
                stored.processing_path.read_text(encoding="utf-8")
            )
        except (FileNotFoundError, OSError, ValidationError):
            return None
        if (
            record.source_id != stored.metadata.source_id
            or record.agent_project_id != agent_project_id
            or record.source_sha256 != stored.metadata.sha256
            or record.processor_version != PROCESSOR_VERSION
        ):
            return None
        return record

    @staticmethod
    def _load_valid_result(
        stored: StoredRequirementSource,
        agent_project_id: str,
    ) -> DocumentProcessingResult | None:
        try:
            result = DocumentProcessingResult.model_validate_json(
                stored.result_path.read_text(encoding="utf-8")
            )
        except (FileNotFoundError, OSError, ValidationError):
            return None
        if (
            result.source_id != stored.metadata.source_id
            or result.agent_project_id != agent_project_id
            or result.source_sha256 != stored.metadata.sha256
            or result.processor_version != PROCESSOR_VERSION
            or result.document_type is not DOCUMENT_TYPES[stored.metadata.extension]
        ):
            return None
        return result

    @staticmethod
    def _persist_record(
        stored: StoredRequirementSource,
        record: DocumentProcessingRecord,
    ) -> None:
        DocumentProcessingService._persist_json(
            stored.processing_partial_path,
            stored.processing_path,
            record.model_dump(mode="json"),
        )

    @staticmethod
    def _persist_result(
        stored: StoredRequirementSource,
        result: DocumentProcessingResult,
    ) -> None:
        DocumentProcessingService._persist_json(
            stored.result_partial_path,
            stored.result_path,
            result.model_dump(mode="json"),
        )

    @staticmethod
    def _persist_json(partial_path, final_path, value: dict) -> None:
        try:
            partial_path.write_text(
                json.dumps(value, ensure_ascii=False, separators=(",", ":")),
                encoding="utf-8",
            )
            partial_path.replace(final_path)
        except (OSError, TypeError, ValueError) as exc:
            try:
                partial_path.unlink(missing_ok=True)
            except OSError:
                pass
            raise DocumentProcessingStorageError(
                "Document processing state could not be persisted"
            ) from exc

    @staticmethod
    def _remove_result(stored: StoredRequirementSource) -> None:
        try:
            stored.result_path.unlink(missing_ok=True)
            stored.result_partial_path.unlink(missing_ok=True)
        except OSError as exc:
            raise DocumentProcessingStorageError(
                "Previous document processing result could not be replaced"
            ) from exc


class _SafeProcessingFailure(Exception):
    def __init__(
        self,
        code: DocumentProcessingErrorCode,
        message: str,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
