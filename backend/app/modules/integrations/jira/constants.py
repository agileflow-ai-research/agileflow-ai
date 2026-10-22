"""Constants for Jira Cloud OAuth 2.0 (3LO) integration."""

ATLASSIAN_AUTHORIZE_URL = "https://auth.atlassian.com/authorize"
ATLASSIAN_TOKEN_URL = "https://auth.atlassian.com/oauth/token"
ATLASSIAN_AUDIENCE = "api.atlassian.com"

# Configured Jira OAuth 2.0 scopes (including offline_access for refresh-token support)
JIRA_SCOPES = (
    "read:jira-work",
    "write:jira-work",
    "read:board-scope:jira-software",
    "read:sprint:jira-software",
    "write:sprint:jira-software",
    "offline_access",
)

# Server-side OAuth state lifetime and capacity constraints
DEFAULT_STATE_TTL_SECONDS = 600  # 10 minutes
MAX_PENDING_STATES = 1000
