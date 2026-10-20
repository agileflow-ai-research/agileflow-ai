# N2C video processing

N2C consumes immutable `VID-###` Node 1 sources. It verifies the stored source, extracts a mono 16 kHz WAV through `VideoAudioExtractor`, transcribes that temporary WAV through the existing `SpeechToTextProvider`, and persists video-specific status/result sidecars. Temporary audio is removed when the controlled workspace closes on both success and failure.

The production extractor invokes the configured FFmpeg executable with an explicit argument list, `shell=False`, `-nostdin`, a bounded timeout, and a backend-created output path. API responses and persisted configuration expose only the executable basename, never a configured filesystem path or FFmpeg stderr.

Normal tests inject fake extraction and transcription providers and never execute FFmpeg or faster-whisper.

For an optional local smoke test, ensure FFmpeg is already on `PATH` (or set `VIDEO_FFMPEG_PATH`), upload a small MP4/MOV/WEBM containing speech, and call the existing source processing endpoints. Do not use production or sensitive media for this check.
