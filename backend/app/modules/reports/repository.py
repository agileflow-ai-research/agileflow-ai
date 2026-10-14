from typing import Any

from pydantic import ValidationError
from pymongo.database import Database
from pymongo.errors import PyMongoError

from app.common.id_generator import validate_id
from app.common.traceability import TraceabilityRelationType
from app.database.collections import TRACEABILITY_LINKS
from app.database.mongodb import get_database
from app.schemas.traceability import TraceabilityLink


class TraceabilityRepositoryError(RuntimeError):
    """Raised when traceability persistence cannot be completed safely."""


class InvalidTraceabilityDocumentError(TraceabilityRepositoryError):
    """Raised when stored traceability data violates the canonical schema."""


class TraceabilityRepository:
    """Immutable, project-scoped access to pairwise traceability links."""

    def __init__(self, database: Database[dict[str, Any]] | None = None) -> None:
        configured_database = database if database is not None else get_database()
        self._links = configured_database[TRACEABILITY_LINKS]

    @staticmethod
    def _public_document(document: dict[str, Any]) -> dict[str, Any]:
        return {key: value for key, value in document.items() if key != "_id"}

    @classmethod
    def _deserialize(cls, document: dict[str, Any]) -> TraceabilityLink:
        try:
            return TraceabilityLink.model_validate(cls._public_document(document))
        except ValidationError as exc:
            raise InvalidTraceabilityDocumentError(
                "Invalid persisted traceability link"
            ) from exc

    def next_trace_sequence(self, project_id: str) -> int:
        """Return the next global TRACE sequence using the established max scan."""
        validate_id(project_id, "PRJ")
        try:
            largest_sequence = 0
            for document in self._links.find({}, {"trace_id": 1, "_id": 0}):
                trace_id = document.get("trace_id")
                if not isinstance(trace_id, str):
                    continue
                try:
                    validate_id(trace_id, "TRACE")
                except ValueError:
                    continue
                largest_sequence = max(
                    largest_sequence,
                    int(trace_id.rsplit("-", maxsplit=1)[1]),
                )
            return largest_sequence + 1
        except PyMongoError as exc:
            raise TraceabilityRepositoryError(
                "Could not allocate a traceability ID"
            ) from exc

    def create_link(
        self,
        project_id: str,
        link: TraceabilityLink,
    ) -> TraceabilityLink:
        if link.project_id != project_id:
            raise ValueError("Traceability write must match project_id")
        existing = self.find_exact_edge(
            project_id=project_id,
            source_artifact_id=link.source_artifact_id,
            target_artifact_id=link.target_artifact_id,
            relation_type=link.relation_type,
        )
        if existing is not None:
            return existing
        document = link.model_dump(mode="python")
        try:
            self._links.insert_one(document.copy())
        except PyMongoError as exc:
            raise TraceabilityRepositoryError(
                "Could not persist traceability link"
            ) from exc
        return self._deserialize(document)

    def find_link_by_id(
        self,
        project_id: str,
        trace_id: str,
    ) -> TraceabilityLink | None:
        try:
            document = self._links.find_one(
                {"project_id": project_id, "trace_id": trace_id},
                {"_id": 0},
            )
        except PyMongoError as exc:
            raise TraceabilityRepositoryError(
                "Could not retrieve traceability link"
            ) from exc
        return self._deserialize(document) if document is not None else None

    def find_exact_edge(
        self,
        project_id: str,
        source_artifact_id: str,
        target_artifact_id: str,
        relation_type: TraceabilityRelationType,
    ) -> TraceabilityLink | None:
        try:
            document = self._links.find_one(
                {
                    "project_id": project_id,
                    "source_artifact_id": source_artifact_id,
                    "target_artifact_id": target_artifact_id,
                    "relation_type": relation_type.value,
                },
                {"_id": 0},
            )
        except PyMongoError as exc:
            raise TraceabilityRepositoryError(
                "Could not retrieve exact traceability edge"
            ) from exc
        return self._deserialize(document) if document is not None else None

    def list_links(self, project_id: str) -> list[TraceabilityLink]:
        return self._list_by_query({"project_id": project_id})

    def list_outgoing_links(
        self,
        project_id: str,
        source_artifact_id: str,
    ) -> list[TraceabilityLink]:
        return self._list_by_query(
            {
                "project_id": project_id,
                "source_artifact_id": source_artifact_id,
            }
        )

    def list_incoming_links(
        self,
        project_id: str,
        target_artifact_id: str,
    ) -> list[TraceabilityLink]:
        return self._list_by_query(
            {
                "project_id": project_id,
                "target_artifact_id": target_artifact_id,
            }
        )

    def _list_by_query(self, query: dict[str, Any]) -> list[TraceabilityLink]:
        try:
            documents = self._links.find(query, {"_id": 0}).sort(
                [("created_at", 1), ("trace_id", 1)]
            )
            return [self._deserialize(document) for document in documents]
        except PyMongoError as exc:
            raise TraceabilityRepositoryError(
                "Could not list traceability links"
            ) from exc
