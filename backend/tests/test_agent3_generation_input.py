from copy import deepcopy
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.common.status import AgentRunStatus, AgentType
from app.modules.agents.implementation.contracts.enums import (
    ImplementationOutputCode,
)
from app.modules.agents.implementation.generation.input_loader import (
    ApprovedGenerationInputError,
    ApprovedGenerationInputLoader,
    GenerationInputErrorCode,
)
from app.modules.agents.implementation.generation.schemas import (
    GenerationValidationError,
    GenerationValidationResult,
    RelativeOutputPath,
)
from app.modules.agents.implementation.generation.validation import (
    UnsafeOutputPathError,
    resolve_workspace_output_path,
    validate_relative_output_path,
)
from app.modules.agents.implementation.runs.schemas import ImplementationRunStatus
from app.modules.standalone.service import AgentProjectNotFoundError
from test_agent3_implementation_runs import (
    OWNER_ID,
    PROJECT_ID,
    USER,
    create,
    harness,
)


class LoaderStandalone:
    def __init__(self, source, *, agent_type=AgentType.IMPLEMENTATION):
        self.source = source
        self.agent_type = agent_type
        self.get_project_calls = 0
        self.get_run_calls = 0
        self.create_calls = 0
        self.inference_calls = 0

    def get_project(self, project_id, current_user):
        self.get_project_calls += 1
        self.source.require_active_project(current_user.user_id, project_id)
        return SimpleNamespace(
            agent_project_id=project_id,
            owner_user_id=current_user.user_id,
            agent_type=self.agent_type,
        )

    def get_run(self, project_id, run_id, current_user):
        self.get_run_calls += 1
        return self.source.get_run(project_id, run_id, current_user)

    def create_run(self, *args, **kwargs):
        self.create_calls += 1
        raise AssertionError("The generation input loader must not create runs")


@pytest.fixture
def approved_run(tmp_path):
    run_service, stored, _, readiness = harness(tmp_path)
    response = create(run_service, readiness)
    boundary = LoaderStandalone(stored)
    loader = ApprovedGenerationInputLoader(boundary)
    return loader, boundary, stored, response, readiness


def assert_error(loader, run_id, code, *, project_id=PROJECT_ID, user=USER):
    with pytest.raises(ApprovedGenerationInputError) as captured:
        loader.load(project_id, run_id, user)
    assert captured.value.code is code


def test_valid_queued_approved_run_loads_exact_historical_context(approved_run):
    loader, boundary, stored, response, readiness = approved_run

    context = loader.load(PROJECT_ID, response.run_id, USER)

    assert context.run_id == response.run_id
    assert context.operational_status is AgentRunStatus.QUEUED
    assert (
        context.trusted_project_specification
        == response.approved_input.trusted_project_specification
    )
    assert context.trusted_readiness == response.approved_input.trusted_readiness
    assert context.selected_outputs == tuple(response.selected_outputs)
    assert (
        context.effective_implementation_stack.model_dump()
        == readiness.effective_stack
    )
    assert context.approval == response.approved_input.approval
    assert context.traceability_root_refs == tuple(response.traceability_root_refs)
    assert boundary.get_project_calls == 1
    assert boundary.get_run_calls == 1
    assert boundary.create_calls == 0
    assert boundary.inference_calls == 0
    assert stored.create_calls == 1


def test_loading_is_detached_read_only_and_does_not_change_run(approved_run):
    loader, _, stored, response, _ = approved_run
    before = stored.runs[0].model_dump(mode="json")

    context = loader.load(PROJECT_ID, response.run_id, USER)

    with pytest.raises(ValidationError):
        context.run_id = "RUN-999"
    with pytest.raises(ValidationError):
        context.effective_implementation_stack.frontend = "changed locally"
    assert stored.runs[0].model_dump(mode="json") == before
    assert stored.runs[0].status is AgentRunStatus.QUEUED
    assert stored.runs[0].output_manifest == {}


def test_loader_does_not_write_generated_files(tmp_path, approved_run):
    loader, _, _, response, _ = approved_run
    before = sorted(path.relative_to(tmp_path) for path in tmp_path.rglob("*"))

    loader.load(PROJECT_ID, response.run_id, USER)

    after = sorted(path.relative_to(tmp_path) for path in tmp_path.rglob("*"))
    assert after == before


def test_missing_run_is_rejected(approved_run):
    loader, _, _, _, _ = approved_run
    assert_error(loader, "RUN-999", GenerationInputErrorCode.RUN_NOT_FOUND)


def test_unauthorized_project_is_rejected_without_disclosure(approved_run):
    loader, _, _, response, _ = approved_run
    assert_error(
        loader,
        response.run_id,
        GenerationInputErrorCode.PROJECT_NOT_ACCESSIBLE,
        user=SimpleNamespace(user_id="USR-002"),
    )


def test_wrong_project_binding_is_rejected(approved_run):
    loader, _, stored, response, _ = approved_run
    stored.runs[0] = stored.runs[0].model_copy(
        update={"agent_project_id": "AGP-004"}
    )
    assert_error(loader, response.run_id, GenerationInputErrorCode.WRONG_PROJECT)


def test_wrong_agent_project_is_rejected(approved_run):
    _, _, stored, response, _ = approved_run
    loader = ApprovedGenerationInputLoader(
        LoaderStandalone(stored, agent_type=AgentType.TESTING_VALIDATION)
    )
    assert_error(loader, response.run_id, GenerationInputErrorCode.WRONG_AGENT_TYPE)


def test_missing_implementation_snapshot_is_rejected(approved_run):
    loader, _, stored, response, _ = approved_run
    stored.runs[0] = stored.runs[0].model_copy(update={"input_snapshot": {}})
    assert_error(
        loader,
        response.run_id,
        GenerationInputErrorCode.MISSING_IMPLEMENTATION_SNAPSHOT,
    )


def test_missing_final_approval_is_rejected(approved_run):
    loader, _, stored, response, _ = approved_run
    snapshot = deepcopy(stored.runs[0].input_snapshot)
    snapshot.pop("approval")
    stored.runs[0] = stored.runs[0].model_copy(update={"input_snapshot": snapshot})
    assert_error(
        loader, response.run_id, GenerationInputErrorCode.MISSING_FINAL_APPROVAL
    )


def test_rejected_final_approval_is_rejected(approved_run):
    loader, _, stored, response, _ = approved_run
    snapshot = deepcopy(stored.runs[0].input_snapshot)
    snapshot["approval"]["decision"] = "REJECTED"
    stored.runs[0] = stored.runs[0].model_copy(update={"input_snapshot": snapshot})
    assert_error(
        loader, response.run_id, GenerationInputErrorCode.INVALID_FINAL_APPROVAL
    )


def test_invalid_snapshot_generation_state_is_rejected(approved_run):
    loader, _, stored, response, _ = approved_run
    snapshot = deepcopy(stored.runs[0].input_snapshot)
    snapshot["run_status"] = "NOT_READY"
    stored.runs[0] = stored.runs[0].model_copy(update={"input_snapshot": snapshot})
    assert_error(
        loader,
        response.run_id,
        GenerationInputErrorCode.INVALID_GENERATION_READINESS,
    )


def test_missing_mandatory_generation_context_is_rejected(approved_run):
    loader, _, stored, response, _ = approved_run
    snapshot = deepcopy(stored.runs[0].input_snapshot)
    snapshot.pop("trusted_project_specification")
    stored.runs[0] = stored.runs[0].model_copy(update={"input_snapshot": snapshot})
    assert_error(
        loader,
        response.run_id,
        GenerationInputErrorCode.MISSING_GENERATION_CONTEXT,
    )


def test_incomplete_effective_stack_is_rejected_as_corrupted(approved_run):
    loader, _, stored, response, _ = approved_run
    snapshot = deepcopy(stored.runs[0].input_snapshot)
    snapshot["implementation_stack"].pop("database")
    snapshot["trusted_readiness"]["effective_stack"].pop("database")
    stored.runs[0] = stored.runs[0].model_copy(update={"input_snapshot": snapshot})
    assert_error(
        loader,
        response.run_id,
        GenerationInputErrorCode.CORRUPTED_APPROVED_DATA,
    )


def test_unsupported_selected_output_is_rejected(approved_run):
    loader, _, stored, response, _ = approved_run
    snapshot = deepcopy(stored.runs[0].input_snapshot)
    snapshot["selected_outputs"] = ["UNAPPROVED_OUTPUT"]
    stored.runs[0] = stored.runs[0].model_copy(update={"input_snapshot": snapshot})
    assert_error(
        loader,
        response.run_id,
        GenerationInputErrorCode.UNSUPPORTED_SELECTED_OUTPUT,
    )


def test_corrupted_snapshot_digest_is_rejected(approved_run):
    loader, _, stored, response, _ = approved_run
    snapshot = deepcopy(stored.runs[0].input_snapshot)
    snapshot["selected_outputs_digest"] = "0" * 64
    stored.runs[0] = stored.runs[0].model_copy(update={"input_snapshot": snapshot})
    assert_error(
        loader,
        response.run_id,
        GenerationInputErrorCode.CORRUPTED_APPROVED_DATA,
    )


@pytest.mark.parametrize(
    "value",
    [
        "/etc/passwd",
        "C:/Windows/system.ini",
        "C:\\Windows\\system.ini",
        "../secrets.txt",
        "src/../../secrets.txt",
        "src\\index.js",
        "src//index.js",
        "./src/index.js",
        "src/CON.txt",
        "src/file.js:stream",
        "src/index.js ",
        "",
    ],
)
def test_unsafe_relative_output_paths_are_rejected(value):
    with pytest.raises((UnsafeOutputPathError, ValidationError)):
        RelativeOutputPath(value)


def test_valid_nested_relative_output_path_is_accepted(tmp_path):
    value = "apps/frontend/src/components/BookingForm.jsx"
    assert validate_relative_output_path(value) == value
    assert RelativeOutputPath(value).root == value

    workspace = tmp_path.resolve() / "AGP-003" / "RUN-001"
    resolved = resolve_workspace_output_path(workspace, value)
    assert resolved.is_relative_to(workspace)
    assert not workspace.exists()
    assert not resolved.exists()


def test_validation_result_contract_requires_error_consistency():
    assert GenerationValidationResult(valid=True).errors == ()
    error = GenerationValidationError(code="UNSAFE_PATH", message="Invalid path")
    assert GenerationValidationResult(valid=False, errors=(error,)).valid is False
    with pytest.raises(ValidationError):
        GenerationValidationResult(valid=True, errors=(error,))
    with pytest.raises(ValidationError):
        GenerationValidationResult(valid=False)


def test_snapshot_state_constant_remains_ready_for_generation():
    assert ImplementationRunStatus.READY_FOR_GENERATION == "READY_FOR_GENERATION"
    assert [item.value for item in ImplementationOutputCode] == [
        "PROJECT_STRUCTURE",
        "FRONTEND_CODE",
        "BACKEND_CODE",
        "DATABASE_IMPLEMENTATION",
        "API_IMPLEMENTATION",
        "CONFIGURATION_FILES",
        "CONTAINER_CONFIGURATION",
        "GIT_SUMMARY",
    ]
