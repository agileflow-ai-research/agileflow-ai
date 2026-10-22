from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import ModuleType, SimpleNamespace
import sys

import pytest

from app.modules.agents.testing_validation.intelligence.taxonomy import (
    AGENT4_TESTING_TAXONOMY_VERSION,
    AGENT4_ZERO_SHOT_LABEL_DESCRIPTION_VERSION,
    TESTING_INTELLIGENCE_LABEL_ORDER,
    TESTING_INTELLIGENCE_TAXONOMY,
)
from app.modules.agents.testing_validation.intelligence.zero_shot import constants
from app.modules.agents.testing_validation.intelligence.zero_shot.classifier import (
    Agent4ZeroShotClassifier,
    Agent4ZeroShotInferenceError,
    Agent4ZeroShotInvalidResponseError,
    candidate_mapping,
    inference_configuration_fingerprint,
)
from app.modules.agents.testing_validation.intelligence.zero_shot.runtime import (
    Agent4ZeroShotModelLoader,
    Agent4ZeroShotTokenizationError,
    RuntimeBatchOutput,
)
from app.modules.agents.testing_validation.intelligence.zero_shot.service import (
    Agent4ZeroShotGateError,
    Agent4ZeroShotService,
)
from app.modules.agents.testing_validation.intelligence.zero_shot.storage import (
    Agent4ZeroShotStorage,
    Agent4ZeroShotStorageError,
)
from app.modules.agents.testing_validation.preparation.chunking.storage import Agent4ChunkStorage
from app.modules.agents.testing_validation.workflow.storage import Agent4WorkflowStorage
from app.modules.standalone.service import StandaloneService
from test_agent4_n2_orchestration import add_text, confirm, create_project, load, n2_context
from test_agent4_testing_intelligence_contracts import chunk, chunk_set
from test_standalone_foundation import user


NOW = datetime(2026, 3, 1, tzinfo=UTC)


class FakeRuntime:
    def __init__(self, *, fail_text=None, token_count=20, max_length=512,
                 scores=None, bad=None, device="cpu"):
        self.calls = []
        self.fail_text = fail_text
        self.token_count = token_count
        self.max_length = max_length
        self.scores = scores
        self.bad = bad
        self.device = device

    def infer(self, texts, **kwargs):
        self.calls.append((list(texts), kwargs))
        if self.fail_text and any(self.fail_text in text for text in texts):
            raise RuntimeError("private runtime detail")
        labels = list(reversed(kwargs["candidate_labels"]))
        responses = []
        for _ in texts:
            response_labels = list(labels)
            values = list(self.scores or [index / 20 for index in range(15)])
            if self.bad == "missing":
                response_labels.pop()
                values.pop()
            elif self.bad == "duplicate":
                response_labels[-1] = response_labels[0]
            elif self.bad == "unknown":
                response_labels[-1] = "unknown description"
            responses.append({"labels": response_labels, "scores": values})
        return RuntimeBatchOutput(
            responses=responses,
            input_token_counts=[self.token_count] * len(texts),
            model_max_length=self.max_length,
            device=self.device,
        )


def classify(runtime=None, *, at=NOW):
    item = chunk()
    manifest = chunk_set(item)
    runtime = runtime or FakeRuntime()
    device, results = Agent4ZeroShotClassifier(runtime).classify(
        manifest, confirmed_source_ids={item.source_id}, processed_at=at
    )
    return runtime, device, results[0]


def test_pinned_configuration_and_authoritative_candidate_mapping():
    assert constants.MODEL_ID == "MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli"
    assert constants.MODEL_REVISION == "6f5cf0a2b59cabb106aca4c287eed12e357e90eb"
    assert constants.MODEL_TASK == "zero-shot-classification"
    assert constants.INFERENCE_BATCH_SIZE == 4
    assert constants.HYPOTHESIS_TEMPLATE == "This software specification describes {}."
    assert constants.HYPOTHESIS_TEMPLATE_VERSION == "ZH1"
    assert constants.ZERO_SHOT_STAGE_VERSION == "Z1"
    mapping = candidate_mapping()
    assert list(mapping) == list(TESTING_INTELLIGENCE_LABEL_ORDER)
    assert list(mapping.values()) == [
        TESTING_INTELLIGENCE_TAXONOMY[label].model_description
        for label in TESTING_INTELLIGENCE_LABEL_ORDER
    ]
    assert len(mapping) == len(set(mapping.values())) == 15
    assert AGENT4_TESTING_TAXONOMY_VERSION == "T1"
    assert AGENT4_ZERO_SHOT_LABEL_DESCRIPTION_VERSION == "ZL1"


def test_model_loader_is_lazy_process_cached_and_device_keyed(monkeypatch):
    calls = {"tokenizer": 0, "model": 0, "pipeline": []}
    cuda = SimpleNamespace(available=False, is_available=lambda: cuda.available)
    torch = ModuleType("torch")
    torch.cuda = cuda
    transformers = ModuleType("transformers")

    class TokenizerFactory:
        @staticmethod
        def from_pretrained(*args, **kwargs):
            calls["tokenizer"] += 1
            return SimpleNamespace(model_max_length=512)

    class ModelFactory:
        @staticmethod
        def from_pretrained(*args, **kwargs):
            calls["model"] += 1
            return SimpleNamespace(config=SimpleNamespace(max_position_embeddings=512))

    def pipeline(*args, **kwargs):
        calls["pipeline"].append(kwargs["device"])
        return object()

    transformers.AutoTokenizer = TokenizerFactory
    transformers.AutoModelForSequenceClassification = ModelFactory
    transformers.pipeline = pipeline
    monkeypatch.setitem(sys.modules, "torch", torch)
    monkeypatch.setitem(sys.modules, "transformers", transformers)
    Agent4ZeroShotModelLoader.reset_for_tests()
    cpu_first = Agent4ZeroShotModelLoader.load(local_files_only=True)
    cpu_second = Agent4ZeroShotModelLoader.load(local_files_only=True)
    assert cpu_first is cpu_second and cpu_first.device == "cpu"
    assert calls == {"tokenizer": 1, "model": 1, "pipeline": [-1]}
    cuda.available = True
    gpu = Agent4ZeroShotModelLoader.load(local_files_only=True)
    assert gpu is not cpu_first and gpu.device == "cuda"
    assert calls == {"tokenizer": 2, "model": 2, "pipeline": [-1, 0]}
    Agent4ZeroShotModelLoader.reset_for_tests()


def test_runtime_receives_exact_text_complete_candidates_and_multilabel_configuration():
    runtime, _, result = classify()
    texts, kwargs = runtime.calls[0]
    assert texts == [chunk().text]
    assert kwargs["candidate_labels"] == list(candidate_mapping().values())
    assert kwargs["hypothesis_template"] == constants.HYPOTHESIS_TEMPLATE
    assert kwargs["batch_size"] == 4
    assert len(result.label_scores) == 15
    assert list(result.label_scores) == list(TESTING_INTELLIGENCE_LABEL_ORDER)
    assert "accepted_labels" not in type(result).model_fields
    assert any(score < 0.5 for score in result.label_scores.values())
    assert all(score >= 0 for score in result.label_scores.values())


def test_descending_runtime_output_maps_to_canonical_codes_without_top_k():
    _, _, result = classify(FakeRuntime(scores=[1.0, 0.0, *([0.2] * 13)]))
    assert list(result.label_scores) == list(TESTING_INTELLIGENCE_LABEL_ORDER)
    assert sorted(result.label_scores.values()) == sorted([1.0, 0.0, *([0.2] * 13)])
    assert sum(result.label_scores.values()) != pytest.approx(1.0)
    assert "NON_TESTABLE_CONTEXT" in result.model_dump(mode="json")["label_scores"]


@pytest.mark.parametrize("bad", ["missing", "duplicate", "unknown"])
def test_incomplete_duplicate_or_unknown_model_labels_are_rejected(bad):
    with pytest.raises(Agent4ZeroShotInvalidResponseError):
        classify(FakeRuntime(bad=bad))


@pytest.mark.parametrize("score", [-0.01, 1.01, float("nan"), float("inf")])
def test_non_finite_or_out_of_range_scores_are_rejected(score):
    with pytest.raises(Agent4ZeroShotInvalidResponseError):
        classify(FakeRuntime(scores=[score, *([0.2] * 14)]))


def test_result_identity_ignores_time_and_device_but_binds_configuration():
    _, _, first = classify(FakeRuntime(device="cpu"), at=NOW)
    _, _, second = classify(FakeRuntime(device="cuda"), at=NOW + timedelta(days=1))
    assert first.result_id == second.result_id
    assert first.processed_at != second.processed_at
    assert first.model_id == constants.MODEL_ID
    assert first.model_revision == constants.MODEL_REVISION
    assert inference_configuration_fingerprint() == inference_configuration_fingerprint()


def test_truncation_is_explicit_and_does_not_mutate_chunk():
    original = chunk().model_dump_json()
    runtime, _, result = classify(FakeRuntime(token_count=600, max_length=512))
    assert result.input_metadata.model_max_tokens == 512
    assert result.input_metadata.input_token_count == 600
    assert result.input_metadata.truncated is True
    assert result.input_metadata.tokens_discarded == 88
    assert result.warnings[0].code == "MODEL_INPUT_TRUNCATED"
    assert chunk().model_dump_json() == original


def test_batch_failure_splits_and_identifies_irreducible_chunk():
    runtime = FakeRuntime(fail_text="Only administrators")
    with pytest.raises(Agent4ZeroShotInferenceError) as caught:
        classify(runtime)
    assert caught.value.chunk_id == chunk().chunk_id
    assert len(runtime.calls) == 1  # irreducible one-item batch is never retried


def service_for(context, runtime, *, clock=lambda: NOW):
    _, _, _, root, projects, runs, _, _, _ = context
    return Agent4ZeroShotService(
        StandaloneService(projects, runs), Agent4WorkflowStorage(root),
        Agent4ChunkStorage(root), Agent4ZeroShotStorage(root),
        Agent4ZeroShotClassifier(runtime), clock=clock,
    )


def prepared(context):
    client, _, executor, _, _, _, _, _, _ = context
    project_id = create_project(client)
    source = add_text(client, project_id, "The system shall create a booking.")
    confirm(client, project_id)
    executor.drain()
    return client, project_id, source


def test_service_persists_complete_manifest_without_rules_and_cache_avoids_runtime(n2_context):
    client, project_id, source = prepared(n2_context)
    root = n2_context[3]
    runtime = FakeRuntime()
    service = service_for(n2_context, runtime)
    immutable = {p: p.read_bytes() for p in (root / project_id).rglob("*") if p.is_file()}
    first = service.build(project_id, source["source_id"], user())
    path = root / project_id / "intelligence" / f"{source['source_id']}.zero-shot.json"
    assert path.is_file()
    assert not list((root / project_id).rglob("*.rules.json"))
    raw = path.read_bytes()
    cached = service.build(project_id, source["source_id"], user())
    assert cached == first and len(runtime.calls) == 1 and path.read_bytes() == raw
    assert all(p.read_bytes() == value for p, value in immutable.items())
    workflow = load(client, project_id)
    assert workflow["current_node_id"] == "TESTING_INTELLIGENCE"
    assert workflow["nodes"][2]["status"] == "NOT_STARTED"
    assert workflow["nodes"][3]["status"] == "LOCKED"
    assert n2_context[5].documents == {}
    assert not list((root / project_id).rglob("*.hybrid.json"))


def test_force_rebuild_calls_runtime_and_preserves_result_ids(n2_context):
    _, project_id, source = prepared(n2_context)
    runtime = FakeRuntime()
    service = service_for(n2_context, runtime)
    first = service.build(project_id, source["source_id"], user())
    service._clock = lambda: NOW + timedelta(seconds=1)
    second = service.build(project_id, source["source_id"], user(), force=True)
    assert len(runtime.calls) == 2
    assert second.processed_at != first.processed_at
    assert [item.result_id for item in second.results] == [item.result_id for item in first.results]


def test_corrupt_cache_rebuilds_and_failure_writes_no_manifest(n2_context):
    _, project_id, source = prepared(n2_context)
    root = n2_context[3]
    path = root / project_id / "intelligence" / f"{source['source_id']}.zero-shot.json"
    good_runtime = FakeRuntime()
    service_for(n2_context, good_runtime).build(project_id, source["source_id"], user())
    path.write_text("not-json", encoding="utf-8")
    service_for(n2_context, good_runtime).build(project_id, source["source_id"], user())
    path.unlink()
    with pytest.raises(Agent4ZeroShotInferenceError):
        service_for(n2_context, FakeRuntime(fail_text="system")).build(
            project_id, source["source_id"], user()
        )
    assert not path.exists()


def test_atomic_failure_cleans_partial(n2_context, monkeypatch):
    _, project_id, source = prepared(n2_context)
    root = n2_context[3]
    original = Path.replace
    monkeypatch.setattr(Path, "replace", lambda self, target: (_ for _ in ()).throw(OSError("boom")) if self.name.endswith(".zero-shot.json.part") else original(self, target))
    with pytest.raises(Agent4ZeroShotStorageError):
        service_for(n2_context, FakeRuntime()).build(project_id, source["source_id"], user())
    assert not list((root / project_id).rglob("*.zero-shot.json.part"))


def test_service_requires_completed_n2(n2_context):
    client = n2_context[0]
    project_id = create_project(client)
    source = add_text(client, project_id)
    confirm(client, project_id)
    with pytest.raises(Agent4ZeroShotGateError, match="must complete"):
        service_for(n2_context, FakeRuntime()).build(project_id, source["source_id"], user())

