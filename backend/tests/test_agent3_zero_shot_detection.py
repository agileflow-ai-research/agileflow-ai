import hashlib
import json
from types import SimpleNamespace

import pytest

from app.main import app
from app.modules.agents.implementation.extraction.schemas import DocumentType
from app.modules.agents.implementation.router import (
    get_implementation_upload_storage,
    get_zero_shot_detection_service,
)
from app.modules.agents.implementation.semantic_discovery.schemas import (
    ArtifactDetectionLabel,
    ChunkContext,
    ChunkProvenance,
    SemanticChunk,
)
from app.modules.agents.implementation.semantic_discovery.zero_shot import constants
from app.modules.agents.implementation.semantic_discovery.zero_shot import service as service_module
from app.modules.agents.implementation.semantic_discovery.zero_shot.classifier import (
    ClassificationOutcome,
    ZeroShotClassifier,
)
from app.modules.agents.implementation.semantic_discovery.zero_shot.model_loader import (
    LoadedZeroShotModel,
    ZeroShotModelUnavailableError,
)
from app.modules.agents.implementation.semantic_discovery.zero_shot.schemas import ZeroShotScore
from app.modules.agents.implementation.semantic_discovery.zero_shot.service import (
    ZeroShotDetectionService,
)
from app.modules.standalone.router import get_agent_run_repository
from app.modules.standalone.service import StandaloneService
from test_agent3_document_extraction import (
    PNG,
    create_project,
    extraction_context,
    extract,
    upload,
    upload_dir,
)
from test_agent3_semantic_chunking import build as build_chunks


def semantic_chunk(text="POST /api/bookings"):
    normalized = text.strip()
    return SemanticChunk(
        chunk_id="CHK-0123456789ABCDEF0123",
        chunk_index=0,
        text=normalized,
        text_hash=hashlib.sha256(normalized.encode()).hexdigest(),
        token_count=max(1, len(normalized.split())),
        character_count=len(normalized),
        context=ChunkContext(),
        provenance=ChunkProvenance(
            upload_id="A3UP-0123456789abcdef0123456789abcdef",
            agent_project_id="AGP-003",
            original_filename="spec.txt",
            source_sha256="a" * 64,
            document_type=DocumentType.TXT,
            line_start=1,
            line_end=1,
        ),
    )


class FakeTokenizer:
    def __init__(self, count=20):
        self.count = count

    def __call__(self, *_args, **_kwargs):
        return {"input_ids": list(range(self.count))}


class FakePipeline:
    def __init__(self, scores=None, fail_text=None):
        self.calls = []
        self.scores = scores or {}
        self.fail_text = fail_text

    def __call__(self, texts, **kwargs):
        self.calls.append((texts, kwargs))
        values = texts if isinstance(texts, list) else [texts]
        if self.fail_text and any(self.fail_text in value for value in values):
            raise RuntimeError("safe test failure")
        responses = []
        for _ in values:
            labels = list(kwargs["candidate_labels"])
            responses.append({
                "labels": labels,
                "scores": [self.scores.get(label, 0.1) for label in labels],
            })
        return responses if isinstance(texts, list) else responses[0]


class FakeLoader:
    loaded = None

    @classmethod
    def load(cls, *, local_files_only):
        assert local_files_only is True
        return cls.loaded


def classifier_with(scores=None, *, token_count=20, fail_text=None, max_length=512):
    pipeline = FakePipeline(scores, fail_text)
    FakeLoader.loaded = LoadedZeroShotModel(
        pipeline=pipeline,
        tokenizer=FakeTokenizer(token_count),
        device="cpu",
        model_max_length=max_length,
    )
    return ZeroShotClassifier(local_files_only=True, loader=FakeLoader), pipeline


def test_frozen_taxonomy_mapping_template_and_multi_label_invocation():
    assert len(constants.CANDIDATE_LABELS) == 13
    assert set(constants.CANDIDATE_LABELS) == set(ArtifactDetectionLabel)
    assert all(description.strip() for description in constants.CANDIDATE_LABELS.values())
    assert constants.HYPOTHESIS_TEMPLATE == "This software-engineering text describes {}."
    classifier, pipeline = classifier_with()
    classifier.classify_chunks([semantic_chunk()])
    _, kwargs = pipeline.calls[0]
    assert kwargs["candidate_labels"] == list(constants.CANDIDATE_LABELS.values())
    assert kwargs["hypothesis_template"] == constants.HYPOTHESIS_TEMPLATE
    assert kwargs["multi_label"] is True
    assert kwargs["truncation"] is True


def test_all_raw_scores_display_threshold_cap_other_and_determinism():
    descriptions = list(constants.CANDIDATE_LABELS.values())
    scores = {description: 0.51 + index / 100 for index, description in enumerate(descriptions)}
    classifier, _ = classifier_with(scores)
    first = classifier.classify_chunks([semantic_chunk()])[1][0]
    second = classifier.classify_chunks([semantic_chunk()])[1][0]
    assert first.scores == second.scores
    assert len(first.scores) == 13
    assert len(first.display_predictions) == constants.MAX_DISPLAY_LABELS
    assert all(item.score >= constants.MODEL_DISPLAY_THRESHOLD for item in first.display_predictions)

    other_description = constants.CANDIDATE_LABELS[ArtifactDetectionLabel.OTHER_CONTEXT]
    classifier, _ = classifier_with({other_description: 0.9})
    outcome = classifier.classify_chunks([semantic_chunk("Company background")])[1][0]
    assert [item.label for item in outcome.display_predictions] == [ArtifactDetectionLabel.OTHER_CONTEXT]


def test_tokenizer_aware_count_truncation_and_chunk_failure_isolation():
    classifier, _ = classifier_with(token_count=600, fail_text="FAIL", max_length=512)
    chunks = [semantic_chunk("normal"), semantic_chunk("FAIL")]
    chunks[1].chunk_id = "CHK-FFFFFFFFFFFFFFFFFFFF"
    outcomes = classifier.classify_chunks(chunks)[1]
    assert outcomes[0].model_token_count == 600
    assert outcomes[0].input_truncated is True
    assert outcomes[0].error is False
    assert outcomes[1].error is True
    assert outcomes[1].scores == []


class StubClassifier:
    def __init__(self, *, fail_model=False, fail_chunk=False, truncated=False):
        self.calls = 0
        self.fail_model = fail_model
        self.fail_chunk = fail_chunk
        self.truncated = truncated

    def classify_chunks(self, chunks):
        self.calls += 1
        if self.fail_model:
            raise ZeroShotModelUnavailableError("secret path must never escape")
        outcomes = []
        for index, chunk in enumerate(chunks):
            failed = self.fail_chunk and index == len(chunks) - 1
            scores = [] if failed else [
                ZeroShotScore(label=label, score=0.9 if label is ArtifactDetectionLabel.API_SPECIFICATION else 0.1)
                for label in ArtifactDetectionLabel
            ]
            outcomes.append(ClassificationOutcome(
                chunk_id=chunk.chunk_id,
                text_hash=chunk.text_hash,
                model_token_count=600 if self.truncated else 20,
                model_max_length=512,
                input_truncated=self.truncated,
                inference_ms=10.0,
                scores=scores,
                display_predictions=[] if failed else [scores[6]],
                error=failed,
            ))
        return SimpleNamespace(device="cpu"), outcomes


@pytest.fixture
def zero_context(extraction_context):
    authentication, projects, root = extraction_context
    storage = app.dependency_overrides[get_implementation_upload_storage]()
    runs = app.dependency_overrides[get_agent_run_repository]()
    classifier = StubClassifier()
    service = ZeroShotDetectionService(StandaloneService(projects, runs), storage, classifier)
    app.dependency_overrides[get_zero_shot_detection_service] = lambda: service
    try:
        yield authentication, projects, root, classifier
    finally:
        app.dependency_overrides.pop(get_zero_shot_detection_service, None)


def prepare(client, content=b"POST /api/bookings\n\nGeneral context"):
    project = create_project(client)
    metadata = upload(client, project["agent_project_id"], "spec.txt", content)
    assert extract(client, project["agent_project_id"], metadata["upload_id"]).status_code == 200
    assert build_chunks(client, project["agent_project_id"], metadata["upload_id"]).status_code == 200
    return project, metadata


def run_model(client, project_id, upload_id, *, force=False):
    return client.post(
        f"/api/v1/agents/implementation/{project_id}/input-files/{upload_id}/zero-shot-detections",
        params={"force": str(force).lower()},
    )


def get_model(client, project_id, upload_id):
    return client.get(
        f"/api/v1/agents/implementation/{project_id}/input-files/{upload_id}/zero-shot-detections"
    )


def replace_classifier(projects, classifier):
    storage = app.dependency_overrides[get_implementation_upload_storage]()
    runs = app.dependency_overrides[get_agent_run_repository]()
    service = ZeroShotDetectionService(StandaloneService(projects, runs), storage, classifier)
    app.dependency_overrides[get_zero_shot_detection_service] = lambda: service


def test_api_metadata_raw_scores_provenance_metrics_and_cache(zero_context):
    authentication, _, _, classifier = zero_context
    client = authentication.client()
    project, metadata = prepare(client)
    assert get_model(client, project["agent_project_id"], metadata["upload_id"]).status_code == 404
    first = run_model(client, project["agent_project_id"], metadata["upload_id"])
    assert first.status_code == 200
    result = first.json()["data"]
    assert result["classifier_type"] == "ZERO_SHOT_NLI"
    assert result["classifier_version"] == "1"
    assert result["score_semantics"] == "ZERO_SHOT_NLI_NOT_DOMAIN_CALIBRATED"
    assert result["model"] == {
        "model_id": constants.MODEL_ID,
        "revision": constants.MODEL_REVISION,
        "task": "zero-shot-classification",
        "hypothesis_template": constants.HYPOTHESIS_TEMPLATE,
        "multi_label": True,
        "label_map_version": "1",
        "template_version": "1",
        "device": "cpu",
    }
    assert all(len(chunk["scores"]) == 13 for chunk in result["chunks"])
    assert result["chunks"][0]["provenance"]["original_filename"] == "spec.txt"
    assert result["metrics"]["classified_chunk_count"] == result["metrics"]["chunk_count"]
    assert "accuracy" not in result["metrics"]
    assert "agileflow-ai" not in json.dumps(result).lower()
    assert run_model(client, project["agent_project_id"], metadata["upload_id"]).json()["data"] == result
    assert classifier.calls == 1


def test_partial_status_truncation_and_per_chunk_failure(zero_context):
    authentication, projects, _, _ = zero_context
    client = authentication.client()
    project, metadata = prepare(
        client,
        ("# API\n" + "POST /api/bookings response " * 450 + "\n# Tests\n" + "Expected result " * 450).encode(),
    )
    classifier = StubClassifier(fail_chunk=True, truncated=True)
    replace_classifier(projects, classifier)
    result = run_model(client, project["agent_project_id"], metadata["upload_id"], force=True).json()["data"]
    assert result["status"] == "PARTIAL"
    assert result["metrics"]["truncated_chunk_count"] == result["metrics"]["chunk_count"]
    assert result["metrics"]["failed_chunk_count"] == 1
    assert {warning["code"] for warning in result["warnings"]} == {
        "MODEL_INPUT_TRUNCATED", "CHUNK_CLASSIFICATION_FAILED",
    }


def test_model_unavailable_is_safe_failed_result_and_not_cached(zero_context):
    authentication, projects, _, _ = zero_context
    client = authentication.client()
    project, metadata = prepare(client)
    classifier = StubClassifier(fail_model=True)
    replace_classifier(projects, classifier)
    response = run_model(client, project["agent_project_id"], metadata["upload_id"])
    assert response.status_code == 200
    result = response.json()["data"]
    assert result["status"] == "FAILED"
    assert result["model"]["device"] == "unavailable"
    assert result["warnings"][0]["code"] == "MODEL_UNAVAILABLE"
    serialized = json.dumps(result).lower()
    assert "secret path" not in serialized
    assert "traceback" not in serialized
    assert get_model(client, project["agent_project_id"], metadata["upload_id"]).status_code == 404


@pytest.mark.parametrize("change", ["chunk", "classifier", "revision", "label_map", "template", "malformed"])
def test_stale_or_malformed_cache_is_rebuilt(zero_context, monkeypatch, change):
    authentication, _, root, classifier = zero_context
    client = authentication.client()
    project, metadata = prepare(client)
    run_model(client, project["agent_project_id"], metadata["upload_id"])
    sidecar = upload_dir(root, project["agent_project_id"]) / f'{metadata["upload_id"]}.zero-shot-detections.json'
    if change == "malformed":
        sidecar.write_text("not-json", encoding="utf-8")
    else:
        cached = json.loads(sidecar.read_text(encoding="utf-8"))
        if change == "chunk":
            cached["chunks"][0]["text_hash"] = "0" * 64
        elif change == "classifier":
            cached["classifier_version"] = "999"
        elif change == "revision":
            cached["model"]["revision"] = "0" * 40
        elif change == "label_map":
            cached["model"]["label_map_version"] = "999"
        else:
            cached["model"]["template_version"] = "999"
        sidecar.write_text(json.dumps(cached), encoding="utf-8")
    assert get_model(client, project["agent_project_id"], metadata["upload_id"]).status_code == 404
    assert run_model(client, project["agent_project_id"], metadata["upload_id"]).status_code == 200
    assert classifier.calls == 2


def test_runtime_version_change_invalidates_cache(zero_context, monkeypatch):
    authentication, _, _, classifier = zero_context
    client = authentication.client()
    project, metadata = prepare(client)
    run_model(client, project["agent_project_id"], metadata["upload_id"])
    monkeypatch.setattr(service_module, "ZERO_SHOT_CLASSIFIER_VERSION", "2")
    assert get_model(client, project["agent_project_id"], metadata["upload_id"]).status_code == 404
    assert run_model(client, project["agent_project_id"], metadata["upload_id"]).status_code == 200
    assert classifier.calls == 2


def test_security_guards_and_deletion_cleanup(zero_context):
    authentication, _, root, _ = zero_context
    owner = authentication.client("USR-001")
    foreign = authentication.client("USR-002")
    project, metadata = prepare(owner)
    assert run_model(foreign, project["agent_project_id"], metadata["upload_id"]).status_code == 404
    assert run_model(owner, project["agent_project_id"], metadata["upload_id"]).status_code == 200
    sidecar = upload_dir(root, project["agent_project_id"]) / f'{metadata["upload_id"]}.zero-shot-detections.json'
    partial = sidecar.with_name(sidecar.name + ".part")
    partial.write_text("partial", encoding="utf-8")
    owner.patch(f'/api/v1/agent-projects/{project["agent_project_id"]}', json={"status": "ARCHIVED"})
    assert run_model(owner, project["agent_project_id"], metadata["upload_id"]).status_code == 409

    active = create_project(owner)
    missing = upload(owner, active["agent_project_id"], "missing.txt", b"content")
    extract(owner, active["agent_project_id"], missing["upload_id"])
    assert run_model(owner, active["agent_project_id"], missing["upload_id"]).status_code == 409
    image = upload(owner, active["agent_project_id"], "wire.png", PNG, "IMAGE")
    assert run_model(owner, active["agent_project_id"], image["upload_id"]).status_code == 422
    wrong = create_project(owner, "DESIGN_PLANNING")
    assert run_model(owner, wrong["agent_project_id"], metadata["upload_id"]).status_code == 422

    owner.patch(f'/api/v1/agent-projects/{project["agent_project_id"]}', json={"status": "ACTIVE"})
    assert owner.delete(f'/api/v1/agents/implementation/{project["agent_project_id"]}/input-files/{metadata["upload_id"]}').status_code == 200
    assert not sidecar.exists()
    assert not partial.exists()


def test_openapi_exposes_zero_shot_baseline_routes_without_later_stage_routes():
    paths = app.openapi()["paths"]
    route = "/api/v1/agents/implementation/{agent_project_id}/input-files/{upload_id}/zero-shot-detections"
    assert set(paths[route]) == {"get", "post"}
    forbidden = ("fine-tun", "dataset-export", "agent-run", "code-generation", "image-analysis")
    agent_paths = [path for path in paths if path.startswith("/api/v1/agents/implementation")]
    assert not any(any(term in path for term in forbidden) for path in agent_paths)
