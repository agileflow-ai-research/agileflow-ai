import hashlib
import json
from dataclasses import replace

import pytest

from app.main import app
from app.modules.agents.implementation.api.router import (
    get_implementation_upload_storage, get_semantic_artifact_service,
)
from app.modules.agents.implementation.preparation.semantic_extraction import constants
from app.modules.agents.implementation.preparation.semantic_extraction.artifact_service import (
    SemanticArtifactService,
)
from app.modules.agents.implementation.preparation.semantic_extraction.local_model import constants as model_constants
from app.modules.agents.implementation.preparation.semantic_extraction.local_model.adapter import (
    SemanticGenerationMetadata,
)
from app.modules.agents.implementation.preparation.semantic_extraction.local_model.model_loader import (
    SemanticModelUnavailableError,
)
from app.modules.agents.implementation.preparation.schemas import ArtifactDetectionLabel
from app.modules.standalone.service import StandaloneService
from app.modules.standalone.router import get_agent_run_repository
from test_agent3_canonical_artifacts import _complete_review, canonical_url
from test_agent3_document_extraction import create_project, extraction_context, upload_dir
from test_agent3_human_review import prepare_hybrid, put, state
from test_agent3_zero_shot_detection import zero_context


MODEL_REVISION = "70d244cc86ccca08cf5af4e1e306ecf908b1ad5e"


def semantic_url(project_id, upload_id):
    return f"/api/v1/agents/implementation/{project_id}/input-files/{upload_id}/semantic-artifacts"


class FixtureSemanticAdapter:
    def __init__(self, proposal_factory=None, revision=MODEL_REVISION):
        self.proposal_factory = proposal_factory or self._proposal
        self.calls = []
        self.revision = revision
        self.last_generation_metadata = None

    @property
    def configured_model(self):
        return model_constants.SEMANTIC_MODEL_ID, self.revision

    def extract(self, request):
        self.calls.append(request)
        self.last_generation_metadata = SemanticGenerationMetadata(
            attempt_count=1, input_token_count=100,
            output_token_count=30, generation_ms=12,
            first_model_load_ms=250,
            model_id=model_constants.SEMANTIC_MODEL_ID,
            revision=self.revision, device="cpu",
        )
        return self.proposal_factory(request)

    @staticmethod
    def _evidence(request):
        return [{"chunk_id": request.chunk_id, "quote": request.source_text,
                 "start_char": 0, "end_char": len(request.source_text)}]

    def _proposal(self, request):
        evidence = self._evidence(request)
        label = request.artifact_type
        empty = {
            ArtifactDetectionLabel.FUNCTIONAL_REQUIREMENTS: {"requirements": []},
            ArtifactDetectionLabel.NON_FUNCTIONAL_REQUIREMENTS: {"requirements": []},
            ArtifactDetectionLabel.USER_STORIES: {"stories": []},
            ArtifactDetectionLabel.ACCEPTANCE_CRITERIA: {"criteria": []},
            ArtifactDetectionLabel.SYSTEM_ARCHITECTURE: {
                "components": [], "relationships": [],
                "raw_architecture_statements": [],
            },
            ArtifactDetectionLabel.DATABASE_SCHEMA: {"entities": []},
            ArtifactDetectionLabel.UI_FLOW: {"flows": []},
            ArtifactDetectionLabel.TECHNOLOGY_STACK: {"stack": {
                "frontend": [], "styling": [], "backend": [], "database": [],
                "languages": [], "api_styles": [], "other": [],
                "evidence": evidence,
            }},
            ArtifactDetectionLabel.TECHNICAL_CONSTRAINTS: {"constraints": []},
            ArtifactDetectionLabel.IMPLEMENTATION_TASKS: {"tasks": []},
            ArtifactDetectionLabel.TEST_CASES: {"test_cases": []},
        }
        if label is ArtifactDetectionLabel.API_SPECIFICATION:
            return {
                "artifact_type": label.value,
                "endpoints": [{
                    "id": None, "method": "POST", "path": "/api/bookings",
                    "description": None, "request_fields": [],
                    "response_statuses": [409], "evidence": evidence,
                }],
            }
        return {"artifact_type": label.value, **empty[label]}


class UnavailableAdapter(FixtureSemanticAdapter):
    def extract(self, request):
        raise SemanticModelUnavailableError("private cache path")


@pytest.fixture
def semantic_context(zero_context):
    authentication, projects, root, _ = zero_context
    storage = app.dependency_overrides[get_implementation_upload_storage]()
    runs = app.dependency_overrides[get_agent_run_repository]()
    adapter = FixtureSemanticAdapter()
    service = SemanticArtifactService(
        StandaloneService(projects, runs), storage, adapter
    )
    app.dependency_overrides[get_semantic_artifact_service] = lambda: service
    try:
        yield authentication, projects, root, adapter, storage, runs
    finally:
        app.dependency_overrides.pop(get_semantic_artifact_service, None)


def prepare_canonical(client):
    project, metadata = prepare_hybrid(client)
    _complete_review(client, project, metadata)
    response = client.post(canonical_url(
        project["agent_project_id"], metadata["upload_id"]
    ))
    assert response.status_code == 200
    return project, metadata, response.json()["data"]


def test_prerequisites_get_read_only_and_model_unavailable_is_safe(semantic_context):
    authentication, projects, _, _, storage, runs = semantic_context
    client = authentication.client()
    project, metadata = prepare_hybrid(client)
    url = semantic_url(project["agent_project_id"], metadata["upload_id"])
    assert client.get(url).status_code == 409
    assert client.post(url).json()["errors"][0]["message"] == "HUMAN_VERIFICATION_REQUIRED"
    _complete_review(client, project, metadata)
    assert client.post(url).json()["errors"][0]["message"] == "CANONICAL_ARTIFACTS_REQUIRED"
    client.post(canonical_url(project["agent_project_id"], metadata["upload_id"]))
    assert client.get(url).status_code == 404

    unavailable = SemanticArtifactService(
        StandaloneService(projects, runs), storage, UnavailableAdapter()
    )
    app.dependency_overrides[get_semantic_artifact_service] = lambda: unavailable
    response = client.post(url)
    assert response.status_code == 503
    assert response.json()["errors"][0]["message"] == "SEMANTIC_MODEL_UNAVAILABLE"
    assert "path" not in response.text.casefold()


def test_semantic_api_grounding_preview_metrics_cache_and_baseline_immutability(semantic_context):
    authentication, _, root, adapter, _, _ = semantic_context
    client = authentication.client()
    project, metadata, canonical = prepare_canonical(client)
    project_id, upload_id = project["agent_project_id"], metadata["upload_id"]
    directory = upload_dir(root, project_id)
    canonical_path = directory / f"{upload_id}.canonical-artifacts.json"
    canonical_before = hashlib.sha256(canonical_path.read_bytes()).hexdigest()
    url = semantic_url(project_id, upload_id)
    response = client.post(url)
    assert response.status_code == 200
    result = response.json()["data"]
    assert result["model_id"] == model_constants.SEMANTIC_MODEL_ID
    assert result["model_revision"] == MODEL_REVISION
    assert result["semantic_contract_version"] == constants.SEMANTIC_CONTRACT_VERSION
    assert result["metrics"]["target_artifact_count"] >= 1
    assert result["metrics"]["total_attempt_count"] >= 1
    target = next(item for item in result["results"] if item["generation"])
    assert target["model"]["device"] == "cpu"
    assert target["generation"]["first_model_load_ms"] == 250
    assert target["merged_preview"] is not None
    assert target["status"] in {"GROUNDED", "REJECTED", "PARTIALLY_GROUNDED"}
    assert client.post(url).json()["data"] == result
    assert client.get(url).json()["data"] == result
    assert len(adapter.calls) == result["metrics"]["target_artifact_count"]
    assert hashlib.sha256(canonical_path.read_bytes()).hexdigest() == canonical_before
    assert "file_path" not in json.dumps(result).casefold()


def test_unsupported_and_conflicting_values_never_replace_deterministic(semantic_context):
    authentication, projects, _, _, storage, runs = semantic_context
    client = authentication.client()
    project, metadata, _ = prepare_canonical(client)
    url = semantic_url(project["agent_project_id"], metadata["upload_id"])

    def unsupported(request):
        evidence = FixtureSemanticAdapter._evidence(request)
        if request.artifact_type is ArtifactDetectionLabel.API_SPECIFICATION:
            return {"artifact_type": "API_SPECIFICATION", "endpoints": [{
                "id": None, "method": "DELETE", "path": "/invented",
                "description": None, "request_fields": [],
                "response_statuses": [], "evidence": evidence,
            }]}
        return FixtureSemanticAdapter()._proposal(request)

    adapter = FixtureSemanticAdapter(unsupported)
    app.dependency_overrides[get_semantic_artifact_service] = lambda: SemanticArtifactService(
        StandaloneService(projects, runs), storage, adapter
    )
    result = client.post(url, params={"force": "true"}).json()["data"]
    api = next(item for item in result["results"]
               if item["artifact_type"] == "API_SPECIFICATION")
    assert api["validation"]["rejected_facts"] >= 2
    endpoint = api["merged_preview"]["data"]["endpoints"][0]
    assert endpoint["method"] == "POST"
    assert endpoint["path"] == "/api/bookings"
    assert "/invented" not in json.dumps(api["merged_preview"])

    def conflict(request):
        proposal = unsupported(request)
        if request.artifact_type is ArtifactDetectionLabel.API_SPECIFICATION:
            proposal["endpoints"][0]["method"] = "PUT"
            proposal["endpoints"][0]["path"] = "/api/bookings"
            proposal["endpoints"][0]["evidence"][0]["quote"] = request.source_text + " PUT"
            proposal["endpoints"][0]["evidence"][0]["end_char"] += 4
        return proposal

    # PUT is absent from the trusted source, so it remains unsupported rather than conflicting.
    adapter.proposal_factory = conflict
    second = client.post(url, params={"force": "true"}).json()["data"]
    api = next(item for item in second["results"]
               if item["artifact_type"] == "API_SPECIFICATION")
    assert api["merged_preview"]["data"]["endpoints"][0]["method"] == "POST"


def test_cache_versions_canonical_digest_malformed_cache_and_deletion(semantic_context, monkeypatch):
    authentication, projects, root, adapter, storage, runs = semantic_context
    client = authentication.client()
    project, metadata, _ = prepare_canonical(client)
    project_id, upload_id = project["agent_project_id"], metadata["upload_id"]
    url = semantic_url(project_id, upload_id)
    assert client.post(url).status_code == 200
    directory = upload_dir(root, project_id)
    sidecar = directory / f"{upload_id}.semantic-artifacts.json"
    canonical_path = directory / f"{upload_id}.canonical-artifacts.json"

    sidecar.write_text("not-json", encoding="utf-8")
    assert client.get(url).status_code == 404
    assert client.post(url).status_code == 200

    changed_revision = "1" * 40
    changed_adapter = FixtureSemanticAdapter(revision=changed_revision)
    app.dependency_overrides[get_semantic_artifact_service] = lambda: SemanticArtifactService(
        StandaloneService(projects, runs), storage, changed_adapter
    )
    assert client.get(url).status_code == 404

    app.dependency_overrides[get_semantic_artifact_service] = lambda: SemanticArtifactService(
        StandaloneService(projects, runs), storage, adapter
    )
    monkeypatch.setattr(model_constants, "SEMANTIC_PROMPT_VERSION", "999")
    assert client.get(url).status_code == 404
    monkeypatch.setattr(model_constants, "SEMANTIC_PROMPT_VERSION", "1")

    canonical_payload = json.loads(canonical_path.read_text(encoding="utf-8"))
    canonical_payload["warnings"].append("CACHE_IDENTITY_TEST")
    canonical_path.write_text(json.dumps(canonical_payload), encoding="utf-8")
    assert client.get(url).status_code == 404

    assert client.delete(
        f"/api/v1/agents/implementation/{project_id}/input-files/{upload_id}"
    ).status_code == 200
    assert not sidecar.exists()


def test_human_review_change_invalidates_semantic_and_canonical_cache(semantic_context):
    authentication, _, _, _, _, _ = semantic_context
    client = authentication.client()
    project, metadata, _ = prepare_canonical(client)
    project_id, upload_id = project["agent_project_id"], metadata["upload_id"]
    url = semantic_url(project_id, upload_id)
    assert client.post(url).status_code == 200
    current = state(client, project, metadata)
    queue = current["review_queue"][0]
    candidate = queue["hybrid"]["candidates"][0]["label"]
    replacement = "DATABASE_SCHEMA" if candidate != "DATABASE_SCHEMA" else "API_SPECIFICATION"
    changed = put(
        client, project, metadata, queue["chunk"]["chunk_id"],
        current["review"]["review_fingerprint"], [{
            "action": "RELABEL", "source_candidate_label": candidate,
            "final_label": replacement, "note": None,
        }],
    )
    assert changed.status_code == 200
    response = client.get(url)
    assert response.status_code == 409
    assert response.json()["errors"][0]["message"] == "CANONICAL_ARTIFACTS_REQUIRED"


def test_security_and_openapi(semantic_context):
    authentication, _, _, _, _, _ = semantic_context
    owner, foreign = authentication.client("USR-001"), authentication.client("USR-002")
    project, metadata, _ = prepare_canonical(owner)
    url = semantic_url(project["agent_project_id"], metadata["upload_id"])
    assert foreign.post(url).status_code == 404
    wrong = create_project(owner, "DESIGN_PLANNING")
    assert owner.post(semantic_url(wrong["agent_project_id"], metadata["upload_id"])).status_code == 422
    owner.patch(
        f'/api/v1/agent-projects/{project["agent_project_id"]}',
        json={"status": "ARCHIVED"},
    )
    assert owner.post(url).status_code == 409

    paths = app.openapi()["paths"]
    path = "/api/v1/agents/implementation/{agent_project_id}/input-files/{upload_id}/semantic-artifacts"
    assert set(paths[path]) == {"get", "post"}
    forbidden = ("semantic-approval", "agent-run", "code-generation",
                 "image-understanding", "fine-tuning")
    agent_paths = [item for item in paths
                   if item.startswith("/api/v1/agents/implementation")]
    assert not any(any(value in item for value in forbidden) for item in agent_paths)
