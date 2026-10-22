"""Constants for Jira Cloud OAuth 2.0 (3LO) integration."""

ATLASSIAN_AUTHORIZE_URL = "https://auth.atlassian.com/authorize"
ATLASSIAN_TOKEN_URL = "https://auth.atlassian.com/oauth/token"
ATLASSIAN_AUDIENCE = "api.atlassian.com"
ATLASSIAN_API_BASE_URL = "https://api.atlassian.com"
ATLASSIAN_ACCESSIBLE_RESOURCES_URL = (
    "https://api.atlassian.com/oauth/token/accessible-resources"
)

# Configured Jira OAuth 2.0 scopes (including offline_access for refresh-token support)
JIRA_SCOPES = (
    "read:jira-work",
    "write:jira-work",
    "read:project:jira",
    "read:board-scope:jira-software",
    "read:sprint:jira-software",
    "write:sprint:jira-software",
    "offline_access",
)

# Server-side OAuth state lifetime and capacity constraints
DEFAULT_STATE_TTL_SECONDS = 600  # 10 minutes
MAX_PENDING_STATES = 1000

# Refresh token safety margin (5 minutes before expiry to prevent mid-flight expiration)
REFRESH_SAFETY_MARGIN_SECONDS = 300
DEFAULT_JIRA_HTTP_TIMEOUT_SECONDS = 10.0


def build_atlassian_api_url(path: str) -> str:
    """Build an official Atlassian OAuth / resource API URL.

    Strictly anchors to https://api.atlassian.com/...
    """
    clean_path = path.lstrip("/")
    return f"{ATLASSIAN_API_BASE_URL}/{clean_path}"


def build_jira_cloud_url(cloud_id: str, path: str) -> str:
    """Build an official site-specific Jira Cloud API URL.

    Formula: https://api.atlassian.com/ex/jira/{cloudId}/...
    Does NOT accept arbitrary domains or foreign base URLs.
    """
    clean_cloud_id = cloud_id.strip("/")
    clean_path = path.lstrip("/")
    return f"{ATLASSIAN_API_BASE_URL}/ex/jira/{clean_cloud_id}/{clean_path}"
