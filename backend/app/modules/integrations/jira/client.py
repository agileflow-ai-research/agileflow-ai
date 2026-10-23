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
    build_jira_cloud_url,
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

    def search_projects(
        self,
        user_id: str,
        cloud_id: str,
        start_at: int = 0,
        max_results: int = 50,
    ) -> dict[str, Any]:
        """Search projects accessible on the selected Jira Cloud site using Platform REST v3.

        Filters/prefers Jira Software projects via typeKey=software.
        """
        url = build_jira_cloud_url(cloud_id, "rest/api/3/project/search")
        data = self.request(
            user_id=user_id,
            method="GET",
            url=url,
            params={
                "startAt": start_at,
                "maxResults": max_results,
                "typeKey": "software",
            },
        )
        if not isinstance(data, dict):
            raise JiraMalformedResponseError(
                "Expected dict response for Jira project search"
            )
        return data

    def get_project(
        self, user_id: str, cloud_id: str, project_id_or_key: str
    ) -> dict[str, Any]:
        """Fetch details for a single project on the selected Jira Cloud site."""
        url = build_jira_cloud_url(
            cloud_id, f"rest/api/3/project/{project_id_or_key}"
        )
        data = self.request(user_id=user_id, method="GET", url=url)
        if not isinstance(data, dict):
            raise JiraMalformedResponseError(
                "Expected dict response for Jira project details"
            )
        return data

    def get_project_issue_types(
        self, user_id: str, cloud_id: str, project_id_or_key: str
    ) -> list[dict[str, Any]]:
        """Fetch issue types available for a project on Jira Cloud."""
        url = build_jira_cloud_url(
            cloud_id, f"rest/api/3/issue/createmeta/{project_id_or_key}/issuetypes"
        )
        try:
            data = self.request(user_id=user_id, method="GET", url=url)
            if isinstance(data, dict):
                if "values" in data and isinstance(data["values"], list):
                    return data["values"]
                if "issueTypes" in data and isinstance(data["issueTypes"], list):
                    return data["issueTypes"]
            if isinstance(data, list):
                return data
        except Exception:
            pass

        # Fallback to get_project issueTypes
        project_data = self.get_project(user_id, cloud_id, project_id_or_key)
        raw_types = project_data.get("issueTypes")
        if isinstance(raw_types, list):
            return raw_types
        return []

    def get_scrum_boards(
        self,
        user_id: str,
        cloud_id: str,
        project_key_or_id: str,
        start_at: int = 0,
        max_results: int = 50,
    ) -> dict[str, Any]:
        """Query Scrum boards for the selected project using Jira Software Agile REST API."""
        url = build_jira_cloud_url(cloud_id, "rest/agile/1.0/board")
        data = self.request(
            user_id=user_id,
            method="GET",
            url=url,
            params={
                "type": "scrum",
                "projectKeyOrId": project_key_or_id,
                "startAt": start_at,
                "maxResults": max_results,
            },
        )
        if not isinstance(data, dict):
            raise JiraMalformedResponseError(
                "Expected dict response for Jira Scrum boards"
            )
        return data

    def get_board(
        self, user_id: str, cloud_id: str, board_id: int
    ) -> dict[str, Any]:
        """Fetch details for a single board using Jira Software Agile REST API."""
        url = build_jira_cloud_url(cloud_id, f"rest/agile/1.0/board/{board_id}")
        data = self.request(user_id=user_id, method="GET", url=url)
        if not isinstance(data, dict):
            raise JiraMalformedResponseError(
                "Expected dict response for Jira board details"
            )
        return data

    def create_sprint(
        self,
        user_id: str,
        cloud_id: str,
        origin_board_id: int,
        name: str,
        *,
        start_date: str | None = None,
        end_date: str | None = None,
        goal: str | None = None,
    ) -> dict[str, Any]:
        """Create a sprint on a Jira Scrum board.

        Endpoint: POST https://api.atlassian.com/ex/jira/{cloud_id}/rest/agile/1.0/sprint
        """
        url = build_jira_cloud_url(cloud_id, "rest/agile/1.0/sprint")
        payload: dict[str, Any] = {
            "name": name,
            "originBoardId": origin_board_id,
        }
        if start_date:
            payload["startDate"] = f"{start_date}T00:00:00.000Z" if len(start_date) == 10 else start_date
        if end_date:
            payload["endDate"] = f"{end_date}T00:00:00.000Z" if len(end_date) == 10 else end_date
        if goal:
            payload["goal"] = goal

        data = self.request(user_id=user_id, method="POST", url=url, json_data=payload)
        if not isinstance(data, dict):
            raise JiraMalformedResponseError("Expected dict response for created Jira sprint")
        return data

    def create_issue(
        self,
        user_id: str,
        cloud_id: str,
        project_key: str,
        issue_type_name: str,
        summary: str,
        *,
        description: str | None = None,
        parent_key_or_id: str | None = None,
    ) -> dict[str, Any]:
        """Create an unassigned issue in Jira Cloud v3.

        Endpoint: POST https://api.atlassian.com/ex/jira/{cloud_id}/rest/api/3/issue
        Guarantees: Assignee is strictly NOT set (remains Unassigned).
        """
        url = build_jira_cloud_url(cloud_id, "rest/api/3/issue")
        fields: dict[str, Any] = {
            "project": {"key": project_key},
            "issuetype": {"name": issue_type_name},
            "summary": summary,
        }
        if description:
            fields["description"] = {
                "version": 1,
                "type": "doc",
                "content": [
                    {
                        "type": "paragraph",
                        "content": [{"type": "text", "text": description}],
                    }
                ],
            }
        if parent_key_or_id:
            fields["parent"] = (
                {"id": parent_key_or_id}
                if parent_key_or_id.isdigit()
                else {"key": parent_key_or_id}
            )

        data = self.request(
            user_id=user_id, method="POST", url=url, json_data={"fields": fields}
        )
        if not isinstance(data, dict):
            raise JiraMalformedResponseError("Expected dict response for created Jira issue")
        return data

    def add_issues_to_sprint(
        self,
        user_id: str,
        cloud_id: str,
        sprint_id: int,
        issue_keys: list[str],
    ) -> None:
        """Place planned Jira issues into a sprint.

        Endpoint: POST https://api.atlassian.com/ex/jira/{cloud_id}/rest/agile/1.0/sprint/{sprint_id}/issue
        """
        if not issue_keys:
            return
        url = build_jira_cloud_url(cloud_id, f"rest/agile/1.0/sprint/{sprint_id}/issue")
        self.request(
            user_id=user_id, method="POST", url=url, json_data={"issues": issue_keys}
        )

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
