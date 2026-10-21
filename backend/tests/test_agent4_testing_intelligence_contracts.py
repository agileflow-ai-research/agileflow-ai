from datetime import UTC, datetime
from hashlib import sha256
from types import MappingProxyType

import pytest
from pydantic import ValidationError

from app.modules.agents.testing_validation.intelligence.schemas import (
    ClassificationEvidence,
    ClassificationEvidenceType,
    HybridEvidenceState,
    HybridLabelDecision,
    HybridLabelDecisionStatus,
    TestingChunkReference as ChunkReference,
    TestingHybridClassificationResult as HybridResult,
    TestingIntelligenceGroundTruth as GroundTruth,
    TestingRuleClassificationResult as RuleResult,
    TestingZeroShotClassificationResult as ZeroShotResult,
    ZeroShotInputMetadata,
    current_chunk_reference,
)
from app.modules.agents.testing_validation.intelligence.taxonomy import (
    AGENT4_TESTING_TAXONOMY_VERSION,
    AGENT4_ZERO_SHOT_LABEL_DESCRIPTION_VERSION,
    TESTING_INTELLIGENCE_LABEL_ORDER,
    TESTING_INTELLIGENCE_TAXONOMY,
    TestingIntelligenceLabel as IntelligenceLabel,
    get_testing_taxonomy_entry,
)
from app.modules.agents.testing_validation.preparation.chunking.constants import (
    CHUNKER_VERSION,
    CHUNK_POLICY_VERSION,
)
from app.modules.agents.testing_validation.preparation.chunking.schemas import (
    TestingChunk as Chunk,
    TestingChunkMetrics as ChunkMetrics,
    TestingChunkSet as ChunkSet,
    TestingChunkSourceSpan as ChunkSpan,
)
from app.modules.agents.testing_validation.workflow.schemas import (
    Agent4TestGenerationNodeId,
    Agent4WorkflowNodeStatus,
)
from test_agent4_n2_orchestration import (
    add_text,
    confirm,
    create_project,
    load,
    n2_context,
)


HEX_A = "a" * 32
HEX_B = "b" * 32
CHUNK_TEXT = "Only administrators may delete another user's booking."
SHA_A = sha256(CHUNK_TEXT.encode("utf-8")).hexdigest()
SHA_B = "b" * 64
NOW = datetime(2026, 1, 2, tzinfo=UTC)


def chunk() -> Chunk:
    return Chunk(
        chunk_id=f"A4CHK-{HEX_A}",
        agent_project_id="AGP-123",
        source_id=f"A4SRC-{HEX_A}",
        normalized_artifact_id=f"A4ART-{HEX_A}",
        artifact_type="FUNCTIONAL_REQUIREMENTS",
        source_type="TEXT",
        sequence=1,
        heading_path=[],
        structure_type="TEXT",
        text=CHUNK_TEXT,
        text_sha256=SHA_A,
        token_count=8,
        overlap_token_count=0,
        source_segment_ids=[f"A4SEG-{HEX_A}"],
        source_spans=[
            ChunkSpan(
                source_segment_id=f"A4SEG-{HEX_A}",
                segment_kind="TEXT",
                start_offset=0,
                end_offset=55,
            )
        ],
        source_evidence_sha256=SHA_B,
        normalization_fingerprint="c" * 64,
        inherited_warning_codes=[],
    )


def chunk_set(item: Chunk | None = None) -> ChunkSet:
    item = item or chunk()
    return ChunkSet(
        chunker_version=CHUNKER_VERSION,
        policy_version=CHUNK_POLICY_VERSION,
        policy_fingerprint="d" * 64,
        input_fingerprint="e" * 64,
        chunk_set_fingerprint="f" * 64,
        agent_project_id=item.agent_project_id,
        source_id=item.source_id,
        normalized_artifact_id=item.normalized_artifact_id,
        normalization_fingerprint=item.normalization_fingerprint,
        source_evidence_sha256=item.source_evidence_sha256,
        chunk_ids=[item.chunk_id],
        chunks=[item],
        metrics=ChunkMetrics(
            chunk_count=1,
            total_tokens=item.token_count,
            min_chunk_tokens=item.token_count,
            max_chunk_tokens=item.token_count,
        ),
        created_at=NOW,
    )


def reference() -> ChunkReference:
    item = chunk()
    return current_chunk_reference(
        item, chunk_set(item), confirmed_source_ids={item.source_id}
    )


def evidence(**overrides) -> ClassificationEvidence:
    data = {
        "evidence_id": f"A4EVD-{HEX_A}",
        "chunk_id": f"A4CHK-{HEX_A}",
        "label": "AUTHORIZATION",
        "evidence_type": "RULE",
        "quote": "Only administrators",
        "start_offset": 0,
        "end_offset": 19,
        "source_segment_ids": [f"A4SEG-{HEX_A}"],
        "confidence": 0.9,
        "reason_code": "ROLE_RESTRICTION",
    }
    data.update(overrides)
    return ClassificationEvidence.model_validate(data)


def full_scores() -> dict[str, float]:
    return {label.value: index / 20 for index, label in enumerate(TESTING_INTELLIGENCE_LABEL_ORDER)}


def zero_shot(**overrides) -> ZeroShotResult:
    data = {
        "result_id": f"A4ZSC-{HEX_A}",
        "chunk": reference(),
        "taxonomy_version": "T1",
        "model_id": "future/model",
        "model_revision": "revision-1",
        "label_scores": full_scores(),
        "label_description_version": "ZL1",
        "hypothesis_template_version": "H1",
        "input_metadata": {
            "input_token_count": 8,
            "model_max_tokens": 512,
            "truncated": False,
            "tokens_discarded": 0,
        },
        "inference_duration_ms": 4.2,
        "processed_at": NOW,
    }
    data.update(overrides)
    return ZeroShotResult.model_validate(data)


def test_taxonomy_is_exact_versioned_ordered_and_read_only():
    expected = (
        "FUNCTIONAL_BEHAVIOR", "INPUT_VALIDATION", "BOUNDARY_CONSTRAINT",
        "DATA_INTEGRITY", "API_CONTRACT", "UI_WORKFLOW", "AUTHENTICATION",
        "AUTHORIZATION", "SECURITY_CONTROL", "PERFORMANCE_SLO",
        "RELIABILITY_RECOVERY", "ERROR_HANDLING", "ACCEPTANCE_CONDITION",
        "STATE_PERSISTENCE", "NON_TESTABLE_CONTEXT",
    )
    assert AGENT4_TESTING_TAXONOMY_VERSION == "T1"
    assert tuple(label.value for label in TESTING_INTELLIGENCE_LABEL_ORDER) == expected
    assert len(IntelligenceLabel) == 15
    assert len(set(IntelligenceLabel)) == 15
    assert isinstance(TESTING_INTELLIGENCE_TAXONOMY, MappingProxyType)
    assert tuple(TESTING_INTELLIGENCE_TAXONOMY) == TESTING_INTELLIGENCE_LABEL_ORDER
    with pytest.raises(TypeError):
        TESTING_INTELLIGENCE_TAXONOMY[IntelligenceLabel.API_CONTRACT] = None


def test_every_taxonomy_entry_is_complete_and_unknown_labels_are_rejected():
    for label in TESTING_INTELLIGENCE_LABEL_ORDER:
        entry = get_testing_taxonomy_entry(label)
        assert entry.code is label
        assert entry.definition
        assert entry.model_description
        assert entry.evaluation_definition
    assert AGENT4_ZERO_SHOT_LABEL_DESCRIPTION_VERSION == "ZL1"
    with pytest.raises(ValueError):
        IntelligenceLabel("API")
    with pytest.raises(ValueError):
        get_testing_taxonomy_entry("POSITIVE_BEHAVIOR")


def test_semantic_fact_values_are_not_classifier_labels():
    forbidden = {
        "POSITIVE_BEHAVIOR", "NEGATIVE_BEHAVIOR", "EXPECTED_RESULT",
        "ERROR_RESULT", "MIN_VALUE", "MAX_VALUE", "ACTOR", "FIELD",
        "ENTITY", "UNIQUENESS",
    }
    actual = {label.value for label in IntelligenceLabel}
    assert actual.isdisjoint(forbidden)
    assert list(actual).count("NON_TESTABLE_CONTEXT") == 1
    assert "Uniqueness is a subtype" in get_testing_taxonomy_entry(
        "DATA_INTEGRITY"
    ).exclusion_notes[0]


def test_chunk_reference_binds_identity_and_not_chunk_text():
    item = chunk()
    result = current_chunk_reference(
        item, chunk_set(item), confirmed_source_ids={item.source_id}
    )
    payload = result.model_dump(mode="json")
    assert payload["chunk_id"] == item.chunk_id
    assert payload["source_id"] == item.source_id
    assert payload["artifact_type"] == "FUNCTIONAL_REQUIREMENTS"
    assert payload["text_sha256"] == item.text_sha256
    assert "text" not in payload
    assert "source_spans" not in payload


def test_chunk_eligibility_requires_confirmed_source_and_exact_text_hash():
    item = chunk()
    manifest = chunk_set(item)
    with pytest.raises(ValueError, match="confirmation snapshot"):
        current_chunk_reference(item, manifest, confirmed_source_ids=set())
    corrupt_hash = item.model_copy(update={"text_sha256": "0" * 64})
    corrupt_manifest = chunk_set(corrupt_hash)
    with pytest.raises(ValueError, match="evidence hash"):
        current_chunk_reference(
            corrupt_hash,
            corrupt_manifest,
            confirmed_source_ids={corrupt_hash.source_id},
        )


@pytest.mark.parametrize("change", ["membership", "content", "version", "image"])
def test_chunk_eligibility_requires_current_textual_manifest_evidence(change):
    item = chunk()
    manifest = chunk_set(item)
    if change == "membership":
        outsider = item.model_copy(update={"chunk_id": f"A4CHK-{HEX_B}"})
        with pytest.raises(ValueError, match="not present"):
            current_chunk_reference(
                outsider, manifest, confirmed_source_ids={outsider.source_id}
            )
    elif change == "content":
        altered = item.model_copy(update={"text": "changed"})
        with pytest.raises(ValueError, match="does not match"):
            current_chunk_reference(
                altered, manifest, confirmed_source_ids={altered.source_id}
            )
    elif change == "version":
        stale = manifest.model_copy(update={"chunker_version": "C0"})
        with pytest.raises(ValueError, match="current chunking policy"):
            current_chunk_reference(
                item, stale, confirmed_source_ids={item.source_id}
            )
    else:
        image = Chunk.model_validate(
            {**item.model_dump(mode="json"), "source_type": "IMAGE"}
        )
        image_manifest = chunk_set(image)
        with pytest.raises(ValueError, match="image sources"):
            current_chunk_reference(
                image, image_manifest, confirmed_source_ids={image.source_id}
            )


def test_evidence_is_strict_grounded_and_score_bounded():
    value = evidence()
    assert value.chunk_id == reference().chunk_id
    assert value.label is IntelligenceLabel.AUTHORIZATION
    with pytest.raises(ValidationError):
        evidence(extra="forbidden")
    with pytest.raises(ValidationError):
        evidence(label="UNKNOWN")
    with pytest.raises(ValidationError):
        evidence(start_offset=-1)
    with pytest.raises(ValidationError):
        evidence(start_offset=20, end_offset=10)
    with pytest.raises(ValidationError):
        evidence(start_offset=0, end_offset=None)
    with pytest.raises(ValidationError):
        evidence(confidence=-0.01)
    with pytest.raises(ValidationError):
        evidence(confidence=1.01)


def test_rule_result_is_multilabel_canonical_strict_and_model_free():
    second = evidence(
        evidence_id=f"A4EVD-{HEX_B}",
        label="FUNCTIONAL_BEHAVIOR",
    )
    result = RuleResult(
        result_id=f"A4RUL-{HEX_A}",
        chunk=reference(),
        taxonomy_version="T1",
        rules_version="R1",
        detected_labels=["AUTHORIZATION", "FUNCTIONAL_BEHAVIOR"],
        rule_evidence=[evidence(), second],
        processed_at=NOW,
    )
    assert result.detected_labels == [
        IntelligenceLabel.FUNCTIONAL_BEHAVIOR,
        IntelligenceLabel.AUTHORIZATION,
    ]
    payload = result.model_dump(mode="json")
    assert "model_id" not in payload
    assert "model_revision" not in payload
    with pytest.raises(ValidationError):
        RuleResult.model_validate(
            {**payload, "detected_labels": ["AUTHORIZATION", "AUTHORIZATION"]}
        )
    with pytest.raises(ValidationError):
        RuleResult.model_validate(
            {**payload, "taxonomy_version": "T2"}
        )
    with pytest.raises(ValidationError):
        RuleResult.model_validate({**payload, "rules_version": None})


def test_rule_evidence_must_match_type_chunk_and_detected_label():
    base = {
        "result_id": f"A4RUL-{HEX_A}",
        "chunk": reference(),
        "taxonomy_version": "T1",
        "rules_version": "R1",
        "detected_labels": ["AUTHORIZATION"],
        "processed_at": NOW,
    }
    with pytest.raises(ValidationError, match="RULE evidence"):
        RuleResult(
            **base,
            rule_evidence=[evidence(evidence_type="ZERO_SHOT")],
        )
    with pytest.raises(ValidationError, match="result chunk"):
        RuleResult(
            **base,
            rule_evidence=[evidence(chunk_id=f"A4CHK-{HEX_B}")],
        )
    with pytest.raises(ValidationError, match="must be detected"):
        RuleResult(
            **base,
            rule_evidence=[evidence(label="SECURITY_CONTROL")],
        )


def test_zero_shot_contract_requires_full_bounded_canonical_score_vector():
    result = zero_shot()
    assert list(result.label_scores) == list(TESTING_INTELLIGENCE_LABEL_ORDER)
    assert result.multi_label is True
    assert result.task == "zero-shot-classification"
    payload = result.model_dump(mode="json")
    assert not any("threshold" in key for key in payload)
    missing = full_scores()
    missing.pop("API_CONTRACT")
    with pytest.raises(ValidationError, match="complete taxonomy"):
        zero_shot(label_scores=missing)
    with pytest.raises(ValidationError):
        zero_shot(label_scores={**full_scores(), "UNKNOWN": 0.5})
    with pytest.raises(ValidationError):
        zero_shot(label_scores={**full_scores(), "API_CONTRACT": 1.1})
    with pytest.raises(ValidationError):
        zero_shot(model_id="")
    with pytest.raises(ValidationError):
        zero_shot(model_revision="")


def test_zero_shot_truncation_metadata_is_consistent_and_strict():
    assert ZeroShotInputMetadata(
        input_token_count=600,
        model_max_tokens=512,
        truncated=True,
        tokens_discarded=88,
    ).truncated
    with pytest.raises(ValidationError):
        ZeroShotInputMetadata(
            input_token_count=600,
            model_max_tokens=512,
            truncated=False,
            tokens_discarded=88,
        )
    with pytest.raises(ValidationError):
        ZeroShotInputMetadata.model_validate(
            {
                "input_token_count": 8,
                "model_max_tokens": 512,
                "truncated": False,
                "tokens_discarded": 0,
                "threshold": 0.5,
            }
        )


def decision(label, status, state) -> HybridLabelDecision:
    return HybridLabelDecision(
        label=label,
        status=status,
        evidence_state=state,
        reason_codes=["EXPLAINABLE_POLICY_REASON"],
        rule_evidence_ids=[f"A4EVD-{HEX_A}"],
        model_score=0.85,
    )


def test_hybrid_contract_is_multilabel_explainable_and_disjoint():
    result = HybridResult(
        result_id=f"A4HYB-{HEX_A}",
        chunk=reference(),
        taxonomy_version="T1",
        rule_result_id=f"A4RUL-{HEX_A}",
        zero_shot_result_id=f"A4ZSC-{HEX_A}",
        hybrid_policy_version="H1",
        accepted_labels=["AUTHORIZATION", "FUNCTIONAL_BEHAVIOR"],
        review_required_labels=["SECURITY_CONTROL"],
        rejected_labels=["NON_TESTABLE_CONTEXT"],
        decisions=[
            decision("FUNCTIONAL_BEHAVIOR", "ACCEPTED", "AGREEMENT"),
            decision("AUTHORIZATION", "ACCEPTED", "RULE_ONLY"),
            decision("SECURITY_CONTROL", "REVIEW_REQUIRED", "CONFLICT"),
            decision("NON_TESTABLE_CONTEXT", "REJECTED", "MODEL_ONLY"),
        ],
        processed_at=NOW,
    )
    assert result.accepted_labels == [
        IntelligenceLabel.FUNCTIONAL_BEHAVIOR,
        IntelligenceLabel.AUTHORIZATION,
    ]
    assert result.review_required_labels == [IntelligenceLabel.SECURITY_CONTROL]
    assert result.decisions[2].evidence_state is HybridEvidenceState.CONFLICT
    assert "test_cases" not in HybridResult.model_fields
    assert "facts" not in HybridResult.model_fields


def test_hybrid_rejects_duplicates_overlaps_unknowns_and_unexplained_groups():
    common = {
        "result_id": f"A4HYB-{HEX_A}",
        "chunk": reference(),
        "taxonomy_version": "T1",
        "rule_result_id": f"A4RUL-{HEX_A}",
        "zero_shot_result_id": f"A4ZSC-{HEX_A}",
        "hybrid_policy_version": "H1",
        "review_required_labels": [],
        "rejected_labels": [],
        "processed_at": NOW,
    }
    with pytest.raises(ValidationError):
        HybridResult(
            **common,
            accepted_labels=["AUTHORIZATION", "AUTHORIZATION"],
            decisions=[],
        )
    with pytest.raises(ValidationError, match="disjoint"):
        HybridResult(
            **{**common, "review_required_labels": ["AUTHORIZATION"]},
            accepted_labels=["AUTHORIZATION"],
            decisions=[decision("AUTHORIZATION", "ACCEPTED", "AGREEMENT")],
        )
    with pytest.raises(ValidationError):
        HybridResult(
            **common,
            accepted_labels=["UNKNOWN"],
            decisions=[],
        )
    with pytest.raises(ValidationError, match="cover"):
        HybridResult(
            **common,
            accepted_labels=["AUTHORIZATION"],
            decisions=[],
        )


def test_ground_truth_uses_the_same_versioned_multilabel_vocabulary():
    sample = GroundTruth(
        chunk_id=f"A4CHK-{HEX_A}",
        taxonomy_version="T1",
        expected_labels=["SECURITY_CONTROL", "AUTHORIZATION"],
    )
    assert sample.expected_labels == [
        IntelligenceLabel.AUTHORIZATION,
        IntelligenceLabel.SECURITY_CONTROL,
    ]
    with pytest.raises(ValidationError):
        GroundTruth(
            chunk_id=f"A4CHK-{HEX_A}",
            taxonomy_version="T1",
            expected_labels=["ACTOR"],
        )


def test_contract_use_does_not_mutate_completed_n2_workflow_or_create_results(n2_context):
    client, _, executor, root, _, runs, _, _, _ = n2_context
    project_id = create_project(client)
    add_text(client, project_id)
    confirm(client, project_id)
    executor.drain()
    before = (root / project_id / "workflow.json").read_bytes()

    workflow = load(client, project_id)
    GroundTruth(
        chunk_id=f"A4CHK-{HEX_A}",
        taxonomy_version="T1",
        expected_labels=["FUNCTIONAL_BEHAVIOR"],
    )

    after = (root / project_id / "workflow.json").read_bytes()
    node_status = {node["node_id"]: node["status"] for node in workflow["nodes"]}
    assert before == after
    assert workflow["current_node_id"] == Agent4TestGenerationNodeId.TESTING_INTELLIGENCE
    assert node_status[Agent4TestGenerationNodeId.TESTING_INTELLIGENCE] == Agent4WorkflowNodeStatus.NOT_STARTED
    assert node_status[Agent4TestGenerationNodeId.CONTEXT_TESTABILITY] == Agent4WorkflowNodeStatus.LOCKED
    assert workflow.get("n3_execution") is None
    assert runs.documents == {}
    assert not list((root / project_id).rglob("*.rules.json"))
    assert not list((root / project_id).rglob("*.zero-shot.json"))
    assert not list((root / project_id).rglob("*.hybrid.json"))

