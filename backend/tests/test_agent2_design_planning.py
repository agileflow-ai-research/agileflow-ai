from copy import deepcopy
import json

import pytest

from app.main import app
from app.modules.agents.design_planning.engine import Agent2Engine
from app.modules.agents.design_planning.router import get_agent2_engine
from app.modules.agents.design_planning.schemas import Agent2InputContext, DesignPlanningOutputCode
from app.modules.standalone.router import get_agent_project_repository, get_agent_run_repository
from test_standalone_foundation import FakeAgentProjectRepository, FakeAgentRunRepository


EPICS = [{
    "id": "EPIC-001", "title": "Booking", "outcome": "Customers can book",
    "priority": "HIGH", "source_refs": ["SPEC-001"],
}]
FEATURES = [{
    "id": "FEATURE-001", "epic_id": "EPIC-001", "title": "Create booking",
    "description": "Capture and confirm bookings", "source_refs": ["SPEC-001"],
}]
STORIES = [{
    "id": "STORY-001", "epic_id": "EPIC-001", "feature_id": "FEATURE-001",
    "actor": "customer", "goal": "create a booking", "benefit": "reserve a slot",
    "acceptance_criteria": ["The booking is confirmed"], "priority": "HIGH",
    "estimate_points": 5, "source_refs": ["SPEC-001"],
}]
TASKS = [{
    "id": "TASK-001", "epic_id": "EPIC-001", "feature_id": "FEATURE-001",
    "story_id": "STORY-001", "title": "Implement booking", "description": "Build booking flow",
    "required_skills": ["API"], "estimate_points": 3, "depends_on": [],
    "source_refs": ["SPEC-001"],
}]
SPRINTS = [{
    "id": "SPRINT-001", "name": "Sprint 1", "duration_days": 10,
    "capacity_points": 10, "item_refs": ["TASK-001"], "dependency_notes": [],
}]
ASSIGNMENTS = [{
    "task_id": "TASK-001", "team_slot": "Team member 1", "role": "Developer",
    "rationale": "API skill match", "sprint_id": "SPRINT-001",
}]


class FixedProvider:
    def __init__(self, response):
        self.response = deepcopy(response)
        self.calls = []

    def generate_structured(self, **kwargs):
        self.calls.append(kwargs)
        return deepcopy(self.response)


class SequenceProvider:
    def __init__(self, responses):
        self.responses = [deepcopy(response) for response in responses]
        self.calls = []

    def generate_structured(self, **kwargs):
        self.calls.append(kwargs)
        index = min(len(self.calls) - 1, len(self.responses) - 1)
        return deepcopy(self.responses[index])


@pytest.fixture
def agent2_context(authentication_context):
    projects = FakeAgentProjectRepository()
    runs = FakeAgentRunRepository()
    provider = FixedProvider({"EPICS": EPICS})
    app.dependency_overrides[get_agent_project_repository] = lambda: projects
    app.dependency_overrides[get_agent_run_repository] = lambda: runs
    app.dependency_overrides[get_agent2_engine] = lambda: Agent2Engine(provider)
    try:
        yield authentication_context, projects, runs, provider
    finally:
        app.dependency_overrides.pop(get_agent_project_repository, None)
        app.dependency_overrides.pop(get_agent_run_repository, None)
        app.dependency_overrides.pop(get_agent2_engine, None)


def create_project(client, agent_type="DESIGN_PLANNING"):
    response = client.post("/api/v1/agent-projects", json={
        "agent_type": agent_type, "name": "BookEase", "domain": "Hospitality",
    })
    assert response.status_code == 201
    return response.json()["data"]


def test_run_uses_shared_lifecycle_snapshot_and_selected_outputs(agent2_context):
    authentication, _, runs, provider = agent2_context
    client = authentication.client()
    project = create_project(client)
    response = client.post(
        f"/api/v1/agents/design-planning/{project['agent_project_id']}/run",
        json={"requirements": "Guests need to book rooms.", "selected_outputs": ["EPICS"]},
    )
    assert response.status_code == 200
    result = response.json()["data"]
    assert result["status"] == "COMPLETED"
    assert result["agent_type"] == "DESIGN_PLANNING"
    assert result["run_mode"] == "DEFAULT"
    assert result["correction_attempts"] == 0
    assert set(result["outputs"]) == {"EPICS"}
    persisted = runs.documents[result["run_id"]]
    assert persisted["started_at"] and persisted["completed_at"]
    assert persisted["input_snapshot"]["specification_sources"] == [{
        "source_id": "SPEC-001", "source_type": "REQUIREMENTS",
        "content": "Guests need to book rooms.",
    }]
    assert set(provider.calls[0]["json_schema"]["properties"]) == {"EPICS"}


def test_wrong_type_foreign_and_archived_projects_are_rejected(agent2_context):
    authentication, _, _, _ = agent2_context
    owner = authentication.client("USR-001")
    foreign = authentication.client("USR-002")
    wrong = create_project(owner, "REQUIREMENTS")
    payload = {"requirements": "Valid specification", "selected_outputs": ["EPICS"]}
    assert owner.post(f"/api/v1/agents/design-planning/{wrong['agent_project_id']}/run", json=payload).status_code == 422
    project = create_project(owner)
    assert foreign.post(f"/api/v1/agents/design-planning/{project['agent_project_id']}/run", json=payload).status_code == 404
    owner.patch(f"/api/v1/agent-projects/{project['agent_project_id']}", json={"status": "ARCHIVED"})
    assert owner.post(f"/api/v1/agents/design-planning/{project['agent_project_id']}/run", json=payload).status_code == 409


@pytest.mark.parametrize("payload", [
    {"requirements": "  ", "selected_outputs": ["EPICS"]},
    {"requirements": "Valid", "selected_outputs": []},
    {"requirements": "Valid", "selected_outputs": ["UNKNOWN"]},
    {"requirements": "Valid", "selected_outputs": ["TASK_ASSIGNMENT"]},
    {"requirements": "Valid", "development_team_count": 2, "selected_outputs": ["SPRINT_PLAN"]},
])
def test_invalid_inputs_create_no_run(agent2_context, payload):
    authentication, _, runs, _ = agent2_context
    client = authentication.client()
    project = create_project(client)
    response = client.post(f"/api/v1/agents/design-planning/{project['agent_project_id']}/run", json=payload)
    assert response.status_code == 422
    assert runs.documents == {}


def test_planning_hierarchy_and_sprint_constraints_are_validated():
    outputs = {
        "EPICS": EPICS, "FEATURES": FEATURES, "USER_STORIES": STORIES,
        "TASKS": TASKS, "SPRINT_PLAN": SPRINTS, "TASK_ASSIGNMENT": ASSIGNMENTS,
    }
    context = Agent2InputContext(
        project_name="BookEase", domain="Hospitality",
        specification_sources=[{"source_id": "SPEC-001", "source_type": "SRS", "content": "Booking system"}],
        development_team_count=1, sprint_duration=10,
    )
    result = Agent2Engine(FixedProvider(outputs)).execute(context, [
        DesignPlanningOutputCode.EPICS, DesignPlanningOutputCode.FEATURES,
        DesignPlanningOutputCode.USER_STORIES, DesignPlanningOutputCode.TASKS,
        DesignPlanningOutputCode.SPRINT_PLAN, DesignPlanningOutputCode.TASK_ASSIGNMENT,
    ])
    assert result["FEATURES"][0]["epic_id"] == "EPIC-001"
    assert result["TASKS"][0]["story_id"] == "STORY-001"


def test_design_outputs_are_structured_specs_not_fake_rendered_images():
    outputs = {
        "SYSTEM_ARCHITECTURE": {
            "style": "Layered", "components": [{
                "id": "COMP-001", "name": "Booking API", "responsibility": "Manage bookings",
                "dependencies": [], "source_refs": ["SPEC-001"],
            }], "boundaries": ["Browser to API"], "interactions": ["HTTPS JSON"],
            "constraints": ["Responsive web"], "assumptions": ["Single region"],
        },
        "UML_DIAGRAMS": {"diagrams": [{
            "id": "UML-001", "title": "Booking sequence", "diagram_type": "SEQUENCE",
            "notation": "MERMAID", "source": "sequenceDiagram\nCustomer->>API: Create booking",
            "source_refs": ["SPEC-001"],
        }], "assumptions": []},
        "WIREFRAMES": {"fidelity": "STRUCTURED_LOW_FIDELITY", "screens": [{
            "id": "WF-001", "name": "Booking form", "purpose": "Collect booking details",
            "regions": ["Header", "Form", "Actions"], "interactions": ["Submit booking"],
            "source_refs": ["SPEC-001"],
        }], "assumptions": []},
    }
    context = Agent2InputContext(
        project_name="BookEase", domain="Hospitality",
        specification_sources=[{"source_id": "SPEC-001", "source_type": "REQUIREMENTS", "content": "Guests book rooms"}],
    )
    result = Agent2Engine(FixedProvider(outputs)).execute(context, [
        DesignPlanningOutputCode.SYSTEM_ARCHITECTURE,
        DesignPlanningOutputCode.UML_DIAGRAMS,
        DesignPlanningOutputCode.WIREFRAMES,
    ])
    assert result["UML_DIAGRAMS"]["diagrams"][0]["notation"] == "MERMAID"
    assert result["WIREFRAMES"]["fidelity"] == "STRUCTURED_LOW_FIDELITY"
    assert "image" not in str(result).lower()


def test_invalid_hierarchy_becomes_failed_run(agent2_context):
    authentication, _, _, provider = agent2_context
    provider.response = {"EPICS": [{**EPICS[0], "source_refs": ["SPEC-999"]}]}
    client = authentication.client()
    project = create_project(client)
    result = client.post(
        f"/api/v1/agents/design-planning/{project['agent_project_id']}/run",
        json={"SRS": "A usable SRS", "selected_outputs": ["EPICS"]},
    ).json()["data"]
    assert result["status"] == "FAILED"
    assert result["errors"][0]["code"] == "STRUCTURED_OUTPUT_INVALID"
    assert result["errors"][0]["details"]["findings"][0]["code"] == "SOURCE_REFERENCE_INVALID"
    assert len(provider.calls) == 3


def test_successful_correction_is_visible_in_persisted_run(agent2_context):
    authentication, _, runs, _ = agent2_context
    provider = SequenceProvider([
        {"EPICS": [{**EPICS[0], "source_refs": ["SPEC-999"]}]},
        {"EPICS": EPICS},
    ])
    app.dependency_overrides[get_agent2_engine] = lambda: Agent2Engine(provider)
    client = authentication.client()
    project = create_project(client)
    result = client.post(
        f"/api/v1/agents/design-planning/{project['agent_project_id']}/run",
        json={"requirements": "A valid requirement", "selected_outputs": ["EPICS"]},
    ).json()["data"]
    assert result["status"] == "COMPLETED"
    assert result["correction_attempts"] == 1
    correction = next(item for item in result["warnings"] if item["code"] == "OUTPUT_CORRECTED")
    assert correction["details"]["correction_attempts"] == 1
    assert runs.documents[result["run_id"]]["status"].value == "COMPLETED"


def test_jira_plan_is_structured_and_never_claims_sync(agent2_context):
    authentication, _, _, provider = agent2_context
    provider.response = {"JIRA_PLAN": {
        "epics": EPICS, "stories": STORIES, "tasks": TASKS,
        "sprints": SPRINTS, "assignments": ASSIGNMENTS,
        "priorities": [{"item_id": "STORY-001", "priority": "HIGH"}],
        "synchronization": "NOT_PERFORMED",
    }}
    client = authentication.client()
    project = create_project(client)
    result = client.post(
        f"/api/v1/agents/design-planning/{project['agent_project_id']}/run",
        json={"requirements": "Guests book rooms", "development_team_count": 1, "selected_outputs": ["JIRA_PLAN"]},
    ).json()["data"]
    assert result["outputs"]["JIRA_PLAN"]["synchronization"] == "NOT_PERFORMED"
    assert {"epics", "stories", "tasks", "sprints", "assignments", "priorities"}.issubset(result["outputs"]["JIRA_PLAN"])
    assert any(item["code"] == "JIRA_NOT_SYNCHRONIZED" for item in result["warnings"])


def test_cross_artifact_design_references_are_validated_and_traceable():
    outputs = {
        "SYSTEM_ARCHITECTURE": {
            "style": "Layered", "components": [{
                "id": "COMP-001", "name": "Booking API", "responsibility": "Manage bookings",
                "dependencies": [], "source_refs": ["SPEC-001"],
            }], "boundaries": [], "interactions": [], "constraints": [], "assumptions": [],
        },
        "DATABASE_SCHEMA": {
            "technology": "PostgreSQL", "entities": [{
                "id": "ENTITY-001", "name": "Booking", "fields": [{
                    "name": "id", "data_type": "UUID", "required": True, "constraints": ["PRIMARY KEY"],
                }], "relationships": [], "source_refs": ["SPEC-001"],
            }], "assumptions": [],
        },
        "API_SPECIFICATION": {
            "base_path": "/api/v1", "operations": [{
                "id": "API-001", "method": "POST", "path": "/bookings", "summary": "Create booking",
                "request": "Booking details", "response": "Created booking", "errors": ["409 conflict"],
                "authentication": "Bearer", "source_refs": ["SPEC-001"],
                "component_refs": ["COMP-001"], "entity_refs": ["ENTITY-001"],
            }], "assumptions": [],
        },
        "WIREFRAMES": {"fidelity": "STRUCTURED_LOW_FIDELITY", "screens": [{
            "id": "WF-001", "name": "Booking form", "purpose": "Create booking",
            "regions": ["Form"], "interactions": ["Submit"], "components": ["Date picker"],
            "source_refs": ["SPEC-001"],
        }], "assumptions": []},
        "UI_FLOW": {"flows": [{
            "id": "FLOW-001", "actor": "Guest", "goal": "Book", "steps": ["Complete form"],
            "alternate_paths": [], "screen_refs": ["WF-001"], "source_refs": ["SPEC-001"],
        }]},
    }
    context = Agent2InputContext(
        project_name="BookEase", domain="Hospitality",
        specification_sources=[{"source_id": "SPEC-001", "source_type": "REQUIREMENTS", "content": "Book rooms"}],
    )
    selected = [DesignPlanningOutputCode(code) for code in outputs]
    result = Agent2Engine(FixedProvider(outputs)).execute(context, selected)
    assert result["API_SPECIFICATION"]["operations"][0]["component_refs"] == ["COMP-001"]
    assert result["UI_FLOW"]["flows"][0]["screen_refs"] == ["WF-001"]


def test_cross_artifact_validation_is_selected_output_aware():
    api_only = {
        "API_SPECIFICATION": {
            "base_path": "/api/v1", "operations": [{
                "id": "API-001", "method": "GET", "path": "/bookings", "summary": "List bookings",
                "request": None, "response": "Booking list", "errors": [], "authentication": "Bearer",
                "source_refs": ["SPEC-001"], "component_refs": ["COMP-999"], "entity_refs": ["ENTITY-999"],
            }], "assumptions": [],
        },
    }
    context = Agent2InputContext(
        project_name="BookEase", domain="Hospitality",
        specification_sources=[{"source_id": "SPEC-001", "source_type": "SRS", "content": "List bookings"}],
    )
    result = Agent2Engine(FixedProvider(api_only)).execute(
        context, [DesignPlanningOutputCode.API_SPECIFICATION]
    )
    assert result["API_SPECIFICATION"]["operations"][0]["id"] == "API-001"


def test_invalid_generated_reference_is_corrected_once():
    invalid = {"EPICS": [{**EPICS[0], "source_refs": ["SPEC-999"]}]}
    valid = {"EPICS": EPICS}
    provider = SequenceProvider([invalid, valid])
    context = Agent2InputContext(
        project_name="BookEase", domain="Hospitality",
        specification_sources=[{"source_id": "SPEC-001", "source_type": "REQUIREMENTS", "content": "Book"}],
    )
    execution = Agent2Engine(provider).execute_with_metadata(context, [DesignPlanningOutputCode.EPICS])
    assert execution.correction_attempts == 1
    assert len(provider.calls) == 2
    assert "SOURCE_REFERENCE_INVALID" in provider.calls[1]["user_prompt"]


def test_bounded_correction_exhausts_after_two_attempts():
    invalid = {"EPICS": [{**EPICS[0], "source_refs": ["SPEC-999"]}]}
    provider = SequenceProvider([invalid])
    context = Agent2InputContext(
        project_name="BookEase", domain="Hospitality",
        specification_sources=[{"source_id": "SPEC-001", "source_type": "REQUIREMENTS", "content": "Book"}],
    )
    with pytest.raises(ValueError, match="after 2 correction attempts") as error:
        Agent2Engine(provider).execute(context, [DesignPlanningOutputCode.EPICS])
    assert len(provider.calls) == 3
    assert error.value.findings[0].code == "SOURCE_REFERENCE_INVALID"


def test_deterministic_user_error_never_calls_provider(agent2_context):
    authentication, _, _, provider = agent2_context
    client = authentication.client()
    project = create_project(client)
    response = client.post(
        f"/api/v1/agents/design-planning/{project['agent_project_id']}/run",
        json={"requirements": "Valid", "selected_outputs": ["SPRINT_PLAN"]},
    )
    assert response.status_code == 422
    assert provider.calls == []


def test_sprint_capacity_utilization_and_duration_warning_are_deterministic():
    outputs = {"TASKS": TASKS, "SPRINT_PLAN": SPRINTS}
    context = Agent2InputContext(
        project_name="BookEase", domain="Hospitality",
        specification_sources=[{"source_id": "SPEC-001", "source_type": "REQUIREMENTS", "content": "Book"}],
        development_team_count=2, sprint_duration=10, expected_project_duration="5 days",
    )
    execution = Agent2Engine(FixedProvider(outputs)).execute_with_metadata(
        context, [DesignPlanningOutputCode.TASKS, DesignPlanningOutputCode.SPRINT_PLAN]
    )
    sprint = execution.outputs["SPRINT_PLAN"][0]
    assert sprint["capacity_points"] == 20
    assert sprint["planned_points"] == 3
    assert sprint["utilization_percent"] == 15.0
    assert any("outside" in warning for warning in sprint["planning_warnings"])
    assert any(item.severity == "WARNING" for item in execution.validation_findings)


def test_dependency_order_across_sprints_is_corrected():
    dependent = {**TASKS[0], "id": "TASK-002", "title": "Expose booking API", "depends_on": ["TASK-001"]}
    tasks = [TASKS[0], dependent]
    wrong = {
        "TASKS": tasks,
        "SPRINT_PLAN": [
            {**SPRINTS[0], "id": "SPRINT-001", "item_refs": ["TASK-002"]},
            {**SPRINTS[0], "id": "SPRINT-002", "name": "Sprint 2", "item_refs": ["TASK-001"]},
        ],
    }
    corrected = deepcopy(wrong)
    corrected["SPRINT_PLAN"][0]["item_refs"] = ["TASK-001"]
    corrected["SPRINT_PLAN"][1]["item_refs"] = ["TASK-002"]
    provider = SequenceProvider([wrong, corrected])
    context = Agent2InputContext(
        project_name="BookEase", domain="Hospitality",
        specification_sources=[{"source_id": "SPEC-001", "source_type": "REQUIREMENTS", "content": "Book"}],
        development_team_count=1, sprint_duration=10,
    )
    execution = Agent2Engine(provider).execute_with_metadata(
        context, [DesignPlanningOutputCode.TASKS, DesignPlanningOutputCode.SPRINT_PLAN]
    )
    assert execution.correction_attempts == 1
    assert execution.outputs["SPRINT_PLAN"][0]["item_refs"] == ["TASK-001"]


def test_skill_aware_assignment_uses_only_supplied_developers():
    frontend_task = {
        **TASKS[0], "id": "TASK-002", "title": "Build React booking screen",
        "description": "Implement UI", "required_skills": ["React"], "depends_on": ["TASK-001"],
    }
    outputs = {"TASKS": [TASKS[0], frontend_task], "TASK_ASSIGNMENT": ASSIGNMENTS}
    context = Agent2InputContext(
        project_name="BookEase", domain="Hospitality",
        specification_sources=[{"source_id": "SPEC-001", "source_type": "REQUIREMENTS", "content": "Book"}],
        development_team_count=2,
        team_composition="Alice: Backend Developer | Python, API; Bob: Frontend Developer | React",
    )
    result = Agent2Engine(FixedProvider(outputs)).execute(
        context, [DesignPlanningOutputCode.TASKS, DesignPlanningOutputCode.TASK_ASSIGNMENT]
    )
    by_task = {item["task_id"]: item for item in result["TASK_ASSIGNMENT"]}
    assert by_task["TASK-001"]["team_slot"] == "Alice"
    assert by_task["TASK-002"]["team_slot"] == "Bob"
    assert by_task["TASK-002"]["skill_matches"] == ["React"]
    assert by_task["TASK-002"]["confidence_score"] > 0


def test_assignment_without_details_uses_generic_team_slots():
    outputs = {"TASKS": TASKS, "TASK_ASSIGNMENT": ASSIGNMENTS}
    context = Agent2InputContext(
        project_name="BookEase", domain="Hospitality",
        specification_sources=[{"source_id": "SPEC-001", "source_type": "REQUIREMENTS", "content": "Book"}],
        development_team_count=1,
    )
    result = Agent2Engine(FixedProvider(outputs)).execute(
        context, [DesignPlanningOutputCode.TASKS, DesignPlanningOutputCode.TASK_ASSIGNMENT]
    )
    assignment = result["TASK_ASSIGNMENT"][0]
    assert assignment["team_slot"] == "Team member 1"
    assert "No named developer" in assignment["rationale"]


def test_historical_agent2_run_retrieval(agent2_context):
    authentication, _, _, provider = agent2_context
    provider.response = {
        "SYSTEM_ARCHITECTURE": {
            "style": "Layered",
            "components": [{
                "id": "COMP-001",
                "name": "Booking Service",
                "responsibility": "Manage reservations",
                "dependencies": [],
                "source_refs": ["SPEC-001"],
            }],
            "boundaries": ["API boundary"],
            "interactions": ["REST"],
            "constraints": ["Single region"],
            "assumptions": ["PostgreSQL backing store"],
        },
        "EPICS": EPICS,
    }
    client = authentication.client()
    project = create_project(client)
    run_response = client.post(
        f"/api/v1/agents/design-planning/{project['agent_project_id']}/run",
        json={
            "requirements": "Guests need to reserve rooms online.",
            "selected_outputs": ["SYSTEM_ARCHITECTURE", "EPICS"],
        },
    )
    assert run_response.status_code == 200
    completed_run = run_response.json()["data"]
    assert completed_run["status"] == "COMPLETED"
    assert completed_run["correction_attempts"] == 0
    run_id = completed_run["run_id"]
    agent_project_id = project["agent_project_id"]

    # Retrieve historical run via shared standalone endpoint
    retrieval_response = client.get(
        f"/api/v1/agent-projects/{agent_project_id}/runs/{run_id}"
    )
    assert retrieval_response.status_code == 200
    retrieved_data = retrieval_response.json()["data"]

    # Verify fields match the completed run and historical requirements
    assert retrieved_data["run_id"] == run_id
    assert retrieved_data["agent_project_id"] == agent_project_id
    assert retrieved_data["agent_type"] == "DESIGN_PLANNING"
    assert retrieved_data["run_mode"] == "DEFAULT"
    assert retrieved_data["status"] == "COMPLETED"
    assert set(retrieved_data["selected_outputs"]) == {"SYSTEM_ARCHITECTURE", "EPICS"}
    assert retrieved_data["output_manifest"] == completed_run["outputs"]
    assert "SYSTEM_ARCHITECTURE" in retrieved_data["output_manifest"]
    assert "EPICS" in retrieved_data["output_manifest"]
    assert retrieved_data["warnings"] == completed_run["warnings"]
    assert retrieved_data["errors"] == []
    assert retrieved_data["started_at"] == completed_run["started_at"]
    assert retrieved_data["completed_at"] == completed_run["completed_at"]


def test_timeline_based_sprint_plan_accepts_dates_without_team_count(agent2_context):
    authentication, _, runs, provider = agent2_context
    provider.response = {"SPRINT_PLAN": SPRINTS}
    client = authentication.client()
    project = create_project(client)
    response = client.post(
        f"/api/v1/agents/design-planning/{project['agent_project_id']}/run",
        json={
            "requirements": "Build booking platform",
            "planning_mode": "TIMELINE_BASED",
            "project_start_date": "2026-11-01",
            "expected_project_duration": "2 months",
            "sprint_duration": 14,
            "selected_outputs": ["SPRINT_PLAN"],
        },
    )
    assert response.status_code == 200
    result = response.json()["data"]
    assert result["status"] == "COMPLETED"
    sprint = result["outputs"]["SPRINT_PLAN"][0]
    assert sprint["start_date"] == "2026-11-01"
    assert sprint["end_date"] == "2026-11-15"
    assert sprint["duration_days"] == 14
    assert sprint["capacity_points"] is None
    assert sprint["utilization_percent"] is None
    assert "Timeline-based" in sprint["estimate_basis"]


def test_missing_sprint_duration_blocks_timeline_planning(agent2_context):
    authentication, _, _, _ = agent2_context
    client = authentication.client()
    project = create_project(client)
    response = client.post(
        f"/api/v1/agents/design-planning/{project['agent_project_id']}/run",
        json={
            "requirements": "Build booking platform",
            "planning_mode": "TIMELINE_BASED",
            "project_start_date": "2026-11-01",
            "expected_project_duration": "2 months",
            "selected_outputs": ["SPRINT_PLAN"],
        },
    )
    assert response.status_code == 422
    assert "sprint_duration" in response.text


def test_missing_project_start_date_blocks_timeline_planning(agent2_context):
    authentication, _, _, _ = agent2_context
    client = authentication.client()
    project = create_project(client)
    response = client.post(
        f"/api/v1/agents/design-planning/{project['agent_project_id']}/run",
        json={
            "requirements": "Build booking platform",
            "planning_mode": "TIMELINE_BASED",
            "expected_project_duration": "2 months",
            "sprint_duration": 14,
            "selected_outputs": ["SPRINT_PLAN"],
        },
    )
    assert response.status_code == 422
    assert "project_start_date" in response.text


def test_capacity_aware_sprint_plan_requires_team_count(agent2_context):
    authentication, _, _, _ = agent2_context
    client = authentication.client()
    project = create_project(client)
    response = client.post(
        f"/api/v1/agents/design-planning/{project['agent_project_id']}/run",
        json={
            "requirements": "Build booking platform",
            "planning_mode": "CAPACITY_AWARE",
            "project_start_date": "2026-11-01",
            "expected_project_duration": "2 months",
            "sprint_duration": 14,
            "selected_outputs": ["SPRINT_PLAN"],
        },
    )
    assert response.status_code == 422
    assert "development_team_count" in response.text


def test_task_assignment_requires_development_team_count(agent2_context):
    authentication, _, _, _ = agent2_context
    client = authentication.client()
    project = create_project(client)
    response = client.post(
        f"/api/v1/agents/design-planning/{project['agent_project_id']}/run",
        json={
            "requirements": "Build booking platform",
            "selected_outputs": ["TASK_ASSIGNMENT"],
        },
    )
    assert response.status_code == 422
    assert "development_team_count" in response.text


def test_jira_plan_alone_does_not_require_development_team_count(agent2_context):
    authentication, _, _, provider = agent2_context
    provider.response = {"JIRA_PLAN": {
        "epics": EPICS, "stories": STORIES, "tasks": TASKS,
        "sprints": SPRINTS, "assignments": [],
        "priorities": [{"item_id": "STORY-001", "priority": "HIGH"}],
        "synchronization": "NOT_PERFORMED",
    }}
    client = authentication.client()
    project = create_project(client)
    response = client.post(
        f"/api/v1/agents/design-planning/{project['agent_project_id']}/run",
        json={
            "requirements": "Guests book rooms",
            "selected_outputs": ["JIRA_PLAN"],
        },
    )
    assert response.status_code == 200
    result = response.json()["data"]
    assert result["status"] == "COMPLETED"
    assert result["outputs"]["JIRA_PLAN"]["assignments"] == []


def test_sprint_plan_and_jira_plan_work_without_task_assignment(agent2_context):
    authentication, _, _, provider = agent2_context
    provider.response = {
        "SPRINT_PLAN": SPRINTS,
        "JIRA_PLAN": {
            "epics": EPICS, "stories": STORIES, "tasks": TASKS,
            "sprints": SPRINTS, "assignments": [],
            "priorities": [{"item_id": "STORY-001", "priority": "HIGH"}],
            "synchronization": "NOT_PERFORMED",
        },
    }
    client = authentication.client()
    project = create_project(client)
    response = client.post(
        f"/api/v1/agents/design-planning/{project['agent_project_id']}/run",
        json={
            "requirements": "Guests book rooms",
            "planning_mode": "TIMELINE_BASED",
            "project_start_date": "2026-11-01",
            "expected_project_duration": "60 days",
            "sprint_duration": 14,
            "selected_outputs": ["SPRINT_PLAN", "JIRA_PLAN"],
        },
    )
    assert response.status_code == 200
    result = response.json()["data"]
    assert result["status"] == "COMPLETED"
    assert result["outputs"]["JIRA_PLAN"]["assignments"] == []
    assert result["outputs"]["SPRINT_PLAN"][0]["start_date"] == "2026-11-01"


def test_target_scenario_timeline_planning_all_seven_outputs_without_task_assignment(agent2_context):
    authentication, _, _, provider = agent2_context
    provider.response = {
        "PRODUCT_BACKLOG": [
            {"item_id": "EPIC-001", "item_type": "EPIC", "title": "Booking", "priority": "HIGH", "parent_id": None, "source_refs": ["SPEC-001"]},
            {"item_id": "FEATURE-001", "item_type": "FEATURE", "title": "Create booking", "priority": "HIGH", "parent_id": "EPIC-001", "source_refs": ["SPEC-001"]},
            {"item_id": "STORY-001", "item_type": "STORY", "title": "Book a room", "priority": "HIGH", "parent_id": "FEATURE-001", "source_refs": ["SPEC-001"]},
            {"item_id": "TASK-001", "item_type": "TASK", "title": "Implement booking", "priority": "HIGH", "parent_id": "STORY-001", "source_refs": ["SPEC-001"]},
        ],
        "EPICS": EPICS,
        "FEATURES": FEATURES,
        "USER_STORIES": STORIES,
        "TASKS": TASKS,
        "SPRINT_PLAN": SPRINTS,
        "JIRA_PLAN": {
            "epics": EPICS,
            "stories": STORIES,
            "tasks": TASKS,
            "sprints": SPRINTS,
            "assignments": [],
            "priorities": [{"item_id": "STORY-001", "priority": "HIGH"}],
            "synchronization": "NOT_PERFORMED",
        },
    }
    client = authentication.client()
    project = create_project(client)
    selected_outputs = [
        "PRODUCT_BACKLOG",
        "EPICS",
        "FEATURES",
        "USER_STORIES",
        "TASKS",
        "SPRINT_PLAN",
        "JIRA_PLAN",
    ]
    response = client.post(
        f"/api/v1/agents/design-planning/{project['agent_project_id']}/run",
        json={
            "requirements": "Guests book rooms online",
            "planning_mode": "TIMELINE_BASED",
            "project_start_date": "2026-11-01",
            "expected_project_duration": "60 days",
            "sprint_duration": 14,
            "selected_outputs": selected_outputs,
        },
    )
    assert response.status_code == 200
    result = response.json()["data"]
    assert result["status"] == "COMPLETED"
    for code in selected_outputs:
        assert code in result["outputs"]
    assert "TASK_ASSIGNMENT" not in result["outputs"]
    sprint = result["outputs"]["SPRINT_PLAN"][0]
    assert sprint["start_date"] == "2026-11-01"
    assert sprint["duration_days"] == 14
    assert sprint["capacity_points"] is None
    assert "Timeline-based" in sprint["estimate_basis"]
    assert "TASK-001" in sprint["item_refs"]
    jira = result["outputs"]["JIRA_PLAN"]
    assert jira["assignments"] == []
    assert jira["synchronization"] == "NOT_PERFORMED"


class CallTrackingProvider:
    def __init__(self, handler=None):
        self.calls = []
        self._handler = handler

    def generate_structured(self, **kwargs):
        self.calls.append(kwargs)
        if self._handler:
            return self._handler(kwargs)
        properties = kwargs.get("json_schema", {}).get("properties", {})
        return {key: [] for key in properties}


def test_target_7_output_jira_scenario_uses_staged_generation_and_dependency_order():
    stage1_response = {
        "PRODUCT_BACKLOG": [
            {"item_id": "EPIC-001", "item_type": "EPIC", "title": "Booking", "priority": "HIGH", "parent_id": None, "source_refs": ["SPEC-001"]},
            {"item_id": "FEATURE-001", "item_type": "FEATURE", "title": "Create booking", "priority": "HIGH", "parent_id": "EPIC-001", "source_refs": ["SPEC-001"]},
            {"item_id": "STORY-001", "item_type": "STORY", "title": "Book a room", "priority": "HIGH", "parent_id": "FEATURE-001", "source_refs": ["SPEC-001"]},
            {"item_id": "TASK-001", "item_type": "TASK", "title": "Implement booking", "priority": "HIGH", "parent_id": "STORY-001", "source_refs": ["SPEC-001"]},
        ],
        "EPICS": EPICS,
        "FEATURES": FEATURES,
    }
    stage2_response = {
        "USER_STORIES": STORIES,
        "TASKS": TASKS,
    }
    stage3_response = {
        "SPRINT_PLAN": SPRINTS,
    }

    call_index = 0
    def handler(kwargs):
        nonlocal call_index
        schema_props = set(kwargs["json_schema"]["properties"].keys())
        call_index += 1
        if schema_props == {"PRODUCT_BACKLOG", "EPICS", "FEATURES"}:
            return deepcopy(stage1_response)
        elif schema_props == {"USER_STORIES", "TASKS"}:
            return deepcopy(stage2_response)
        elif schema_props == {"SPRINT_PLAN"}:
            return deepcopy(stage3_response)
        raise ValueError(f"Unexpected stage schema: {schema_props}")

    provider = CallTrackingProvider(handler=handler)
    engine = Agent2Engine(provider)
    context = Agent2InputContext(
        project_name="BookEase",
        domain="Hospitality",
        specification_sources=[{"source_id": "SPEC-001", "source_type": "REQUIREMENTS", "content": "Guests book rooms online"}],
        planning_mode="TIMELINE_BASED",
        project_start_date="2026-11-01",
        expected_project_duration="60 days",
        sprint_duration=14,
    )
    selected_outputs = [
        DesignPlanningOutputCode.PRODUCT_BACKLOG,
        DesignPlanningOutputCode.EPICS,
        DesignPlanningOutputCode.FEATURES,
        DesignPlanningOutputCode.USER_STORIES,
        DesignPlanningOutputCode.TASKS,
        DesignPlanningOutputCode.SPRINT_PLAN,
        DesignPlanningOutputCode.JIRA_PLAN,
    ]

    execution = engine.execute_with_metadata(context, selected_outputs)

    # 1. Target 7-output Jira scenario uses staged generation (exactly 3 calls: Stage 1, Stage 2, Stage 3)
    assert len(provider.calls) == 3

    # 2. Correct stage dependency order
    call_0_keys = set(provider.calls[0]["json_schema"]["properties"].keys())
    call_1_keys = set(provider.calls[1]["json_schema"]["properties"].keys())
    call_2_keys = set(provider.calls[2]["json_schema"]["properties"].keys())
    assert call_0_keys == {"PRODUCT_BACKLOG", "EPICS", "FEATURES"}
    assert call_1_keys == {"USER_STORIES", "TASKS"}
    assert call_2_keys == {"SPRINT_PLAN"}

    # Compact dependency context passed to later stages
    assert "Stage 1" in provider.calls[1]["user_prompt"]
    assert "EPIC-001" in provider.calls[1]["user_prompt"]
    assert "TASK-001" in provider.calls[2]["user_prompt"]

    # 3. JIRA_PLAN constructed deterministically from validated artifacts
    assert "JIRA_PLAN" in execution.outputs
    assert execution.outputs["JIRA_PLAN"]["epics"] == EPICS
    assert execution.outputs["JIRA_PLAN"]["stories"] == STORIES
    assert execution.outputs["JIRA_PLAN"]["tasks"] == TASKS
    assert execution.outputs["JIRA_PLAN"]["sprints"][0]["start_date"] == "2026-11-01"
    assert execution.outputs["JIRA_PLAN"]["synchronization"] == "NOT_PERFORMED"

    # 4. Final output contains exactly selected outputs
    assert set(execution.outputs.keys()) == {c.value for c in selected_outputs}
    assert "TASK_ASSIGNMENT" not in execution.outputs

    # 5. SPRINT_PLAN is timeline-based
    sprint = execution.outputs["SPRINT_PLAN"][0]
    assert sprint["start_date"] == "2026-11-01"
    assert sprint["duration_days"] == 14
    assert sprint["capacity_points"] is None
    assert "Timeline-based" in sprint["estimate_basis"]


def test_valid_stage_1_not_regenerated_when_stage_2_correction_occurs():
    stage1_response = {
        "PRODUCT_BACKLOG": [
            {"item_id": "EPIC-001", "item_type": "EPIC", "title": "Booking", "priority": "HIGH", "parent_id": None, "source_refs": ["SPEC-001"]},
            {"item_id": "FEATURE-001", "item_type": "FEATURE", "title": "Create booking", "priority": "HIGH", "parent_id": "EPIC-001", "source_refs": ["SPEC-001"]},
        ],
        "EPICS": EPICS,
        "FEATURES": FEATURES,
    }
    # Invalid Stage 2 (references non-existent EPIC-999)
    invalid_stage2 = {
        "USER_STORIES": [{**STORIES[0], "epic_id": "EPIC-999"}],
        "TASKS": [{**TASKS[0], "epic_id": "EPIC-999"}],
    }
    # Corrected Stage 2
    valid_stage2 = {
        "USER_STORIES": STORIES,
        "TASKS": TASKS,
    }
    stage3_response = {
        "SPRINT_PLAN": SPRINTS,
    }

    call_records = []
    def handler(kwargs):
        props = set(kwargs["json_schema"]["properties"].keys())
        call_records.append((props, kwargs["user_prompt"]))
        if props == {"PRODUCT_BACKLOG", "EPICS", "FEATURES"}:
            return deepcopy(stage1_response)
        elif props == {"USER_STORIES", "TASKS"}:
            if len([p for p, _ in call_records if p == {"USER_STORIES", "TASKS"}]) == 1:
                return deepcopy(invalid_stage2)
            return deepcopy(valid_stage2)
        elif props == {"SPRINT_PLAN"}:
            return deepcopy(stage3_response)
        raise ValueError(f"Unexpected stage: {props}")

    provider = CallTrackingProvider(handler=handler)
    engine = Agent2Engine(provider)
    context = Agent2InputContext(
        project_name="BookEase",
        domain="Hospitality",
        specification_sources=[{"source_id": "SPEC-001", "source_type": "REQUIREMENTS", "content": "Guests book rooms online"}],
        planning_mode="TIMELINE_BASED",
        project_start_date="2026-11-01",
        expected_project_duration="60 days",
        sprint_duration=14,
    )
    selected_outputs = [
        DesignPlanningOutputCode.PRODUCT_BACKLOG,
        DesignPlanningOutputCode.EPICS,
        DesignPlanningOutputCode.FEATURES,
        DesignPlanningOutputCode.USER_STORIES,
        DesignPlanningOutputCode.TASKS,
        DesignPlanningOutputCode.SPRINT_PLAN,
        DesignPlanningOutputCode.JIRA_PLAN,
    ]

    execution = engine.execute_with_metadata(context, selected_outputs)

    assert len(call_records) == 4
    stage_schemas = [p for p, _ in call_records]
    assert stage_schemas[0] == {"PRODUCT_BACKLOG", "EPICS", "FEATURES"}
    assert stage_schemas[1] == {"USER_STORIES", "TASKS"}
    assert stage_schemas[2] == {"USER_STORIES", "TASKS"}
    assert stage_schemas[3] == {"SPRINT_PLAN"}

    # Stage 1 was called EXACTLY ONCE and NEVER regenerated during Stage 2's correction
    stage1_call_count = sum(1 for s in stage_schemas if s == {"PRODUCT_BACKLOG", "EPICS", "FEATURES"})
    assert stage1_call_count == 1

    # Stage 2 correction prompt included validation findings and asked only for Stage 2
    assert "Correction attempt 1 of 2" in call_records[2][1]
    assert "STORY_EPIC_REFERENCE_INVALID" in call_records[2][1]

    assert execution.correction_attempts == 1
    assert "JIRA_PLAN" in execution.outputs


def test_schema_pattern_regex_removed_for_model_provider_but_validated_in_pydantic():
    from app.modules.agents.design_planning.engine import selected_schema
    from pydantic import TypeAdapter, ValidationError
    from app.modules.agents.design_planning.schemas import OUTPUT_MODELS

    selected = [
        DesignPlanningOutputCode.EPICS,
        DesignPlanningOutputCode.FEATURES,
        DesignPlanningOutputCode.USER_STORIES,
        DesignPlanningOutputCode.TASKS,
        DesignPlanningOutputCode.SPRINT_PLAN,
    ]
    schema = selected_schema(selected)

    def check_no_pattern(node):
        if isinstance(node, dict):
            assert "pattern" not in node, f"Found pattern in schema node: {node}"
            for v in node.values():
                check_no_pattern(v)
        elif isinstance(node, list):
            for v in node:
                check_no_pattern(v)

    check_no_pattern(schema)

    bad_epics = [{**EPICS[0], "id": "INVALID_ID"}]
    with pytest.raises(ValidationError):
        TypeAdapter(OUTPUT_MODELS[DesignPlanningOutputCode.EPICS]).validate_python(bad_epics)


def test_ids_and_references_survive_stage_merge():
    stage1_response = {
        "PRODUCT_BACKLOG": [
            {"item_id": "EPIC-001", "item_type": "EPIC", "title": "Booking", "priority": "HIGH", "parent_id": None, "source_refs": ["SPEC-001"]},
            {"item_id": "FEATURE-001", "item_type": "FEATURE", "title": "Create booking", "priority": "HIGH", "parent_id": "EPIC-001", "source_refs": ["SPEC-001"]},
            {"item_id": "STORY-001", "item_type": "STORY", "title": "Book a room", "priority": "HIGH", "parent_id": "FEATURE-001", "source_refs": ["SPEC-001"]},
            {"item_id": "TASK-001", "item_type": "TASK", "title": "Implement booking", "priority": "HIGH", "parent_id": "STORY-001", "source_refs": ["SPEC-001"]},
        ],
        "EPICS": EPICS,
        "FEATURES": FEATURES,
    }
    stage2_response = {
        "USER_STORIES": STORIES,
        "TASKS": TASKS,
    }
    stage3_response = {
        "SPRINT_PLAN": SPRINTS,
    }

    def handler(kwargs):
        props = set(kwargs["json_schema"]["properties"].keys())
        if props == {"PRODUCT_BACKLOG", "EPICS", "FEATURES"}:
            return deepcopy(stage1_response)
        elif props == {"USER_STORIES", "TASKS"}:
            return deepcopy(stage2_response)
        elif props == {"SPRINT_PLAN"}:
            return deepcopy(stage3_response)
        raise ValueError(f"Unexpected stage schema: {props}")

    provider = CallTrackingProvider(handler=handler)
    engine = Agent2Engine(provider)
    context = Agent2InputContext(
        project_name="BookEase",
        domain="Hospitality",
        specification_sources=[{"source_id": "SPEC-001", "source_type": "REQUIREMENTS", "content": "Guests book rooms online"}],
        planning_mode="TIMELINE_BASED",
        project_start_date="2026-11-01",
        expected_project_duration="60 days",
        sprint_duration=14,
    )
    selected_outputs = [
        DesignPlanningOutputCode.PRODUCT_BACKLOG,
        DesignPlanningOutputCode.EPICS,
        DesignPlanningOutputCode.FEATURES,
        DesignPlanningOutputCode.USER_STORIES,
        DesignPlanningOutputCode.TASKS,
        DesignPlanningOutputCode.SPRINT_PLAN,
        DesignPlanningOutputCode.JIRA_PLAN,
    ]

    execution = engine.execute_with_metadata(context, selected_outputs)
    outputs = execution.outputs

    epic_id = outputs["EPICS"][0]["id"]
    assert outputs["FEATURES"][0]["epic_id"] == epic_id
    assert outputs["USER_STORIES"][0]["epic_id"] == epic_id
    assert outputs["TASKS"][0]["epic_id"] == epic_id
    assert outputs["JIRA_PLAN"]["epics"][0]["id"] == epic_id

    feature_id = outputs["FEATURES"][0]["id"]
    assert outputs["USER_STORIES"][0]["feature_id"] == feature_id
    assert outputs["TASKS"][0]["feature_id"] == feature_id

    story_id = outputs["USER_STORIES"][0]["id"]
    assert outputs["TASKS"][0]["story_id"] == story_id
    assert outputs["JIRA_PLAN"]["stories"][0]["id"] == story_id

    task_id = outputs["TASKS"][0]["id"]
    assert task_id in outputs["SPRINT_PLAN"][0]["item_refs"]
    assert outputs["JIRA_PLAN"]["tasks"][0]["id"] == task_id

    priority_ids = {p["item_id"] for p in outputs["JIRA_PLAN"]["priorities"]}
    assert epic_id in priority_ids
    assert story_id in priority_ids

    from app.modules.agents.design_planning.validation import collect_consistency_findings
    findings = collect_consistency_findings(context, outputs)
    assert not any(f.severity == "ERROR" for f in findings)


def test_staged_jira_plan_compatible_with_preview():
    stage1_response = {
        "PRODUCT_BACKLOG": [
            {"item_id": "EPIC-001", "item_type": "EPIC", "title": "Booking", "priority": "HIGH", "parent_id": None, "source_refs": ["SPEC-001"]},
            {"item_id": "FEATURE-001", "item_type": "FEATURE", "title": "Create booking", "priority": "HIGH", "parent_id": "EPIC-001", "source_refs": ["SPEC-001"]},
            {"item_id": "STORY-001", "item_type": "STORY", "title": "Book a room", "priority": "HIGH", "parent_id": "FEATURE-001", "source_refs": ["SPEC-001"]},
            {"item_id": "TASK-001", "item_type": "TASK", "title": "Implement booking", "priority": "HIGH", "parent_id": "STORY-001", "source_refs": ["SPEC-001"]},
        ],
        "EPICS": EPICS,
        "FEATURES": FEATURES,
    }
    stage2_response = {
        "USER_STORIES": STORIES,
        "TASKS": TASKS,
    }
    stage3_response = {
        "SPRINT_PLAN": SPRINTS,
    }

    def handler(kwargs):
        props = set(kwargs["json_schema"]["properties"].keys())
        if props == {"PRODUCT_BACKLOG", "EPICS", "FEATURES"}:
            return deepcopy(stage1_response)
        elif props == {"USER_STORIES", "TASKS"}:
            return deepcopy(stage2_response)
        elif props == {"SPRINT_PLAN"}:
            return deepcopy(stage3_response)
        raise ValueError(f"Unexpected stage schema: {props}")

    provider = CallTrackingProvider(handler=handler)
    engine = Agent2Engine(provider)
    context = Agent2InputContext(
        project_name="BookEase",
        domain="Hospitality",
        specification_sources=[{"source_id": "SPEC-001", "source_type": "REQUIREMENTS", "content": "Guests book rooms online"}],
        planning_mode="TIMELINE_BASED",
        project_start_date="2026-11-01",
        expected_project_duration="60 days",
        sprint_duration=14,
    )
    selected_outputs = [
        DesignPlanningOutputCode.PRODUCT_BACKLOG,
        DesignPlanningOutputCode.EPICS,
        DesignPlanningOutputCode.FEATURES,
        DesignPlanningOutputCode.USER_STORIES,
        DesignPlanningOutputCode.TASKS,
        DesignPlanningOutputCode.SPRINT_PLAN,
        DesignPlanningOutputCode.JIRA_PLAN,
    ]

    execution = engine.execute_with_metadata(context, selected_outputs)
    outputs = execution.outputs

    from app.modules.agents.design_planning.schemas import JiraPlan
    validated_plan = JiraPlan.model_validate(outputs["JIRA_PLAN"])
    assert len(validated_plan.epics) == 1
    assert len(validated_plan.stories) == 1
    assert len(validated_plan.tasks) == 1
    assert len(validated_plan.sprints) == 1
    assert validated_plan.synchronization == "NOT_PERFORMED"


def test_pydantic_error_paths_and_types_are_captured_safely():
    raw = {
        "FEATURES": [{
            "id": "FEAT-001",
            "epic_id": "EPIC-001",
            "title": "Room Search",
            "description": "Filter by date",
            "source_refs": ["SPEC-001"],
        }]
    }
    validated, findings = Agent2Engine._validate_schema(raw, [DesignPlanningOutputCode.FEATURES])
    assert validated is None
    assert len(findings) == 1
    finding = findings[0]
    assert finding.code == "SCHEMA_VALIDATION_FAILED"
    assert finding.path == "FEATURES.0.id"
    assert "string_pattern_mismatch" in finding.message
    assert "FEATURES" in finding.message
    assert "FEAT-001" not in finding.message


def test_canonical_id_guidance_exists_after_regex_stripping():
    from app.modules.agents.design_planning.engine import selected_schema, SYSTEM_PROMPT
    schema = selected_schema([DesignPlanningOutputCode.EPICS, DesignPlanningOutputCode.FEATURES])

    assert "pattern" not in json.dumps(schema)

    features_def = schema["$defs"]["Feature"]["properties"]
    assert "FEATURE-001" in features_def["id"]["description"]
    assert "EPIC-001" in features_def["epic_id"]["description"]

    assert "EPIC-001" in SYSTEM_PROMPT
    assert "FEATURE-001" in SYSTEM_PROMPT
    assert "FEAT-001" in SYSTEM_PROMPT


def test_id_format_pydantic_validation_rules():
    from app.modules.agents.design_planning.schemas import Epic, Feature
    from pydantic import TypeAdapter, ValidationError

    epic_adapter = TypeAdapter(Epic)
    feature_adapter = TypeAdapter(Feature)

    # EPIC-1 is rejected
    with pytest.raises(ValidationError):
        epic_adapter.validate_python({
            "id": "EPIC-1", "title": "Booking", "outcome": "Book rooms",
            "priority": "HIGH", "source_refs": ["SPEC-001"]
        })

    # EPIC-001 is accepted
    valid_epic = epic_adapter.validate_python({
        "id": "EPIC-001", "title": "Booking", "outcome": "Book rooms",
        "priority": "HIGH", "source_refs": ["SPEC-001"]
    })
    assert valid_epic.id == "EPIC-001"

    # FEATURE-1 is rejected
    with pytest.raises(ValidationError):
        feature_adapter.validate_python({
            "id": "FEATURE-1", "epic_id": "EPIC-001", "title": "Search",
            "description": "Search rooms", "source_refs": ["SPEC-001"]
        })

    # FEAT-001 is rejected
    with pytest.raises(ValidationError):
        feature_adapter.validate_python({
            "id": "FEAT-001", "epic_id": "EPIC-001", "title": "Search",
            "description": "Search rooms", "source_refs": ["SPEC-001"]
        })

    # FEATURE-001 is accepted
    valid_feature = feature_adapter.validate_python({
        "id": "FEATURE-001", "epic_id": "EPIC-001", "title": "Search",
        "description": "Search rooms", "source_refs": ["SPEC-001"]
    })
    assert valid_feature.id == "FEATURE-001"


def test_correction_receives_actionable_validation_findings():
    from app.modules.agents.design_planning.validation import ValidationFinding
    findings = [
        ValidationFinding(
            code="SCHEMA_VALIDATION_FAILED",
            message="FEATURES validation error (string_pattern_mismatch): String should match pattern '^FEATURE-\\d{3,}$'",
            path="FEATURES.0.id",
        )
    ]
    context = Agent2InputContext(
        project_name="BookEase", domain="Hospitality",
        specification_sources=[{"source_id": "SPEC-001", "source_type": "REQUIREMENTS", "content": "Book rooms"}],
    )
    prompt = Agent2Engine._build_stage_correction_prompt(
        context, [DesignPlanningOutputCode.FEATURES], {"FEATURES": []}, findings, attempt=1
    )

    assert "Field: FEATURES.0.id" in prompt
    assert "string_pattern_mismatch" in prompt
    assert "FEATURE IDs must strictly match format FEATURE-### (e.g. FEATURE-001" in prompt
