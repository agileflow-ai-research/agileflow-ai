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
