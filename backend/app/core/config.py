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
    agent3_upload_root: Path = (
        BACKEND_DIR / "storage" / "standalone" / "implementation"
    )
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
