from types import SimpleNamespace

from app.common.status import AgentType
from app.modules.agents.requirements.api.discovery_routes import (
    get_discovery_results,
    retry_requirement_n3,
    router,
)


USER = SimpleNamespace(user_id="USR-001")


class FakeStandalone:
    def require_active_project(self, user_id, project_id):
        assert user_id == USER.user_id
        return SimpleNamespace(agent_project_id=project_id, agent_type=AgentType.REQUIREMENTS)


class FakeReadService:
    def __init__(self):
        self.calls = []

    def get(self, project, execution, user):
        self.calls.append((project, execution, user.user_id))
        return SimpleNamespace(execution_id=execution)


class FakeN3Service:
    def __init__(self):
        self.calls = []

    def retry(self, project, owner):
        self.calls.append((project, owner))
        return SimpleNamespace(execution_id="N3-AAAAAAAAAAAAAAAA-002")


def test_discovery_get_delegates_without_mutating_or_exposing_paths():
    service = FakeReadService()
    response = get_discovery_results("AGP-001", "N3-AAAAAAAAAAAAAAAA-001", service, USER)

    assert service.calls == [("AGP-001", "N3-AAAAAAAAAAAAAAAA-001", "USR-001")]
    assert response.data.execution_id == "N3-AAAAAAAAAAAAAAAA-001"
    assert not hasattr(response.data, "path")


def test_retry_validates_project_then_delegates_to_n3_authority():
    service = FakeN3Service()
    response = retry_requirement_n3(
        "AGP-001", service, USER, FakeStandalone()
    )

    assert service.calls == [("AGP-001", "USR-001")]
    assert response.data.execution_id == "N3-AAAAAAAAAAAAAAAA-002"


def test_discovery_router_has_no_manual_start_endpoint():
    paths = {(route.path, tuple(route.methods)) for route in router.routes}
    assert not any("start" in path.lower() for path, _ in paths)
