from typing import Any

from pymongo import MongoClient
from pymongo.database import Database

from app.core.config import settings


_client: MongoClient[dict[str, Any]] = MongoClient(settings.mongodb_uri)


def get_database() -> Database[dict[str, Any]]:
    """Return the MongoDB database configured for AgileFlow AI."""
    return _client[settings.mongodb_database]


def ping_database() -> bool:
    """Ping MongoDB and return whether the server acknowledged the command."""
    response = get_database().command("ping")
    return response.get("ok") == 1


def close_mongodb_client() -> None:
    """Close the shared MongoDB client."""
    _client.close()
