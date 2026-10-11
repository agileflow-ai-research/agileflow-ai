from typing import Any

from pymongo.database import Database
from pymongo.errors import PyMongoError

from app.common.id_generator import validate_id
from app.database.collections import USERS
from app.database.mongodb import get_database
from app.schemas.user import User


class UserRepositoryError(RuntimeError):
    """Raised when User persistence cannot be completed safely."""


class UserRepository:
    """MongoDB persistence operations for User registration."""

    def __init__(self, database: Database[dict[str, Any]] | None = None) -> None:
        configured_database = database if database is not None else get_database()
        self._collection = configured_database[USERS]

    @staticmethod
    def _document_without_mongodb_id(
        document: dict[str, Any],
    ) -> dict[str, Any]:
        return {key: value for key, value in document.items() if key != "_id"}

    def find_user_by_email(self, email: str) -> dict[str, Any] | None:
        try:
            document = self._collection.find_one(
                {"email": email},
                {"_id": 0},
            )
        except PyMongoError as exc:
            raise UserRepositoryError("Could not find user") from exc
        return (
            self._document_without_mongodb_id(document)
            if document is not None
            else None
        )

    def find_user_by_id(self, user_id: str) -> dict[str, Any] | None:
        try:
            document = self._collection.find_one(
                {"user_id": user_id},
                {"_id": 0},
            )
        except PyMongoError as exc:
            raise UserRepositoryError("Could not find user") from exc
        return (
            self._document_without_mongodb_id(document)
            if document is not None
            else None
        )

    def next_user_sequence(self) -> int:
        """Return one greater than the largest valid persisted USR sequence."""
        try:
            largest_sequence = 0
            for document in self._collection.find(
                {},
                {"user_id": 1, "_id": 0},
            ):
                user_id = document.get("user_id")
                if not isinstance(user_id, str):
                    continue
                try:
                    validate_id(user_id, "USR")
                except ValueError:
                    continue
                largest_sequence = max(
                    largest_sequence,
                    int(user_id.rsplit("-", maxsplit=1)[1]),
                )
            return largest_sequence + 1
        except PyMongoError as exc:
            raise UserRepositoryError("Could not allocate a user ID") from exc

    def create_user(self, user: User) -> dict[str, Any]:
        document = user.model_dump(mode="python")
        try:
            self._collection.insert_one(document.copy())
        except PyMongoError as exc:
            raise UserRepositoryError("Could not create user") from exc
        return self._document_without_mongodb_id(document)
