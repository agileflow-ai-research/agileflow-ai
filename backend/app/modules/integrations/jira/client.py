"""Reusable authenticated Jira Cloud API client.

Encapsulates OAuth access token resolution, Bearer authentication,
URL validation, bounded retries on 401, error normalization, and
the accessible-resources primitive.
"""

import json
from typing import Any
import httpx

from app.modules.integrations.jira.constants import (
    ATLASSIAN_ACCESSIBLE_RESOURCES_URL,
    ATLASSIAN_API_BASE_URL,
    DEFAULT_JIRA_HTTP_TIMEOUT_SECONDS,
)
from app.modules.integrations.jira.schemas import AtlassianAccessibleResource
from app.modules.integrations.jira.service import (
    JiraAuthenticationError,
    JiraMalformedResponseError,
    JiraNetworkError,
    JiraNetworkTimeoutError,
    JiraOAuthService,
    JiraPermissionError,
    JiraRateLimitError,
    JiraRemoteApiError,
    JiraResourceNotFoundError,
)


class JiraApiClient:
    """Reusable authenticated client for Atlassian and Jira Cloud REST APIs.

    Guarantees:
    - Never logs access tokens, refresh tokens, or client secrets.
    - Resolves and injects valid access tokens transparently.
    - Anchors strictly to https://api.atlassian.com URLs.
    - Bounded single-retry on 401 with token refresh.
    - Normalizes Atlassian error responses into typed exceptions.
    """

    def __init__(
        self,
        service: JiraOAuthService,
        http_client: httpx.Client | None = None,
        timeout_seconds: float = DEFAULT_JIRA_HTTP_TIMEOUT_SECONDS,
    ) -> None:
        self._service = service
        self._client = http_client
        self._timeout_seconds = timeout_seconds

    def _validate_url(self, url: str) -> None:
        """Enforce that API calls strictly target the official api.atlassian.com domain."""
        if not url.startswith(ATLASSIAN_API_BASE_URL):
            raise ValueError(
                f"Jira API requests must target {ATLASSIAN_API_BASE_URL}, got: {url}"
            )

    def request(
        self,
        user_id: str,
        method: str,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        json_data: Any = None,
        headers: dict[str, str] | None = None,
    ) -> Any:
        """Execute an authenticated HTTP request to an Atlassian API endpoint.

        Performs bounded retry (max 1 retry) on 401 by force-refreshing the OAuth token.
        """
        self._validate_url(url)

        token = self._service.get_valid_access_token(user_id)
        response = self._execute_http(
            method=method,
            url=url,
            token=token,
            params=params,
            json_data=json_data,
            extra_headers=headers,
        )

        if response.status_code == 401:
            # Token may have been invalidated upstream; attempt one token refresh and retry
            new_token = self._service.get_valid_access_token(
                user_id, force_refresh=True
            )
            response = self._execute_http(
                method=method,
                url=url,
                token=new_token,
                params=params,
                json_data=json_data,
                extra_headers=headers,
            )
            if response.status_code == 401:
                self._service.mark_reauthorization_required(
                    user_id, "Atlassian API rejected token with 401 after refresh"
                )
                raise JiraAuthenticationError(
                    "Atlassian API authentication failed after token refresh"
                )

        return self._handle_response(response)

    def get_accessible_resources(
        self, user_id: str
    ) -> list[AtlassianAccessibleResource]:
        """Fetch accessible Atlassian Cloud sites/resources for the authenticated user.

        Endpoint: GET https://api.atlassian.com/oauth/token/accessible-resources
        Returns a normalized list of AtlassianAccessibleResource.
        Does NOT assume the first resource is the desired Jira site.
        """
        data = self.request(
            user_id=user_id,
            method="GET",
            url=ATLASSIAN_ACCESSIBLE_RESOURCES_URL,
        )
        if not isinstance(data, list):
            raise JiraMalformedResponseError(
                "Expected list of accessible resources from Atlassian"
            )

        resources: list[AtlassianAccessibleResource] = []
        for item in data:
            if isinstance(item, dict) and "id" in item and "name" in item and "url" in item:
                resources.append(
                    AtlassianAccessibleResource(
                        id=str(item["id"]),
                        name=str(item["name"]),
                        url=str(item["url"]),
                        scopes=[str(s) for s in item.get("scopes", [])],
                        avatar_url=str(item["avatarUrl"]) if item.get("avatarUrl") else None,
                    )
                )

        return resources

    def _execute_http(
        self,
        *,
        method: str,
        url: str,
        token: str,
        params: dict[str, Any] | None,
        json_data: Any,
        extra_headers: dict[str, str] | None,
    ) -> httpx.Response:
        req_headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
        }
        if json_data is not None:
            req_headers["Content-Type"] = "application/json"
        if extra_headers:
            req_headers.update(extra_headers)

        try:
            if self._client is not None:
                return self._client.request(
                    method=method,
                    url=url,
                    params=params,
                    json=json_data,
                    headers=req_headers,
                    timeout=self._timeout_seconds,
                )
            return httpx.request(
                method=method,
                url=url,
                params=params,
                json=json_data,
                headers=req_headers,
                timeout=self._timeout_seconds,
            )
        except httpx.TimeoutException as exc:
            raise JiraNetworkTimeoutError(
                "Atlassian API request timed out"
            ) from exc
        except httpx.HTTPError as exc:
            raise JiraNetworkError(
                "Network error connecting to Atlassian API"
            ) from exc

    def _handle_response(self, response: httpx.Response) -> Any:
        if response.status_code == 403:
            raise JiraPermissionError(
                "Insufficient permissions for requested Atlassian resource"
            )
        if response.status_code == 404:
            raise JiraResourceNotFoundError(
                "Requested Atlassian resource was not found"
            )
        if response.status_code == 429:
            raise JiraRateLimitError(
                "Atlassian API rate limit exceeded"
            )
        if response.status_code >= 400:
            raise JiraRemoteApiError(
                f"Atlassian API returned HTTP {response.status_code}"
            )

        if response.status_code == 204 or not response.content:
            return None

        try:
            return response.json()
        except (json.JSONDecodeError, ValueError) as exc:
            raise JiraMalformedResponseError(
                "Atlassian API returned invalid JSON response"
            ) from exc
