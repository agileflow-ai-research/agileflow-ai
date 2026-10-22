from dataclasses import replace

import pytest

from app.modules.agents.requirements.contracts.schemas import RequirementSourceType
from app.modules.agents.requirements.discovery.classification.protocol import (
    ClassifierConfiguration,
    ProviderClassification,
    RequirementClassifierError,
)
from app.modules.agents.requirements.discovery.classification.service import (
    RequirementClassificationError,
    RequirementClassificationService,
)
from app.modules.agents.requirements.discovery.classification.transformer import (
    HYPOTHESIS_TEMPLATE,
    LABEL_DESCRIPTIONS,
    TransformerRequirementClassifier,
)
from app.modules.agents.requirements.discovery.contracts import (
    CandidateDiscoverySignal,
    ClassificationPolicyReason,
    ClassificationScore,
    RequirementCandidate,
    RequirementCandidateSet,
    RequirementClassificationLabel,
)
from app.modules.agents.requirements.processing.preparation.schemas import NormalizedProvenanceSpan


def candidate(index: int, text: str) -> RequirementCandidate:
    return RequirementCandidate(
        candidate_id=f"RC-{index:016X}",
        candidate_identity=f"{index:064x}",
        agent_project_id="AGP-020",
        n2_execution_id="N2-AAAAAAAAAAAAAAAA-001",
        chunk_set_digest="d" * 64,
        chunk_id=f"CHK-{index:016X}",
        source_id=f"DOC-{index:03d}",
        source_type=RequirementSourceType.DOCUMENT,
        text=text,
        start_offset=0,
        end_offset=len(text),
        discovery_signals=(CandidateDiscoverySignal.MODAL_MUST,),
        provenance=(NormalizedProvenanceSpan(
            normalized_start_offset=0,
            normalized_end_offset=len(text),
            page_numbers=[index],
        ),),
    )


def candidate_set(*items: RequirementCandidate) -> RequirementCandidateSet:
    return RequirementCandidateSet(
        contract_version="1",
        agent_project_id="AGP-020",
        n2_execution_id="N2-AAAAAAAAAAAAAAAA-001",
        chunk_set_digest="d" * 64,
        discovery_input_identity="e" * 64,
        candidates=items,
    )


def score_vector(winner, confidence=0.8, runner_up=0.15):
    remaining = next(
        label for label in RequirementClassificationLabel
        if label not in {winner, RequirementClassificationLabel.OTHER}
    ) if winner is not RequirementClassificationLabel.OTHER else RequirementClassificationLabel.FUNCTIONAL
    values = {label: 0.05 for label in RequirementClassificationLabel}
    values[winner] = confidence
    values[remaining] = runner_up
    return tuple(ClassificationScore(label=label, score=values[label]) for label in RequirementClassificationLabel)


class FakeClassifier:
    def __init__(self, outputs=(), *, model_id="fake/model", failure=False):
        self.outputs = tuple(outputs)
        self.failure = failure
        self.configuration = ClassifierConfiguration(
            provider_type="FAKE",
            provider_version="1.0",
            model_id=model_id,
            requested_revision="revision-1",
            resolved_revision="revision-1",
            task="zero-shot-classification",
            label_descriptions=dict(LABEL_DESCRIPTIONS),
            hypothesis_template=HYPOTHESIS_TEMPLATE,
            device="cpu",
            batch_size=4,
            local_files_only=True,
        )

    def classify(self, candidates):
        if self.failure:
            raise RequirementClassifierError("private provider details")
        return self.outputs


def prediction(item, label, confidence=0.8, runner_up=0.15):
    return ProviderClassification(
        candidate_id=item.candidate_id,
        winner=label,
        scores=score_vector(label, confidence, runner_up),
    )


def test_fake_classifies_all_labels_preserving_scores_order_and_traceability():
    items = (
        candidate(1, "The system must create accounts."),
        candidate(2, "The page must respond quickly."),
        candidate(3, "The project must have a meeting."),
    )
    labels = tuple(RequirementClassificationLabel)
    provider = FakeClassifier(
        [prediction(item, label) for item, label in zip(items, labels, strict=True)]
    )
    result = RequirementClassificationService(provider).classify(candidate_set(*items))
    assert [item.label for item in result.classifications] == list(labels)
    assert [item.candidate_id for item in result.classifications] == [item.candidate_id for item in items]
    assert result.classifications[0].scores == provider.outputs[0].scores
    assert result.classifications[0].confidence == 0.8
    assert result.candidate_set.candidates[0].text == items[0].text
    assert result.candidate_set.candidates[0].provenance[0].page_numbers == [1]


@pytest.mark.parametrize("label", [RequirementClassificationLabel.FUNCTIONAL, RequirementClassificationLabel.NON_FUNCTIONAL])
def test_low_confidence_fr_or_nfr_is_demoted_to_other(label):
    item = candidate(1, "The system must do something.")
    result = RequirementClassificationService(
        FakeClassifier([prediction(item, label, confidence=0.49, runner_up=0.3)]),
        minimum_confidence=0.5,
        minimum_margin=None,
    ).classify(candidate_set(item)).classifications[0]
    assert result.label is RequirementClassificationLabel.OTHER
    assert result.raw_winner is label
    assert result.confidence == 0.49
    assert result.policy_reason is ClassificationPolicyReason.LOW_CONFIDENCE


def test_margin_policy_demotes_close_winner_but_retains_high_confidence_result():
    item = candidate(1, "The system must create accounts.")
    close = RequirementClassificationService(
        FakeClassifier([prediction(item, RequirementClassificationLabel.FUNCTIONAL, 0.7, 0.65)]),
        minimum_margin=0.1,
    ).classify(candidate_set(item)).classifications[0]
    clear = RequirementClassificationService(
        FakeClassifier([prediction(item, RequirementClassificationLabel.FUNCTIONAL, 0.8, 0.2)]),
        minimum_margin=0.1,
    ).classify(candidate_set(item)).classifications[0]
    assert close.label is RequirementClassificationLabel.OTHER
    assert close.policy_reason is ClassificationPolicyReason.INSUFFICIENT_MARGIN
    assert clear.label is RequirementClassificationLabel.FUNCTIONAL
    assert clear.policy_reason is None


def test_fingerprint_is_deterministic_and_changes_with_model_or_policy():
    empty = candidate_set()
    first = RequirementClassificationService(FakeClassifier()).classify(empty).model.configuration_fingerprint
    repeat = RequirementClassificationService(FakeClassifier()).classify(empty).model.configuration_fingerprint
    changed_model = RequirementClassificationService(FakeClassifier(model_id="other/model")).classify(empty).model.configuration_fingerprint
    changed_policy = RequirementClassificationService(FakeClassifier(), minimum_confidence=0.7).classify(empty).model.configuration_fingerprint
    assert first == repeat
    assert len({first, changed_model, changed_policy}) == 3


def test_provider_failure_and_changed_order_become_safe_typed_failures():
    item = candidate(1, "The system must create accounts.")
    with pytest.raises(RequirementClassificationError, match="could not be classified") as failure:
        RequirementClassificationService(FakeClassifier(failure=True)).classify(candidate_set(item))
    assert "private" not in str(failure.value)
    wrong = replace(prediction(item, RequirementClassificationLabel.FUNCTIONAL), candidate_id="RC-0000000000000002")
    with pytest.raises(RequirementClassificationError, match="ordering"):
        RequirementClassificationService(FakeClassifier([wrong])).classify(candidate_set(item))


def test_empty_candidate_set_does_not_call_provider():
    provider = FakeClassifier(failure=True)
    result = RequirementClassificationService(provider).classify(candidate_set())
    assert result.classifications == ()


def test_repeated_fake_inference_is_deterministic_and_does_not_rewrite_text():
    item = candidate(1, "The exact system statement must remain unchanged.")
    service = RequirementClassificationService(
        FakeClassifier([prediction(item, RequirementClassificationLabel.FUNCTIONAL)])
    )
    first = service.classify(candidate_set(item))
    second = service.classify(candidate_set(item))
    assert first == second
    assert first.candidate_set.candidates[0].text == item.text


def test_transformer_provider_is_lazy_cached_batched_and_maps_semantic_labels():
    calls = {"factory": 0, "batches": []}

    def pipeline(texts, **kwargs):
        calls["batches"].append((list(texts), kwargs))
        return [
            {
                "labels": list(LABEL_DESCRIPTIONS.values()),
                "scores": [0.8, 0.15, 0.05],
            }
            for _ in texts
        ]

    def factory():
        calls["factory"] += 1
        return pipeline, "resolved-revision"

    provider = TransformerRequirementClassifier(batch_size=2, pipeline_factory=factory)
    assert calls["factory"] == 0
    items = tuple(candidate(index, f"System must perform action {index}.") for index in range(1, 4))
    first = provider.classify(items)
    second = provider.classify(items[:1])
    assert calls["factory"] == 1
    assert [len(batch[0]) for batch in calls["batches"]] == [2, 1, 1]
    assert all(item.winner is RequirementClassificationLabel.FUNCTIONAL for item in first + second)
    assert calls["batches"][0][1]["multi_label"] is False
    assert provider.configuration.resolved_revision == "resolved-revision"


def test_transformer_provider_maps_malformed_response_to_typed_failure():
    provider = TransformerRequirementClassifier(
        pipeline_factory=lambda: (lambda _texts, **_kwargs: {"labels": [], "scores": []}, None)
    )
    with pytest.raises(RequirementClassifierError, match="inference failed"):
        provider.classify((candidate(1, "The system must create accounts."),))
