import hashlib
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from uuid import uuid4

from app.common.document_extraction.extractors import (
    extract_docx,
    extract_pdf,
    extract_structured,
    extract_text,
)
from app.common.document_extraction.schemas import (
    DOCXContent,
    PDFContent,
    StructuredContent,
)
from app.common.id_generator import validate_id
from app.common.status import AgentStage, AgentType
from app.modules.agents.testing_validation.contracts.sources import (
    TestGenerationInputSourceType,
)
from app.modules.agents.testing_validation.preparation.extraction.constants import (
    AGENT4_EXTRACTION_SCHEMA_VERSION,
    AGENT4_EXTRACTION_VERSION,
    AGENT4_EXTRACTOR_NAME,
    MAX_DOCX_ARCHIVE_ENTRIES,
    MAX_DOCX_UNCOMPRESSED_BYTES,
    MAX_EXTRACTED_CHARACTERS,
    MAX_PDF_PAGES,
)
from app.modules.agents.testing_validation.preparation.extraction.schemas import (
    Agent4DocumentExtractionResult,
    Agent4DocumentFormat,
    Agent4ExtractionError,
    Agent4ExtractionErrorCode,
    Agent4ExtractionStatus,
    Agent4ExtractionWarning,
)
from app.modules.agents.testing_validation.preparation.extraction.storage import (
    Agent4ExtractionStorage,
)
from app.modules.agents.testing_validation.sources.storage import (
    Agent4SourceNotFoundError,
    Agent4SourceStorage,
    StoredAgent4Source,
)
from app.modules.agents.testing_validation.workflow.schemas import (
    Agent4TestGenerationNodeId,
    Agent4WorkflowNodeStatus,
)
from app.modules.agents.testing_validation.workflow.digests import source_set_digest
from app.modules.agents.testing_validation.workflow.service import (
    Agent4WorkflowStageError,
    WrongAgent4WorkflowProjectError,
)
from app.modules.agents.testing_validation.workflow.storage import (
    AGENT4_WORKFLOW_STATE_LOCK,
    Agent4WorkflowStorage,
)
from app.modules.auth.schemas import UserPublicResponse
from app.modules.standalone.service import StandaloneService


EXTRACTION_LOCK = RLock()
DOCUMENT_FORMATS = {
    ".pdf": Agent4DocumentFormat.PDF,
    ".docx": Agent4DocumentFormat.DOCX,
    ".txt": Agent4DocumentFormat.TXT,
    ".md": Agent4DocumentFormat.MD,
    ".json": Agent4DocumentFormat.JSON,
    ".yaml": Agent4DocumentFormat.YAML,
    ".yml": Agent4DocumentFormat.YML,
}


class Agent4ExtractionGateError(ValueError):
    pass


class Agent4ExtractionNotFoundError(LookupError):
    pass


class Agent4ExtractionIntegrityError(ValueError):
    def __init__(self, code: Agent4ExtractionErrorCode, message: str) -> None:
        super().__init__(message)
        self.code = code


class Agent4UnsupportedExtractionSourceError(ValueError):
    pass


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Agent4DocumentExtractionService:
    def __init__(
        self,
        standalone_service: StandaloneService,
        source_storage: Agent4SourceStorage,
        workflow_storage: Agent4WorkflowStorage,
        extraction_storage: Agent4ExtractionStorage,
        *,
        clock=utc_now,
    ) -> None:
        self._standalone = standalone_service
        self._sources = source_storage
        self._workflow = workflow_storage
        self._extractions = extraction_storage
        self._clock = clock

    def extract(
        self,
        agent_project_id: str,
        source_id: str,
        current_user: UserPublicResponse,
        *,
        force: bool = False,
    ) -> Agent4DocumentExtractionResult:
        with AGENT4_WORKFLOW_STATE_LOCK, EXTRACTION_LOCK:
            stored = self.require_confirmed_source(
                agent_project_id, source_id, current_user
            )
            self._require_document(stored)
            integrity_error = self._verify_integrity(stored)
            if integrity_error is not None:
                result = self._failure(stored, integrity_error[0], integrity_error[1])
                self._extractions.save(result, owner_user_id=current_user.user_id)
                return result
            if not force:
                cached = self._extractions.load(
                    agent_project_id=stored.metadata.agent_project_id,
                    owner_user_id=current_user.user_id,
                    source_id=source_id,
                )
                if self._cache_is_current(cached, stored):
                    return cached
            result = self._run(stored)
            self._extractions.save(result, owner_user_id=current_user.user_id)
            return result

    def get_existing(
        self,
        agent_project_id: str,
        source_id: str,
        current_user: UserPublicResponse,
    ) -> Agent4DocumentExtractionResult:
        with AGENT4_WORKFLOW_STATE_LOCK, EXTRACTION_LOCK:
            stored = self.require_confirmed_source(
                agent_project_id, source_id, current_user
            )
            self._require_document(stored)
            integrity_error = self._verify_integrity(stored)
            if integrity_error is not None:
                raise Agent4ExtractionIntegrityError(*integrity_error)
            cached = self._extractions.load(
                agent_project_id=stored.metadata.agent_project_id,
                owner_user_id=current_user.user_id,
                source_id=source_id,
            )
            if not self._cache_is_current(cached, stored):
                raise Agent4ExtractionNotFoundError(source_id)
            return cached

    def require_confirmed_source(
        self,
        agent_project_id: str,
        source_id: str,
        current_user: UserPublicResponse,
    ) -> StoredAgent4Source:
        with AGENT4_WORKFLOW_STATE_LOCK:
            project = self._require_project(agent_project_id, current_user)
            workflow = self._workflow.load(
                agent_project_id=project.agent_project_id,
                owner_user_id=current_user.user_id,
            )
            if workflow is None or workflow.n1_confirmation is None:
                raise Agent4ExtractionGateError(
                    "Input and output setup must be confirmed before preparation"
                )
            n1 = next(
                node
                for node in workflow.nodes
                if node.node_id is Agent4TestGenerationNodeId.INPUT_OUTPUT_SETUP
            )
            if n1.status is not Agent4WorkflowNodeStatus.COMPLETED:
                raise Agent4ExtractionGateError(
                    "Input and output setup must be completed before preparation"
                )
            if source_id not in workflow.n1_confirmation.source_ids:
                raise Agent4SourceNotFoundError(source_id)
            confirmed_sources = [
                self._sources.locate(
                    agent_project_id=project.agent_project_id,
                    owner_user_id=current_user.user_id,
                    source_id=confirmed_source_id,
                ).metadata
                for confirmed_source_id in workflow.n1_confirmation.source_ids
            ]
            if (
                source_set_digest(confirmed_sources)
                != workflow.n1_confirmation.source_set_digest
            ):
                raise Agent4ExtractionGateError(
                    "The collected source metadata no longer matches the confirmed setup"
                )
            return self._sources.locate(
                agent_project_id=project.agent_project_id,
                owner_user_id=current_user.user_id,
                source_id=source_id,
            )

    def require_source_integrity(self, stored: StoredAgent4Source) -> None:
        if stored.metadata.source_type is TestGenerationInputSourceType.TEXT:
            return
        integrity_error = self._verify_integrity(stored)
        if integrity_error is not None:
            raise Agent4ExtractionIntegrityError(*integrity_error)

    def _require_project(self, agent_project_id: str, current_user: UserPublicResponse):
        try:
            validate_id(agent_project_id, "AGP")
        except (TypeError, ValueError) as exc:
            raise Agent4ExtractionGateError("Invalid Agent 4 project identity") from exc
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

    @staticmethod
    def _require_document(stored: StoredAgent4Source) -> None:
        source_type = stored.metadata.source_type
        if source_type is TestGenerationInputSourceType.TEXT:
            raise Agent4UnsupportedExtractionSourceError(
                "TEXT sources do not require document extraction"
            )
        if source_type is TestGenerationInputSourceType.IMAGE:
            raise Agent4UnsupportedExtractionSourceError(
                "IMAGE semantic analysis is not implemented"
            )
        if stored.metadata.extension not in DOCUMENT_FORMATS:
            raise Agent4UnsupportedExtractionSourceError(
                "This document format is not supported for extraction"
            )

    @staticmethod
    def _verify_integrity(
        stored: StoredAgent4Source,
    ) -> tuple[Agent4ExtractionErrorCode, str] | None:
        path = stored.file_path
        if path is None or not path.is_file():
            return (
                Agent4ExtractionErrorCode.SOURCE_FILE_MISSING,
                "The stored source file is unavailable.",
            )
        expected_size = stored.metadata.size_bytes
        try:
            actual_size = path.stat().st_size
            if actual_size != expected_size:
                return (
                    Agent4ExtractionErrorCode.SOURCE_SIZE_MISMATCH,
                    "The stored source size no longer matches its collected metadata.",
                )
            digest = hashlib.sha256()
            with path.open("rb") as stream:
                while chunk := stream.read(1024 * 1024):
                    digest.update(chunk)
        except OSError:
            return (
                Agent4ExtractionErrorCode.SOURCE_FILE_MISSING,
                "The stored source file could not be read safely.",
            )
        if digest.hexdigest() != stored.metadata.sha256:
            return (
                Agent4ExtractionErrorCode.SOURCE_HASH_MISMATCH,
                "The stored source hash no longer matches its collected metadata.",
            )
        return None

    def _run(self, stored: StoredAgent4Source) -> Agent4DocumentExtractionResult:
        document_format = DOCUMENT_FORMATS[stored.metadata.extension]
        try:
            status, content, metrics, warnings = self._dispatch(
                stored.file_path, document_format
            )
        except UnicodeError:
            return self._failure(
                stored,
                Agent4ExtractionErrorCode.ENCODING_ERROR,
                "The document is not valid UTF-8 text.",
            )
        except Exception:
            code = {
                Agent4DocumentFormat.PDF: Agent4ExtractionErrorCode.INVALID_PDF,
                Agent4DocumentFormat.DOCX: Agent4ExtractionErrorCode.INVALID_DOCX,
            }.get(document_format, Agent4ExtractionErrorCode.EXTRACTOR_ERROR)
            return self._failure(
                stored, code, "The document could not be extracted safely."
            )
        extracted_text = (
            content.combined_text
            if hasattr(content, "combined_text")
            else content.normalized_text
        )
        structured = (
            content.structured_content
            if isinstance(content, StructuredContent)
            else None
        )
        pages = content.pages if isinstance(content, PDFContent) else []
        blocks = content.blocks if isinstance(content, DOCXContent) else []
        mapped_warnings = [
            Agent4ExtractionWarning(
                code=warning.code.value,
                message=warning.message,
                page_number=warning.location.page_number if warning.location else None,
                block_index=warning.location.block_index if warning.location else None,
            )
            for warning in warnings
        ]
        mapped_status = Agent4ExtractionStatus(status.value)
        error = None
        if mapped_status is Agent4ExtractionStatus.FAILED:
            code = self._failed_code(document_format, mapped_warnings)
            error = Agent4ExtractionError(
                code=code, message=self._failure_message(code)
            )
        return self._result(
            stored,
            status=mapped_status,
            extracted_text=extracted_text,
            structured_content=structured,
            pages=pages,
            blocks=blocks,
            metrics=metrics.model_dump(),
            warnings=mapped_warnings,
            truncated=any(
                item.code == "CONTENT_TRUNCATED" for item in mapped_warnings
            ),
            error=error,
        )

    @staticmethod
    def _dispatch(path: Path, document_format: Agent4DocumentFormat):
        if document_format is Agent4DocumentFormat.PDF:
            return extract_pdf(
                path,
                max_pages=MAX_PDF_PAGES,
                max_characters=MAX_EXTRACTED_CHARACTERS,
            )
        if document_format is Agent4DocumentFormat.DOCX:
            return extract_docx(
                path,
                max_characters=MAX_EXTRACTED_CHARACTERS,
                max_uncompressed_bytes=MAX_DOCX_UNCOMPRESSED_BYTES,
                max_archive_entries=MAX_DOCX_ARCHIVE_ENTRIES,
            )
        if document_format is Agent4DocumentFormat.TXT:
            return extract_text(path, max_characters=MAX_EXTRACTED_CHARACTERS)
        if document_format is Agent4DocumentFormat.MD:
            return extract_text(
                path, max_characters=MAX_EXTRACTED_CHARACTERS, markdown=True
            )
        return extract_structured(
            path,
            max_characters=MAX_EXTRACTED_CHARACTERS,
            yaml_document=document_format
            in {Agent4DocumentFormat.YAML, Agent4DocumentFormat.YML},
        )

    @staticmethod
    def _failed_code(document_format, warnings):
        codes = {item.code for item in warnings}
        if "INVALID_STRUCTURED_CONTENT" in codes:
            return (
                Agent4ExtractionErrorCode.INVALID_JSON
                if document_format is Agent4DocumentFormat.JSON
                else Agent4ExtractionErrorCode.INVALID_YAML
            )
        if "NO_EXTRACTABLE_TEXT" in codes or "EMPTY_DOCUMENT" in codes:
            return Agent4ExtractionErrorCode.NO_EXTRACTABLE_TEXT
        return Agent4ExtractionErrorCode.EXTRACTOR_ERROR

    @staticmethod
    def _failure_message(code):
        return {
            Agent4ExtractionErrorCode.INVALID_JSON: "The JSON document is invalid.",
            Agent4ExtractionErrorCode.INVALID_YAML: "The YAML document is invalid or unsafe.",
            Agent4ExtractionErrorCode.NO_EXTRACTABLE_TEXT: (
                "The document contains no trustworthy extractable text."
            ),
        }.get(code, "The document could not be extracted safely.")

    def _failure(self, stored, code, message):
        return self._result(
            stored,
            status=Agent4ExtractionStatus.FAILED,
            error=Agent4ExtractionError(code=code, message=message),
        )

    def _result(
        self,
        stored,
        *,
        status,
        extracted_text="",
        structured_content=None,
        pages=None,
        blocks=None,
        metrics=None,
        warnings=None,
        truncated=False,
        error=None,
    ):
        metadata = stored.metadata
        return Agent4DocumentExtractionResult(
            schema_version=AGENT4_EXTRACTION_SCHEMA_VERSION,
            extraction_id=f"A4EXT-{uuid4().hex}",
            agent_project_id=metadata.agent_project_id,
            source_id=metadata.source_id,
            artifact_type=metadata.artifact_type,
            document_format=DOCUMENT_FORMATS[metadata.extension],
            status=status,
            extractor_name=AGENT4_EXTRACTOR_NAME,
            extractor_version=AGENT4_EXTRACTION_VERSION,
            source_sha256=metadata.sha256,
            source_size_bytes=metadata.size_bytes,
            extracted_text=extracted_text,
            structured_content=structured_content,
            pages=pages or [],
            blocks=blocks or [],
            metrics=metrics or {},
            warnings=warnings or [],
            truncated=truncated,
            error=error,
            extracted_at=self._clock(),
        )

    @staticmethod
    def _cache_is_current(cached, stored):
        return (
            cached is not None
            and cached.source_id == stored.metadata.source_id
            and cached.source_sha256 == stored.metadata.sha256
            and cached.source_size_bytes == stored.metadata.size_bytes
            and cached.extractor_version == AGENT4_EXTRACTION_VERSION
            and cached.schema_version == AGENT4_EXTRACTION_SCHEMA_VERSION
        )
