import math

import pytest

from app.modules.agents.requirements.contracts.schemas import RequirementSourceType
from app.modules.agents.requirements.quality.clarity.service import RequirementClarityService
from app.modules.agents.requirements.quality.conflicts.service import RequirementConflictService
from app.modules.agents.requirements.quality.exact_duplicates import ExactDuplicateDetector
from app.modules.agents.requirements.quality.findings.contracts import (
    ClarificationIntent, QualityFindingType,
)
from app.modules.agents.requirements.quality.findings.service import (
    QualityConsolidationError, QualityConsolidationErrorCode,
    QualityFindingConsolidationService,
)
from app.modules.agents.requirements.quality.semantic_duplicates.service import SemanticDuplicateService
from test_agent1_conflicts import FakeNliProvider, scores
from test_agent1_exact_duplicates import quality_input, requirement
from test_agent1_semantic_duplicates import FakeProvider


def pipeline(value, *, semantic_vectors=None, conflict_vectors=None,
             nli_outputs=()):
    exact = ExactDuplicateDetector().detect(value)
    semantic_vectors = semantic_vectors if semantic_vectors is not None else tuple(
        (1.0, 0.0) for _ in value.requirements
    )
    semantic = SemanticDuplicateService(FakeProvider(semantic_vectors)).detect(value, exact)
    conflict_vectors = conflict_vectors if conflict_vectors is not None else tuple(
        (1.0, 0.0) for _ in value.requirements
    )
    conflicts = RequirementConflictService(
        FakeProvider(conflict_vectors), FakeNliProvider(nli_outputs)
    ).detect(value, exact, semantic)
    clarity = RequirementClarityService().analyze(value)
    return exact, semantic, conflicts, clarity


def consolidate(value, upstream):
    return QualityFindingConsolidationService().consolidate(value, *upstream)


def test_exact_group_becomes_one_finding_and_one_candidate():
    statement = "The system shall archive invoices."
    items = tuple(requirement(index, statement) for index in range(1, 4))
    value = quality_input(*items)
    result = consolidate(value, pipeline(value))
    assert result.total_findings == result.exact_duplicate_findings == 1
    finding = result.findings[0]
    assert finding.finding_type is QualityFindingType.EXACT_DUPLICATE
    assert finding.evidence.exact_duplicate_group.count == 3
    assert finding.evidence.upstream_evidence_id.startswith("QDUP-")
    assert finding.affected_requirements == items
    assert result.clarification_candidates[0].intent is ClarificationIntent.DUPLICATE_REVIEW


def test_semantic_pair_becomes_finding_with_model_evidence():
    left = requirement(1, "Users can cancel bookings.")
    right = requirement(2, "Customers may cancel reservations.")
    value = quality_input(left, right)
    upstream = pipeline(
        value, semantic_vectors=((1.0, 0.0), (1.0, 0.0)),
        conflict_vectors=((1.0, 0.0), (0.0, 1.0)),
    )
    result = consolidate(value, upstream)
    finding = result.findings[0]
    assert finding.finding_type is QualityFindingType.SEMANTIC_DUPLICATE
    assert finding.evidence.semantic_duplicate_pair.evidence.cosine_similarity == 1.0
    assert finding.detector_fingerprint == upstream[1].detector_fingerprint
    assert result.clarification_candidates[0].intent is ClarificationIntent.SEMANTIC_DUPLICATE_REVIEW


def test_conflict_pair_becomes_finding_with_directional_evidence():
    left = requirement(1, "Users may cancel bookings.")
    right = requirement(2, "Users may not cancel bookings.")
    value = quality_input(left, right)
    upstream = pipeline(
        value, semantic_vectors=((1.0, 0.0), (0.0, 1.0)),
        conflict_vectors=((1.0, 0.0), (1.0, 0.0)),
        nli_outputs=(scores(), scores()),
    )
    result = consolidate(value, upstream)
    finding = result.findings[0]
    assert finding.finding_type is QualityFindingType.CONFLICT
    assert finding.evidence.conflict_pair.left_to_right
    assert finding.evidence.conflict_pair.right_to_left
    assert result.clarification_candidates[0].intent is ClarificationIntent.CONFLICT_RESOLUTION


def test_clarity_issues_become_separate_findings_and_candidates():
    item = requirement(1, "The service shall respond quickly.")
    value = quality_input(item)
    result = consolidate(value, pipeline(value))
    assert [item.finding_type for item in result.findings] == [
        QualityFindingType.AMBIGUITY,
        QualityFindingType.MISSING_INFORMATION,
    ]
    assert [item.intent for item in result.clarification_candidates] == [
        ClarificationIntent.AMBIGUITY_CLARIFICATION,
        ClarificationIntent.MISSING_INFORMATION_REQUEST,
    ]
    assert result.ambiguity_findings == result.missing_information_findings == 1


def test_semantic_and_conflict_same_pair_remain_distinct_and_ordered():
    value = quality_input(requirement(1, "Users may cancel bookings."),
                          requirement(2, "Users may not cancel bookings."))
    upstream = pipeline(
        value, semantic_vectors=((1.0, 0.0), (1.0, 0.0)),
        conflict_vectors=((1.0, 0.0), (1.0, 0.0)),
        nli_outputs=(scores(), scores()),
    )
    result = consolidate(value, upstream)
    assert [item.finding_type for item in result.findings] == [
        QualityFindingType.SEMANTIC_DUPLICATE, QualityFindingType.CONFLICT,
    ]
    assert [candidate.finding_id for candidate in result.clarification_candidates] == [
        finding.finding_id for finding in result.findings
    ]


@pytest.mark.parametrize("source_type", list(RequirementSourceType))
def test_full_requirement_and_typed_provenance_are_retained(source_type):
    item = requirement(1, "The service shall respond quickly.",
                       source_type=source_type, source_number=2, chunk_number=3)
    value = quality_input(item)
    finding = consolidate(value, pipeline(value)).findings[0]
    retained = finding.affected_requirements[0]
    assert retained == item
    assert retained.statement == item.statement
    assert retained.candidate_id == item.candidate_id
    assert retained.chunk_id == item.chunk_id
    assert retained.source_id == item.source_id
    assert retained.provenance == item.provenance


def test_ids_fingerprint_result_and_reasons_are_deterministic():
    value = quality_input(requirement(1, "Respond quickly."))
    upstream = pipeline(value)
    service = QualityFindingConsolidationService()
    first, second = service.consolidate(value, *upstream), service.consolidate(value, *upstream)
    assert first == second
    assert first.result_identity == second.result_identity
    assert first.consolidation_fingerprint == service.configuration_fingerprint
    assert all(item.finding_id.startswith("QF-") for item in first.findings)
    assert all(item.clarification_candidate_id.startswith("QCL-") for item in first.clarification_candidates)
    assert all(item.requires_human_input for item in first.clarification_candidates)
    assert all(item.reason for item in first.clarification_candidates)


def test_counts_deduplicate_affected_requirements():
    value = quality_input(requirement(1, "Users may cancel quickly."),
                          requirement(2, "Users may not cancel quickly."))
    upstream = pipeline(
        value, semantic_vectors=((1.0, 0.0), (1.0, 0.0)),
        conflict_vectors=((1.0, 0.0), (1.0, 0.0)),
        nli_outputs=(scores(), scores()),
    )
    result = consolidate(value, upstream)
    assert result.total_findings == sum((
        result.exact_duplicate_findings, result.semantic_duplicate_findings,
        result.conflict_findings, result.ambiguity_findings,
        result.missing_information_findings,
    ))
    assert result.affected_requirement_count == 2
    assert result.clarification_candidate_count == result.total_findings


def test_empty_quality_and_empty_evidence_return_zero_result():
    value = quality_input()
    result = consolidate(value, pipeline(value))
    assert result.findings == result.clarification_candidates == ()
    assert result.total_findings == result.affected_requirement_count == 0


@pytest.mark.parametrize("index", range(4))
def test_each_upstream_identity_mismatch_is_rejected(index):
    value = quality_input(requirement(1, "Clear requirement."))
    upstream = list(pipeline(value))
    upstream[index] = upstream[index].model_copy(update={"quality_input_identity": "f" * 64})
    with pytest.raises(QualityConsolidationError) as error:
        consolidate(value, tuple(upstream))
    assert error.value.code is QualityConsolidationErrorCode.IDENTITY_MISMATCH


def test_project_and_upstream_relationship_mismatches_are_rejected():
    value = quality_input(requirement(1, "Clear requirement."))
    upstream = list(pipeline(value))
    upstream[0] = upstream[0].model_copy(update={"agent_project_id": "AGP-999"})
    with pytest.raises(QualityConsolidationError):
        consolidate(value, tuple(upstream))
    upstream = list(pipeline(value))
    upstream[2] = upstream[2].model_copy(update={"semantic_duplicate_result_identity": "f" * 64})
    with pytest.raises(QualityConsolidationError) as error:
        consolidate(value, tuple(upstream))
    assert error.value.code is QualityConsolidationErrorCode.IDENTITY_MISMATCH


def test_changed_embedded_requirement_traceability_is_rejected():
    item = requirement(1, "Respond quickly.")
    value = quality_input(item)
    upstream = list(pipeline(value))
    issue = upstream[3].issues[0]
    changed = issue.requirement.model_copy(update={"statement": "Changed statement."})
    changed_issue = issue.model_copy(update={"requirement": changed})
    upstream[3] = upstream[3].model_copy(update={"issues": (changed_issue,)})
    with pytest.raises(QualityConsolidationError) as error:
        consolidate(value, tuple(upstream))
    assert error.value.code is QualityConsolidationErrorCode.TRACEABILITY_INVALID


def test_unknown_requirement_is_rejected():
    item = requirement(1, "Respond quickly.")
    value = quality_input(item)
    upstream = list(pipeline(value))
    unknown = item.model_copy(update={
        "requirement_id": "FR-FFFFFFFFFFFFFFFF",
        "candidate_id": "RC-FFFFFFFFFFFFFFFF",
    })
    changed_issue = upstream[3].issues[0].model_copy(update={"requirement": unknown})
    upstream[3] = upstream[3].model_copy(update={"issues": (changed_issue,)})
    with pytest.raises(QualityConsolidationError) as error:
        consolidate(value, tuple(upstream))
    assert error.value.code is QualityConsolidationErrorCode.TRACEABILITY_INVALID


def test_exact_pair_leaking_into_semantic_or_conflict_is_rejected():
    first = requirement(1, "Same requirement.")
    second = requirement(2, first.statement)
    exact_value = quality_input(first, second)
    exact_upstream = list(pipeline(exact_value))

    template_value = quality_input(requirement(1, "One wording."), requirement(2, "Other wording."))
    semantic_template = pipeline(
        template_value, semantic_vectors=((1.0, 0.0), (1.0, 0.0)),
        conflict_vectors=((1.0, 0.0), (0.0, 1.0)),
    )[1].pairs[0]
    leaked_semantic = semantic_template.model_copy(update={
        "quality_input_identity": exact_value.input_identity,
        "left": first, "right": second,
    })
    exact_upstream[1] = exact_upstream[1].model_copy(update={
        "pairs": (leaked_semantic,), "pair_count": 1,
    })
    exact_upstream[2] = exact_upstream[2].model_copy(update={
        "semantic_duplicate_result_identity": exact_upstream[1].result_identity,
    })
    with pytest.raises(QualityConsolidationError) as error:
        consolidate(exact_value, tuple(exact_upstream))
    assert error.value.code is QualityConsolidationErrorCode.UPSTREAM_INCONSISTENT

    conflict_template = pipeline(
        template_value, semantic_vectors=((1.0, 0.0), (0.0, 1.0)),
        conflict_vectors=((1.0, 0.0), (1.0, 0.0)), nli_outputs=(scores(), scores()),
    )[2].conflicts[0]
    exact_upstream = list(pipeline(exact_value))
    leaked_conflict = conflict_template.model_copy(update={
        "quality_input_identity": exact_value.input_identity,
        "left": first, "right": second,
    })
    exact_upstream[2] = exact_upstream[2].model_copy(update={
        "conflicts": (leaked_conflict,), "conflict_count": 1,
        "relatedness_candidate_pair_count": 1, "nli_evaluated_pair_count": 1,
    })
    with pytest.raises(QualityConsolidationError) as error:
        consolidate(exact_value, tuple(exact_upstream))
    assert error.value.code is QualityConsolidationErrorCode.UPSTREAM_INCONSISTENT


def test_candidate_contract_has_no_answer_resolution_score_or_severity():
    value = quality_input(requirement(1, "Respond quickly."))
    result = consolidate(value, pipeline(value))
    candidate_fields = set(type(result.clarification_candidates[0]).model_fields)
    finding_fields = set(type(result.findings[0]).model_fields)
    assert not candidate_fields.intersection({"answer", "question", "resolution", "rewritten_requirement"})
    assert not finding_fields.intersection({"severity", "quality_score", "resolution"})
