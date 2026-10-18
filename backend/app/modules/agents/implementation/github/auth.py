import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import httpx
import jwt

from app.core.config import Settings


class GitHubPrivateKeyError(RuntimeError):
    pass


class GitHubAppAuthenticationError(RuntimeError):
    pass


class GitHubAppPermissionError(RuntimeError):
    pass


class GitHubInstallationRevokedError(RuntimeError):
    pass


class GitHubExternalServiceError(RuntimeError):
    pass


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class GitHubAppAuthenticator:
    def __init__(self, settings: Settings, *, clock=utc_now) -> None:
        self._client_id = settings.github_app_client_id
        self._private_key_path = settings.github_app_private_key_path
        self._api_base_url = settings.github_api_base_url.rstrip("/")
        self._timeout_seconds = settings.github_http_timeout_seconds
        self._clock = clock

    def create_app_jwt(self) -> str:
        if not self._client_id:
            raise GitHubAppAuthenticationError(
                "GitHub App client ID is not configured"
            )
        private_key = self._read_private_key()
        now = self._clock()
        payload = {
            "iss": self._client_id,
            "iat": int((now - timedelta(seconds=60)).timestamp()),
            "exp": int((now + timedelta(minutes=9)).timestamp()),
        }
        try:
            return jwt.encode(payload, private_key, algorithm="RS256")
        except (jwt.PyJWTError, ValueError, TypeError) as exc:
            raise GitHubPrivateKeyError(
                "GitHub App private key is invalid"
            ) from exc

    def create_installation_token(self, installation_id: int) -> str:
        app_jwt = self.create_app_jwt()
        try:
            response = httpx.post(
                f"{self._api_base_url}/app/installations/"
                f"{installation_id}/access_tokens",
                headers={
                    "Accept": "application/vnd.github+json",
                    "Authorization": f"Bearer {app_jwt}",
                    "X-GitHub-Api-Version": "2022-11-28",
                },
                timeout=self._timeout_seconds,
            )
        except httpx.HTTPError as exc:
            raise GitHubExternalServiceError(
                "GitHub is temporarily unavailable"
            ) from exc
        if response.status_code == 401:
            raise GitHubAppAuthenticationError(
                "GitHub App authentication failed"
            )
        if response.status_code == 403:
            raise GitHubAppPermissionError(
                "GitHub App does not have permission to access this installation"
            )
        if response.status_code == 404:
            raise GitHubInstallationRevokedError(
                "GitHub connection is no longer valid. Reconnect GitHub."
            )
        if response.status_code >= 400:
            raise GitHubExternalServiceError(
                "GitHub installation authentication failed"
            )
        body = self._json_object(response)
        token = body.get("token")
        expires_at = body.get("expires_at")
        try:
            expires = datetime.fromisoformat(
                expires_at.replace("Z", "+00:00")
            ) if isinstance(expires_at, str) else None
        except ValueError:
            expires = None
        if (
            not isinstance(token, str)
            or not token
            or expires is None
            or expires.tzinfo is None
            or expires <= self._clock()
        ):
            raise GitHubExternalServiceError(
                "GitHub returned an invalid installation token response"
            )
        return token

    def _read_private_key(self) -> str:
        path = self._private_key_path
        if path is None:
            raise GitHubPrivateKeyError(
                "GitHub App private key path is not configured"
            )
        try:
            if not path.is_file():
                raise GitHubPrivateKeyError(
                    "GitHub App private key path must reference a readable file"
                )
            return path.read_text(encoding="utf-8")
        except GitHubPrivateKeyError:
            raise
        except (OSError, UnicodeError) as exc:
            raise GitHubPrivateKeyError(
                "GitHub App private key file cannot be read"
            ) from exc

    @staticmethod
    def _json_object(response: httpx.Response) -> dict[str, Any]:
        try:
            body = response.json()
        except (json.JSONDecodeError, ValueError) as exc:
            raise GitHubExternalServiceError(
                "GitHub returned an invalid response"
            ) from exc
        if not isinstance(body, dict):
            raise GitHubExternalServiceError(
                "GitHub returned an invalid response"
            )
        return body
