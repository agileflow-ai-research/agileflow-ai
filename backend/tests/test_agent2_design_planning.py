from copy import deepcopy

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
