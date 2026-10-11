from app.core.config import Settings
from app.database import collections
from app.database import mongodb


EXPECTED_COLLECTIONS = {
    "PROJECTS": "projects",
    "CLIENT_INPUTS": "client_inputs",
    "REQUIREMENTS": "requirements",
    "DESIGN_ARTIFACTS": "design_artifacts",
    "BACKLOG_ITEMS": "backlog_items",
    "TEST_CASES": "test_cases",
    "IMPLEMENTATION_ARTIFACTS": "implementation_artifacts",
    "EXECUTION_LOGS": "execution_logs",
    "TEST_RESULTS": "test_results",
    "SECURITY_FINDINGS": "security_findings",
    "BUG_REPORTS": "bug_reports",
    "APPROVALS": "approvals",
    "TRACEABILITY_LINKS": "traceability_links",
    "WORKFLOW_EVENTS": "workflow_events",
}


class FakeDatabase:
    def __init__(self) -> None:
        self.commands: list[str] = []

    def command(self, command: str) -> dict[str, int]:
        self.commands.append(command)
        return {"ok": 1}


class FakeMongoClient:
    def __init__(self) -> None:
        self.database = FakeDatabase()
        self.requested_database: str | None = None
        self.closed = False

    def __getitem__(self, database_name: str) -> FakeDatabase:
        self.requested_database = database_name
        return self.database

    def close(self) -> None:
        self.closed = True


def test_mongodb_settings_defaults(monkeypatch) -> None:
    monkeypatch.delenv("MONGODB_URI", raising=False)
    monkeypatch.delenv("MONGODB_DATABASE", raising=False)

    configured_settings = Settings(_env_file=None)

    assert configured_settings.mongodb_uri == "mongodb://localhost:27017"
    assert configured_settings.mongodb_database == "agileflow_ai"


def test_mongodb_settings_read_environment(monkeypatch) -> None:
    monkeypatch.setenv("MONGODB_URI", "mongodb://db.example.test:27018")
    monkeypatch.setenv("MONGODB_DATABASE", "agileflow_test")

    configured_settings = Settings(_env_file=None)

    assert configured_settings.mongodb_uri == "mongodb://db.example.test:27018"
    assert configured_settings.mongodb_database == "agileflow_test"


def test_official_collection_names() -> None:
    actual_collections = {
        name: value
        for name, value in vars(collections).items()
        if name.isupper() and isinstance(value, str)
    }

    assert actual_collections == EXPECTED_COLLECTIONS


def test_database_helpers_use_shared_client(monkeypatch) -> None:
    fake_client = FakeMongoClient()
    monkeypatch.setattr(mongodb, "_client", fake_client)

    database = mongodb.get_database()

    assert database is fake_client.database
    assert fake_client.requested_database == mongodb.settings.mongodb_database
    assert mongodb.ping_database() is True
    assert fake_client.database.commands == ["ping"]

    mongodb.close_mongodb_client()
    assert fake_client.closed is True
