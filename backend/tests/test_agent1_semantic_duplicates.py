import math
import sys
from types import SimpleNamespace

import pytest

from app.modules.agents.requirements.contracts.schemas import RequirementSourceType
from app.modules.agents.requirements.discovery.contracts import StructuredRequirementType
from app.modules.agents.requirements.infrastructure.digests import stable_json_sha256
from app.modules.agents.requirements.quality.contracts import EmbeddingModelIdentity
from app.modules.agents.requirements.quality.exact_duplicates import ExactDuplicateDetector
from app.modules.agents.requirements.quality.semantic_duplicates.protocol import (
    RequirementEmbeddingProviderError,
)
from app.modules.agents.requirements.quality.semantic_duplicates.service import (
    SemanticDuplicateError,
    SemanticDuplicateErrorCode,
    SemanticDuplicateService,
)
from app.modules.agents.requirements.quality.semantic_duplicates.transformer import (
    SentenceTransformerEmbeddingProvider,
)
from test_agent1_exact_duplicates import quality_input, requirement


class FakeProvider:
    def __init__(self, vectors, *, model_id="fake/semantic", dimension=2):
        self.vectors = vectors
        self.calls = []
        self.fail = False
        values = {
            "provider_type": "FAKE", "provider_version": "1",
            "model_id": model_id, "requested_revision": "r1",
            "resolved_revision": "r1", "device": "cpu",
            "normalize_embeddings": True, "embedding_dimension": dimension,
            "batch_size": 8, "preprocessing_policy": "EXACT_PERSISTED_STATEMENT",
        }
        self._identity = EmbeddingModelIdentity(
            **values, configuration_fingerprint=stable_json_sha256(values)
        )

    @property
    def model_identity(self):
        return self._identity

    def encode(self, statements):
        self.calls.append(statements)
        if self.fail:
            raise RequirementEmbeddingProviderError("hidden provider detail")
        return self.vectors


def exact(value):
    return ExactDuplicateDetector().detect(value)


def test_semantic_paraphrase_emits_traceable_pair_with_evidence():
    left = requirement(1, "The user can cancel a booking.")
    right = requirement(2, "Customers are able to cancel an existing reservation.")
    value = quality_input(left, right)
    provider = FakeProvider(((1.0, 0.0), (0.9, math.sqrt(0.19))))
    result = SemanticDuplicateService(provider, threshold=0.82).detect(value, exact(value))
    pair = result.pairs[0]
    assert result.pair_count == 1
    assert pair.left == left and pair.right == right
    assert pair.left.statement == left.statement and pair.right.statement == right.statement
    assert pair.evidence.cosine_similarity == pytest.approx(0.9)
    assert pair.evidence.threshold == 0.82
    assert pair.evidence.model_configuration_fingerprint == provider.model_identity.configuration_fingerprint
    assert pair.semantic_duplicate_id.startswith("QSEM-")


def test_unrelated_below_threshold_produces_no_pair():
    value = quality_input(requirement(1, "Cancel a booking."),
                          requirement(2, "Load within three seconds."))
    result = SemanticDuplicateService(FakeProvider(((1.0, 0.0), (0.0, 1.0)))).detect(value, exact(value))
    assert result.pairs == ()


def test_s2_exact_pair_is_excluded_but_paraphrase_can_match():
    first = requirement(1, "The system shall send an email.")
    second = requirement(2, first.statement)
    third = requirement(3, "An email must be sent by the system.")
    value = quality_input(first, second, third)
    result = SemanticDuplicateService(FakeProvider(
        ((1.0, 0.0), (1.0, 0.0), (0.9, math.sqrt(0.19)))
    )).detect(value, exact(value))
    ids = [(pair.left.requirement_id, pair.right.requirement_id) for pair in result.pairs]
    assert (first.requirement_id, second.requirement_id) not in ids
    assert ids == [(first.requirement_id, third.requirement_id),
                   (second.requirement_id, third.requirement_id)]


@pytest.mark.parametrize("left_type,right_type", [
    (StructuredRequirementType.FUNCTIONAL, StructuredRequirementType.FUNCTIONAL),
    (StructuredRequirementType.NON_FUNCTIONAL, StructuredRequirementType.NON_FUNCTIONAL),
    (StructuredRequirementType.FUNCTIONAL, StructuredRequirementType.NON_FUNCTIONAL),
])
def test_all_structured_type_combinations_are_compared(left_type, right_type):
    left = requirement(1, "Passwords must be encrypted.", kind=left_type)
    right = requirement(2, "Stored credentials shall use encryption.", kind=right_type)
    value = quality_input(left, right)
    pair = SemanticDuplicateService(FakeProvider(((1.0, 0.0), (1.0, 0.0)))).detect(value, exact(value)).pairs[0]
    assert pair.left.requirement_type is left_type
    assert pair.right.requirement_type is right_type


@pytest.mark.parametrize("source_type", list(RequirementSourceType))
def test_same_and_cross_source_chunk_traceability_and_provenance(source_type):
    left = requirement(1, "Store audit records.", source_type=source_type,
                       source_number=1, chunk_number=1)
    right = requirement(2, "Retain audit history.", source_type=source_type,
                        source_number=2, chunk_number=2)
    value = quality_input(left, right)
    pair = SemanticDuplicateService(FakeProvider(((1.0, 0.0), (1.0, 0.0)))).detect(value, exact(value)).pairs[0]
    assert pair.left.candidate_id == left.candidate_id
    assert pair.right.chunk_id == right.chunk_id
    assert pair.left.source_id != pair.right.source_id
    assert pair.left.provenance == left.provenance
    assert pair.right.provenance == right.provenance


def test_pair_order_is_evidence_order_without_self_or_reversed_pairs():
    items = tuple(requirement(index, f"Requirement wording {index}.") for index in range(1, 4))
    value = quality_input(*items)
    result = SemanticDuplicateService(FakeProvider(((1.0, 0.0),) * 3)).detect(value, exact(value))
    assert [(pair.left.requirement_id, pair.right.requirement_id) for pair in result.pairs] == [
        (items[0].requirement_id, items[1].requirement_id),
        (items[0].requirement_id, items[2].requirement_id),
        (items[1].requirement_id, items[2].requirement_id),
    ]


def test_repeated_run_has_deterministic_pair_and_result_identities():
    value = quality_input(requirement(1, "Cancel booking."), requirement(2, "Cancel reservation."))
    service = SemanticDuplicateService(FakeProvider(((1.0, 0.0), (1.0, 0.0))))
    first, second = service.detect(value, exact(value)), service.detect(value, exact(value))
    assert first == second
    assert first.result_identity == second.result_identity
    assert first.pairs[0].semantic_duplicate_id == second.pairs[0].semantic_duplicate_id


def test_empty_and_single_inputs_do_not_initialize_provider():
    provider = FakeProvider(())
    service = SemanticDuplicateService(provider)
    empty = quality_input()
    single = quality_input(requirement(1, "Only requirement."), identity="b" * 64)
    assert service.detect(empty, exact(empty)).pairs == ()
    assert service.detect(single, exact(single)).pairs == ()
    assert provider.calls == []


def test_only_exact_duplicate_pair_does_not_initialize_provider():
    first = requirement(1, "Exact duplicate.")
    value = quality_input(first, requirement(2, first.statement))
    provider = FakeProvider(())
    assert SemanticDuplicateService(provider).detect(value, exact(value)).pairs == ()
    assert provider.calls == []


def test_wrong_exact_result_identity_is_rejected():
    value = quality_input(requirement(1, "A."), requirement(2, "B."))
    other = quality_input(identity="f" * 64)
    with pytest.raises(SemanticDuplicateError) as error:
        SemanticDuplicateService(FakeProvider(())).detect(value, exact(other))
    assert error.value.code is SemanticDuplicateErrorCode.INPUT_MISMATCH


@pytest.mark.parametrize("vectors", [
    ((1.0, 0.0),),
    ((1.0, 0.0), (1.0,)),
    ((1.0, 0.0), (math.nan, 0.0)),
    ((1.0, 0.0), (math.inf, 0.0)),
    ((1.0, 0.0), (0.0, 0.0)),
])
def test_malformed_embeddings_are_rejected(vectors):
    value = quality_input(requirement(1, "A."), requirement(2, "B."))
    with pytest.raises(SemanticDuplicateError) as error:
        SemanticDuplicateService(FakeProvider(vectors)).detect(value, exact(value))
    assert error.value.code is SemanticDuplicateErrorCode.EMBEDDING_INVALID


def test_provider_failure_is_safe_and_typed():
    value = quality_input(requirement(1, "A."), requirement(2, "B."))
    provider = FakeProvider(())
    provider.fail = True
    with pytest.raises(SemanticDuplicateError) as error:
        SemanticDuplicateService(provider).detect(value, exact(value))
    assert error.value.code is SemanticDuplicateErrorCode.PROVIDER_FAILURE
    assert "hidden" not in str(error.value)


def test_threshold_and_model_change_detector_fingerprint():
    first = FakeProvider((), model_id="fake/a")
    second = FakeProvider((), model_id="fake/b")
    assert SemanticDuplicateService(first, threshold=0.82).configuration_fingerprint != SemanticDuplicateService(first, threshold=0.9).configuration_fingerprint
    assert SemanticDuplicateService(first).configuration_fingerprint != SemanticDuplicateService(second).configuration_fingerprint


def test_requirement_limit_fails_without_silent_truncation():
    value = quality_input(*(requirement(index, f"R {index}") for index in range(1, 4)))
    with pytest.raises(SemanticDuplicateError) as error:
        SemanticDuplicateService(FakeProvider(()), max_requirements=2).detect(value, exact(value))
    assert error.value.code is SemanticDuplicateErrorCode.REQUIREMENT_LIMIT_EXCEEDED


def test_real_provider_is_lazy_cached_configured_and_normalizes(monkeypatch):
    calls = {"construct": [], "encode": []}

    class Model:
        def __init__(self, *args, **kwargs):
            calls["construct"].append((args, kwargs))

        def encode(self, statements, **kwargs):
            calls["encode"].append((statements, kwargs))
            return ((1.0, 0.0), (0.0, 1.0))

    monkeypatch.setitem(sys.modules, "sentence_transformers",
                        SimpleNamespace(SentenceTransformer=Model))
    provider = SentenceTransformerEmbeddingProvider(
        model_id="custom/model", revision="commit", device="cpu",
        batch_size=7, local_files_only=True, embedding_dimension=2,
    )
    assert calls["construct"] == []
    assert provider.encode(("first", "second")) == ((1.0, 0.0), (0.0, 1.0))
    provider.encode(("first", "second"))
    assert len(calls["construct"]) == 1
    args, constructor_options = calls["construct"][0]
    assert args == ("custom/model",)
    assert constructor_options == {"revision": "commit", "device": "cpu", "local_files_only": True}
    statements, encode_options = calls["encode"][0]
    assert statements == ["first", "second"]
    assert encode_options["batch_size"] == 7
    assert encode_options["normalize_embeddings"] is True
    assert provider.model_identity.model_id == "custom/model"
    assert provider.model_identity.device == "cpu"


def test_real_provider_empty_input_is_lazy_and_failure_is_mapped(monkeypatch):
    provider = SentenceTransformerEmbeddingProvider(embedding_dimension=2)
    assert provider.encode(()) == ()

    class BrokenModel:
        def __init__(self, *_args, **_kwargs):
            raise RuntimeError("private cache path")

    monkeypatch.setitem(sys.modules, "sentence_transformers",
                        SimpleNamespace(SentenceTransformer=BrokenModel))
    with pytest.raises(RequirementEmbeddingProviderError) as error:
        provider.encode(("first", "second"))
    assert "private cache path" not in str(error.value)
