from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


BACKEND_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    app_name: str = "AgileFlow AI"
    app_env: str = "development"
    api_v1_prefix: str = "/api/v1"
    frontend_origin: str = "http://localhost:5173"
    mongodb_uri: str = "mongodb://localhost:27017"
    mongodb_database: str = "agileflow_ai"
    jwt_secret_key: str | None = None
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 60
    model_provider: str = "openai_compatible"
    model_api_key: str | None = None
    model_name: str = "gpt-4.1-mini"
    model_base_url: str = "https://api.openai.com/v1"
    model_timeout_seconds: float = 60.0
    agent1_source_root: Path = (
        BACKEND_DIR / "storage" / "standalone" / "requirements"
    )
    transcription_provider: str = "faster_whisper"
    faster_whisper_model: str = "small"
    faster_whisper_device: str = "cpu"
    faster_whisper_compute_type: str = "int8"
    faster_whisper_language: str = ""
    video_ffmpeg_path: str = "ffmpeg"
    video_ffmpeg_timeout_seconds: float = 120.0
    agent1_chunk_target_chars: int = 900
    agent1_chunk_max_chars: int = 1200
    agent1_chunk_overlap_sentences: int = 1
    agent1_classifier_model_id: str = (
        "MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli"
    )
    agent1_classifier_model_revision: str = (
        "6f5cf0a2b59cabb106aca4c287eed12e357e90eb"
    )
    agent1_classifier_device: str = "cpu"
    agent1_classifier_batch_size: int = 4
    agent1_classifier_local_files_only: bool = False
    agent1_classifier_minimum_confidence: float = 0.5
    agent1_classifier_minimum_margin: float = 0.1
    agent3_upload_root: Path = (
        BACKEND_DIR / "storage" / "standalone" / "implementation"
    )
    agent3_zero_shot_local_files_only: bool = False
    agent3_semantic_model_id: str = "Qwen/Qwen3-1.7B"
    agent3_semantic_model_revision: str = "70d244cc86ccca08cf5af4e1e306ecf908b1ad5e"
    agent3_semantic_local_files_only: bool = False
    agent3_semantic_device: str = "auto"
    github_app_id: str | None = None
    github_app_client_id: str | None = None
    github_app_client_secret: str | None = None
    github_app_slug: str | None = None
    github_app_setup_callback_url: str | None = None
    github_app_oauth_callback_url: str | None = None
    github_app_private_key_path: Path | None = None
    github_web_base_url: str = "https://github.com"
    github_api_base_url: str = "https://api.github.com"
    frontend_base_url: str = "http://localhost:5173"
    github_http_timeout_seconds: float = 10.0

    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
