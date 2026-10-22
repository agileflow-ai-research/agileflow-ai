import inspect

import pytest

from app.modules.agents.requirements.contracts.schemas import RequirementSourceType
from app.modules.agents.requirements.discovery.contracts import StructuredRequirementType
from app.modules.agents.requirements.quality.clarity.service import RequirementClarityService
from app.modules.agents.requirements.quality.contracts import (
    RequirementClarityIssueType,
    RequirementClaritySignal,
    ValidatedQualityInput,
)
from test_agent1_exact_duplicates import quality_input, requirement


def analyze(statement, **kwargs):
    item = requirement(1, statement, **kwargs)
    return item, RequirementClarityService().analyze(quality_input(item))


def signals(result):
    return [item.signal_code for item in result.issues]


def test_vague_performance_emits_ambiguity_and_missing_target():
    statement = "The application should respond quickly."
    original, result = analyze(statement)
    assert signals(result) == [
        RequirementClaritySignal.VAGUE_QUALIFIER,
        RequirementClaritySignal.PERFORMANCE_TARGET_MISSING,
    ]
    assert result.ambiguity_count == 1
    assert result.missing_information_count == 1
    assert all(item.requirement == original for item in result.issues)


def test_explicit_duration_does_not_emit_performance_missing():
    _, result = analyze("The page shall load within 3 seconds.")
    assert RequirementClaritySignal.PERFORMANCE_TARGET_MISSING not in signals(result)
    _, result = analyze("The API shall return a response within 500 milliseconds for 95% of requests.",
                        kind=StructuredRequirementType.NON_FUNCTIONAL)
    assert result.issues == ()


def test_vague_capacity_emits_quantifier_and_missing_target():
    _, result = analyze("The system shall support many concurrent users.")
    assert signals(result) == [
        RequirementClaritySignal.VAGUE_QUANTIFIER,
        RequirementClaritySignal.CAPACITY_TARGET_MISSING,
    ]


def test_explicit_capacity_is_clear_and_ordinary_users_are_not_capacity():
    assert analyze("The system shall support 500 concurrent users.")[1].issues == ()
    assert analyze("Users can register.")[1].issues == ()


def test_high_availability_emits_subjective_and_missing_target():
    _, result = analyze("The service shall be highly available.",
                        kind=StructuredRequirementType.NON_FUNCTIONAL)
    assert signals(result) == [
        RequirementClaritySignal.SUBJECTIVE_TERM,
        RequirementClaritySignal.AVAILABILITY_TARGET_MISSING,
    ]


def test_percentage_availability_is_measurable():
    assert analyze("The service shall maintain 99.9% monthly availability.",
                   kind=StructuredRequirementType.NON_FUNCTIONAL)[1].issues == ()


def test_vague_frequency_emits_ambiguity_and_missing_schedule():
    _, result = analyze("Backups shall run regularly.")
    assert signals(result) == [
        RequirementClaritySignal.VAGUE_FREQUENCY,
        RequirementClaritySignal.FREQUENCY_VALUE_MISSING,
    ]


@pytest.mark.parametrize("statement", [
    "Backups shall run every 24 hours.",
    "Backups shall run daily.",
    "Reports shall run weekly.",
    "Archives shall run monthly.",
])
def test_explicit_frequency_is_clear(statement):
    assert analyze(statement)[1].issues == ()


@pytest.mark.parametrize("phrase", ["when appropriate", "if necessary", "as needed"])
def test_unclear_condition_emits_ambiguity_and_missing_detail(phrase):
    _, result = analyze(f"The account may be disabled {phrase}.")
    assert signals(result) == [
        RequirementClaritySignal.UNCLEAR_CONDITION,
        RequirementClaritySignal.CONDITION_DETAIL_MISSING,
    ]


@pytest.mark.parametrize("phrase", ["etc.", "and so on", "and similar", "and related items"])
def test_open_ended_language_is_ambiguous(phrase):
    _, result = analyze(f"The user can upload PDF, DOCX, {phrase}")
    assert signals(result) == [RequirementClaritySignal.OPEN_ENDED_PHRASE]


@pytest.mark.parametrize("term", ["user-friendly", "intuitive", "easy to use", "seamless", "robust"])
def test_subjective_terms_are_ambiguous(term):
    _, result = analyze(f"The interface shall be {term}.")
    assert signals(result) == [RequirementClaritySignal.SUBJECTIVE_TERM]


def test_evidence_preserves_original_case_text_and_exact_offsets():
    statement = "The page shall respond QUICKLY."
    original, result = analyze(statement)
    issue = result.issues[0]
    assert issue.evidence_text == "QUICKLY"
    assert statement[issue.evidence_start:issue.evidence_end] == issue.evidence_text
    assert issue.requirement.statement == original.statement == statement


@pytest.mark.parametrize("source_type", list(RequirementSourceType))
def test_full_typed_traceability_is_retained(source_type):
    original, result = analyze(
        "The service shall respond quickly.", source_type=source_type,
        source_number=2, chunk_number=3,
    )
    issue = result.issues[0]
    assert issue.requirement.candidate_id == original.candidate_id
    assert issue.requirement.chunk_id == original.chunk_id
    assert issue.requirement.source_id == original.source_id
    assert issue.requirement.source_type is source_type
    assert issue.requirement.provenance == original.provenance


@pytest.mark.parametrize("kind", list(StructuredRequirementType))
def test_fr_and_nfr_are_analyzed_without_reclassification(kind):
    original, result = analyze("The administrator may suspend users when appropriate.", kind=kind)
    assert result.issues
    assert all(item.requirement.requirement_type is kind for item in result.issues)
    assert original.requirement_type is kind


def test_weak_modals_alone_are_not_ambiguous():
    for statement in ("Users should register.", "Users may register.", "Users could register."):
        assert analyze(statement)[1].issues == ()


@pytest.mark.parametrize("statement", [
    "The breakfast menu shall load.",
    "The system shall store quicklyish identifiers.",
    "The reasonableValue field shall be retained.",
    "The system shall classify regularity metrics.",
])
def test_token_boundaries_prevent_substring_false_positives(statement):
    assert analyze(statement)[1].issues == ()


def test_clear_functional_requirement_has_zero_issues():
    assert analyze("The administrator shall disable an account after three failed login attempts.")[1].issues == ()


def test_issue_ids_result_identity_and_fingerprint_are_deterministic():
    value = quality_input(requirement(1, "Respond quickly."),
                          requirement(2, "Run backups regularly."))
    service = RequirementClarityService()
    first, second = service.analyze(value), service.analyze(value)
    assert first == second
    assert first.result_identity == second.result_identity
    assert [item.issue_id for item in first.issues] == [item.issue_id for item in second.issues]
    assert service.configuration_fingerprint == RequirementClarityService().configuration_fingerprint
    assert all(item.issue_id.startswith(("QAMB-", "QMISS-")) for item in first.issues)


def test_requirement_and_catalog_order_are_stable_without_duplicate_issues():
    first = requirement(2, "Respond quickly and quickly.")
    second = requirement(1, "Run backups regularly.")
    result = RequirementClarityService().analyze(quality_input(first, second))
    assert [item.requirement.requirement_id for item in result.issues[:3]] == [
        first.requirement_id, first.requirement_id, first.requirement_id,
    ]
    signatures = [(item.requirement.requirement_id, item.signal_code,
                   item.evidence_start, item.evidence_end) for item in result.issues]
    assert len(signatures) == len(set(signatures))


def test_empty_quality_input_is_valid_and_deterministic():
    value = quality_input()
    result = RequirementClarityService().analyze(value)
    assert result.issues == ()
    assert result.ambiguity_count == result.missing_information_count == 0
    assert result.affected_requirement_count == 0
    assert result == RequirementClarityService().analyze(value)


def test_boundary_is_pure_and_accepts_only_validated_quality_input():
    annotation = inspect.signature(RequirementClarityService.analyze).parameters["value"].annotation
    assert annotation is ValidatedQualityInput
    source = inspect.getsource(RequirementClarityService)
    for forbidden in ("open(", "path(", "embedding", "sentence_transformer", "nli", "workflow", "persist"):
        assert forbidden not in source.casefold()
