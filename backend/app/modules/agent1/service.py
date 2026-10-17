from datetime import datetime, timezone
from pathlib import Path
import re
from typing import Any

from fastapi import UploadFile

from app.common.id_generator import generate_id
from app.common.model_provider import ModelProviderError
from app.common.transcription_provider import (
    TranscriptionProviderConfigurationError,
    TranscriptionProviderError,
)
from app.common.status import AgentRunMode, AgentType
from app.core.config import settings
from app.modules.agent1.engine import Agent1Engine, StructuredOutputInvalidError
from app.modules.agent1.extractor import ExtractionEmptyError, ExtractionError
from app.modules.agent1.processing import ProcessorNotConfiguredError, SourceProcessorResolver
from app.modules.agent1.repository import (
    RequirementSourceRepository,
)
from app.modules.agent1.schemas import (
    ALLOWED_EXTENSIONS,
    EXTENSION_TO_SOURCE_TYPE,
    PREFIX_BY_SOURCE_TYPE,
    Agent1InputContext,
    Agent1RunRequest,
    Agent1RunResult,
    RequirementSource,
    RequirementSourceRecord,
    RequirementSourceResponse,
    RequirementSourceType,
    SourceProcessingResult,
    SourceProcessingStatus,
)
from app.modules.auth.schemas import UserPublicResponse
from app.modules.standalone.schemas import AgentProject, AgentRun, AgentRunMessage
from app.modules.standalone.service import StandaloneService


class WrongAgentProjectTypeError(ValueError):
    pass


class SourceNotFoundError(LookupError):
    pass


class NoUsableSourceError(ValueError):
    """Raised when a run has no usable (extracted) sources to process."""


DISALLOWED_MIME_PATTERNS = (
    "executable",
    "x-msdownload",
    "x-sh",
    "x-bat",
    "x-csh",
    "x-python",
    "javascript",
    "application/x-dosexec",
)


def sanitize_filename(filename: str) -> str:
    base = Path(filename).name
    cleaned = re.sub(r"[^\w\.\-]", "_", base)
    if not cleaned or cleaned.startswith("."):
        cleaned = f"upload_{cleaned}".strip(".")
    return cleaned


def validate_mime_type(source_type: RequirementSourceType, mime_type: str | None) -> None:
    if not mime_type:
        return
    mime_lower = mime_type.lower().strip()
    for disallowed in DISALLOWED_MIME_PATTERNS:
        if disallowed in mime_lower:
            raise ValueError(f"Disallowed executable or script MIME type: {mime_type}")
    if source_type == RequirementSourceType.AUDIO and not (
        mime_lower.startswith("audio/") or mime_lower == "application/octet-stream"
    ):
        raise ValueError(f"MIME type '{mime_type}' is not valid for AUDIO source")
    if source_type == RequirementSourceType.VIDEO and not (
        mime_lower.startswith("video/") or mime_lower == "application/octet-stream"
    ):
        raise ValueError(f"MIME type '{mime_type}' is not valid for VIDEO source")
    if source_type == RequirementSourceType.DOCUMENT:
        if mime_lower.startswith("audio/") or mime_lower.startswith("video/"):
            raise ValueError(f"MIME type '{mime_type}' is not valid for DOCUMENT source")


class RequirementSourceService:
    def __init__(
        self,
        standalone_service: StandaloneService,
        source_repository: RequirementSourceRepository,
        upload_dir: str | Path | None = None,
        max_upload_size: int | None = None,
    ) -> None:
        self._standalone = standalone_service
        self._repository = source_repository
        self._upload_dir = Path(upload_dir or settings.upload_dir)
        self._max_upload_size = max_upload_size or settings.max_upload_size_bytes

    async def add_source(
        self,
        agent_project_id: str,
        current_user: UserPublicResponse,
        file: UploadFile,
        source_type: RequirementSourceType | None = None,
    ) -> RequirementSourceResponse:
        project = self._standalone.require_active_project(
            current_user.user_id, agent_project_id
        )
        if project.agent_type is not AgentType.REQUIREMENTS:
            raise WrongAgentProjectTypeError(
                "Agent project must have agent_type REQUIREMENTS"
            )

        original_filename = file.filename or "unknown"
        ext = Path(original_filename).suffix.lower()
        if not ext:
            raise ValueError(f"File '{original_filename}' has no extension")

        if source_type is not None:
            if ext not in ALLOWED_EXTENSIONS[source_type]:
                allowed = ", ".join(sorted(ALLOWED_EXTENSIONS[source_type]))
                raise ValueError(
                    f"File '{original_filename}' with extension '{ext}' is not valid for {source_type.value}. Allowed: {allowed}"
                )
            resolved_type = source_type
        else:
            resolved_type = EXTENSION_TO_SOURCE_TYPE.get(ext)
            if resolved_type is None:
                raise ValueError(f"Unsupported file extension '{ext}'")

        validate_mime_type(resolved_type, file.content_type)

        content = await file.read()
        file_size = len(content)
        if file_size == 0:
            raise ValueError(f"Uploaded file '{original_filename}' is empty")
        if file_size > self._max_upload_size:
            raise ValueError(
                f"File '{original_filename}' size ({file_size} bytes) exceeds maximum allowed limit of {self._max_upload_size} bytes"
            )

        prefix = PREFIX_BY_SOURCE_TYPE[resolved_type]
        seq = self._repository.next_source_sequence(agent_project_id, prefix)
        source_id = generate_id(prefix, seq)

        safe_name = sanitize_filename(original_filename)
        project_dir = self._upload_dir / agent_project_id
        project_dir.mkdir(parents=True, exist_ok=True)
        stored_file_path = project_dir / f"{source_id}_{safe_name}"
        stored_file_path.write_bytes(content)

        now = datetime.now(timezone.utc)
        record = RequirementSourceRecord(
            source_id=source_id,
            agent_project_id=agent_project_id,
            owner_user_id=current_user.user_id,
            source_type=resolved_type,
            original_filename=original_filename,
            safe_filename=safe_name,
            storage_path=str(stored_file_path),
            mime_type=file.content_type,
            file_size=file_size,
            processing_status=SourceProcessingStatus.READY,
            is_deleted=False,
            created_at=now,
            updated_at=now,
        )
        saved = self._repository.create_source(record)
        return RequirementSourceResponse.model_validate(saved)

    async def upload_sources(
        self,
        agent_project_id: str,
        current_user: UserPublicResponse,
        files: list[UploadFile],
        source_type: RequirementSourceType | None = None,
    ) -> list[RequirementSourceResponse]:
        results: list[RequirementSourceResponse] = []
        for file in files:
            result = await self.add_source(agent_project_id, current_user, file, source_type)
            results.append(result)
        return results

    def list_sources(
        self,
        agent_project_id: str,
        current_user: UserPublicResponse,
    ) -> list[RequirementSourceResponse]:
        project = self._standalone.require_active_project(
            current_user.user_id, agent_project_id
        )
        if project.agent_type is not AgentType.REQUIREMENTS:
            raise WrongAgentProjectTypeError(
                "Agent project must have agent_type REQUIREMENTS"
            )
        documents = self._repository.list_sources(agent_project_id, current_user.user_id)
        return [RequirementSourceResponse.model_validate(doc) for doc in documents]

    def delete_source(
        self,
        agent_project_id: str,
        source_id: str,
        current_user: UserPublicResponse,
    ) -> None:
        project = self._standalone.require_active_project(
            current_user.user_id, agent_project_id
        )
        if project.agent_type is not AgentType.REQUIREMENTS:
            raise WrongAgentProjectTypeError(
                "Agent project must have agent_type REQUIREMENTS"
            )
        source = self._repository.get_source(agent_project_id, source_id, current_user.user_id)
        if source is None:
            raise SourceNotFoundError(f"Source {source_id} not found in project {agent_project_id}")

        self._repository.delete_source(agent_project_id, source_id, current_user.user_id)
        storage_path = source.get("storage_path")
        if storage_path:
            try:
                p = Path(storage_path)
                if p.is_file():
                    p.unlink(missing_ok=True)
            except OSError:
                pass


        # Success — persist and add to engine context
class RequirementSourceProcessingService:
    """Process sources independently without creating runs or invoking Agent 1."""

    def __init__(
        self,
        standalone_service: StandaloneService,
        source_repository: RequirementSourceRepository,
        resolver: SourceProcessorResolver | None = None,
    ) -> None:
        self._standalone = standalone_service
        self._repository = source_repository
        self._resolver = resolver or SourceProcessorResolver()

    def process_sources(
        self, agent_project_id: str, current_user: UserPublicResponse
    ) -> list[SourceProcessingResult]:
        project = self._standalone.require_active_project(
            current_user.user_id, agent_project_id
        )
        if project.agent_type is not AgentType.REQUIREMENTS:
            raise WrongAgentProjectTypeError(
                "Agent project must have agent_type REQUIREMENTS"
            )
        results: list[SourceProcessingResult] = []
        raw_sources = self._repository.list_sources_for_run(
            agent_project_id, current_user.user_id
        )
        for raw in raw_sources:
            source_id = raw["source_id"]
            source_type = RequirementSourceType(raw["source_type"])
            try:
                processor = self._resolver.resolve(source_type)
            except ProcessorNotConfiguredError:
                results.append(
                    SourceProcessingResult(
                        source_id=source_id,
                        source_type=source_type,
                        processing_status=SourceProcessingStatus.READY,
                        processing_error_code="PROCESSOR_NOT_CONFIGURED",
                        processing_error_message=(
                            f"{source_type.value.title()} processing is not configured yet."
                        ),
                    )
                )
                continue

            self._repository.update_source_processing(
                agent_project_id,
                source_id,
                current_user.user_id,
                SourceProcessingStatus.PROCESSING,
                clear_result=True,
            )
            try:
                normalized_text = processor.process(raw["storage_path"])
            except TranscriptionProviderConfigurationError:
                result = self._fail_source(
                    agent_project_id, source_id, source_type, current_user.user_id,
                    "TRANSCRIPTION_PROVIDER_NOT_CONFIGURED",
                    "Audio transcription is not configured.",
                )
            except TranscriptionProviderError:
                result = self._fail_source(
                    agent_project_id, source_id, source_type, current_user.user_id,
                    "AUDIO_TRANSCRIPTION_FAILED",
                    "The audio source could not be transcribed.",
                )
            except (ExtractionEmptyError, ValueError):
                code = (
                    "NO_USABLE_TRANSCRIPT"
                    if source_type is RequirementSourceType.AUDIO
                    else "NO_EXTRACTABLE_TEXT"
                )
                message = (
                    "No usable transcript could be produced."
                    if source_type is RequirementSourceType.AUDIO
                    else "No usable text could be extracted."
                )
                result = self._fail_source(
                    agent_project_id, source_id, source_type, current_user.user_id,
                    code, message,
                )
            except Exception:
                code = (
                    "AUDIO_TRANSCRIPTION_FAILED"
                    if source_type is RequirementSourceType.AUDIO
                    else "DOCUMENT_PROCESSING_FAILED"
                )
                message = (
                    "The audio source could not be transcribed."
                    if source_type is RequirementSourceType.AUDIO
                    else "The document could not be processed."
                )
                result = self._fail_source(
                    agent_project_id, source_id, source_type, current_user.user_id,
                    code, message,
                )
            else:
                self._repository.update_source_processing(
                    agent_project_id,
                    source_id,
                    current_user.user_id,
                    SourceProcessingStatus.COMPLETED,
                    normalized_text=normalized_text,
                    processed_at=datetime.now(timezone.utc),
                )
                result = SourceProcessingResult(
                    source_id=source_id,
                    source_type=source_type,
                    processing_status=SourceProcessingStatus.COMPLETED,
                )
            results.append(result)
        return results

    def _fail_source(
        self, agent_project_id, source_id, source_type, owner_user_id, code, message
    ) -> SourceProcessingResult:
        self._repository.update_source_processing(
            agent_project_id,
            source_id,
            owner_user_id,
            SourceProcessingStatus.FAILED,
            processing_error_code=code,
            processing_error_message=message,
            processed_at=datetime.now(timezone.utc),
        )
        return SourceProcessingResult(
            source_id=source_id,
            source_type=source_type,
            processing_status=SourceProcessingStatus.FAILED,
            processing_error_code=code,
            processing_error_message=message,
        )


class Agent1Service:
    def __init__(
        self,
        standalone_service: StandaloneService,
        source_repository: RequirementSourceRepository,
        engine: Agent1Engine,
    ) -> None:
        self._standalone = standalone_service
        self._repository = source_repository
        self._engine = engine

    def run(
        self,
        agent_project_id: str,
        request: Agent1RunRequest,
        current_user: UserPublicResponse,
    ) -> Agent1RunResult:
        project = self._standalone.require_active_project(
            current_user.user_id, agent_project_id
        )
        if project.agent_type is not AgentType.REQUIREMENTS:
            raise WrongAgentProjectTypeError(
                "Agent project must have agent_type REQUIREMENTS"
            )

        # Processing is a separate Step 2 operation. Runs only consume completed text.
        raw_sources = self._repository.list_sources_for_run(
            agent_project_id, current_user.user_id
        )
        engine_sources = [
            RequirementSource(
                source_id=raw["source_id"],
                source_type="DOCUMENT",
                content=raw["normalized_text"],
            )
            for raw in raw_sources
            if raw.get("processing_status") == SourceProcessingStatus.COMPLETED.value
            and raw.get("normalized_text")
        ]

        # Merge TEXT input if supplied
        if request.text:
            engine_sources.insert(
                0,
                RequirementSource(
                    source_id="TEXT-001",
                    source_type="TEXT",
                    content=request.text,
                ),
            )

        if not engine_sources:
            raise NoUsableSourceError(
                "No usable requirement sources are available. "
                "Upload at least one document or enter text."
            )

        context = self._build_context(project, request, engine_sources)
        selected = [code.value for code in request.selected_outputs]

        run = self._standalone.create_run(
            current_user.user_id,
            agent_project_id,
            AgentRunMode.DEFAULT,
            selected,
            context.model_dump(mode="json", exclude_none=True),
        )
        run = self._standalone.mark_run_running(
            current_user.user_id, agent_project_id, run.run_id
        )
        try:
            outputs = self._engine.execute(context, request.selected_outputs)
            all_warnings = self._warnings_for(outputs, selected)
            run = self._standalone.complete_run(
                current_user.user_id,
                agent_project_id,
                run.run_id,
                outputs,
                all_warnings,
            )
        except StructuredOutputInvalidError as exc:
            run = self._fail(run, "STRUCTURED_OUTPUT_INVALID", str(exc))
        except ModelProviderError:
            run = self._fail(
                run,
                "MODEL_EXECUTION_FAILED",
                "The configured model provider could not generate the requested outputs",
            )
        except Exception:
            run = self._fail(
                run,
                "INTERNAL_ERROR",
                "Agent 1 execution failed unexpectedly",
            )
        return self.to_result(run)

    @staticmethod
    def _build_context(
        project: AgentProject,
        request: Agent1RunRequest,
        sources: list[RequirementSource],
    ) -> Agent1InputContext:
        return Agent1InputContext(
            project_name=project.name.strip(),
            domain=project.domain.strip(),
            sources=sources,
            background_context=request.background_context,
            business_goals=request.business_goals,
            known_constraints=request.known_constraints,
            existing_requirements=request.existing_requirements,
            additional_notes=request.additional_notes,
        )

    def _fail(self, run: AgentRun, code: str, message: str) -> AgentRun:
        return self._standalone.fail_run(
            run.owner_user_id,
            run.agent_project_id,
            run.run_id,
            [AgentRunMessage(code=code, message=message)],
        )

    @staticmethod
    def _warnings_for(
        outputs: dict[str, Any], selected: list[str]
    ) -> list[AgentRunMessage]:
        supplemental = sorted(set(outputs) - set(selected))
        if not supplemental:
            return []
        return [
            AgentRunMessage(
                code="CLARIFICATION_REQUIRED",
                message="Quality issues required supplemental clarification evidence",
                details={"supplemental_outputs": supplemental},
            )
        ]

    @staticmethod
    def to_result(run: AgentRun) -> Agent1RunResult:
        return Agent1RunResult(
            run_id=run.run_id,
            agent_project_id=run.agent_project_id,
            agent_type=run.agent_type,
            run_mode=run.run_mode,
            status=run.status,
            selected_outputs=run.selected_outputs,
            started_at=run.started_at,
            completed_at=run.completed_at,
            outputs=run.output_manifest,
            warnings=run.warnings,
            errors=run.errors,
        )
