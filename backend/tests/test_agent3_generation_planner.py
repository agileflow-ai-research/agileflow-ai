from copy import deepcopy
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.common.status import AgentType
from app.modules.agents.implementation.contracts.enums import (
    ImplementationOutputCode as Output,
)
from app.modules.agents.implementation.generation.input_loader import (
    ApprovedGenerationInputLoader,
)
from app.modules.agents.implementation.generation.planner import (
    DeterministicGenerationPlanner,
    GenerationPlanningError,
    GenerationPlanningErrorCode,
    GenerationPlanValidator,
)
from app.modules.agents.implementation.generation.schemas import (
    GenerationPlanStatus,
    PlannedFileCategory,
    PlannedFileEntry,
    PlanningEvidenceKind,
    RelativeOutputPath,
)
from app.modules.agents.implementation.preparation.readiness.schemas import (
    FindingSeverity,
)
from app.modules.agents.implementation.preparation.readiness.trusted.schemas import (
    TrustedReadinessEvaluationRequest,
)
from app.modules.agents.implementation.preparation.readiness.trusted.service import (
    TrustedReadinessService,
)
from app.modules.agents.implementation.preparation.readiness.trusted.storage import (
    TrustedReadinessStorage,
)
from app.modules.agents.implementation.preparation.schemas import (
    ArtifactDetectionLabel as Category,
)
from app.modules.agents.implementation.runs.service import ImplementationRunService
from test_agent3_implementation_runs import (
    FakeConsolidation,
    FakeReadiness,
    FakeRepository,
    FakeStandalone,
    NOW,
    OWNER_ID,
    PROJECT_ID,
    USER,
    project_item,
    request,
    specification,
)


ALL_OUTPUTS = tuple(Output)


class LoaderBoundary:
    def __init__(self, stored):
        self.stored = stored
        self.create_calls = 0
        self.github_calls = 0
        self.inference_calls = 0

    def get_project(self, project_id, current_user):
        self.stored.require_active_project(current_user.user_id, project_id)
        return SimpleNamespace(
            agent_project_id=project_id,
            owner_user_id=current_user.user_id,
            agent_type=AgentType.IMPLEMENTATION,
        )

    def get_run(self, project_id, run_id, current_user):
        return self.stored.get_run(project_id, run_id, current_user)

    def create_run(self, *args, **kwargs):
        self.create_calls += 1
        raise AssertionError("Planner must not create an AgentRun")


def quickbook_specification(*, include_ui=True):
    categories = {
        Category.FUNCTIONAL_REQUIREMENTS: [
            project_item(
                Category.FUNCTIONAL_REQUIREMENTS,
                "A",
                {"id": "FR-001", "statement": "Patients shall book appointments."},
            )
        ],
        Category.API_SPECIFICATION: [
            project_item(
                Category.API_SPECIFICATION,
                "B",
                {
                    "id": "API-001",
                    "method": "POST",
                    "path": "/api/bookings",
                    "description": "Create a booking",
                    "request_fields": ["patient_id", "slot_id"],
                    "response_statuses": [201, 409],
                },
            ),
            project_item(
                Category.API_SPECIFICATION,
                "C",
                {
                    "id": "API-002",
                    "method": "GET",
                    "path": "/api/bookings/{booking_id}",
                    "description": "Read a booking",
                    "request_fields": [],
                    "response_statuses": [200, 404],
                },
            ),
        ],
        Category.DATABASE_SCHEMA: [
            project_item(
                Category.DATABASE_SCHEMA,
                "D",
                {
                    "name": "bookings",
                    "fields": [
                        {
                            "name": "id",
                            "type": "BIGINT",
                            "nullable": False,
                            "primary_key": True,
                            "foreign_key": None,
                        },
                        {
                            "name": "patient_id",
                            "type": "BIGINT",
                            "nullable": False,
                            "primary_key": False,
                            "foreign_key": "patients(id)",
                        },
                    ],
                },
            )
        ],
        Category.SYSTEM_ARCHITECTURE: [
            project_item(
                Category.SYSTEM_ARCHITECTURE,
                "F",
                {"kind": "components", "name": "Booking API", "type": "service"},
            )
        ],
        Category.TECHNOLOGY_STACK: [
            project_item(
                Category.TECHNOLOGY_STACK,
                "0",
                {"category": "database", "value": "MySQL"},
            )
        ],
        Category.TECHNICAL_CONSTRAINTS: [
            project_item(
                Category.TECHNICAL_CONSTRAINTS,
                "1",
                {"id": "TC-001", "statement": "Use the approved PP1 stack."},
            )
        ],
    }
    if include_ui:
        categories[Category.UI_FLOW] = [
            project_item(
                Category.UI_FLOW,
                "E",
                {
                    "name": "Booking Flow",
                    "steps": [
                        {"order": 1, "screen_or_action": "Open booking form"},
                        {"order": 2, "screen_or_action": "Submit booking"},
                    ],
                },
            )
        ]
    return specification(categories)


def approved_context(tmp_path, outputs=ALL_OUTPUTS, *, include_ui=True):
    final = quickbook_specification(include_ui=include_ui)
    consolidation = FakeConsolidation(final)
    readiness_service = TrustedReadinessService(
        FakeStandalone(),
        consolidation,
        TrustedReadinessStorage(tmp_path / "readiness"),
        clock=lambda: NOW,
    )
    readiness = readiness_service.evaluate(
        PROJECT_ID,
        TrustedReadinessEvaluationRequest(selected_outputs=list(outputs)),
        USER,
    )
    stored = FakeStandalone()
    run_service = ImplementationRunService(
        stored,
        consolidation,
        FakeReadiness(readiness),
        FakeRepository(),
        FakeRepository(),
        clock=lambda: NOW,
    )
    warning_codes = sorted(
        item.issue_code
        for item in readiness.findings
        if item.severity is FindingSeverity.WARNING and not item.resolved
    )
    response = run_service.create(
        PROJECT_ID,
        request(readiness, acknowledged_warning_codes=warning_codes),
        USER,
    )[0]
    boundary = LoaderBoundary(stored)
    context = ApprovedGenerationInputLoader(boundary).load(
        PROJECT_ID, response.run_id, USER
    )
    return context, boundary, stored, response


def paths(plan):
    return {item.relative_output_path.root for item in plan.planned_files}


def file_for(plan, relative_path):
    return next(
        item
        for item in plan.planned_files
        if item.relative_output_path.root == relative_path
    )


def planned_file(
    suffix,
    path,
    *,
    dependencies=(),
    references=(),
    order=1,
):
    return PlannedFileEntry(
        planned_file_id=f"GPF-{suffix * 32}",
        relative_output_path=RelativeOutputPath(path),
        responsibility="A deterministic test responsibility.",
        output_codes=(Output.PROJECT_STRUCTURE,),
        dependency_file_ids=dependencies,
        supporting_specification_item_ids=references,
        file_category=PlannedFileCategory.PROJECT_STRUCTURE,
        evidence_kind=(
            PlanningEvidenceKind.TRUSTED_SPECIFICATION
            if references
            else PlanningEvidenceKind.STRUCTURAL
        ),
        generation_order=order,
    )


def assert_planning_error(code, callback):
    with pytest.raises(GenerationPlanningError) as captured:
        callback()
    assert captured.value.code is code


def test_quickbook_plan_is_deterministic_and_traceable(tmp_path):
    context, _, _, _ = approved_context(tmp_path)
    planner = DeterministicGenerationPlanner()

    first = planner.plan(context)
    second = planner.plan(context)

    assert first == second
    assert first.plan_fingerprint == second.plan_fingerprint
    assert first.status is GenerationPlanStatus.READY
    assert set(first.approved_output_codes) == set(ALL_OUTPUTS)
    assert set(first.traceability_coverage.represented_outputs) == set(ALL_OUTPUTS)
    assert "backend/src/routes/bookings.routes.js" in paths(first)
    assert "frontend/src/pages/booking-flow-page.jsx" in paths(first)
    assert "database/schema.sql" in paths(first)
    assert [item.output_code for item in first.non_file_deliverables] == [
        Output.GIT_SUMMARY
    ]


@pytest.mark.parametrize(
    ("output", "expected_path", "file_expected"),
    [
        (Output.PROJECT_STRUCTURE, "README.md", True),
        (Output.FRONTEND_CODE, "frontend/src/main.jsx", True),
        (Output.BACKEND_CODE, "backend/src/app.js", True),
        (Output.DATABASE_IMPLEMENTATION, "database/schema.sql", True),
        (Output.API_IMPLEMENTATION, "backend/src/routes/bookings.routes.js", True),
        (Output.CONFIGURATION_FILES, ".env.example", True),
        (Output.CONTAINER_CONFIGURATION, "docker-compose.yml", True),
        (Output.GIT_SUMMARY, None, False),
    ],
)
def test_each_approved_output_is_handled(
    tmp_path, output, expected_path, file_expected
):
    context, _, _, _ = approved_context(tmp_path, (output,))
    plan = DeterministicGenerationPlanner().plan(context)

    assert plan.approved_output_codes == (output,)
    assert plan.traceability_coverage.represented_outputs == (output,)
    if file_expected:
        assert expected_path in paths(plan)
        assert all(set(item.output_codes) == {output} for item in plan.planned_files)
        assert not plan.non_file_deliverables
    else:
        assert not plan.planned_files
        assert plan.non_file_deliverables[0].output_code is Output.GIT_SUMMARY


def test_only_approved_outputs_and_essential_scaffolding_are_planned(tmp_path):
    context, _, _, _ = approved_context(tmp_path, (Output.API_IMPLEMENTATION,))
    plan = DeterministicGenerationPlanner().plan(context)

    assert paths(plan) == {
        "backend/package.json",
        "backend/src/app.js",
        "backend/src/routes/bookings.routes.js",
    }
    assert all(item.output_codes == (Output.API_IMPLEMENTATION,) for item in plan.planned_files)
    assert "database/schema.sql" not in paths(plan)
    assert "frontend/src/main.jsx" not in paths(plan)


def test_domain_files_use_only_trusted_quickbook_evidence(tmp_path):
    context, _, _, _ = approved_context(tmp_path)
    plan = DeterministicGenerationPlanner().plan(context)
    specification_ids = {
        item.project_item_id
        for items in context.trusted_project_specification.categories.values()
        for item in items
    }

    route = file_for(plan, "backend/src/routes/bookings.routes.js")
    page = file_for(plan, "frontend/src/pages/booking-flow-page.jsx")
    schema = file_for(plan, "database/schema.sql")
    assert route.supporting_specification_item_ids
    assert page.supporting_specification_item_ids
    assert schema.supporting_specification_item_ids
    assert set(route.supporting_specification_item_ids).issubset(specification_ids)
    assert set(page.supporting_specification_item_ids).issubset(specification_ids)
    assert set(schema.supporting_specification_item_ids).issubset(specification_ids)
    assert "appointments" not in " ".join(paths(plan))


def test_structural_files_are_honest_about_lacking_direct_requirement_evidence(tmp_path):
    context, _, _, _ = approved_context(tmp_path, (Output.FRONTEND_CODE,))
    plan = DeterministicGenerationPlanner().plan(context)
    package = file_for(plan, "frontend/package.json")

    assert package.evidence_kind is PlanningEvidenceKind.STRUCTURAL
    assert package.supporting_specification_item_ids == ()
    assert package.planned_file_id in plan.traceability_coverage.structural_file_ids


def test_missing_optional_ui_detail_is_reported_without_fabrication(tmp_path):
    context, _, _, _ = approved_context(
        tmp_path, (Output.FRONTEND_CODE,), include_ui=False
    )
    plan = DeterministicGenerationPlanner().plan(context)

    assert plan.status is GenerationPlanStatus.READY_WITH_WARNINGS
    assert "NAMED_UI_FLOW_NOT_AVAILABLE" in {
        item.code for item in plan.validation_findings
    }
    assert not any("/pages/" in path for path in paths(plan))


def test_unknown_traceability_reference_is_rejected(tmp_path):
    context, _, _, _ = approved_context(tmp_path, (Output.PROJECT_STRUCTURE,))
    item = planned_file(
        "a", "README.md", references=("PSI-" + "F" * 24,)
    )
    assert_planning_error(
        GenerationPlanningErrorCode.UNKNOWN_TRACEABILITY_REFERENCE,
        lambda: GenerationPlanValidator.validate_files(
            (item,), context.selected_outputs, set()
        ),
    )


def test_duplicate_and_case_insensitive_paths_are_rejected():
    exact = (
        planned_file("a", "src/app.js"),
        planned_file("b", "src/app.js"),
    )
    assert_planning_error(
        GenerationPlanningErrorCode.DUPLICATE_OUTPUT_PATH,
        lambda: GenerationPlanValidator.validate_files(
            exact, (Output.PROJECT_STRUCTURE,), set()
        ),
    )
    folded = (
        planned_file("a", "src/App.js"),
        planned_file("b", "src/app.js"),
    )
    assert_planning_error(
        GenerationPlanningErrorCode.CASE_INSENSITIVE_PATH_COLLISION,
        lambda: GenerationPlanValidator.validate_files(
            folded, (Output.PROJECT_STRUCTURE,), set()
        ),
    )


def test_file_directory_namespace_collision_is_rejected():
    files = (
        planned_file("a", "backend"),
        planned_file("b", "backend/app.js"),
    )
    assert_planning_error(
        GenerationPlanningErrorCode.FILE_DIRECTORY_NAMESPACE_COLLISION,
        lambda: GenerationPlanValidator.validate_files(
            files, (Output.PROJECT_STRUCTURE,), set()
        ),
    )


@pytest.mark.parametrize(
    "path",
    ["../escape.js", "/absolute.js", "C:/drive.js", "src\\backslash.js"],
)
def test_unsafe_planned_paths_are_rejected(path):
    with pytest.raises(ValidationError):
        planned_file("a", path)


def test_missing_dependency_and_cycles_are_rejected():
    missing = planned_file(
        "a", "src/a.js", dependencies=("GPF-" + "f" * 32,)
    )
    assert_planning_error(
        GenerationPlanningErrorCode.MISSING_DEPENDENCY,
        lambda: GenerationPlanValidator.validate_files(
            (missing,), (Output.PROJECT_STRUCTURE,), set()
        ),
    )

    left_id = "GPF-" + "a" * 32
    right_id = "GPF-" + "b" * 32
    cycle = (
        planned_file("a", "src/a.js", dependencies=(right_id,)),
        planned_file("b", "src/b.js", dependencies=(left_id,)),
    )
    assert_planning_error(
        GenerationPlanningErrorCode.DEPENDENCY_CYCLE,
        lambda: GenerationPlanValidator.validate_files(
            cycle, (Output.PROJECT_STRUCTURE,), set()
        ),
    )


def test_generation_order_is_stable_and_respects_dependencies(tmp_path):
    context, _, _, _ = approved_context(tmp_path)
    plan = DeterministicGenerationPlanner().plan(context)
    positions = {file_id: index for index, file_id in enumerate(plan.generation_order)}

    for item in plan.planned_files:
        assert item.generation_order == positions[item.planned_file_id] + 1
        assert all(
            positions[dependency] < positions[item.planned_file_id]
            for dependency in item.dependency_file_ids
        )


def test_plan_fingerprints_bind_inputs_and_policy_version(tmp_path):
    all_context, _, _, _ = approved_context(tmp_path / "all")
    api_context, _, _, _ = approved_context(
        tmp_path / "api", (Output.API_IMPLEMENTATION,)
    )

    first = DeterministicGenerationPlanner().plan(all_context)
    changed_input = DeterministicGenerationPlanner().plan(api_context)
    changed_policy = DeterministicGenerationPlanner("GEN-R1.2-2").plan(
        all_context
    )

    assert first.source_snapshot_fingerprint != changed_input.source_snapshot_fingerprint
    assert first.plan_fingerprint != changed_input.plan_fingerprint
    assert first.identity != changed_input.identity
    assert first.identity != changed_policy.identity
    assert first.plan_fingerprint != changed_policy.plan_fingerprint


def test_inconsistent_plan_fingerprint_is_rejected(tmp_path):
    context, _, _, _ = approved_context(tmp_path)
    plan = DeterministicGenerationPlanner().plan(context)
    corrupted = plan.model_copy(update={"plan_fingerprint": "0" * 64})

    assert_planning_error(
        GenerationPlanningErrorCode.INVALID_PLAN_FINGERPRINT,
        lambda: GenerationPlanValidator.validate_plan(corrupted, context),
    )


def test_plan_cannot_replace_approved_outputs_or_stack(tmp_path):
    context, _, _, _ = approved_context(tmp_path)
    plan = DeterministicGenerationPlanner().plan(context)
    wrong_outputs = plan.model_copy(
        update={"approved_output_codes": (Output.PROJECT_STRUCTURE,)}
    )
    assert_planning_error(
        GenerationPlanningErrorCode.UNAUTHORIZED_OUTPUT,
        lambda: GenerationPlanValidator.validate_plan(wrong_outputs, context),
    )

    wrong_stack = plan.model_copy(
        update={
            "effective_stack": plan.effective_stack.model_copy(
                update={"database": "PostgreSQL"}
            )
        }
    )
    assert_planning_error(
        GenerationPlanningErrorCode.UNSUPPORTED_EFFECTIVE_STACK,
        lambda: GenerationPlanValidator.validate_plan(wrong_stack, context),
    )


def test_planning_has_no_external_side_effects(tmp_path):
    context, boundary, stored, response = approved_context(tmp_path)
    before_run = deepcopy(stored.runs[0].model_dump(mode="json"))
    before_paths = sorted(path.relative_to(tmp_path) for path in tmp_path.rglob("*"))
    create_calls = stored.create_calls

    DeterministicGenerationPlanner().plan(context)

    after_paths = sorted(path.relative_to(tmp_path) for path in tmp_path.rglob("*"))
    assert after_paths == before_paths
    assert stored.create_calls == create_calls == 1
    assert boundary.create_calls == 0
    assert boundary.github_calls == 0
    assert boundary.inference_calls == 0
    assert stored.runs[0].model_dump(mode="json") == before_run
    assert stored.runs[0].run_id == response.run_id
    assert stored.runs[0].output_manifest == {}


def test_approved_context_is_required():
    assert_planning_error(
        GenerationPlanningErrorCode.INVALID_CONTEXT,
        lambda: DeterministicGenerationPlanner().plan(None),
    )
