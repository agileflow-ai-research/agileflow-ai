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

from app.database.collections import JIRA_CONNECTIONS, JIRA_SYNCS
from app.database.mongodb import get_database
from app.modules.integrations.jira.schemas import (
    JiraConnectionDocument,
    JiraSelectedBoard,
    JiraSelectedProject,
    JiraSelectedSite,
    JiraSyncDocument,
)


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
        if new_refresh_token is not None and isinstance(new_refresh_token, str) and new_refresh_token.strip():
            set_fields["refresh_token"] = new_refresh_token.strip()

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

    def update_selected_site(
        self, owner_id: str, site: JiraSelectedSite
    ) -> dict[str, Any] | None:
        """Update selected Jira site.

        If the selected cloud_id is changing, clear any previously selected project and board.
        """
        existing = self.find_by_owner(owner_id)
        if not existing:
            return None

        current_site = existing.get("selected_site")
        is_changing_site = not current_site or current_site.get("cloud_id") != site.cloud_id

        update_fields: dict[str, Any] = {
            "selected_site": site.model_dump(mode="python"),
            "updated_at": datetime.now(timezone.utc),
        }
        if is_changing_site:
            update_fields["selected_project"] = None
            update_fields["selected_board"] = None

        try:
            persisted = self._collection.find_one_and_update(
                {"owner_id": owner_id, "provider": "JIRA"},
                {"$set": update_fields},
                projection={"_id": 0},
                return_document=ReturnDocument.AFTER,
            )
        except PyMongoError as exc:
            raise JiraConnectionRepositoryError(
                "Could not persist selected Jira site"
            ) from exc

        return _clean_document(persisted) if persisted is not None else None

    def update_selected_project(
        self, owner_id: str, project: JiraSelectedProject
    ) -> dict[str, Any] | None:
        """Update selected Jira project.

        If the selected project is changing, clear any previously selected board.
        """
        existing = self.find_by_owner(owner_id)
        if not existing:
            return None

        current_project = existing.get("selected_project")
        is_changing_project = (
            not current_project
            or current_project.get("project_id") != project.project_id
            or current_project.get("project_key") != project.project_key
        )

        update_fields: dict[str, Any] = {
            "selected_project": project.model_dump(mode="python"),
            "updated_at": datetime.now(timezone.utc),
        }
        if is_changing_project:
            update_fields["selected_board"] = None

        try:
            persisted = self._collection.find_one_and_update(
                {"owner_id": owner_id, "provider": "JIRA"},
                {"$set": update_fields},
                projection={"_id": 0},
                return_document=ReturnDocument.AFTER,
            )
        except PyMongoError as exc:
            raise JiraConnectionRepositoryError(
                "Could not persist selected Jira project"
            ) from exc

        return _clean_document(persisted) if persisted is not None else None

    def update_selected_board(
        self, owner_id: str, board: JiraSelectedBoard
    ) -> dict[str, Any] | None:
        """Update selected Scrum board."""
        try:
            persisted = self._collection.find_one_and_update(
                {"owner_id": owner_id, "provider": "JIRA"},
                {
                    "$set": {
                        "selected_board": board.model_dump(mode="python"),
                        "updated_at": datetime.now(timezone.utc),
                    }
                },
                projection={"_id": 0},
                return_document=ReturnDocument.AFTER,
            )
        except PyMongoError as exc:
            raise JiraConnectionRepositoryError(
                "Could not persist selected Jira board"
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


class JiraSyncRepositoryError(RuntimeError):
    """Raised when Jira sync persistence operations fail."""


class JiraSyncRepository:
    """Repository handling persistence of Jira synchronization records and traceability."""

    def __init__(
        self,
        database: Database[dict[str, Any]] | None = None,
    ) -> None:
        configured_database = database if database is not None else get_database()
        self._collection = configured_database[JIRA_SYNCS]

    def find_by_sync_id(self, sync_id: str) -> dict[str, Any] | None:
        """Find a synchronization record by its unique sync_id."""
        try:
            document = self._collection.find_one({"sync_id": sync_id}, {"_id": 0})
        except PyMongoError as exc:
            raise JiraSyncRepositoryError(
                "Could not retrieve Jira sync record by sync_id"
            ) from exc
        return _clean_document(document) if document is not None else None

    def find_latest_by_run(
        self, agent_project_id: str, run_id: str
    ) -> dict[str, Any] | None:
        """Find the most recent synchronization record for an approved run."""
        try:
            cursor = (
                self._collection.find(
                    {"agent_project_id": agent_project_id, "run_id": run_id},
                    {"_id": 0},
                )
                .sort("created_at", -1)
                .limit(1)
            )
            docs = list(cursor)
            document = docs[0] if docs else None
        except PyMongoError as exc:
            raise JiraSyncRepositoryError(
                "Could not retrieve latest Jira sync record for run"
            ) from exc
        return _clean_document(document) if document is not None else None

    def find_active_by_run(
        self, agent_project_id: str, run_id: str
    ) -> dict[str, Any] | None:
        """Find an in-progress synchronization record for this run to prevent concurrent executions."""
        try:
            document = self._collection.find_one(
                {
                    "agent_project_id": agent_project_id,
                    "run_id": run_id,
                    "status": "IN_PROGRESS",
                },
                {"_id": 0},
            )
        except PyMongoError as exc:
            raise JiraSyncRepositoryError(
                "Could not check for active Jira synchronization"
            ) from exc
        return _clean_document(document) if document is not None else None

    def upsert(self, sync_doc: JiraSyncDocument) -> dict[str, Any]:
        """Insert or update a Jira synchronization record."""
        document = sync_doc.model_dump(mode="python")
        try:
            persisted = self._collection.find_one_and_update(
                {"sync_id": sync_doc.sync_id},
                {"$set": document},
                upsert=True,
                projection={"_id": 0},
                return_document=ReturnDocument.AFTER,
            )
        except PyMongoError as exc:
            raise JiraSyncRepositoryError(
                "Could not persist Jira sync record"
            ) from exc
        return _clean_document(persisted or document)
