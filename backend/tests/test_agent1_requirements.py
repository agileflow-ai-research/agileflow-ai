from copy import deepcopy
import json

import httpx
import pytest

from app.common.model_provider import (
    ModelProviderError,
    ModelStructuredOutputError,
    OpenAICompatibleProvider,
    UnavailableModelProvider,
)
from app.main import app
from app.modules.agents.requirements.engine import Agent1Engine, _selected_schema, find_exact_duplicates
from app.modules.agents.requirements.schemas import (
    Agent1InputContext,
    QualityFindingCategory,
    RequirementOutputCode,
)
from app.modules.agents.requirements.router import get_agent1_engine
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

CLINIC_CONTEXT = Agent1InputContext(
    project_name="Clinic Appointment Booking System",
    domain="Healthcare",
    sources=[
        {
            "source_id": "TEXT-001",
            "source_type": "TEXT",
            "content": (
                "Patients should create accounts, see doctors and slots, "
                "book and cancel appointments, and receive confirmation."
            ),
        }
    ],
    business_goals="Reduce telephone bookings and scheduling conflicts.",
    known_constraints=(
        "Responsive web application. Online payment is not required."
    ),
)

ALL_OUTPUTS = {
    "FUNCTIONAL_REQUIREMENTS": [
        {
            "id": "FR-001",
            "statement": "The system shall let patients book an available slot.",
            "source_refs": ["TEXT-001"],
            "rationale": "Reduce telephone bookings.",
        }
    ],
    "NON_FUNCTIONAL_REQUIREMENTS": [
        {
            "id": "NFR-001",
            "category": "Security",
            "statement": "The system shall protect patient account data.",
            "measure": "Security controls require stakeholder confirmation.",
            "source_refs": ["TEXT-001"],
        }
    ],
    "USER_STORIES": [
        {
            "id": "US-001",
            "actor": "patient",
            "goal": "book an available appointment slot",
            "benefit": "I can arrange dental care without calling the clinic",
            "source_refs": ["TEXT-001"],
            "requirement_refs": ["FR-001"],
        }
    ],
    "ACCEPTANCE_CRITERIA": [
        {
            "id": "AC-001",
            "related_ids": ["FR-001", "US-001"],
            "given": "an available appointment slot",
            "when": "a patient books the slot",
            "then": "the booking is saved and confirmed",
        }
    ],
    "PERSONAS": [
        {
            "id": "PER-001",
            "role": "Patient",
            "goals": ["Book an appointment online"],
            "pain_points": ["Telephone booking delays"],
            "context": "Uses a responsive web application.",
        }
    ],
    "QUALITY_FINDINGS": [
        {
            "id": "QF-001",
            "category": "AMBIGUITY",
            "affected_refs": ["NFR-001"],
            "explanation": "Easy to use is not measurable.",
            "suggested_clarification": "Which usability target should be met?",
        }
    ],
    "CLARIFICATION_QUESTIONS": [
        {
            "id": "CQ-001",
            "question": "Which usability target should be met?",
            "reason": "The requested ease of use is not measurable.",
            "related_refs": ["NFR-001"],
        }
    ],
    "SRS": {
        "title": "Clinic Appointment Booking System SRS",
        "overview": "Requirements for responsive dental appointment booking.",
        "sections": [
            {
                "title": "Scope",
                "content": "Patient booking and clinic schedule management.",
            }
        ],
        "assumptions": [],
        "unresolved_issues": ["Usability and security targets require clarification."],
    },
}


class FixedProvider:
    def __init__(self, response):
        self.response = deepcopy(response)
        self.calls = []

    def generate_structured(self, **kwargs):
        self.calls.append(kwargs)
        return deepcopy(self.response)


class FailingProvider:
    def generate_structured(self, **kwargs):
        del kwargs
        raise ModelProviderError("provider unavailable")


class InvalidJsonProvider:
    def generate_structured(self, **kwargs):
        del kwargs
        raise ModelStructuredOutputError("invalid json")


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
    assert set(provider.calls[0]["json_schema"]["properties"]) == {
        "FUNCTIONAL_REQUIREMENTS"
    }

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


@pytest.mark.parametrize("code", list(RequirementOutputCode))
def test_each_of_the_eight_output_schemas_accepts_real_response_shapes(code):
    value = deepcopy(ALL_OUTPUTS[code.value])
    if code is RequirementOutputCode.USER_STORIES:
        value[0]["requirement_refs"] = []
    elif code is RequirementOutputCode.ACCEPTANCE_CRITERIA:
        value[0]["related_ids"] = ["TEXT-001"]
    elif code is RequirementOutputCode.QUALITY_FINDINGS:
        value[0]["affected_refs"] = ["TEXT-001"]
        value[0]["suggested_clarification"] = None
    elif code is RequirementOutputCode.CLARIFICATION_QUESTIONS:
        value[0]["related_refs"] = ["TEXT-001"]
    provider = FixedProvider({code.value: value})

    outputs = Agent1Engine(provider).execute(CLINIC_CONTEXT, [code])

    assert set(outputs) == {code.value}


def test_combined_outputs_preserve_requirement_story_criterion_traceability():
    selected = list(RequirementOutputCode)
    outputs = Agent1Engine(FixedProvider(ALL_OUTPUTS)).execute(
        CLINIC_CONTEXT, selected
    )

    assert set(outputs) == {code.value for code in selected}
    assert outputs["USER_STORIES"][0]["requirement_refs"] == ["FR-001"]
    assert outputs["ACCEPTANCE_CRITERIA"][0]["related_ids"] == [
        "FR-001",
        "US-001",
    ]


@pytest.mark.parametrize(
    "mutate",
    [
        lambda output: output["USER_STORIES"][0].update(
            requirement_refs=["FR-999"]
        ),
        lambda output: output["ACCEPTANCE_CRITERIA"][0].update(
            related_ids=["US-999"]
        ),
    ],
)
def test_invalid_cross_artifact_references_are_rejected(mutate):
    response = deepcopy(ALL_OUTPUTS)
    mutate(response)

    with pytest.raises(ValueError, match="invalid"):
        Agent1Engine(FixedProvider(response)).execute(
            CLINIC_CONTEXT, list(RequirementOutputCode)
        )


def test_duplicate_generated_requirement_statements_are_rejected():
    response = deepcopy(ALL_OUTPUTS)
    response["FUNCTIONAL_REQUIREMENTS"].append(
        {
            **response["FUNCTIONAL_REQUIREMENTS"][0],
            "id": "FR-002",
        }
    )

    with pytest.raises(ValueError, match="duplicate requirement statements"):
        Agent1Engine(FixedProvider(response)).execute(
            CLINIC_CONTEXT, list(RequirementOutputCode)
        )


@pytest.mark.parametrize(
    "response",
    [
        {
            "FUNCTIONAL_REQUIREMENTS": [
                {**VALID_FUNCTIONAL[0], "unexpected": True}
            ]
        },
        {
            "FUNCTIONAL_REQUIREMENTS": [
                {**VALID_FUNCTIONAL[0], "statement": "   "}
            ]
        },
        {
            "FUNCTIONAL_REQUIREMENTS": [
                {**VALID_FUNCTIONAL[0], "statement": "Owned by RUN-999"}
            ]
        },
    ],
)
def test_unexpected_blank_and_backend_metadata_outputs_are_rejected(response):
    with pytest.raises(ValueError):
        Agent1Engine(FixedProvider(response)).execute(
            CLINIC_CONTEXT, [RequirementOutputCode.FUNCTIONAL_REQUIREMENTS]
        )


def test_invalid_json_provider_content_becomes_structured_output_invalid(
    agent1_context,
):
    authentication, _, _, _ = agent1_context
    app.dependency_overrides[get_agent1_engine] = lambda: Agent1Engine(
        InvalidJsonProvider()
    )
    client = authentication.client()
    project = create_project(client)

    result = client.post(
        f"/api/v1/agents/requirements/{project['agent_project_id']}/run",
        json=run_payload(),
    ).json()["data"]

    assert result["status"] == "FAILED"
    assert result["errors"][0]["code"] == "STRUCTURED_OUTPUT_INVALID"


def test_missing_provider_configuration_is_a_safe_persisted_failure(
    agent1_context,
):
    authentication, _, runs, _ = agent1_context
    app.dependency_overrides[get_agent1_engine] = lambda: Agent1Engine(
        UnavailableModelProvider("MODEL_API_KEY is not configured")
    )
    client = authentication.client()
    project = create_project(client)

    result = client.post(
        f"/api/v1/agents/requirements/{project['agent_project_id']}/run",
        json=run_payload(),
    ).json()["data"]

    assert result["status"] == "FAILED"
    assert result["errors"] == [
        {
            "code": "MODEL_EXECUTION_FAILED",
            "message": "The configured model provider could not generate the requested outputs",
            "details": None,
        }
    ]
    assert "MODEL_API_KEY" not in str(result)
    assert runs.documents[result["run_id"]]["status"].value == "FAILED"


def test_quality_issue_adds_only_required_supplemental_clarification():
    quality = deepcopy(ALL_OUTPUTS["QUALITY_FINDINGS"])
    quality[0]["affected_refs"] = ["TEXT-001"]
    outputs = Agent1Engine(
        FixedProvider({"QUALITY_FINDINGS": quality})
    ).execute(CLINIC_CONTEXT, [RequirementOutputCode.QUALITY_FINDINGS])

    assert set(outputs) == {"QUALITY_FINDINGS", "CLARIFICATION_QUESTIONS"}
    assert outputs["CLARIFICATION_QUESTIONS"][0]["related_refs"] == [
        "TEXT-001"
    ]


def test_exact_duplicate_adds_clarification_without_unselected_quality_output():
    duplicate_context = Agent1InputContext(
        project_name=CLINIC_CONTEXT.project_name,
        domain=CLINIC_CONTEXT.domain,
        sources=[
            {
                "source_id": "TEXT-001",
                "source_type": "TEXT",
                "content": "Patients book slots.\nPatients book slots.",
            }
        ],
    )
    outputs = Agent1Engine(
        FixedProvider({"FUNCTIONAL_REQUIREMENTS": VALID_FUNCTIONAL})
    ).execute(
        duplicate_context,
        [RequirementOutputCode.FUNCTIONAL_REQUIREMENTS],
    )

    assert set(outputs) == {
        "FUNCTIONAL_REQUIREMENTS",
        "CLARIFICATION_QUESTIONS",
    }
    assert "QUALITY_FINDINGS" not in outputs


class StubResponse:
    def __init__(self, body):
        self._body = body

    def raise_for_status(self):
        return None

    def json(self):
        return self._body


def test_openai_compatible_provider_parses_real_api_response_shape(monkeypatch):
    captured = {}

    def post(url, **kwargs):
        captured.update(url=url, **kwargs)
        return StubResponse(
            {
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {"FUNCTIONAL_REQUIREMENTS": VALID_FUNCTIONAL}
                            )
                        }
                    }
                ]
            }
        )

    monkeypatch.setattr(httpx, "post", post)
    provider = OpenAICompatibleProvider(
        api_key="test-secret",
        model="test-model",
        base_url="https://provider.example/v1",
        timeout_seconds=3,
    )

    result = provider.generate_structured(
        system_prompt="system",
        user_prompt="user",
        json_schema={"type": "object"},
    )

    assert result == {"FUNCTIONAL_REQUIREMENTS": VALID_FUNCTIONAL}
    assert captured["url"] == "https://provider.example/v1/chat/completions"
    assert captured["json"]["response_format"]["type"] == "json_schema"


@pytest.mark.parametrize(
    "provider_error",
    [
        httpx.TimeoutException("timed out"),
        httpx.HTTPStatusError(
            "provider error",
            request=httpx.Request("POST", "https://provider.example"),
            response=httpx.Response(500),
        ),
    ],
)
def test_provider_timeout_and_http_errors_are_safely_wrapped(
    monkeypatch, provider_error
):
    def post(*args, **kwargs):
        del args, kwargs
        raise provider_error

    monkeypatch.setattr(httpx, "post", post)
    provider = OpenAICompatibleProvider(
        api_key="test-secret",
        model="test-model",
        base_url="https://provider.example/v1",
        timeout_seconds=3,
    )

    with pytest.raises(ModelProviderError, match="generation failed"):
        provider.generate_structured(
            system_prompt="system",
            user_prompt="user",
            json_schema={"type": "object"},
        )
