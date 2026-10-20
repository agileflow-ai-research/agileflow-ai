import hashlib
import json
import subprocess
from pathlib import Path
from tempfile import TemporaryFile

from app.modules.agents.requirements.processing.video.constants import (
    EXTRACTED_AUDIO_CHANNELS,
    EXTRACTED_AUDIO_SAMPLE_RATE,
)
from app.modules.agents.requirements.processing.video.providers.base import (
    VideoAudioExtractionConfiguration,
    VideoAudioExtractionError,
    VideoAudioExtractorUnavailableError,
    VideoNoAudioTrackError,
    VideoUnreadableError,
)


_STDERR_LIMIT = 8 * 1024


class FFmpegAudioExtractor:
    def __init__(self, *, executable: str, timeout_seconds: float) -> None:
        self._executable = executable.strip()
        self._timeout_seconds = timeout_seconds

    @property
    def configuration(self) -> VideoAudioExtractionConfiguration:
        executable_name = Path(self._executable).name or "unconfigured"
        values = {
            "provider": "ffmpeg",
            "provider_version": "cli",
            "executable": executable_name,
            "timeout_seconds": self._timeout_seconds,
            "sample_rate_hz": EXTRACTED_AUDIO_SAMPLE_RATE,
            "channels": EXTRACTED_AUDIO_CHANNELS,
        }
        fingerprint = hashlib.sha256(
            json.dumps(values, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        return VideoAudioExtractionConfiguration(**values, fingerprint=fingerprint)

    def extract_audio(self, input_video_path: Path, output_audio_path: Path) -> None:
        if not self._executable or self._timeout_seconds <= 0:
            raise VideoAudioExtractorUnavailableError(
                "The video audio extractor is not configured"
            )
        if output_audio_path.exists():
            raise VideoAudioExtractionError("The extraction target already exists")
        command = [
            self._executable,
            "-nostdin",
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            str(input_video_path),
            "-map",
            "0:a:0",
            "-vn",
            "-ac",
            str(EXTRACTED_AUDIO_CHANNELS),
            "-ar",
            str(EXTRACTED_AUDIO_SAMPLE_RATE),
            "-f",
            "wav",
            "-n",
            str(output_audio_path),
        ]
        try:
            with TemporaryFile() as error_output:
                completed = subprocess.run(
                    command,
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=error_output,
                    timeout=self._timeout_seconds,
                    check=False,
                    shell=False,
                )
                error_output.seek(0, 2)
                error_output.seek(max(0, error_output.tell() - _STDERR_LIMIT))
                stderr = error_output.read(_STDERR_LIMIT).decode(
                    "utf-8", errors="replace"
                ).lower()
        except FileNotFoundError as exc:
            raise VideoAudioExtractorUnavailableError(
                "The configured video audio extractor is unavailable"
            ) from exc
        except subprocess.TimeoutExpired as exc:
            raise VideoAudioExtractionError("Video audio extraction timed out") from exc
        except OSError as exc:
            raise VideoAudioExtractionError("Video audio extraction could not start") from exc

        if completed.returncode != 0:
            if any(
                marker in stderr
                for marker in (
                    "matches no streams",
                    "does not contain any stream",
                    "stream map '0:a:0' matches no streams",
                )
            ):
                raise VideoNoAudioTrackError("The video has no usable audio track")
            if any(
                marker in stderr
                for marker in ("invalid data", "moov atom not found", "could not find codec")
            ):
                raise VideoUnreadableError("The video could not be decoded")
            raise VideoAudioExtractionError("Video audio extraction failed")
        if not output_audio_path.is_file() or output_audio_path.stat().st_size == 0:
            raise VideoNoAudioTrackError("The video has no usable audio track")
