"""Persistence layer for Jira Cloud OAuth 2.0 connections.

SECURITY NOTICE & AT-REST LIMITATION:
This repository encapsulates all database operations for Jira OAuth tokens.
The current application foundation does not include an enterprise token
encryption / key-management facility (e.g., KMS, Vault, envelope encryption).
In adherence to repository security rules, we do NOT invent custom weak encryption.
Instead, all token persistence is isolated strictly behind this abstraction,
sensitive tokens are never exposed across API or logging surfaces, and proper
at-rest envelope encryption remains an explicit external production requirement.
"""

from datetime import datetime, timezone
from typing import Any

from pymongo import ReturnDocument
from pymongo.database import Database
from pymongo.errors import PyMongoError

from app.database.collections import JIRA_CONNECTIONS
from app.database.mongodb import get_database
from app.modules.integrations.jira.schemas import JiraConnectionDocument


class JiraConnectionRepositoryError(RuntimeError):
    """Raised when Jira connection persistence operations fail."""


def _clean_document(document: dict[str, Any]) -> dict[str, Any]:
    """Strip MongoDB _id and ensure UTC timezones on datetime values."""
    result = {key: value for key, value in document.items() if key != "_id"}
    for key, value in result.items():
        if isinstance(value, datetime) and value.tzinfo is None:
            result[key] = value.replace(tzinfo=timezone.utc)
    return result


class JiraConnectionRepository:
    """Repository handling persistence of Jira Cloud OAuth connections."""

    def __init__(
        self,
        database: Database[dict[str, Any]] | None = None,
    ) -> None:
        configured_database = database if database is not None else get_database()
        self._collection = configured_database[JIRA_CONNECTIONS]

    def find_by_owner(self, owner_id: str) -> dict[str, Any] | None:
        """Find the Jira connection belonging to an authenticated owner."""
        try:
            document = self._collection.find_one(
                {"owner_id": owner_id, "provider": "JIRA"},
                {"_id": 0},
            )
        except PyMongoError as exc:
            raise JiraConnectionRepositoryError(
                "Could not retrieve Jira connection from database"
            ) from exc
        return _clean_document(document) if document is not None else None

    def upsert(self, connection: JiraConnectionDocument) -> dict[str, Any]:
        """Insert or update a Jira connection for the authenticated owner."""
        document = connection.model_dump(mode="python")
        try:
            persisted = self._collection.find_one_and_update(
                {"owner_id": connection.owner_id, "provider": "JIRA"},
                {"$set": document},
                upsert=True,
                projection={"_id": 0},
                return_document=ReturnDocument.AFTER,
            )
        except PyMongoError as exc:
            raise JiraConnectionRepositoryError(
                "Could not persist Jira connection"
            ) from exc
        return _clean_document(persisted or document)

    def update_tokens_atomic(
        self,
        owner_id: str,
        expected_refresh_token: str,
        new_access_token: str,
        new_refresh_token: str | None,
        expires_at: datetime,
        now: datetime,
    ) -> dict[str, Any] | None:
        """Atomically rotate Jira OAuth tokens conditioned on the expected refresh token.

        Guarantees concurrency safety by verifying the expected refresh token matches,
        preventing race conditions where concurrent calls overwrite newer rotated tokens.
        """
        filter_query: dict[str, Any] = {
            "owner_id": owner_id,
            "provider": "JIRA",
            "refresh_token": expected_refresh_token,
        }
        set_fields: dict[str, Any] = {
            "access_token": new_access_token,
            "expires_at": expires_at,
            "updated_at": now,
            "status": "CONNECTED",
            "reauthorization_reason": None,
        }
        if new_refresh_token is not None:
            set_fields["refresh_token"] = new_refresh_token

        update_query: dict[str, Any] = {
            "$set": set_fields,
            "$inc": {"version": 1},
        }

        try:
            persisted = self._collection.find_one_and_update(
                filter_query,
                update_query,
                projection={"_id": 0},
                return_document=ReturnDocument.AFTER,
            )
        except PyMongoError as exc:
            raise JiraConnectionRepositoryError(
                "Could not atomically update rotated Jira tokens"
            ) from exc

        return _clean_document(persisted) if persisted is not None else None

    def mark_reauthorization_required(
        self,
        owner_id: str,
        reason: str = "Jira authorization expired or revoked; reauthorization required",
    ) -> dict[str, Any] | None:
        """Mark a Jira connection as requiring reauthorization without deleting it.

        Ensures failed authentication does not corrupt or delete Agent 2 run data.
        """
        try:
            persisted = self._collection.find_one_and_update(
                {"owner_id": owner_id, "provider": "JIRA"},
                {
                    "$set": {
                        "status": "REAUTHORIZATION_REQUIRED",
                        "reauthorization_reason": reason,
                        "updated_at": datetime.now(timezone.utc),
                    }
                },
                projection={"_id": 0},
                return_document=ReturnDocument.AFTER,
            )
        except PyMongoError as exc:
            raise JiraConnectionRepositoryError(
                "Could not update Jira connection status to reauthorization required"
            ) from exc

        return _clean_document(persisted) if persisted is not None else None

    def delete_by_owner(self, owner_id: str) -> bool:
        """Remove a Jira connection for the authenticated owner.

        Disconnect currently removes the AgileFlow-side connection and stored tokens.
        """
        try:
            result = self._collection.delete_one(
                {"owner_id": owner_id, "provider": "JIRA"}
            )
            return result.deleted_count > 0
        except PyMongoError as exc:
            raise JiraConnectionRepositoryError(
                "Could not delete Jira connection"
            ) from exc
