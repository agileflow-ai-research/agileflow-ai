import math
from types import SimpleNamespace

import numpy as np
import pytest
from pydantic import ValidationError

from app.modules.agents.requirements.contracts.schemas import RequirementSourceType
from app.modules.agents.requirements.discovery.contracts import StructuredRequirementType
from app.modules.agents.requirements.quality.conflicts.protocol import RequirementConflictProviderError
from app.modules.agents.requirements.quality.conflicts.service import (
    ConflictDetectionError, ConflictDetectionErrorCode, RequirementConflictService,
)
from app.modules.agents.requirements.quality.conflicts.transformer import (
    TransformerRequirementConflictProvider,
)
from app.modules.agents.requirements.quality.contracts import (
    NliRelation, NliRelationScore, NliScoreVector,
)
from app.modules.agents.requirements.quality.exact_duplicates import ExactDuplicateDetector
from app.modules.agents.requirements.quality.semantic_duplicates.service import SemanticDuplicateService
from test_agent1_exact_duplicates import quality_input, requirement
from test_agent1_semantic_duplicates import FakeProvider


def scores(*, contradiction=0.9, neutral=0.05, entailment=0.05):
    return NliScoreVector(scores=(
        NliRelationScore(relation=NliRelation.ENTAILMENT, score=entailment),
        NliRelationScore(relation=NliRelation.NEUTRAL, score=neutral),
        NliRelationScore(relation=NliRelation.CONTRADICTION, score=contradiction),
    ))


@pytest.mark.parametrize("values", [
    (0.2, 0.3, 0.5),
    (0.00042366981506347656, 0.0003554821014404297, 0.9990234375),
    (0.2, 0.3, 0.5004),
    (float(np.float32(0.2)), float(np.float32(0.3)), float(np.float32(0.5))),
])
def test_nli_score_vector_accepts_exact_and_small_numeric_normalization_drift(values):
    vector = scores(entailment=values[0], neutral=values[1], contradiction=values[2])
    assert tuple(item.score for item in vector.scores) == values


@pytest.mark.parametrize("values", [
    (0.2, 0.3, 0.499),
    (0.2, 0.3, 0.501),
    (-0.01, 0.5, 0.51),
    (1.01, 0.0, 0.0),
    (float("nan"), 0.5, 0.5),
    (float("inf"), 0.0, 0.0),
])
def test_nli_score_vector_rejects_invalid_or_materially_non_normalized_values(values):
    with pytest.raises(ValidationError):
        scores(entailment=values[0], neutral=values[1], contradiction=values[2])


def test_nli_score_vector_preserves_complete_relation_taxonomy():
    vector = scores()
    assert tuple(item.relation for item in vector.scores) == tuple(NliRelation)


class FakeNliProvider:
    def __init__(self, outputs=(), model_id="fake/nli"):
        self.outputs = outputs
        self.calls = []
        self.fail = False
        self.configuration = {
            "provider_type": "FAKE_NLI", "provider_version": "1",
            "model_id": model_id, "requested_revision": "r1",
            "resolved_revision": "r1", "device": "cpu",
            "task": "text-pair-natural-language-inference",
            "label_mapping_policy": {relation: "FAKE" for relation in NliRelation},
            "batch_size": 4,
            "preprocessing_policy": "EXACT_PERSISTED_STATEMENT_SEQUENCE_PAIR",
        }

    def evaluate(self, pairs):
        self.calls.append(pairs)
        if self.fail:
            raise RequirementConflictProviderError("private model detail")
        return self.outputs


def upstream(value, semantic_vectors=None):
    exact = ExactDuplicateDetector().detect(value)
    vectors = semantic_vectors or tuple((1.0, 0.0) for _ in value.requirements)
    semantic = SemanticDuplicateService(FakeProvider(vectors)).detect(value, exact)
    return exact, semantic


def service(embeddings, nli, **kwargs):
    return RequirementConflictService(FakeProvider(embeddings), nli, **kwargs)


@pytest.mark.parametrize("left_text,right_text", [
    ("The system shall allow users to cancel bookings.",
     "The system shall not allow users to cancel bookings."),
    ("The service must retain audit records.",
     "The service must never retain audit records."),
])
def test_related_contradictory_requirements_emit_conflict(left_text, right_text):
    left, right = requirement(1, left_text), requirement(2, right_text)
    value = quality_input(left, right)
    exact, semantic = upstream(value)
    nli = FakeNliProvider((scores(contradiction=0.9, neutral=0.06, entailment=0.04),
                           scores(contradiction=0.8, neutral=0.1, entailment=0.1)))
    result = service(((1.0, 0.0), (0.9, math.sqrt(0.19))), nli).detect(value, exact, semantic)
    conflict = result.conflicts[0]
    assert conflict.left == left and conflict.right == right
    assert conflict.final_contradiction_score == pytest.approx(0.85)
    assert conflict.left_to_right.relation_scores.score_for(NliRelation.CONTRADICTION) == 0.9
    assert conflict.right_to_left.relation_scores.score_for(NliRelation.CONTRADICTION) == 0.8
    assert nli.calls == [((left_text, right_text), (right_text, left_text))]


@pytest.mark.parametrize("relation_scores", [
    scores(contradiction=0.1, neutral=0.8, entailment=0.1),
    scores(contradiction=0.05, neutral=0.05, entailment=0.9),
])
def test_neutral_and_entailment_pairs_are_not_conflicts(relation_scores):
    value = quality_input(requirement(1, "Users can view bookings."),
                          requirement(2, "Users can inspect booking details."))
    exact, semantic = upstream(value)
    result = service(((1.0, 0.0), (1.0, 0.0)),
                     FakeNliProvider((relation_scores, relation_scores))).detect(value, exact, semantic)
    assert result.conflicts == ()
    assert result.nli_evaluated_pair_count == 1


@pytest.mark.parametrize("similarity,called", [(0.9, True), (0.6, True), (0.4, False)])
def test_relatedness_prefilter_controls_nli(similarity, called):
    value = quality_input(requirement(1, "First."), requirement(2, "Second."))
    exact, semantic = upstream(value, ((1.0, 0.0), (0.0, 1.0)))
    nli = FakeNliProvider((scores(), scores()))
    vector = (similarity, math.sqrt(1 - similarity * similarity))
    result = service(((1.0, 0.0), vector), nli).detect(value, exact, semantic)
    assert bool(nli.calls) is called
    assert result.relatedness_candidate_pair_count == int(called)


def test_semantic_duplicate_pair_remains_eligible_for_conflict():
    value = quality_input(requirement(1, "Users may cancel."),
                          requirement(2, "Users may not cancel."))
    exact, semantic = upstream(value)
    assert semantic.pair_count == 1
    nli = FakeNliProvider((scores(), scores()))
    assert service(((1.0, 0.0), (1.0, 0.0)), nli).detect(value, exact, semantic).conflict_count == 1


def test_exact_duplicate_pair_is_excluded_and_models_are_not_called():
    first = requirement(1, "Users may cancel.")
    value = quality_input(first, requirement(2, first.statement))
    exact, semantic = upstream(value)
    embeddings, nli = FakeProvider(()), FakeNliProvider(())
    result = RequirementConflictService(embeddings, nli).detect(value, exact, semantic)
    assert result.conflicts == () and embeddings.calls == [] and nli.calls == []


@pytest.mark.parametrize("left_type,right_type", [
    (StructuredRequirementType.FUNCTIONAL, StructuredRequirementType.FUNCTIONAL),
    (StructuredRequirementType.NON_FUNCTIONAL, StructuredRequirementType.NON_FUNCTIONAL),
    (StructuredRequirementType.FUNCTIONAL, StructuredRequirementType.NON_FUNCTIONAL),
])
def test_cross_type_conflicts_preserve_types(left_type, right_type):
    left = requirement(1, "Allow access.", kind=left_type)
    right = requirement(2, "Prohibit access.", kind=right_type)
    value = quality_input(left, right)
    exact, semantic = upstream(value)
    conflict = service(((1.0, 0.0), (1.0, 0.0)),
                       FakeNliProvider((scores(), scores()))).detect(value, exact, semantic).conflicts[0]
    assert conflict.left.requirement_type is left_type
    assert conflict.right.requirement_type is right_type


@pytest.mark.parametrize("source_type", list(RequirementSourceType))
def test_source_chunk_and_typed_provenance_traceability(source_type):
    left = requirement(1, "Allow access.", source_type=source_type,
                       source_number=1, chunk_number=1)
    right = requirement(2, "Prohibit access.", source_type=source_type,
                        source_number=2, chunk_number=2)
    value = quality_input(left, right)
    exact, semantic = upstream(value)
    conflict = service(((1.0, 0.0), (1.0, 0.0)),
                       FakeNliProvider((scores(), scores()))).detect(value, exact, semantic).conflicts[0]
    assert conflict.left.statement == left.statement
    assert conflict.right.statement == right.statement
    assert conflict.left.candidate_id == left.candidate_id
    assert conflict.right.chunk_id == right.chunk_id
    assert conflict.left.source_id != conflict.right.source_id
    assert conflict.left.provenance == left.provenance
    assert conflict.right.provenance == right.provenance


def test_threshold_equality_is_conflict_and_below_is_not():
    value = quality_input(requirement(1, "Allow."), requirement(2, "Forbid."))
    exact, semantic = upstream(value)
    equal = scores(contradiction=0.8, neutral=0.1, entailment=0.1)
    low = scores(contradiction=0.79, neutral=0.11, entailment=0.1)
    assert service(((1.0, 0.0), (1.0, 0.0)), FakeNliProvider((equal, equal))).detect(value, exact, semantic).conflict_count == 1
    assert service(((1.0, 0.0), (1.0, 0.0)), FakeNliProvider((low, low))).detect(value, exact, semantic).conflict_count == 0


def test_conflict_and_result_identity_and_order_are_deterministic():
    items = tuple(requirement(i, f"Requirement {i}.") for i in range(1, 4))
    value = quality_input(*items)
    exact, semantic = upstream(value)
    nli = FakeNliProvider((scores(),) * 6)
    detector = service(((1.0, 0.0),) * 3, nli)
    first, replay = detector.detect(value, exact, semantic), detector.detect(value, exact, semantic)
    assert first == replay
    assert [pair.conflict_id for pair in first.conflicts] == [pair.conflict_id for pair in replay.conflicts]
    assert [(pair.left.requirement_id, pair.right.requirement_id) for pair in first.conflicts] == [
        (items[0].requirement_id, items[1].requirement_id),
        (items[0].requirement_id, items[2].requirement_id),
        (items[1].requirement_id, items[2].requirement_id),
    ]


def test_empty_and_single_inputs_are_valid_without_provider_calls():
    for value in (quality_input(), quality_input(requirement(1, "Only."), identity="b" * 64)):
        exact, semantic = upstream(value)
        embeddings, nli = FakeProvider(()), FakeNliProvider(())
        assert RequirementConflictService(embeddings, nli).detect(value, exact, semantic).conflicts == ()
        assert embeddings.calls == [] and nli.calls == []


def test_wrong_upstream_identities_are_rejected():
    value = quality_input(requirement(1, "A."), requirement(2, "B."))
    exact, semantic = upstream(value)
    other = quality_input(identity="f" * 64)
    with pytest.raises(ConflictDetectionError) as error:
        service((), FakeNliProvider()).detect(value, ExactDuplicateDetector().detect(other), semantic)
    assert error.value.code is ConflictDetectionErrorCode.INPUT_INVALID
    wrong_semantic = SemanticDuplicateService(FakeProvider(())).detect(other, ExactDuplicateDetector().detect(other))
    with pytest.raises(ConflictDetectionError) as error:
        service((), FakeNliProvider()).detect(value, exact, wrong_semantic)
    assert error.value.code is ConflictDetectionErrorCode.INPUT_INVALID


@pytest.mark.parametrize("vectors", [
    ((1.0, 0.0),), ((1.0, 0.0), (1.0,)),
    ((1.0, 0.0), (math.nan, 0.0)), ((1.0, 0.0), (math.inf, 0.0)),
])
def test_malformed_relatedness_embeddings_are_rejected(vectors):
    value = quality_input(requirement(1, "A."), requirement(2, "B."))
    exact, semantic = upstream(value)
    with pytest.raises(ConflictDetectionError) as error:
        service(vectors, FakeNliProvider()).detect(value, exact, semantic)
    assert error.value.code is ConflictDetectionErrorCode.RELATEDNESS_INVALID


def test_provider_failures_and_malformed_nli_are_safe_typed_errors():
    value = quality_input(requirement(1, "A."), requirement(2, "B."))
    exact, semantic = upstream(value)
    embedding = FakeProvider(())
    embedding.fail = True
    with pytest.raises(ConflictDetectionError) as error:
        RequirementConflictService(embedding, FakeNliProvider()).detect(value, exact, semantic)
    assert error.value.code is ConflictDetectionErrorCode.RELATEDNESS_FAILED
    nli = FakeNliProvider((SimpleNamespace(), SimpleNamespace()))
    with pytest.raises(ConflictDetectionError) as error:
        service(((1.0, 0.0), (1.0, 0.0)), nli).detect(value, exact, semantic)
    assert error.value.code is ConflictDetectionErrorCode.MODEL_RESPONSE_INVALID
    nli.fail = True
    with pytest.raises(ConflictDetectionError) as error:
        service(((1.0, 0.0), (1.0, 0.0)), nli).detect(value, exact, semantic)
    assert error.value.code is ConflictDetectionErrorCode.PROVIDER_FAILED
    assert "private" not in str(error.value)


def test_configuration_fingerprint_changes_with_thresholds_and_model():
    embedding = FakeProvider(())
    first = RequirementConflictService(embedding, FakeNliProvider(model_id="a"))
    assert first.configuration_fingerprint != RequirementConflictService(embedding, FakeNliProvider(model_id="a"), relatedness_threshold=0.6).configuration_fingerprint
    assert first.configuration_fingerprint != RequirementConflictService(embedding, FakeNliProvider(model_id="a"), contradiction_threshold=0.9).configuration_fingerprint
    assert first.configuration_fingerprint != RequirementConflictService(embedding, FakeNliProvider(model_id="b")).configuration_fingerprint


def test_transformer_provider_is_lazy_cached_pairwise_and_maps_labels():
    import torch
    calls = {"load": 0, "tokenize": []}

    class Tokenizer:
        def __call__(self, premises, hypotheses, **kwargs):
            calls["tokenize"].append((premises, hypotheses, kwargs))
            return {"input_ids": torch.tensor([[1, 2], [2, 1]])}

    class Model:
        config = SimpleNamespace(id2label={0: "entailment", 1: "neutral", 2: "contradiction"})
        def __call__(self, **_kwargs):
            return SimpleNamespace(logits=torch.tensor([[0.0, 0.0, 4.0], [4.0, 0.0, 0.0]]))

    def loader():
        calls["load"] += 1
        return Tokenizer(), Model(), "resolved"

    provider = TransformerRequirementConflictProvider(
        model_id="custom/nli", revision="requested", loader=loader,
    )
    assert calls["load"] == 0
    result = provider.evaluate((("A", "B"), ("B", "A")))
    provider.evaluate((("A", "B"), ("B", "A")))
    assert calls["load"] == 1
    assert calls["tokenize"][0][0:2] == (["A", "B"], ["B", "A"])
    assert result[0].score_for(NliRelation.CONTRADICTION) > 0.9
    assert provider.configuration["model_id"] == "custom/nli"
    assert provider.configuration["resolved_revision"] == "requested"
    assert provider.configuration["device"] == "cpu"


def test_transformer_rejects_untrustworthy_label_mapping_safely():
    model = SimpleNamespace(config=SimpleNamespace(id2label={0: "LABEL_0", 1: "LABEL_1", 2: "LABEL_2"}))
    provider = TransformerRequirementConflictProvider(
        loader=lambda: (object(), model, None)
    )
    with pytest.raises(RequirementConflictProviderError) as error:
        provider.evaluate((("A", "B"),))
    assert "LABEL_0" not in str(error.value)
