from datetime import datetime, timezone
from typing import Any

from pymongo.database import Database
from pymongo.errors import PyMongoError

from app.common.id_generator import validate_id
from app.database.mongodb import get_database
from app.modules.agent1.schemas import RequirementSourceRecord, SourceProcessingStatus

REQUIREMENT_SOURCES = "requirement_sources"


class RequirementSourceRepositoryError(RuntimeError):
    """Raised when RequirementSource persistence cannot be completed."""


def _public_document(document: dict[str, Any]) -> dict[str, Any]:
    public_document = {
        key: value for key, value in document.items() if key != "_id"
    }
    for key, value in public_document.items():
        if isinstance(value, datetime) and value.tzinfo is None:
            public_document[key] = value.replace(tzinfo=timezone.utc)
    return public_document


class RequirementSourceRepository:
    """MongoDB persistence for project-associated requirement input sources."""

    def __init__(
        self,
        database: Database[dict[str, Any]] | None = None,
    ) -> None:
        configured_database = database if database is not None else get_database()
        self._collection = configured_database[REQUIREMENT_SOURCES]

    def next_source_sequence(self, agent_project_id: str, prefix: str) -> int:
        """Allocate next sequence number for a given prefix in an agent project."""
        try:
            largest_sequence = 0
            for document in self._collection.find(
                {"agent_project_id": agent_project_id},
                {"source_id": 1, "_id": 0},
            ):
                source_id = document.get("source_id")
                if not isinstance(source_id, str):
                    continue
                if not source_id.startswith(f"{prefix}-"):
                    continue
                try:
                    validate_id(source_id, prefix)
                except ValueError:
                    continue
                sequence_part = source_id.rsplit("-", maxsplit=1)[1]
                largest_sequence = max(largest_sequence, int(sequence_part))
            return largest_sequence + 1
        except PyMongoError as exc:
            raise RequirementSourceRepositoryError(
                "Could not allocate requirement source ID"
            ) from exc

    def create_source(self, source: RequirementSourceRecord) -> dict[str, Any]:
        document = source.model_dump(mode="python")
        try:
            self._collection.insert_one(document.copy())
        except PyMongoError as exc:
            raise RequirementSourceRepositoryError(
                "Could not save requirement source"
            ) from exc
        return _public_document(document)

    def list_sources(
        self,
        agent_project_id: str,
        owner_user_id: str,
    ) -> list[dict[str, Any]]:
        query: dict[str, Any] = {
            "agent_project_id": agent_project_id,
            "owner_user_id": owner_user_id,
            "is_deleted": {"$ne": True},
        }
        try:
            documents = self._collection.find(query, {"_id": 0}).sort(
                [("created_at", 1), ("source_id", 1)]
            )
            return [_public_document(doc) for doc in documents]
        except PyMongoError as exc:
            raise RequirementSourceRepositoryError(
                "Could not list requirement sources"
            ) from exc

    def get_source(
        self,
        agent_project_id: str,
        source_id: str,
        owner_user_id: str,
    ) -> dict[str, Any] | None:
        try:
            document = self._collection.find_one(
                {
                    "agent_project_id": agent_project_id,
                    "source_id": source_id,
                    "owner_user_id": owner_user_id,
                    "is_deleted": {"$ne": True},
                },
                {"_id": 0},
            )
        except PyMongoError as exc:
            raise RequirementSourceRepositoryError(
                "Could not retrieve requirement source"
            ) from exc
        return _public_document(document) if document is not None else None

    def delete_source(
        self,
        agent_project_id: str,
        source_id: str,
        owner_user_id: str,
    ) -> bool:
        try:
            result = self._collection.update_one(
                {
                    "agent_project_id": agent_project_id,
                    "source_id": source_id,
                    "owner_user_id": owner_user_id,
                    "is_deleted": {"$ne": True},
                },
                {"$set": {"is_deleted": True, "updated_at": datetime.now(timezone.utc)}},
            )
            return result.modified_count > 0
        except PyMongoError as exc:
            raise RequirementSourceRepositoryError(
                "Could not delete requirement source"
            ) from exc

    def update_source_processing(
        self,
        agent_project_id: str,
        source_id: str,
        owner_user_id: str,
        processing_status: SourceProcessingStatus,
        normalized_text: str | None = None,
        processing_error_code: str | None = None,
        processing_error_message: str | None = None,
        processed_at: datetime | None = None,
        clear_result: bool = False,
    ) -> bool:
        """Persist one safe source-processing transition."""
        update_fields: dict[str, Any] = {
            "processing_status": processing_status.value,
            "updated_at": datetime.now(timezone.utc),
        }
        unset_fields: dict[str, str] = {}
        if clear_result:
            unset_fields = {
                "normalized_text": "",
                "processing_error_code": "",
                "processing_error_message": "",
                "processed_at": "",
            }
        if normalized_text is not None:
            update_fields["normalized_text"] = normalized_text
        if processing_error_code is not None:
            update_fields["processing_error_code"] = processing_error_code
        if processing_error_message is not None:
            update_fields["processing_error_message"] = processing_error_message
        if processed_at is not None:
            update_fields["processed_at"] = processed_at
        update: dict[str, Any] = {"$set": update_fields}
        if unset_fields:
            update["$unset"] = unset_fields
        try:
            result = self._collection.update_one(
                {
                    "agent_project_id": agent_project_id,
                    "source_id": source_id,
                    "owner_user_id": owner_user_id,
                    "is_deleted": {"$ne": True},
                },
                update,
            )
            return result.modified_count > 0
        except PyMongoError as exc:
            raise RequirementSourceRepositoryError(
                "Could not update requirement source processing result"
            ) from exc

    def list_sources_for_run(
        self,
        agent_project_id: str,
        owner_user_id: str,
    ) -> list[dict[str, Any]]:
        """List non-deleted sources for an agent run (includes storage_path)."""
        query: dict[str, Any] = {
            "agent_project_id": agent_project_id,
            "owner_user_id": owner_user_id,
            "is_deleted": {"$ne": True},
        }
        try:
            documents = self._collection.find(query, {"_id": 0}).sort(
                [("created_at", 1), ("source_id", 1)]
            )
            return [_public_document(doc) for doc in documents]
        except PyMongoError as exc:
            raise RequirementSourceRepositoryError(
                "Could not list requirement sources for run"
            ) from exc
