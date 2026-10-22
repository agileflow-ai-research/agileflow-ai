import inspect

import pytest

from app.modules.agents.requirements.contracts.schemas import RequirementSourceType
from app.modules.agents.requirements.discovery.contracts import StructuredRequirementType
from app.modules.agents.requirements.processing.preparation.schemas import (
    MediaSegmentReference,
    NormalizedProvenanceSpan,
)
from app.modules.agents.requirements.quality.contracts import (
    QualityRequirement,
    ValidatedQualityInput,
)
from app.modules.agents.requirements.quality.exact_duplicates import ExactDuplicateDetector


def requirement(index, statement, *, kind=StructuredRequirementType.FUNCTIONAL,
                source_type=RequirementSourceType.DOCUMENT, source_number=None,
                chunk_number=None):
    source_number = source_number or index
    chunk_number = chunk_number or index
    prefix = "FR" if kind is StructuredRequirementType.FUNCTIONAL else "NFR"
    source_prefix = {
        RequirementSourceType.DOCUMENT: "DOC",
        RequirementSourceType.AUDIO: "AUD",
        RequirementSourceType.VIDEO: "VID",
    }[source_type]
    media = [] if source_type is RequirementSourceType.DOCUMENT else [
        MediaSegmentReference(segment_index=index, start_seconds=1.0,
                              end_seconds=2.0)
    ]
    provenance = NormalizedProvenanceSpan(
        normalized_start_offset=0, normalized_end_offset=len(statement),
        page_numbers=[index] if source_type is RequirementSourceType.DOCUMENT else [],
        media_segments=media,
    )
    return QualityRequirement(
        requirement_id=f"{prefix}-{index:016X}",
        requirement_type=kind,
        statement=statement,
        candidate_id=f"RC-{index:016X}",
        candidate_identity=f"{index:064x}",
        chunk_id=f"CHK-{chunk_number:016X}",
        source_id=f"{source_prefix}-{source_number:03d}",
        source_type=source_type,
        start_offset=0,
        end_offset=len(statement),
        provenance=(provenance,),
        classification_confidence=0.8,
        classifier_configuration_fingerprint="c" * 64,
    )


def quality_input(*requirements, identity="a" * 64):
    return ValidatedQualityInput(
        contract_version="1", agent_project_id="AGP-020",
        n3_execution_id="N3-AAAAAAAAAAAAAAAA-001", n3_attempt=1,
        n2_execution_id="N2-BBBBBBBBBBBBBBBB-001",
        discovery_input_identity="d" * 64, chunk_set_digest="e" * 64,
        candidate_artifact_digest="1" * 64,
        classification_artifact_digest="2" * 64,
        structured_artifact_digest="3" * 64,
        structured_set_identity="4" * 64,
        classifier_configuration_fingerprint="c" * 64,
        requirements=requirements, input_identity=identity,
    )


@pytest.mark.parametrize("kind", [
    StructuredRequirementType.FUNCTIONAL,
    StructuredRequirementType.NON_FUNCTIONAL,
])
def test_two_identical_same_type_statements_form_one_group(kind):
    first = requirement(1, "The system shall send a confirmation email.", kind=kind)
    second = requirement(2, first.statement, kind=kind)
    result = ExactDuplicateDetector().detect(quality_input(first, second))
    assert result.duplicate_group_count == 1
    assert result.affected_requirement_count == 2
    assert result.duplicate_groups[0].count == 2


def test_cross_type_duplicates_preserve_types_and_original_statements():
    statement = "The system must encrypt stored passwords."
    first = requirement(1, statement)
    second = requirement(2, statement, kind=StructuredRequirementType.NON_FUNCTIONAL)
    group = ExactDuplicateDetector().detect(quality_input(first, second)).duplicate_groups[0]
    assert [item.requirement.requirement_type for item in group.members] == [
        StructuredRequirementType.FUNCTIONAL,
        StructuredRequirementType.NON_FUNCTIONAL,
    ]
    assert [item.requirement.statement for item in group.members] == [statement, statement]


def test_three_duplicates_are_one_group_not_pairs():
    items = tuple(requirement(index, "The user can cancel a booking.")
                  for index in range(1, 4))
    result = ExactDuplicateDetector().detect(quality_input(*items))
    assert result.duplicate_group_count == 1
    assert result.duplicate_groups[0].count == 3


@pytest.mark.parametrize("second", [
    "Users must be able to create an account.",
    "A booking can be cancelled by the user.",
    "The user can cancel a booking",
    "A booking the user can cancel.",
])
def test_semantic_punctuation_and_word_order_differences_do_not_match(second):
    first = requirement(1, "The user can cancel a booking.")
    result = ExactDuplicateDetector().detect(quality_input(first, requirement(2, second)))
    assert result.duplicate_groups == ()


@pytest.mark.parametrize("left,right", [
    ("  The system shall register users.  ", "The system shall register users."),
    ("The  system\tshall register users.", "The system shall register users."),
    ("The system shall\r\nregister users.", "The system shall register users."),
    ("The User CAN Register.", "the user can register."),
    ("Caf\u00e9 access shall be supported.", "Cafe\u0301 access shall be supported."),
    ("Ａccess shall be logged.", "Access shall be logged."),
])
def test_documented_representation_normalization_matches(left, right):
    result = ExactDuplicateDetector().detect(
        quality_input(requirement(1, left), requirement(2, right))
    )
    assert result.duplicate_group_count == 1
    assert [member.requirement.statement for member in result.duplicate_groups[0].members] == [left, right]


@pytest.mark.parametrize("source_type", list(RequirementSourceType))
def test_cross_source_traceability_and_typed_provenance_are_retained(source_type):
    statement = "The platform shall retain audit evidence."
    first = requirement(1, statement, source_type=source_type, source_number=1)
    second = requirement(2, statement, source_type=source_type, source_number=2)
    members = ExactDuplicateDetector().detect(
        quality_input(first, second)
    ).duplicate_groups[0].members
    assert [member.requirement.source_id for member in members] == [
        first.source_id, second.source_id
    ]
    assert members[0].requirement.candidate_id == first.candidate_id
    assert members[0].requirement.chunk_id == first.chunk_id
    assert members[0].requirement.provenance == first.provenance


def test_same_source_different_chunks_are_duplicates():
    statement = "The system shall archive invoices."
    first = requirement(1, statement, source_number=1, chunk_number=1)
    second = requirement(2, statement, source_number=1, chunk_number=2)
    assert ExactDuplicateDetector().detect(
        quality_input(first, second)
    ).duplicate_group_count == 1


def test_same_requirement_record_never_duplicates_itself():
    item = requirement(1, "The system shall archive invoices.")
    assert ExactDuplicateDetector().detect(quality_input(item, item)).duplicate_groups == ()


def test_empty_and_distinct_inputs_have_deterministic_zero_group_result():
    detector = ExactDuplicateDetector()
    empty = quality_input()
    first = detector.detect(empty)
    assert first == detector.detect(empty)
    assert first.duplicate_groups == ()
    assert first.affected_requirement_count == 0
    distinct = quality_input(requirement(1, "First requirement."),
                             requirement(2, "Second requirement."))
    assert detector.detect(distinct).duplicate_groups == ()


def test_group_and_result_identities_are_deterministic_and_membership_sensitive():
    items = tuple(requirement(index, "Identical requirement.") for index in range(1, 4))
    detector = ExactDuplicateDetector()
    two = detector.detect(quality_input(*items[:2], identity="1" * 64))
    replay = detector.detect(quality_input(*items[:2], identity="1" * 64))
    three = detector.detect(quality_input(*items, identity="2" * 64))
    assert two == replay
    assert two.duplicate_groups[0].duplicate_group_id.startswith("QDUP-")
    assert two.duplicate_groups[0].duplicate_group_id != three.duplicate_groups[0].duplicate_group_id
    assert two.result_identity != three.result_identity


def test_detector_fingerprint_is_deterministic_and_versioned():
    first = ExactDuplicateDetector()
    assert first.configuration_fingerprint == ExactDuplicateDetector().configuration_fingerprint
    assert first.configuration_fingerprint != ExactDuplicateDetector(
        normalization_version="2"
    ).configuration_fingerprint


def test_group_and_member_order_follow_quality_input_evidence_order():
    items = (
        requirement(9, "Second group."),
        requirement(7, "First group."),
        requirement(5, "Second group."),
        requirement(3, "First group."),
    )
    groups = ExactDuplicateDetector().detect(quality_input(*items)).duplicate_groups
    assert [[member.requirement.requirement_id for member in group.members]
            for group in groups] == [
        [items[0].requirement_id, items[2].requirement_id],
        [items[1].requirement_id, items[3].requirement_id],
    ]


def test_detector_accepts_only_validated_quality_input_and_has_no_external_dependencies():
    annotation = inspect.signature(ExactDuplicateDetector.detect).parameters["value"].annotation
    assert annotation is ValidatedQualityInput
    source = inspect.getsource(ExactDuplicateDetector)
    for forbidden in ("open(", "Path(", "model", "embedding", "sbert"):
        assert forbidden not in source.casefold()
