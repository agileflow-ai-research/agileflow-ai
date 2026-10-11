from typing import Any

from pymongo import ReturnDocument
from pymongo.database import Database
from pymongo.errors import PyMongoError

from app.common.id_generator import validate_id
from app.database.collections import PROJECTS
from app.database.mongodb import get_database
from app.schemas.project import Project


class ProjectRepositoryError(RuntimeError):
    """Raised when project persistence cannot be completed."""


class ProjectRepository:
    """MongoDB persistence operations for projects only."""

    def __init__(self, database: Database[dict[str, Any]] | None = None) -> None:
        configured_database = database if database is not None else get_database()
        self._collection = configured_database[PROJECTS]

    @staticmethod
    def _public_document(document: dict[str, Any]) -> dict[str, Any]:
        return {key: value for key, value in document.items() if key != "_id"}

    def next_project_sequence(self) -> int:
        """Return one greater than the largest valid persisted PRJ sequence."""
        try:
            largest_sequence = 0
            for document in self._collection.find({}, {"project_id": 1, "_id": 0}):
                project_id = document.get("project_id")
                if not isinstance(project_id, str):
                    continue
                try:
                    validate_id(project_id, "PRJ")
                except ValueError:
                    continue
                largest_sequence = max(
                    largest_sequence,
                    int(project_id.rsplit("-", maxsplit=1)[1]),
                )
            return largest_sequence + 1
        except PyMongoError as exc:
            raise ProjectRepositoryError("Could not allocate a project ID") from exc

    def create_project(self, project: Project) -> dict[str, Any]:
        document = project.model_dump(mode="python")
        try:
            self._collection.insert_one(document.copy())
        except PyMongoError as exc:
            raise ProjectRepositoryError("Could not create project") from exc
        return self._public_document(document)

    def list_projects(self) -> list[dict[str, Any]]:
        try:
            documents = self._collection.find({}, {"_id": 0})
            return [self._public_document(document) for document in documents]
        except PyMongoError as exc:
            raise ProjectRepositoryError("Could not list projects") from exc

    def get_project(self, project_id: str) -> dict[str, Any] | None:
        try:
            document = self._collection.find_one(
                {"project_id": project_id},
                {"_id": 0},
            )
        except PyMongoError as exc:
            raise ProjectRepositoryError("Could not get project") from exc
        return self._public_document(document) if document is not None else None

    def update_project(
        self,
        project_id: str,
        updates: dict[str, Any],
    ) -> dict[str, Any] | None:
        try:
            document = self._collection.find_one_and_update(
                {"project_id": project_id},
                {"$set": updates},
                projection={"_id": 0},
                return_document=ReturnDocument.AFTER,
            )
        except PyMongoError as exc:
            raise ProjectRepositoryError("Could not update project") from exc
        return self._public_document(document) if document is not None else None
