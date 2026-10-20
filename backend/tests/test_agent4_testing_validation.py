from copy import deepcopy

import pytest

from app.main import app
from app.modules.standalone.router import get_agent_project_repository, get_agent_run_repository
from app.modules.agents.testing_validation.engine import Agent4Engine
from app.modules.agents.testing_validation.executor import (
    ToolExecutionError,
    ValidationCommandResult,
    ValidationExecutionResult,
)
from app.modules.agents.testing_validation.router import get_agent4_engine
from app.modules.agents.testing_validation.schemas import Agent4InputContext
from test_standalone_foundation import FakeAgentProjectRepository, FakeAgentRunRepository


TEST_CASE = {
    "id": "TEST-001", "title": "Create booking", "purpose": "Verify booking creation",
    "preconditions": ["Booking API is available"], "test_data": ["Valid booking"],
    "steps": ["Submit the booking"], "expected_result": "Booking is created",
    "source_refs": ["SRC-001"], "representation": "SPECIFICATION", "executable": False,
    "framework": None, "code": None, "execution_status": "NOT_EXECUTED",
}


class FixedProvider:
    def __init__(self, response):
        self.response = deepcopy(response)
        self.calls = []

    def generate_structured(self, **kwargs):
        self.calls.append(kwargs)
        return deepcopy(self.response)


def command_result(status="PASSED", exit_code=0, stdout="2 passed", stderr=""):
    return ValidationCommandResult(
        command=["python", "-m", "pytest"],
        tool="PYTHON_PYTEST",
        exit_code=exit_code,
        execution_status=status,
        stdout=stdout,
        stderr=stderr,
        evidence_metadata={"executor": "DOCKER", "network": "NONE"},
    )


class FixedExecutor:
    def __init__(self, evidence=None):
        self.evidence = evidence or command_result()
        self.calls = []

    def execute(self, request):
        self.calls.append(request)
        skipped = ValidationCommandResult(
            command=[], tool="NONE", exit_code=None, execution_status="SKIPPED",
            stdout="", stderr="", reason="No validation profile was selected",
        )
        tests = self.evidence if request.profile else skipped
        return ValidationExecutionResult(
            build=skipped, tests=tests,
            sandbox={"executor": "DOCKER", "network": "NONE", "profile": request.profile},
        )


class FailingExecutor:
    def __init__(self, message="Secure validation sandbox is unavailable"):
        self.message = message

    def execute(self, request):
        del request
        raise ToolExecutionError(self.message)


@pytest.fixture
def agent4_context(authentication_context):
    projects = FakeAgentProjectRepository()
    runs = FakeAgentRunRepository()
    provider = FixedProvider({"UNIT_TEST_CASES": [TEST_CASE]})
    runner = FixedExecutor()
    app.dependency_overrides[get_agent_project_repository] = lambda: projects
    app.dependency_overrides[get_agent_run_repository] = lambda: runs
    app.dependency_overrides[get_agent4_engine] = lambda: Agent4Engine(provider, runner)
    try:
        yield authentication_context, projects, runs, provider, runner
    finally:
        app.dependency_overrides.pop(get_agent_project_repository, None)
        app.dependency_overrides.pop(get_agent_run_repository, None)
        app.dependency_overrides.pop(get_agent4_engine, None)


def create_project(client, agent_type="TESTING_VALIDATION"):
    payload = {
        "agent_type": agent_type, "name": "Quality Gate", "domain": "Fintech",
    }
    if agent_type == "TESTING_VALIDATION":
        payload["agent_stage"] = "TEST_GENERATION"
    response = client.post("/api/v1/agent-projects", json=payload)
    assert response.status_code == 201
    return response.json()["data"]


def endpoint(project_id):
    return f"/api/v1/agents/testing-validation/{project_id}/run"


def test_test_generation_uses_separate_mode_and_shared_lifecycle(agent4_context):
    authentication, _, runs, provider, _ = agent4_context
    client = authentication.client()
    project = create_project(client)
    response = client.post(endpoint(project["agent_project_id"]), json={
        "run_mode": "TEST_GENERATION", "requirements": "Customers create bookings",
        "selected_outputs": ["UNIT_TEST_CASES"],
    })
    assert response.status_code == 200
    result = response.json()["data"]
    assert result["agent_type"] == "TESTING_VALIDATION"
    assert result["run_mode"] == "TEST_GENERATION"
    assert result["status"] == "COMPLETED"
    assert result["outputs"]["UNIT_TEST_CASES"][0]["representation"] == "SPECIFICATION"
    assert result["outputs"]["UNIT_TEST_CASES"][0]["execution_status"] == "NOT_EXECUTED"
    persisted = runs.documents[result["run_id"]]
    assert persisted["started_at"] and persisted["completed_at"]
    assert persisted["input_snapshot"]["run_mode"] == "TEST_GENERATION"
    assert persisted["input_snapshot"]["inputs"]["sources"][0]["source_id"] == "SRC-001"
    assert set(provider.calls[0]["json_schema"]["properties"]) == {"UNIT_TEST_CASES"}


@pytest.mark.parametrize("payload", [
    {"run_mode": "DEFAULT", "requirements": "x", "selected_outputs": ["UNIT_TEST_CASES"]},
    {"run_mode": "TEST_GENERATION", "requirements": " ", "selected_outputs": ["UNIT_TEST_CASES"]},
    {"run_mode": "TEST_GENERATION", "requirements": "x", "selected_outputs": ["COVERAGE_REPORT"]},
    {"run_mode": "VALIDATION", "selected_outputs": ["TEST_EXECUTION_REPORT"]},
    {"run_mode": "VALIDATION", "source_code_or_project": "print('ok')", "selected_outputs": ["UNIT_TEST_CASES"]},
    {"run_mode": "VALIDATION", "source_code_or_project": "print('ok')", "SRS": "generation input", "selected_outputs": ["CODE_QUALITY_REPORT"]},
    {"run_mode": "VALIDATION", "source_code_or_project": "print('ok')", "selected_outputs": ["ACCEPTANCE_CRITERIA_VALIDATION"]},
    {"run_mode": "VALIDATION", "source_code_or_project": "print('ok')", "run_command": "python -c print('unsafe')", "selected_outputs": ["TEST_EXECUTION_REPORT"]},
    {"run_mode": "VALIDATION", "source_code_or_project": "print('ok')", "run_command": "npx arbitrary-package", "selected_outputs": ["TEST_EXECUTION_REPORT"]},
    {"run_mode": "VALIDATION", "source_code_or_project": "print('ok')", "validation_profile": "PYTHON_PYTEST", "run_command": "python -m pytest -k injected", "selected_outputs": ["TEST_EXECUTION_REPORT"]},
    {"run_mode": "VALIDATION", "source_code_or_project": "print('ok')", "selected_outputs": []},
])
def test_invalid_mode_context_and_output_combinations_create_no_run(agent4_context, payload):
    authentication, _, runs, provider, _ = agent4_context
    client = authentication.client()
    project = create_project(client)
    response = client.post(endpoint(project["agent_project_id"]), json=payload)
    assert response.status_code == 422
    assert runs.documents == {}
    assert provider.calls == []


def test_wrong_type_foreign_and_archived_projects_are_rejected(agent4_context):
    authentication, _, _, _, _ = agent4_context
    owner = authentication.client("USR-001")
    foreign = authentication.client("USR-002")
    payload = {"run_mode": "VALIDATION", "source_code_or_project": "print('ok')", "selected_outputs": ["CODE_QUALITY_REPORT"]}
    wrong = create_project(owner, "REQUIREMENTS")
    assert owner.post(endpoint(wrong["agent_project_id"]), json=payload).status_code == 422
    project = create_project(owner)
    assert foreign.post(endpoint(project["agent_project_id"]), json=payload).status_code == 404
    owner.patch(f"/api/v1/agent-projects/{project['agent_project_id']}", json={"status": "ARCHIVED"})
    assert owner.post(endpoint(project["agent_project_id"]), json=payload).status_code == 409


def test_executable_generation_requires_and_preserves_technical_context(agent4_context):
    authentication, _, _, provider, _ = agent4_context
    provider.response = {"API_TEST_CASES": [{
        **TEST_CASE, "representation": "EXECUTABLE_CODE", "executable": True,
        "framework": "pytest", "code": "def test_booking():\n    assert True",
    }]}
    client = authentication.client()
    project = create_project(client)
    result = client.post(endpoint(project["agent_project_id"]), json={
        "run_mode": "TEST_GENERATION", "requirements": "Create bookings",
        "existing_source_code": "def create_booking(): return True", "technology_stack": "Python, pytest",
        "selected_outputs": ["API_TEST_CASES"],
    }).json()["data"]
    assert result["status"] == "COMPLETED"
    assert result["outputs"]["API_TEST_CASES"][0]["executable"] is True
    assert result["outputs"]["API_TEST_CASES"][0]["execution_status"] == "NOT_EXECUTED"


def test_fake_executable_claim_without_context_fails_structured_validation(agent4_context):
    authentication, _, _, provider, _ = agent4_context
    provider.response = {"UNIT_TEST_CASES": [{
        **TEST_CASE, "representation": "EXECUTABLE_CODE", "executable": True,
        "framework": "pytest", "code": "def test_x(): assert True",
    }]}
    client = authentication.client()
    project = create_project(client)
    result = client.post(endpoint(project["agent_project_id"]), json={
        "run_mode": "TEST_GENERATION", "requirements": "Create bookings",
        "selected_outputs": ["UNIT_TEST_CASES"],
    }).json()["data"]
    assert result["status"] == "FAILED"
    assert result["errors"][0]["code"] == "STRUCTURED_OUTPUT_INVALID"


def test_traceability_is_local_result_mapping(agent4_context):
    authentication, _, _, provider, _ = agent4_context
    provider.response = {
        "UNIT_TEST_CASES": [TEST_CASE],
        "TEST_TRACEABILITY": [{
            "source_ref": "SRC-001", "source_type": "REQUIREMENT",
            "test_refs": ["TEST-001"], "scope": "STANDALONE_RESULT",
        }],
    }
    client = authentication.client()
    project = create_project(client)
    result = client.post(endpoint(project["agent_project_id"]), json={
        "run_mode": "TEST_GENERATION", "requirements": "Create bookings",
        "selected_outputs": ["UNIT_TEST_CASES", "TEST_TRACEABILITY"],
    }).json()["data"]
    assert result["outputs"]["TEST_TRACEABILITY"][0]["scope"] == "STANDALONE_RESULT"


def test_validation_returns_real_tool_evidence_and_structured_failure(agent4_context):
    authentication, _, _, _, runner = agent4_context
    runner.evidence = command_result(
        status="FAILED", exit_code=1, stdout="1 failed",
        stderr="AssertionError: expected 201",
    )
    client = authentication.client()
    project = create_project(client)
    result = client.post(endpoint(project["agent_project_id"]), json={
        "run_mode": "VALIDATION",
        "source_code_or_project": {"app.py": "def create(): return 500", "test_app.py": "# supplied test"},
        "run_command": "python -m pytest",
        "selected_outputs": ["TEST_EXECUTION_REPORT", "BUG_REPORTS", "FINAL_VALIDATION_REPORT"],
    }).json()["data"]
    assert result["status"] == "COMPLETED"
    report = result["outputs"]["TEST_EXECUTION_REPORT"]
    assert report["status"] == "FAILED"
    assert report["evidence"]["evidence_type"] == "ACTUAL_SANDBOX_EXECUTION"
    assert result["outputs"]["BUG_REPORTS"][0]["evidence_type"] == "ACTUAL_SANDBOX_EXECUTION"
    assert result["outputs"]["FINAL_VALIDATION_REPORT"]["readiness"] == "NOT_READY"


def test_validation_never_fabricates_coverage_or_test_execution(agent4_context):
    authentication, _, _, _, runner = agent4_context
    client = authentication.client()
    project = create_project(client)
    result = client.post(endpoint(project["agent_project_id"]), json={
        "run_mode": "VALIDATION", "source_code_or_project": "def add(a, b): return a + b",
        "selected_outputs": ["TEST_EXECUTION_REPORT", "COVERAGE_REPORT", "FINAL_VALIDATION_REPORT"],
    }).json()["data"]
    assert result["outputs"]["TEST_EXECUTION_REPORT"]["status"] == "SKIPPED"
    assert result["outputs"]["COVERAGE_REPORT"]["status"] == "NOT_MEASURED"
    assert result["outputs"]["COVERAGE_REPORT"]["metrics"] == {}
    assert result["outputs"]["FINAL_VALIDATION_REPORT"]["evidence_summary"]["tests_executed"] is False
    assert len(runner.calls) == 1
    assert runner.calls[0].profile is None


def test_static_security_findings_are_scanner_evidence_not_ai_speculation(agent4_context):
    authentication, _, _, _, _ = agent4_context
    client = authentication.client()
    project = create_project(client)
    result = client.post(endpoint(project["agent_project_id"]), json={
        "run_mode": "VALIDATION", "source_code_or_project": "password = 'unsafe'\ndef run(value):\n    return eval(value)",
        "selected_outputs": ["SECURITY_FINDINGS", "CODE_QUALITY_REPORT"],
    }).json()["data"]
    security = result["outputs"]["SECURITY_FINDINGS"]
    assert security["executed"] is True
    assert {item["evidence_type"] for item in security["findings"]} == {"ACTUAL_SCANNER_FINDING"}
    assert security["llm_suggested_observations"] == []


def test_engine_modes_are_explicit_and_cannot_be_merged():
    context = Agent4InputContext(
        project_name="Quality", domain="Finance", run_mode="VALIDATION",
        inputs={"source_code_or_project": "print('ok')"},
    )
    result = Agent4Engine(FixedProvider({}), FixedExecutor()).execute(context, ["COVERAGE_REPORT"])
    assert result["COVERAGE_REPORT"]["status"] == "NOT_MEASURED"


@pytest.mark.parametrize(
    "executor",
    [
        FailingExecutor(),
        FailingExecutor("Secure validation exceeded the execution time limit"),
    ],
)
def test_executor_failure_and_timeout_fail_the_persisted_run(agent4_context, executor):
    authentication, _, runs, provider, _ = agent4_context
    app.dependency_overrides[get_agent4_engine] = lambda: Agent4Engine(provider, executor)
    client = authentication.client()
    project = create_project(client)
    result = client.post(endpoint(project["agent_project_id"]), json={
        "run_mode": "VALIDATION",
        "source_code_or_project": {"test_app.py": "def test_ok(): assert True"},
        "validation_profile": "PYTHON_PYTEST",
        "selected_outputs": ["TEST_EXECUTION_REPORT"],
    }).json()["data"]
    assert result["status"] == "FAILED"
    assert result["errors"][0]["code"] == "TOOL_EXECUTION_FAILED"
    assert runs.documents[result["run_id"]]["status"] == "FAILED"
