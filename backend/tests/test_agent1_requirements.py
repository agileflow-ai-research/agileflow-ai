from copy import deepcopy
import json

import httpx
import pytest

from app.common.model_provider import (
    ModelProviderError,
    OpenAICompatibleProvider,
)
from app.main import app
from app.modules.agents.requirements.engine import Agent1Engine, _selected_schema, find_exact_duplicates
from app.modules.agents.requirements.schemas import (
    Agent1InputContext,
    QualityFindingCategory,
    RequirementOutputCode,
)
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


def test_legacy_agent1_run_route_is_unavailable(authentication_context):
    projects = FakeAgentProjectRepository()
    runs = FakeAgentRunRepository()
    app.dependency_overrides[get_agent_project_repository] = lambda: projects
    app.dependency_overrides[get_agent_run_repository] = lambda: runs
    try:
        client = authentication_context.client()
        project = create_project(client)
        path = f"/api/v1/agents/requirements/{project['agent_project_id']}/run"

        response = client.post(path, json=run_payload())

        assert response.status_code == 404
        assert "/api/v1/agents/requirements/{agent_project_id}/run" not in app.openapi()[
            "paths"
        ]
        assert runs.documents == {}
    finally:
        app.dependency_overrides.pop(get_agent_project_repository, None)
        app.dependency_overrides.pop(get_agent_run_repository, None)


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


def test_quality_findings_do_not_add_unselected_clarification_artifact():
    quality = deepcopy(ALL_OUTPUTS["QUALITY_FINDINGS"])
    quality[0]["affected_refs"] = ["TEXT-001"]
    execution = Agent1Engine(
        FixedProvider({"QUALITY_FINDINGS": quality})
    ).execute_with_metadata(
        CLINIC_CONTEXT, [RequirementOutputCode.QUALITY_FINDINGS]
    )

    assert set(execution.outputs) == {"QUALITY_FINDINGS"}
    assert "CLARIFICATION_QUESTIONS" not in execution.outputs
    assert execution.clarification_recommended is True


def test_exact_duplicate_recommends_but_does_not_add_unselected_clarification():
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
    execution = Agent1Engine(
        FixedProvider({"FUNCTIONAL_REQUIREMENTS": VALID_FUNCTIONAL})
    ).execute_with_metadata(
        duplicate_context,
        [RequirementOutputCode.FUNCTIONAL_REQUIREMENTS],
    )

    assert set(execution.outputs) == {"FUNCTIONAL_REQUIREMENTS"}
    assert "CLARIFICATION_QUESTIONS" not in execution.outputs
    assert "QUALITY_FINDINGS" not in execution.outputs
    assert execution.clarification_recommended is True


def test_selected_clarification_questions_are_returned_and_validated():
    outputs = Agent1Engine(
        FixedProvider({
            "CLARIFICATION_QUESTIONS": [
                {
                    **ALL_OUTPUTS["CLARIFICATION_QUESTIONS"][0],
                    "related_refs": ["TEXT-001"],
                }
            ]
        })
    ).execute(
        CLINIC_CONTEXT,
        [RequirementOutputCode.CLARIFICATION_QUESTIONS],
    )

    assert set(outputs) == {"CLARIFICATION_QUESTIONS"}
    assert outputs["CLARIFICATION_QUESTIONS"][0]["id"] == "CQ-001"


def test_provider_extra_unselected_clarification_is_filtered():
    response = {
        "FUNCTIONAL_REQUIREMENTS": VALID_FUNCTIONAL,
        "CLARIFICATION_QUESTIONS": [
            {
                **ALL_OUTPUTS["CLARIFICATION_QUESTIONS"][0],
                "related_refs": ["TEXT-001"],
            }
        ],
    }
    execution = Agent1Engine(FixedProvider(response)).execute_with_metadata(
        CLINIC_CONTEXT,
        [RequirementOutputCode.FUNCTIONAL_REQUIREMENTS],
    )

    assert set(execution.outputs) == {"FUNCTIONAL_REQUIREMENTS"}
    assert execution.clarification_recommended is True


def test_engine_does_not_mutate_selected_outputs():
    selected = [RequirementOutputCode.FUNCTIONAL_REQUIREMENTS]
    original = list(selected)

    Agent1Engine(
        FixedProvider({"FUNCTIONAL_REQUIREMENTS": VALID_FUNCTIONAL})
    ).execute(CLINIC_CONTEXT, selected)

    assert selected == original


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
