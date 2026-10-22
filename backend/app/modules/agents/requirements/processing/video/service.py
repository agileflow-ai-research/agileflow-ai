import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Lock

from pydantic import ValidationError

from app.modules.agents.requirements.contracts.schemas import RequirementSourceType
from app.modules.agents.requirements.infrastructure.storage import (
    RequirementSourceStorage,
    StoredRequirementSource,
)
from app.modules.agents.requirements.inputs.upload.service import require_requirements_project
from app.modules.agents.requirements.processing.audio.providers.base import (
    AudioTranscriptionError,
    AudioUnreadableError,
    SpeechToTextProvider,
    SpeechToTextProviderNotConfiguredError,
)
from app.modules.agents.requirements.processing.audio.schemas import (
    TranscriptSegment,
    TranscriptionConfiguration,
)
from app.modules.agents.requirements.processing.video.constants import (
    SUPPORTED_VIDEO_TYPES,
    VIDEO_PROCESSOR_VERSION,
)
from app.modules.agents.requirements.processing.video.providers.base import (
    VideoAudioExtractionError,
    VideoAudioExtractor,
    VideoAudioExtractorUnavailableError,
    VideoNoAudioTrackError,
    VideoUnreadableError,
)
from app.modules.agents.requirements.processing.video.schemas import (
    VideoExtractionConfiguration,
    VideoProcessingError,
    VideoProcessingErrorCode,
    VideoProcessingRecord,
    VideoProcessingResult,
    VideoProcessingStatus,
)
from app.modules.auth.schemas import UserPublicResponse
from app.modules.standalone.service import StandaloneService


class VideoProcessingNotFoundError(LookupError):
    pass


class UnsupportedVideoSourceError(ValueError):
    pass


class VideoProcessingStorageError(RuntimeError):
    pass


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class VideoProcessingService:
    _processing_lock = Lock()

    def __init__(
        self,
        standalone_service: StandaloneService,
        storage: RequirementSourceStorage,
        extractor: VideoAudioExtractor,
        transcription_provider: SpeechToTextProvider,
        *,
        clock=utc_now,
    ) -> None:
        self._standalone = standalone_service
        self._storage = storage
        self._extractor = extractor
        self._transcription_provider = transcription_provider
        self._clock = clock

    def process(
        self,
        agent_project_id: str,
        source_id: str,
        current_user: UserPublicResponse,
        *,
        force: bool = False,
    ) -> VideoProcessingRecord:
        stored = self._require_source(agent_project_id, source_id, current_user)
        with self._processing_lock:
            existing = self._load_valid_record(stored, agent_project_id)
            if (
                not force
                and existing is not None
                and existing.status is VideoProcessingStatus.COMPLETED
                and self._load_valid_result(stored, agent_project_id) is not None
            ):
                return existing

            started_at = self._clock()
            processing = self._record(
                stored,
                agent_project_id,
                VideoProcessingStatus.PROCESSING,
                started_at=started_at,
            )
            self._persist_record(stored, processing)
            self._remove_result(stored)
            try:
                self._validate_file(stored)
                with TemporaryDirectory(prefix="agent1-video-") as workspace:
                    audio_path = Path(workspace) / "extracted-audio.wav"
                    self._extractor.extract_audio(stored.file_path, audio_path)
                    if not audio_path.is_file() or audio_path.stat().st_size == 0:
                        raise VideoNoAudioTrackError()
                    transcription = self._transcription_provider.transcribe(audio_path)
                if not transcription.transcript.strip():
                    raise _SafeVideoFailure(
                        VideoProcessingErrorCode.VIDEO_TRANSCRIPTION_FAILED,
                        "The extracted audio did not produce a usable transcript.",
                    )
                result = VideoProcessingResult(
                    source_id=stored.metadata.source_id,
                    agent_project_id=agent_project_id,
                    source_sha256=stored.metadata.sha256,
                    original_filename=stored.metadata.original_filename,
                    mime_type=stored.metadata.mime_type,
                    processor_version=VIDEO_PROCESSOR_VERSION,
                    extraction=self._extraction_configuration(),
                    transcription=self._transcription_configuration(),
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
                    VideoProcessingStatus.COMPLETED,
                    started_at=started_at,
                    completed_at=result.processed_at,
                )
                self._persist_record(stored, completed)
                return completed
            except _SafeVideoFailure as exc:
                failure = exc
            except VideoNoAudioTrackError:
                failure = _SafeVideoFailure(
                    VideoProcessingErrorCode.VIDEO_NO_AUDIO_TRACK,
                    "The video does not contain a usable audio track.",
                )
            except VideoUnreadableError:
                failure = _SafeVideoFailure(
                    VideoProcessingErrorCode.VIDEO_UNREADABLE,
                    "The video source could not be decoded safely.",
                )
            except (
                VideoAudioExtractorUnavailableError,
                VideoAudioExtractionError,
            ):
                failure = _SafeVideoFailure(
                    VideoProcessingErrorCode.VIDEO_AUDIO_EXTRACTION_FAILED,
                    "Audio could not be extracted from the video safely.",
                )
            except (
                SpeechToTextProviderNotConfiguredError,
                AudioUnreadableError,
                AudioTranscriptionError,
            ):
                failure = _SafeVideoFailure(
                    VideoProcessingErrorCode.VIDEO_TRANSCRIPTION_FAILED,
                    "The extracted video audio could not be transcribed safely.",
                )
            except VideoProcessingStorageError:
                raise
            except Exception:
                failure = _SafeVideoFailure(
                    VideoProcessingErrorCode.VIDEO_PROCESSING_FAILED,
                    "The video source could not be processed safely.",
                )
            failed = self._record(
                stored,
                agent_project_id,
                VideoProcessingStatus.FAILED,
                started_at=started_at,
                completed_at=self._clock(),
                error=VideoProcessingError(code=failure.code, message=failure.message),
            )
            self._persist_record(stored, failed)
            return failed

    def get_status(self, agent_project_id, source_id, current_user):
        stored = self._require_source(agent_project_id, source_id, current_user)
        with self._processing_lock:
            record = self._load_valid_record(stored, agent_project_id)
            if record is not None:
                return self._reconcile_completed_record(
                    stored, agent_project_id, record
                )
            return self._record(stored, agent_project_id, VideoProcessingStatus.READY)

    def get_result(self, agent_project_id, source_id, current_user):
        stored = self._require_source(agent_project_id, source_id, current_user)
        with self._processing_lock:
            result = self._load_valid_result(stored, agent_project_id)
            record = self._load_valid_record(stored, agent_project_id)
            if record is not None and record.status is VideoProcessingStatus.COMPLETED:
                record = self._reconcile_completed_record(
                    stored, agent_project_id, record, result=result
                )
            if (
                result is None
                or record is None
                or record.status is not VideoProcessingStatus.COMPLETED
            ):
                raise VideoProcessingNotFoundError(source_id)
            return result

    def _reconcile_completed_record(
        self,
        stored,
        agent_project_id,
        record,
        *,
        result=None,
    ):
        if record.status is not VideoProcessingStatus.COMPLETED:
            return record
        compatible_result = result or self._load_valid_result(stored, agent_project_id)
        if compatible_result is not None:
            return record
        reconciled = self._record(
            stored,
            agent_project_id,
            VideoProcessingStatus.FAILED,
            started_at=record.started_at,
            completed_at=self._clock(),
            error=VideoProcessingError(
                code=VideoProcessingErrorCode.PROCESSING_RESULT_INVALID,
                message="The completed processing result is missing or incompatible. Retry processing.",
            ),
        )
        self._persist_record(stored, reconciled)
        return reconciled

    def _require_source(self, agent_project_id, source_id, current_user):
        project = require_requirements_project(
            self._standalone, agent_project_id, current_user
        )
        stored = self._storage.locate(
            agent_project_id=project.agent_project_id,
            owner_user_id=current_user.user_id,
            source_id=source_id,
            require_file=False,
        )
        if stored.metadata.source_type is not RequirementSourceType.VIDEO:
            raise UnsupportedVideoSourceError("N2C supports VIDEO sources only")
        return stored

    def _validate_file(self, stored: StoredRequirementSource) -> None:
        if not stored.file_path.is_file():
            raise _SafeVideoFailure(
                VideoProcessingErrorCode.VIDEO_FILE_MISSING,
                "The stored video source is missing.",
            )
        if stored.file_path.stat().st_size == 0:
            raise _SafeVideoFailure(
                VideoProcessingErrorCode.VIDEO_EMPTY,
                "The stored video source is empty.",
            )
        expected_mime = SUPPORTED_VIDEO_TYPES.get(stored.metadata.extension)
        if expected_mime is None or stored.metadata.mime_type != expected_mime:
            raise _SafeVideoFailure(
                VideoProcessingErrorCode.VIDEO_UNSUPPORTED_FORMAT,
                "The stored video format is not supported.",
            )
        if self._sha256(stored) != stored.metadata.sha256:
            raise _SafeVideoFailure(
                VideoProcessingErrorCode.VIDEO_CHECKSUM_MISMATCH,
                "The video content no longer matches its recorded checksum.",
            )

    @staticmethod
    def _sha256(stored: StoredRequirementSource) -> str:
        digest = hashlib.sha256()
        with stored.file_path.open("rb") as source:
            while chunk := source.read(64 * 1024):
                digest.update(chunk)
        return digest.hexdigest()

    def _extraction_configuration(self) -> VideoExtractionConfiguration:
        value = self._extractor.configuration
        return VideoExtractionConfiguration(
            provider=value.provider,
            provider_version=value.provider_version,
            executable=value.executable,
            timeout_seconds=value.timeout_seconds,
            sample_rate_hz=value.sample_rate_hz,
            channels=value.channels,
            fingerprint=value.fingerprint,
        )

    def _transcription_configuration(self) -> TranscriptionConfiguration:
        value = self._transcription_provider.configuration
        return TranscriptionConfiguration(
            provider=value.provider,
            provider_version=value.provider_version,
            model_name=value.model_name,
            device=value.device,
            compute_type=value.compute_type,
            language=value.language,
            fingerprint=value.fingerprint,
        )

    def _record(
        self,
        stored,
        agent_project_id,
        status,
        *,
        started_at=None,
        completed_at=None,
        error=None,
    ):
        return VideoProcessingRecord(
            source_id=stored.metadata.source_id,
            agent_project_id=agent_project_id,
            source_sha256=stored.metadata.sha256,
            processor_version=VIDEO_PROCESSOR_VERSION,
            extraction=self._extraction_configuration(),
            transcription=self._transcription_configuration(),
            status=status,
            started_at=started_at,
            completed_at=completed_at,
            error=error,
        )

    def _load_valid_record(self, stored, agent_project_id):
        try:
            record = VideoProcessingRecord.model_validate_json(
                stored.video_processing_path.read_text(encoding="utf-8")
            )
        except (FileNotFoundError, OSError, ValidationError):
            return None
        if (
            record.source_id != stored.metadata.source_id
            or record.agent_project_id != agent_project_id
            or record.source_sha256 != stored.metadata.sha256
            or record.processor_version != VIDEO_PROCESSOR_VERSION
            or record.extraction != self._extraction_configuration()
            or record.transcription != self._transcription_configuration()
        ):
            return None
        return record

    def _load_valid_result(self, stored, agent_project_id):
        try:
            result = VideoProcessingResult.model_validate_json(
                stored.video_result_path.read_text(encoding="utf-8")
            )
        except (FileNotFoundError, OSError, ValidationError):
            return None
        if (
            result.source_id != stored.metadata.source_id
            or result.agent_project_id != agent_project_id
            or result.source_sha256 != stored.metadata.sha256
            or result.original_filename != stored.metadata.original_filename
            or result.mime_type != stored.metadata.mime_type
            or result.processor_version != VIDEO_PROCESSOR_VERSION
            or result.extraction != self._extraction_configuration()
            or result.transcription != self._transcription_configuration()
        ):
            return None
        return result

    @staticmethod
    def _persist_json(partial_path, final_path, value):
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
            raise VideoProcessingStorageError(
                "Video processing state could not be persisted"
            ) from exc

    @classmethod
    def _persist_record(cls, stored, record):
        cls._persist_json(
            stored.video_processing_partial_path,
            stored.video_processing_path,
            record.model_dump(mode="json"),
        )

    @classmethod
    def _persist_result(cls, stored, result):
        cls._persist_json(
            stored.video_result_partial_path,
            stored.video_result_path,
            result.model_dump(mode="json"),
        )

    @staticmethod
    def _remove_result(stored):
        try:
            stored.video_result_path.unlink(missing_ok=True)
            stored.video_result_partial_path.unlink(missing_ok=True)
        except OSError as exc:
            raise VideoProcessingStorageError(
                "Previous video processing result could not be replaced"
            ) from exc


class _SafeVideoFailure(Exception):
    def __init__(self, code: VideoProcessingErrorCode, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
