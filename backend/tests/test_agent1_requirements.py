from copy import deepcopy

import pytest

from app.main import app
from app.modules.agent1.engine import Agent1Engine, _selected_schema, find_exact_duplicates
from app.common.model_provider import ModelProviderError
from app.modules.agent1.schemas import (
    Agent1InputContext,
    QualityFindingCategory,
    RequirementOutputCode,
)
from app.modules.agent1.router import get_agent1_engine
from app.modules.standalone.router import (
    get_agent_project_repository,
    get_agent_run_repository,
)
from test_standalone_foundation import (
    FakeAgentProjectRepository,
    FakeAgentRunRepository,
)


VALID_FUNCTIONAL = [
    {
        "id": "FR-001",
        "statement": "The system shall let members search the catalogue.",
        "source_refs": ["TEXT-001"],
        "rationale": "Members need to find books.",
    }
]


class FixedProvider:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def generate_structured(self, **kwargs):
        self.calls.append(kwargs)
        return deepcopy(self.response)


class FailingProvider:
    def generate_structured(self, **kwargs):
        del kwargs
        raise ModelProviderError("provider unavailable")


@pytest.fixture
def agent1_context(authentication_context):
    projects = FakeAgentProjectRepository()
    runs = FakeAgentRunRepository()
    provider = FixedProvider({"FUNCTIONAL_REQUIREMENTS": VALID_FUNCTIONAL})
    app.dependency_overrides[get_agent_project_repository] = lambda: projects
    app.dependency_overrides[get_agent_run_repository] = lambda: runs
    app.dependency_overrides[get_agent1_engine] = lambda: Agent1Engine(provider)
    try:
        yield authentication_context, projects, runs, provider
    finally:
        app.dependency_overrides.pop(get_agent_project_repository, None)
        app.dependency_overrides.pop(get_agent_run_repository, None)
        app.dependency_overrides.pop(get_agent1_engine, None)


def create_project(client, agent_type="REQUIREMENTS"):
    response = client.post(
        "/api/v1/agent-projects",
        json={
            "agent_type": agent_type,
            "name": "BookEase",
            "domain": "Library",
        },
    )
    assert response.status_code == 201
    return response.json()["data"]


def run_payload():
    return {
        "text": "Members need to search the catalogue.",
        "selected_outputs": ["FUNCTIONAL_REQUIREMENTS"],
        "business_goals": "Reduce time spent finding books.",
    }


def test_agent1_run_uses_shared_lifecycle_and_respects_selected_outputs(
    agent1_context,
):
    authentication, _, runs, provider = agent1_context
    client = authentication.client()
    project = create_project(client)

    response = client.post(
        f"/api/v1/agents/requirements/{project['agent_project_id']}/run",
        json=run_payload(),
    )

    assert response.status_code == 200
    result = response.json()["data"]
    assert result["status"] == "COMPLETED"
    assert result["agent_type"] == "REQUIREMENTS"
    assert result["run_mode"] == "DEFAULT"
    assert result["selected_outputs"] == ["FUNCTIONAL_REQUIREMENTS"]
    assert set(result["outputs"]) == {"FUNCTIONAL_REQUIREMENTS"}
    persisted = runs.documents[result["run_id"]]
    assert persisted["status"] == "COMPLETED"
    assert persisted["started_at"] is not None
    assert persisted["completed_at"] is not None
    assert persisted["input_snapshot"]["project_name"] == "BookEase"
    assert persisted["input_snapshot"]["sources"] == [
        {
            "source_id": "TEXT-001",
            "source_type": "TEXT",
            "content": "Members need to search the catalogue.",
        }
    ]
    assert len(provider.calls) == 1

    history = client.get(
        f"/api/v1/agent-projects/{project['agent_project_id']}/runs"
    ).json()["data"]
    assert [item["run_id"] for item in history] == [result["run_id"]]


def test_agent1_rejects_wrong_type_foreign_and_archived_projects(agent1_context):
    authentication, _, _, _ = agent1_context
    owner_client = authentication.client("USR-001")
    foreign_client = authentication.client("USR-002")

    wrong_type = create_project(owner_client, "DESIGN_PLANNING")
    assert owner_client.post(
        f"/api/v1/agents/requirements/{wrong_type['agent_project_id']}/run",
        json=run_payload(),
    ).status_code == 422

    project = create_project(owner_client)
    assert foreign_client.post(
        f"/api/v1/agents/requirements/{project['agent_project_id']}/run",
        json=run_payload(),
    ).status_code == 404

    owner_client.patch(
        f"/api/v1/agent-projects/{project['agent_project_id']}",
        json={"status": "ARCHIVED"},
    )
    assert owner_client.post(
        f"/api/v1/agents/requirements/{project['agent_project_id']}/run",
        json=run_payload(),
    ).status_code == 409


@pytest.mark.parametrize(
    "payload, field",
    [
        ({"text": "   ", "selected_outputs": ["SRS"]}, "text"),
        ({"text": "A valid source", "selected_outputs": []}, "selected_outputs"),
        (
            {"text": "A valid source", "selected_outputs": ["NOT_SUPPORTED"]},
            "selected_outputs.0",
        ),
    ],
)
def test_agent1_rejects_invalid_input_before_creating_a_run(
    agent1_context, payload, field
):
    authentication, _, runs, _ = agent1_context
    client = authentication.client()
    project = create_project(client)

    response = client.post(
        f"/api/v1/agents/requirements/{project['agent_project_id']}/run",
        json=payload,
    )

    assert response.status_code == 422
    assert any(item["field"] == field for item in response.json()["errors"])
    assert runs.documents == {}


def test_malformed_structured_output_fails_and_persists_structured_error(
    agent1_context,
):
    authentication, _, runs, provider = agent1_context
    client = authentication.client()
    project = create_project(client)
    provider.response = {"FUNCTIONAL_REQUIREMENTS": [{"id": "FR-001"}]}

    response = client.post(
        f"/api/v1/agents/requirements/{project['agent_project_id']}/run",
        json=run_payload(),
    )

    assert response.status_code == 200
    result = response.json()["data"]
    assert result["status"] == "FAILED"
    assert result["outputs"] == {}
    assert result["errors"][0]["code"] == "STRUCTURED_OUTPUT_INVALID"
    assert runs.documents[result["run_id"]]["status"] == "FAILED"


def test_invalid_source_reference_is_structured_output_failure(agent1_context):
    authentication, _, _, provider = agent1_context
    client = authentication.client()
    project = create_project(client)
    provider.response["FUNCTIONAL_REQUIREMENTS"][0]["source_refs"] = ["TEXT-999"]

    response = client.post(
        f"/api/v1/agents/requirements/{project['agent_project_id']}/run",
        json=run_payload(),
    )

    result = response.json()["data"]
    assert result["status"] == "FAILED"
    assert result["errors"][0]["code"] == "STRUCTURED_OUTPUT_INVALID"


def test_model_failure_transitions_running_run_to_failed(agent1_context):
    authentication, _, runs, _ = agent1_context
    app.dependency_overrides[get_agent1_engine] = lambda: Agent1Engine(
        FailingProvider()
    )
    client = authentication.client()
    project = create_project(client)

    result = client.post(
        f"/api/v1/agents/requirements/{project['agent_project_id']}/run",
        json=run_payload(),
    ).json()["data"]

    assert result["status"] == "FAILED"
    assert result["errors"][0]["code"] == "MODEL_EXECUTION_FAILED"
    assert runs.documents[result["run_id"]]["started_at"] is not None
    assert runs.documents[result["run_id"]]["completed_at"] is not None


def test_provider_schema_combines_definitions_and_is_strict():
    schema = _selected_schema(
        [RequirementOutputCode.FUNCTIONAL_REQUIREMENTS, RequirementOutputCode.SRS]
    )

    assert set(schema["properties"]) == {"FUNCTIONAL_REQUIREMENTS", "SRS"}
    assert set(schema["required"]) == {"FUNCTIONAL_REQUIREMENTS", "SRS"}
    assert "FunctionalRequirement" in schema["$defs"]
    assert "SRSArtifact" in schema["$defs"]
    assert "default" not in str(schema)
    assert all(
        definition.get("additionalProperties") is False
        for definition in schema["$defs"].values()
        if definition.get("type") == "object"
    )


def test_deterministic_quality_check_finds_exact_duplicate_statements():
    context = Agent1InputContext(
        project_name="BookEase",
        domain="Library",
        sources=[
            {
                "source_id": "TEXT-001",
                "source_type": "TEXT",
                "content": "The system shall search.\nThe system shall search.",
            }
        ],
    )

    assert find_exact_duplicates(context) == ["the system shall search."]
    assert [category.value for category in QualityFindingCategory] == [
        "AMBIGUITY",
        "MISSING_INFORMATION",
        "CONFLICT",
        "DUPLICATE",
        "INCONSISTENCY",
    ]
