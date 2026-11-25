from copy import deepcopy
import hashlib

import pytest
from pydantic import ValidationError

from app.modules.agents.implementation.generation.adherence import (
    ADHERENCE_POLICY_VERSION,
    CodeAdherenceValidator,
)
from app.modules.agents.implementation.generation.context_builder import (
    FileGenerationContextBuilder,
)
from app.modules.agents.implementation.generation.schemas import (
    AdherenceCheckStatus,
    CodeAdherenceStatus,
    DependencyFingerprint,
    FileDependencyContext,
    GeneratedCandidateStatus,
    GeneratedContentCandidate,
    RelativeOutputPath,
)
from test_agent3_local_code_generation import (
    FakeLocalProvider,
    dependency_candidate,
    generation_fixture,
    service,
)
from app.modules.agents.implementation.generation.schemas import ModelFileResponse


ESM_PACKAGE = (
    '{"name":"quickbook-backend","private":true,"type":"module",'
    '"dependencies":{"express":"4.21.0"}}\n'
)
COMMONJS_PACKAGE = (
    '{"name":"quickbook-backend","private":true,'
    '"dependencies":{"express":"4.21.0"}}\n'
)

VALID_ESM_ROUTE = """import express from 'express';
const router = express.Router();

router.post('/api/bookings', (req, res) => {
  const { patient_id, slot_id } = req.body;
  if (!patient_id || !slot_id) return res.status(409).json({ error: 'conflict' });
  return res.status(201).json({ patient_id, slot_id });
});

router.get('/api/bookings/:booking_id', (req, res) => {
  if (!req.params.booking_id) return res.status(404).json({ error: 'not found' });
  return res.json({ id: req.params.booking_id });
});

export default router;
"""

VALID_COMMONJS_ROUTE = """const express = require('express');
const router = express.Router();
router.post('/api/bookings', (req, res) => {
  const { patient_id, slot_id } = req.body;
  if (!patient_id || !slot_id) return res.status(409).json({ error: 'conflict' });
  return res.status(201).json({ patient_id, slot_id });
});
router.get('/api/bookings/:booking_id', (req, res) => {
  if (!req.params.booking_id) return res.status(404).json({ error: 'not found' });
  return res.json({ id: req.params.booking_id });
});
module.exports = router;
"""

REAL_SMOKE_OUTPUT = """const express = require('express');
const router = express.Router();
const { Booking } = require('../models/booking');

router.post('/api/bookings', async (req, res) => {
  try {
    const { patient_id, slot_id } = req.body;
    const booking = new Booking({ patient_id, slot_id });
    await booking.save();
    res.status(201).json(booking);
  } catch (error) {
    res.status(409).json({ error: error.message });
  }
});

router.get('/api/bookings/:booking_id', async (req, res) => {
  try {
    const booking = await Booking.findById(req.params.booking_id);
    if (!booking) return res.status(404).json({ error: 'Booking not found' });
    res.json(booking);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

module.exports = router;
"""


def _fixture(tmp_path, package_content=ESM_PACKAGE):
    context, plan, planned_file, boundary, stored, run = generation_fixture(
        tmp_path, "backend/src/routes/bookings.routes.js"
    )
    dependencies = {
        dependency_id: dependency_candidate(
            context,
            plan,
            next(
                item
                for item in plan.planned_files
                if item.planned_file_id == dependency_id
            ),
            content=package_content,
        )
        for dependency_id in planned_file.dependency_file_ids
    }
    return context, plan, planned_file, dependencies, boundary, stored, run


def _generate(tmp_path, content, package_content=ESM_PACKAGE, response=None):
    fixture = _fixture(tmp_path, package_content)
    context, plan, planned_file, dependencies, *_ = fixture
    provider = FakeLocalProvider(response or ModelFileResponse(content=content))
    candidate = service(provider).generate_file(
        context, plan, planned_file, dependencies
    )
    return candidate, provider, fixture


def _direct_report(
    tmp_path,
    content,
    *,
    package_content=ESM_PACKAGE,
    extra_dependencies=(),
    candidate_refs=None,
):
    candidate, _, fixture = _generate(tmp_path, content, package_content)
    context, plan, planned_file, dependencies, *_ = fixture
    file_context = FileGenerationContextBuilder().build(
        context, plan, planned_file, dependencies
    )
    file_context = file_context.model_copy(
        update={"dependencies": file_context.dependencies + tuple(extra_dependencies)}
    )
    digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
    payload = candidate.model_dump(mode="python")
    payload.update(
        generated_content=content,
        content_sha256=digest,
        adherence_report=None,
        writer_eligible=False,
        dependency_fingerprints=tuple(
            DependencyFingerprint(
                planned_file_id=item.planned_file_id,
                content_sha256=item.content_sha256,
            )
            for item in file_context.dependencies
        ),
    )
    if candidate_refs is not None:
        payload["relevant_specification_item_ids"] = tuple(candidate_refs)
    baseline = GeneratedContentCandidate.model_validate(payload)
    return CodeAdherenceValidator().validate(file_context, baseline)


def _codes(report):
    return [item.code for item in report.findings]


def _check(report, name):
    return next(item for item in report.checks if item.name == name)


def test_real_gen_r1_3c_output_is_structurally_valid_but_adherence_blocked(tmp_path):
    candidate, provider, _ = _generate(tmp_path, REAL_SMOKE_OUTPUT)

    assert candidate.validation_status is GeneratedCandidateStatus.VALIDATED
    assert candidate.adherence_report.status is CodeAdherenceStatus.BLOCKED
    assert candidate.writer_eligible is False
    assert set(_codes(candidate.adherence_report)) >= {
        "MODULE_SYSTEM_MISMATCH",
        "UNVERIFIED_MODULE_IMPORT",
        "UNVERIFIED_IMPORTED_INTERFACE",
        "UNVERIFIED_PERSISTENCE_INTERFACE",
        "UNAPPROVED_HTTP_STATUS",
    }
    assert len(provider.requests) == 1


def test_esm_project_rejects_commonjs_and_valid_esm_is_writer_eligible(tmp_path):
    mismatch, _, _ = _generate(tmp_path / "bad", VALID_COMMONJS_ROUTE)
    valid, _, _ = _generate(tmp_path / "good", VALID_ESM_ROUTE)

    assert "MODULE_SYSTEM_MISMATCH" in _codes(mismatch.adherence_report)
    assert valid.adherence_report.status is CodeAdherenceStatus.PASS
    assert valid.writer_eligible is True


def test_commonjs_project_accepts_compatible_output(tmp_path):
    candidate, _, _ = _generate(
        tmp_path, VALID_COMMONJS_ROUTE, COMMONJS_PACKAGE
    )
    assert "MODULE_SYSTEM_MISMATCH" not in _codes(candidate.adherence_report)
    assert candidate.adherence_report.status is CodeAdherenceStatus.PASS


def test_unverified_relative_import_and_interface_are_blocking(tmp_path):
    content = VALID_ESM_ROUTE.replace(
        "import express from 'express';",
        "import express from 'express';\nimport { createBooking } from '../services/bookings.js';",
    )
    report = _direct_report(tmp_path, content)
    assert "UNVERIFIED_MODULE_IMPORT" in _codes(report)
    assert "UNVERIFIED_IMPORTED_INTERFACE" in _codes(report)
    assert report.writer_eligible is False


def test_approved_relative_dependency_and_declared_interface_are_accepted(tmp_path):
    dependency_content = "export function createBooking(value) { return value; }\n"
    dependency = FileDependencyContext(
        planned_file_id="GPF-" + "1" * 32,
        relative_output_path=RelativeOutputPath(
            "backend/src/services/bookings.js"
        ),
        responsibility="Expose the verified booking service interface.",
        validated_content=dependency_content,
        content_sha256=hashlib.sha256(dependency_content.encode()).hexdigest(),
    )
    content = VALID_ESM_ROUTE.replace(
        "import express from 'express';",
        "import express from 'express';\nimport { createBooking } from '../services/bookings.js';",
    ).replace(
        "return res.status(201).json({ patient_id, slot_id });",
        "return res.status(201).json(createBooking({ patient_id, slot_id }));",
    )
    report = _direct_report(tmp_path, content, extra_dependencies=(dependency,))
    assert "UNVERIFIED_MODULE_IMPORT" not in _codes(report)
    assert "UNVERIFIED_IMPORTED_INTERFACE" not in _codes(report)
    assert report.status is CodeAdherenceStatus.PASS


def test_existing_dependency_with_undeclared_interface_is_rejected(tmp_path):
    dependency_content = "export function other() {}\n"
    dependency = FileDependencyContext(
        planned_file_id="GPF-" + "2" * 32,
        relative_output_path=RelativeOutputPath(
            "backend/src/services/bookings.js"
        ),
        responsibility="Expose only declared booking interfaces.",
        validated_content=dependency_content,
        content_sha256=hashlib.sha256(dependency_content.encode()).hexdigest(),
    )
    content = VALID_ESM_ROUTE.replace(
        "import express from 'express';",
        "import express from 'express';\nimport { createBooking } from '../services/bookings.js';",
    )
    report = _direct_report(tmp_path, content, extra_dependencies=(dependency,))
    assert "UNVERIFIED_IMPORTED_INTERFACE" in _codes(report)


def test_unknown_external_package_is_rejected_but_express_is_approved(tmp_path):
    content = VALID_ESM_ROUTE.replace(
        "import express from 'express';",
        "import express from 'express';\nimport leftPad from 'left-pad';",
    )
    report = _direct_report(tmp_path, content)
    assert "UNAPPROVED_EXTERNAL_DEPENDENCY" in _codes(report)
    assert not any(
        item.code == "UNAPPROVED_EXTERNAL_DEPENDENCY"
        and "express" in item.observed_behavior
        for item in report.findings
    )


def test_mysql_stack_rejects_explicit_mongoose_without_mislabeling_generic_calls(tmp_path):
    mongoose = VALID_ESM_ROUTE.replace(
        "import express from 'express';",
        "import express from 'express';\nimport mongoose from 'mongoose';",
    )
    explicit = _direct_report(tmp_path / "explicit", mongoose)
    generic = _direct_report(
        tmp_path / "generic",
        VALID_ESM_ROUTE.replace(
            "const router = express.Router();",
            "const router = express.Router();\nconst cache = { save() {} };\ncache.save();",
        ),
    )
    assert "INCOMPATIBLE_DATABASE_DEPENDENCY" in _codes(explicit)
    assert "UNVERIFIED_PERSISTENCE_INTERFACE" not in _codes(generic)


def test_api_method_path_and_status_contracts(tmp_path):
    valid = _direct_report(tmp_path / "valid", VALID_ESM_ROUTE)
    wrong_method = _direct_report(
        tmp_path / "method", VALID_ESM_ROUTE.replace("router.post", "router.put", 1)
    )
    wrong_status = _direct_report(
        tmp_path / "status", VALID_ESM_ROUTE.replace("status(409)", "status(500)")
    )

    assert "UNAPPROVED_HTTP_METHOD" not in _codes(valid)
    assert "UNAPPROVED_HTTP_STATUS" not in _codes(valid)
    assert "UNAPPROVED_HTTP_METHOD" in _codes(wrong_method)
    assert "UNAPPROVED_HTTP_STATUS" in _codes(wrong_status)


def test_express_path_parameter_syntax_is_equivalent(tmp_path):
    report = _direct_report(tmp_path, VALID_ESM_ROUTE)
    assert "UNAPPROVED_API_ENDPOINT" not in _codes(report)
    assert "APPROVED_ENDPOINT_NOT_IMPLEMENTED" not in _codes(report)


def test_unknown_mount_context_requires_review_instead_of_guessing(tmp_path):
    content = VALID_ESM_ROUTE.replace("'/api/bookings'", "'/'", 1)
    report = _direct_report(tmp_path, content)
    assert "ROUTE_MOUNT_CONTEXT_UNRESOLVED" in _codes(report)


def test_unexpected_additional_endpoint_is_blocking(tmp_path):
    content = VALID_ESM_ROUTE.replace(
        "export default router;",
        "router.delete('/api/admin', (_req, res) => res.status(204).end());\n"
        "export default router;",
    )
    report = _direct_report(tmp_path, content)
    assert "UNAPPROVED_API_ENDPOINT" in _codes(report)


def test_model_reported_missing_information_is_not_writer_eligible(tmp_path):
    candidate, _, _ = _generate(
        tmp_path,
        "",
        response=ModelFileResponse(
            content="",
            missing_information=("A repository interface is required.",),
        ),
    )
    assert candidate.validation_status is GeneratedCandidateStatus.MISSING_INFORMATION
    assert candidate.adherence_report.status is CodeAdherenceStatus.BLOCKED
    assert "MODEL_REPORTED_MISSING_INFORMATION" in _codes(candidate.adherence_report)
    assert candidate.writer_eligible is False


def test_unknown_psi_reference_is_rejected(tmp_path):
    candidate, _, fixture = _generate(tmp_path, VALID_ESM_ROUTE)
    unknown = "PSI-" + "F" * 24
    context, plan, planned_file, dependencies, *_ = fixture
    file_context = FileGenerationContextBuilder().build(
        context, plan, planned_file, dependencies
    )
    payload = candidate.model_dump(mode="python")
    payload.update(
        relevant_specification_item_ids=(
            *candidate.relevant_specification_item_ids,
            unknown,
        ),
        adherence_report=None,
        writer_eligible=False,
    )
    baseline = GeneratedContentCandidate.model_validate(payload)
    report = CodeAdherenceValidator().validate(file_context, baseline)
    assert "UNKNOWN_SPECIFICATION_REFERENCE" in _codes(report)


def test_candidate_server_owned_binding_mismatch_is_rejected(tmp_path):
    candidate, _, fixture = _generate(tmp_path, VALID_ESM_ROUTE)
    context, plan, planned_file, dependencies, *_ = fixture
    file_context = FileGenerationContextBuilder().build(
        context, plan, planned_file, dependencies
    )
    payload = candidate.model_dump(mode="python")
    payload.update(
        relative_output_path=RelativeOutputPath(
            "backend/src/routes/unapproved.routes.js"
        ),
        adherence_report=None,
        writer_eligible=False,
    )
    baseline = GeneratedContentCandidate.model_validate(payload)
    report = CodeAdherenceValidator().validate(file_context, baseline)
    assert "CANDIDATE_CONTEXT_BINDING_MISMATCH" in _codes(report)
    assert report.writer_eligible is False


def test_finding_codes_and_report_fingerprint_are_stable(tmp_path):
    first = _direct_report(tmp_path, REAL_SMOKE_OUTPUT)
    second = _direct_report(tmp_path, REAL_SMOKE_OUTPUT)
    assert _codes(first) == _codes(second)
    assert first.report_fingerprint == second.report_fingerprint
    assert first.validation_policy_version == ADHERENCE_POLICY_VERSION


def test_adherence_report_fingerprint_cannot_be_forged(tmp_path):
    report = _direct_report(tmp_path, VALID_ESM_ROUTE)
    with pytest.raises(ValidationError, match="fingerprint"):
        type(report).model_validate(
            {**report.model_dump(mode="python"), "report_fingerprint": "0" * 64}
        )


def test_dynamic_module_reference_requires_review(tmp_path):
    report = _direct_report(
        tmp_path,
        VALID_ESM_ROUTE.replace(
            "const router = express.Router();",
            "const router = express.Router();\nconst optional = import(moduleName);",
        ),
    )
    assert "DYNAMIC_MODULE_REFERENCE" in _codes(report)
    assert report.writer_eligible is False


def test_parser_unavailability_is_explicit_without_claiming_syntax_validation(tmp_path):
    report = _direct_report(tmp_path, VALID_ESM_ROUTE)
    parser = _check(report, "JAVASCRIPT_PARSER")
    assert parser.status is AdherenceCheckStatus.NOT_CHECKED
    assert "JAVASCRIPT_PARSER_UNAVAILABLE" in _codes(report)


def test_approved_run_and_plan_remain_immutable_and_no_side_effects_occur(tmp_path):
    context, plan, planned_file, dependencies, boundary, stored, _ = _fixture(tmp_path)
    context_before = deepcopy(context.model_dump(mode="json"))
    plan_before = deepcopy(plan.model_dump(mode="json"))
    stored_before = deepcopy(stored.runs[0].model_dump(mode="json"))
    paths_before = sorted(path.relative_to(tmp_path) for path in tmp_path.rglob("*"))
    provider = FakeLocalProvider(ModelFileResponse(content=REAL_SMOKE_OUTPUT))

    candidate = service(provider).generate_file(
        context, plan, planned_file, dependencies
    )

    assert candidate.writer_eligible is False
    assert context.model_dump(mode="json") == context_before
    assert plan.model_dump(mode="json") == plan_before
    assert stored.runs[0].model_dump(mode="json") == stored_before
    assert sorted(path.relative_to(tmp_path) for path in tmp_path.rglob("*")) == paths_before
    assert boundary.create_calls == boundary.github_calls == boundary.inference_calls == 0
    assert len(provider.requests) == 1
