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
from app.modules.agents.requirements.processing.audio.constants import (
    AUDIO_PROCESSOR_VERSION,
    SUPPORTED_AUDIO_EXTENSIONS,
)
from app.modules.agents.requirements.processing.audio.providers.base import (
    AudioTranscriptionError,
    AudioUnreadableError,
    SpeechToTextProvider,
    SpeechToTextProviderNotConfiguredError,
)
from app.modules.agents.requirements.processing.audio.schemas import (
    AudioProcessingError,
    AudioProcessingErrorCode,
    AudioProcessingRecord,
    AudioProcessingResult,
    AudioProcessingStatus,
    TranscriptSegment,
    TranscriptionConfiguration,
)
from app.modules.auth.schemas import UserPublicResponse
from app.modules.standalone.service import StandaloneService


class AudioProcessingNotFoundError(LookupError):
    pass


class UnsupportedAudioSourceError(ValueError):
    pass


class AudioProcessingStorageError(RuntimeError):
    pass


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class AudioProcessingService:
    _processing_lock = Lock()

    def __init__(
        self,
        standalone_service: StandaloneService,
        storage: RequirementSourceStorage,
        provider: SpeechToTextProvider,
        *,
        clock=utc_now,
    ) -> None:
        self._standalone = standalone_service
        self._storage = storage
        self._provider = provider
        self._clock = clock

    def process(
        self,
        agent_project_id: str,
        source_id: str,
        current_user: UserPublicResponse,
        *,
        force: bool = False,
    ) -> AudioProcessingRecord:
        stored = self._require_source(agent_project_id, source_id, current_user)
        with self._processing_lock:
            existing = self._load_valid_record(stored, agent_project_id)
            if (
                not force
                and existing is not None
                and existing.status is AudioProcessingStatus.COMPLETED
                and self._load_valid_result(stored, agent_project_id) is not None
            ):
                return existing

            started_at = self._clock()
            processing = self._record(
                stored,
                agent_project_id,
                AudioProcessingStatus.PROCESSING,
                started_at=started_at,
            )
            self._persist_record(stored, processing)
            self._remove_result(stored)
            try:
                if self._sha256(stored) != stored.metadata.sha256:
                    raise _SafeAudioFailure(
                        AudioProcessingErrorCode.SOURCE_CHECKSUM_MISMATCH,
                        "The source content no longer matches its recorded checksum.",
                    )
                transcription = self._provider.transcribe(stored.file_path)
                if not transcription.transcript.strip():
                    raise _SafeAudioFailure(
                        AudioProcessingErrorCode.NO_USABLE_TRANSCRIPT,
                        "The audio did not produce a usable transcript.",
                    )
                result = AudioProcessingResult(
                    source_id=stored.metadata.source_id,
                    agent_project_id=agent_project_id,
                    source_sha256=stored.metadata.sha256,
                    processor_version=AUDIO_PROCESSOR_VERSION,
                    transcription=self._configuration(),
                    transcript=transcription.transcript,
                    segments=[
                        TranscriptSegment(
                            start_seconds=segment.start_seconds,
                            end_seconds=segment.end_seconds,
                            text=segment.text,
                        )
                        for segment in transcription.segments
                    ],
                    detected_language=transcription.detected_language,
                    language_probability=transcription.language_probability,
                    processed_at=self._clock(),
                )
                self._persist_result(stored, result)
                completed = self._record(
                    stored,
                    agent_project_id,
                    AudioProcessingStatus.COMPLETED,
                    started_at=started_at,
                    completed_at=result.processed_at,
                )
                self._persist_record(stored, completed)
                return completed
            except SpeechToTextProviderNotConfiguredError:
                failure = _SafeAudioFailure(
                    AudioProcessingErrorCode.TRANSCRIPTION_PROVIDER_NOT_CONFIGURED,
                    "The local transcription provider is not configured or available.",
                )
            except AudioUnreadableError:
                failure = _SafeAudioFailure(
                    AudioProcessingErrorCode.AUDIO_UNREADABLE,
                    "The audio source could not be decoded safely.",
                )
            except AudioTranscriptionError:
                failure = _SafeAudioFailure(
                    AudioProcessingErrorCode.AUDIO_TRANSCRIPTION_FAILED,
                    "The audio source could not be transcribed safely.",
                )
            except _SafeAudioFailure as exc:
                failure = exc
            except AudioProcessingStorageError:
                raise
            except Exception:
                failure = _SafeAudioFailure(
                    AudioProcessingErrorCode.AUDIO_TRANSCRIPTION_FAILED,
                    "The audio source could not be transcribed safely.",
                )
            failed = self._record(
                stored,
                agent_project_id,
                AudioProcessingStatus.FAILED,
                started_at=started_at,
                completed_at=self._clock(),
                error=AudioProcessingError(code=failure.code, message=failure.message),
            )
            self._persist_record(stored, failed)
            return failed

    def get_status(
        self,
        agent_project_id: str,
        source_id: str,
        current_user: UserPublicResponse,
    ) -> AudioProcessingRecord:
        stored = self._require_source(agent_project_id, source_id, current_user)
        return self._load_valid_record(stored, agent_project_id) or self._record(
            stored, agent_project_id, AudioProcessingStatus.READY
        )

    def get_result(
        self,
        agent_project_id: str,
        source_id: str,
        current_user: UserPublicResponse,
    ) -> AudioProcessingResult:
        stored = self._require_source(agent_project_id, source_id, current_user)
        result = self._load_valid_result(stored, agent_project_id)
        record = self._load_valid_record(stored, agent_project_id)
        if (
            result is None
            or record is None
            or record.status is not AudioProcessingStatus.COMPLETED
        ):
            raise AudioProcessingNotFoundError(source_id)
        return result

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
            stored.metadata.source_type is not RequirementSourceType.AUDIO
            or stored.metadata.extension not in SUPPORTED_AUDIO_EXTENSIONS
        ):
            raise UnsupportedAudioSourceError("N2B supports AUDIO sources only")
        return stored

    def _configuration(self) -> TranscriptionConfiguration:
        configuration = self._provider.configuration
        return TranscriptionConfiguration(
            provider=configuration.provider,
            provider_version=configuration.provider_version,
            model_name=configuration.model_name,
            device=configuration.device,
            compute_type=configuration.compute_type,
            language=configuration.language,
            fingerprint=configuration.fingerprint,
        )

    @staticmethod
    def _sha256(stored: StoredRequirementSource) -> str:
        digest = hashlib.sha256()
        with stored.file_path.open("rb") as source:
            while chunk := source.read(64 * 1024):
                digest.update(chunk)
        return digest.hexdigest()

    def _record(
        self,
        stored: StoredRequirementSource,
        agent_project_id: str,
        status: AudioProcessingStatus,
        *,
        started_at: datetime | None = None,
        completed_at: datetime | None = None,
        error: AudioProcessingError | None = None,
    ) -> AudioProcessingRecord:
        return AudioProcessingRecord(
            source_id=stored.metadata.source_id,
            agent_project_id=agent_project_id,
            source_sha256=stored.metadata.sha256,
            processor_version=AUDIO_PROCESSOR_VERSION,
            transcription=self._configuration(),
            status=status,
            started_at=started_at,
            completed_at=completed_at,
            error=error,
        )

    def _load_valid_record(
        self,
        stored: StoredRequirementSource,
        agent_project_id: str,
    ) -> AudioProcessingRecord | None:
        try:
            record = AudioProcessingRecord.model_validate_json(
                stored.audio_processing_path.read_text(encoding="utf-8")
            )
        except (FileNotFoundError, OSError, ValidationError):
            return None
        if (
            record.source_id != stored.metadata.source_id
            or record.agent_project_id != agent_project_id
            or record.source_sha256 != stored.metadata.sha256
            or record.processor_version != AUDIO_PROCESSOR_VERSION
            or record.transcription != self._configuration()
        ):
            return None
        return record

    def _load_valid_result(
        self,
        stored: StoredRequirementSource,
        agent_project_id: str,
    ) -> AudioProcessingResult | None:
        try:
            result = AudioProcessingResult.model_validate_json(
                stored.audio_result_path.read_text(encoding="utf-8")
            )
        except (FileNotFoundError, OSError, ValidationError):
            return None
        if (
            result.source_id != stored.metadata.source_id
            or result.agent_project_id != agent_project_id
            or result.source_sha256 != stored.metadata.sha256
            or result.processor_version != AUDIO_PROCESSOR_VERSION
            or result.transcription != self._configuration()
        ):
            return None
        return result

    @staticmethod
    def _persist_record(
        stored: StoredRequirementSource, record: AudioProcessingRecord
    ) -> None:
        AudioProcessingService._persist_json(
            stored.audio_processing_partial_path,
            stored.audio_processing_path,
            record.model_dump(mode="json"),
        )

    @staticmethod
    def _persist_result(
        stored: StoredRequirementSource, result: AudioProcessingResult
    ) -> None:
        AudioProcessingService._persist_json(
            stored.audio_result_partial_path,
            stored.audio_result_path,
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
            raise AudioProcessingStorageError(
                "Audio processing state could not be persisted"
            ) from exc

    @staticmethod
    def _remove_result(stored: StoredRequirementSource) -> None:
        try:
            stored.audio_result_path.unlink(missing_ok=True)
            stored.audio_result_partial_path.unlink(missing_ok=True)
        except OSError as exc:
            raise AudioProcessingStorageError(
                "Previous audio processing result could not be replaced"
            ) from exc


class _SafeAudioFailure(Exception):
    def __init__(self, code: AudioProcessingErrorCode, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
