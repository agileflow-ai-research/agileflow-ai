import json
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.modules.agents.testing_validation.context_testability.traceability.canonicalization import (
    lexical_jaccard,
    normalize_api_path,
)
from app.modules.agents.testing_validation.context_testability.traceability.constants import (
    LEXICAL_JACCARD_THRESHOLD,
    LEXICAL_POLICY_VERSION,
    TRACEABILITY_ENGINE_VERSION,
    TRACEABILITY_SCHEMA_VERSION,
)
from app.modules.agents.testing_validation.context_testability.traceability.engine import (
    build_traceability_components,
)
from app.modules.agents.testing_validation.context_testability.traceability.schemas import (
    Agent4TraceabilityManifest,
    TraceabilityCounts,
    TraceabilityEvidenceMethod,
    TraceabilityLink,
    TraceabilityNode,
    TraceabilityRelationType,
)
from app.modules.agents.testing_validation.context_testability.traceability.service import (
    Agent4TraceabilityGateError,
    Agent4TraceabilityService,
)
from app.modules.agents.testing_validation.context_testability.traceability.storage import (
    Agent4TraceabilityStorage,
    Agent4TraceabilityStorageError,
)
from app.modules.agents.testing_validation.contracts.sources import (
    TestGenerationInputArtifactType as A,
    TestGenerationInputSourceType as S,
)
from app.modules.agents.testing_validation.intelligence.effective.storage import (
    Agent4EffectiveStorage,
)
from app.modules.agents.testing_validation.intelligence.semantic.schemas import (
    SemanticResultStatus,
)
from app.modules.agents.testing_validation.intelligence.semantic.storage import (
    Agent4SemanticStorage,
)
from app.modules.agents.testing_validation.preparation.chunking.storage import (
    Agent4ChunkStorage,
)
from app.modules.agents.testing_validation.workflow.schemas import (
    Agent4N3ExecutionStatus,
)
from app.modules.agents.testing_validation.workflow.storage import (
    Agent4WorkflowStorage,
)
from test_agent4_n2_orchestration import add_text, confirm, create_project, load, n2_context
from test_agent4_n3_orchestration import n3_service
from test_standalone_foundation import user


NOW = datetime(2026, 10, 21, tzinfo=timezone.utc)


def source(index, artifact=A.FUNCTIONAL_REQUIREMENTS, source_type=S.TEXT):
    return SimpleNamespace(
        source_id=f"A4SRC-{index:032x}", artifact_type=artifact,
        source_type=source_type, label=None, original_filename=("wireframe.png" if source_type is S.IMAGE else None),
    )


def chunk(index, source_value, text, artifact=A.FUNCTIONAL_REQUIREMENTS):
    return SimpleNamespace(
        chunk_id=f"A4CHK-{index:032x}", agent_project_id="AGP-100",
        source_id=source_value.source_id, artifact_type=artifact,
        source_type=source_value.source_type, text=text,
    )


def components(items, *, semantic=None, effective=None):
    chunk_sets = {
        item[0].source_id: SimpleNamespace(chunks=item[1])
        for item in items if item[0].source_type is not S.IMAGE
    }
    return build_traceability_components(
        project_id="AGP-100", sources=[item[0] for item in items],
        chunk_sets=chunk_sets,
        effective_manifests=effective or {}, semantic_manifests=semantic or {},
    )


def manifest_for(graph):
    return Agent4TraceabilityManifest(
        schema_version=TRACEABILITY_SCHEMA_VERSION,
        engine_version=TRACEABILITY_ENGINE_VERSION,
        lexical_policy_version=LEXICAL_POLICY_VERSION,
        agent_project_id="AGP-100", confirmation_id=f"A4N1C-{'1' * 32}",
        n2_execution_id=f"A4N2E-{'2' * 32}", n3_execution_id=f"A4N3E-{'3' * 32}",
        input_fingerprint="4" * 64, evidence_fingerprints={"evidence": "5" * 64},
        nodes=graph.nodes, links=graph.links,
        unresolved_references=graph.unresolved, ambiguities=graph.ambiguities,
        counts=TraceabilityCounts(
            node_count=len(graph.nodes), link_count=len(graph.links),
            unresolved_count=len(graph.unresolved), ambiguous_count=len(graph.ambiguities),
        ), built_at=NOW,
    )


def test_versions_contracts_and_deterministic_identity_are_strict():
    left = source(1)
    graph_a = components([(left, [chunk(1, left, "FR-001: Create booking")])])
    graph_b = components([(left, [chunk(1, left, "FR-001: Create booking")])])
    assert (TRACEABILITY_SCHEMA_VERSION, TRACEABILITY_ENGINE_VERSION, LEXICAL_POLICY_VERSION) == ("1", "TR1", "LX1")
    assert [item.node_id for item in graph_a.nodes] == [item.node_id for item in graph_b.nodes]
    assert len({item.node_id for item in graph_a.nodes}) == len(graph_a.nodes)
    with pytest.raises(ValidationError, match="extra_forbidden"):
        TraceabilityNode.model_validate({**graph_a.nodes[0].model_dump(), "path": "C:/private"})
    with pytest.raises(ValidationError):
        TraceabilityLink.model_validate({
            "traceability_link_id": f"A4TRL-{'1' * 32}",
            "source_node_id": graph_a.nodes[0].node_id,
            "target_node_id": graph_a.nodes[-1].node_id,
            "relation_type": "INVENTED", "evidence_method": "MAGIC",
            "evidence_references": ["x"], "reason_code": "BAD_LINK",
            "explanation": "invalid", "strength": "EXACT",
            "traceability_version": "TR1",
        })


def test_explicit_fr_us_ac_links_are_directional_exact_and_deterministic():
    fr, us, ac = source(1, A.FUNCTIONAL_REQUIREMENTS), source(2, A.USER_STORIES), source(3, A.ACCEPTANCE_CRITERIA)
    graph = components([
        (fr, [chunk(1, fr, "FR-001: Cancel a booking", A.FUNCTIONAL_REQUIREMENTS)]),
        (us, [chunk(2, us, "US-012: As a user I cancel a booking. Related requirement: FR-001", A.USER_STORIES)]),
        (ac, [chunk(3, ac, "AC-014: Validates US-012 when cancellation succeeds", A.ACCEPTANCE_CRITERIA)]),
    ])
    exact = [item for item in graph.links if item.evidence_method is TraceabilityEvidenceMethod.EXPLICIT_ID]
    assert {(item.relation_type, item.strength.value) for item in exact} == {
        (TraceabilityRelationType.REFINES, "EXACT"),
        (TraceabilityRelationType.VALIDATES, "EXACT"),
    }
    again = components([
        (fr, [chunk(1, fr, "FR-001: Cancel a booking", A.FUNCTIONAL_REQUIREMENTS)]),
        (us, [chunk(2, us, "US-012: As a user I cancel a booking. Related requirement: FR-001", A.USER_STORIES)]),
        (ac, [chunk(3, ac, "AC-014: Validates US-012 when cancellation succeeds", A.ACCEPTANCE_CRITERIA)]),
    ])
    assert [item.traceability_link_id for item in exact] == [
        item.traceability_link_id for item in again.links
        if item.evidence_method is TraceabilityEvidenceMethod.EXPLICIT_ID
    ]


def test_dangling_and_ambiguous_explicit_ids_never_fabricate_a_link():
    fr1, fr2, story = source(1), source(2), source(3, A.USER_STORIES)
    graph = components([
        (fr1, [chunk(1, fr1, "FR-001: First definition")]),
        (fr2, [chunk(2, fr2, "FR-001: Duplicate definition")]),
        (story, [chunk(3, story, "US-001: References FR-001 and FR-999", A.USER_STORIES)]),
    ])
    assert any(item.reference_value == "FR-999" for item in graph.unresolved)
    ambiguity = next(item for item in graph.ambiguities if item.reference_value == "FR-001")
    assert ambiguity.candidate_node_ids == sorted(ambiguity.candidate_node_ids)
    story_node = next(item for item in graph.nodes if item.external_reference_id == "US-001")
    assert not any(item.source_node_id == story_node.node_id and item.evidence_method is TraceabilityEvidenceMethod.EXPLICIT_ID for item in graph.links)


def test_api_operation_matching_is_conservative_and_normalizes_parameters():
    first, second, third = source(1, A.API_SPECIFICATION), source(2, A.API_SPECIFICATION), source(3, A.API_SPECIFICATION)
    graph = components([
        (first, [chunk(1, first, "DELETE /api/bookings/{id}", A.API_SPECIFICATION)]),
        (second, [chunk(2, second, "DELETE /api/bookings/:bookingId", A.API_SPECIFICATION)]),
        (third, [chunk(3, third, "GET /api/bookings/{id}\nDELETE api/broken", A.API_SPECIFICATION)]),
    ])
    api_links = [item for item in graph.links if item.evidence_method is TraceabilityEvidenceMethod.API_ENDPOINT]
    assert len(api_links) == 1
    assert api_links[0].reason_code == "SAME_API_OPERATION"
    assert normalize_api_path("/api/users/:id") == normalize_api_path("/api/users/{userId}")
    assert any(item.reason_code == "MALFORMED_API_ENDPOINT" for item in graph.unresolved)


def test_entity_field_matching_preserves_specificity_and_ambiguity():
    schema1, schema2 = source(1, A.DATABASE_SCHEMA), source(2, A.DATABASE_SCHEMA)
    fact_source = source(3, A.FUNCTIONAL_REQUIREMENTS)
    fact_chunk = chunk(3, fact_source, "The booking status changes.")
    fact = SimpleNamespace(
        fact_id=f"A4FACT-{'4' * 32}", evidence_quote="The booking status changes.",
        evidence_start=4, evidence_end=18, api_method=None, api_endpoint=None,
        target="Booking", field_name="status",
    )
    semantic_result = SimpleNamespace(
        status=SemanticResultStatus.SUCCESS, chunk=fact_chunk,
        semantic_result_id=f"A4SEM-{'5' * 32}", hybrid_result_id=f"A4HYB-{'6' * 32}",
        effective_result_id=f"A4EFF-{'7' * 32}", facts=[fact],
    )
    effective_result = SimpleNamespace(chunk=fact_chunk, review_id=f"A4N3R-{'8' * 32}")
    graph = components([
        (schema1, [chunk(1, schema1, "Entity: Booking\nBooking.status", A.DATABASE_SCHEMA)]),
        (schema2, [chunk(2, schema2, "Table: booking\nbooking_status.value\nBooking.status", A.DATABASE_SCHEMA)]),
        (fact_source, [fact_chunk]),
    ], semantic={fact_source.source_id: SimpleNamespace(results=[semantic_result])},
       effective={fact_source.source_id: SimpleNamespace(results=[effective_result])})
    ambiguity = next(item for item in graph.ambiguities if item.evidence_method is TraceabilityEvidenceMethod.ENTITY_FIELD)
    assert len(ambiguity.candidate_node_ids) == 2
    fact_node = next(item for item in graph.nodes if item.semantic_fact_id)
    assert fact_node.entity_name == "booking" and fact_node.field_name == "status"
    assert fact_node.review_id == f"A4N3R-{'8' * 32}"
    assert not any(item.source_node_id == fact_node.node_id and item.relation_type is TraceabilityRelationType.USES_FIELD for item in graph.links)


def test_feature_and_lexical_matching_are_versioned_conservative_and_neutral():
    feature_a, feature_b = source(1, A.FEATURES), source(2, A.FEATURES)
    req_a, req_b, generic = source(3), source(4), source(5)
    graph = components([
        (feature_a, [chunk(1, feature_a, "Feature: Booking Cancellation", A.FEATURES)]),
        (feature_b, [chunk(2, feature_b, "Feature: Cancel Booking", A.FEATURES)]),
        (req_a, [chunk(3, req_a, "customer cancels active booking reservation")]),
        (req_b, [chunk(4, req_b, "customer cancels active booking reservation safely")]),
        (generic, [chunk(5, generic, "booking report is available")]),
    ])
    lexical = [item for item in graph.links if item.evidence_method is TraceabilityEvidenceMethod.LEXICAL_SIMILARITY]
    feature = [item for item in graph.links if item.evidence_method is TraceabilityEvidenceMethod.FEATURE_NAME]
    assert len(feature) == 1 and feature[0].strength.value == "STRONG"
    assert len(lexical) == 1
    assert lexical[0].relation_type is TraceabilityRelationType.RELATED_TO
    assert lexical[0].lexical_score >= LEXICAL_JACCARD_THRESHOLD
    assert "booking" in lexical[0].matched_tokens
    score, shared = lexical_jaccard("customer cancels active booking reservation", "customer cancels active booking reservation safely")
    assert (round(score, 6), shared) == (lexical[0].lexical_score, lexical[0].matched_tokens)
    assert not any("report" in item.matched_tokens for item in lexical)


def test_semantic_fact_links_exact_chunk_and_effective_review_context():
    evidence_source = source(1)
    evidence_chunk = chunk(1, evidence_source, "DELETE /api/bookings/{id} cancels a booking")
    fact = SimpleNamespace(
        fact_id=f"A4FACT-{'a' * 32}", evidence_quote="DELETE /api/bookings/{id}",
        evidence_start=0, evidence_end=25, api_method="DELETE",
        api_endpoint="/api/bookings/:id", target=None, field_name=None,
    )
    result = SimpleNamespace(
        status=SemanticResultStatus.SUCCESS, chunk=evidence_chunk,
        semantic_result_id=f"A4SEM-{'b' * 32}", hybrid_result_id=f"A4HYB-{'c' * 32}",
        effective_result_id=f"A4EFF-{'d' * 32}", facts=[fact],
    )
    effective_result = SimpleNamespace(chunk=evidence_chunk, review_id=f"A4N3R-{'e' * 32}")
    graph = components(
        [(evidence_source, [evidence_chunk])],
        semantic={evidence_source.source_id: SimpleNamespace(results=[result])},
        effective={evidence_source.source_id: SimpleNamespace(results=[effective_result])},
    )
    fact_node = next(item for item in graph.nodes if item.semantic_fact_id)
    support = next(item for item in graph.links if item.relation_type is TraceabilityRelationType.SUPPORTED_BY)
    endpoint = next(item for item in graph.links if item.relation_type is TraceabilityRelationType.USES_ENDPOINT)
    assert (fact_node.effective_result_id, fact_node.review_id) == (
        f"A4EFF-{'d' * 32}", f"A4N3R-{'e' * 32}",
    )
    assert set(support.evidence_references) >= {
        fact.fact_id, result.semantic_result_id, result.hybrid_result_id,
        result.effective_result_id, effective_result.review_id,
    }
    assert endpoint.evidence_method is TraceabilityEvidenceMethod.API_ENDPOINT


def test_image_is_metadata_only_and_creates_no_inferred_intelligence():
    image = source(1, A.WIREFRAMES, S.IMAGE)
    graph = components([(image, [])])
    assert len(graph.nodes) == 1
    assert graph.nodes[0].chunk_id is None and graph.nodes[0].semantic_fact_id is None
    assert graph.links == []
    assert graph.unresolved[0].reason_code == "IMAGE_HAS_NO_TRUSTED_TEXT_EVIDENCE"


def test_manifest_is_canonical_counted_and_contains_no_paths_or_documents():
    first, second = source(1), source(2)
    graph = components([
        (first, [chunk(1, first, "customer cancels active booking reservation")]),
        (second, [chunk(2, second, "customer cancels active booking reservation safely")]),
    ])
    manifest = manifest_for(graph)
    assert manifest.counts.node_count == len(manifest.nodes)
    assert [item.node_id for item in manifest.nodes] == sorted(item.node_id for item in manifest.nodes)
    assert [item.traceability_link_id for item in manifest.links] == sorted(item.traceability_link_id for item in manifest.links)
    serialized = manifest.model_dump_json()
    assert "C:\\" not in serialized and "/tmp/" not in serialized
    assert "model_revision" not in serialized and "normalized_text" not in serialized
    with pytest.raises(ValidationError, match="counts"):
        Agent4TraceabilityManifest.model_validate({
            **manifest.model_dump(),
            "counts": TraceabilityCounts(node_count=0, link_count=0, unresolved_count=0, ambiguous_count=0),
        })


def test_storage_is_project_scoped_atomic_and_rejects_foreign_owner(tmp_path, monkeypatch):
    src = source(1)
    manifest = manifest_for(components([(src, [chunk(1, src, "FR-001: Create booking")])]))
    storage = Agent4TraceabilityStorage(tmp_path)
    storage.save(manifest, owner_user_id="USR-001")
    path = tmp_path / "AGP-100" / "context-testability" / "traceability.json"
    assert path.is_file() and not path.with_suffix(".json.part").exists()
    assert storage.load(agent_project_id="AGP-100", owner_user_id="USR-001") == manifest
    with pytest.raises(Agent4TraceabilityStorageError, match="identity"):
        storage.load(agent_project_id="AGP-100", owner_user_id="USR-002")
    original = type(path).replace
    monkeypatch.setattr(type(path), "replace", lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("disk")))
    with pytest.raises(Agent4TraceabilityStorageError):
        storage.save(manifest, owner_user_id="USR-001")
    assert not path.with_suffix(".json.part").exists()
    monkeypatch.setattr(type(path), "replace", original)


def trace_service(context):
    root = context[3]
    return Agent4TraceabilityService(
        context[1]._workflow_service, Agent4WorkflowStorage(root), context[1]._sources,
        Agent4ChunkStorage(root), Agent4EffectiveStorage(root), Agent4SemanticStorage(root),
        Agent4TraceabilityStorage(root), clock=lambda: NOW,
    )


def completed_project(context):
    client, _, n2_executor, *_ = context
    project_id = create_project(client)
    add_text(client, project_id, "The system shall create a booking.")
    confirm(client, project_id)
    n2_executor.drain()
    n3, executor = n3_service(context, [0.1] * 14 + [0.99])
    n3.start(project_id, user())
    executor.drain()
    assert load(client, project_id)["n3_execution"]["status"] == "COMPLETED"
    return project_id


def test_service_requires_current_completed_n3_and_rejects_every_noncompleted_state(n2_context):
    project_id = completed_project(n2_context)
    service = trace_service(n2_context)
    record = service._workflows.load(agent_project_id=project_id, owner_user_id=user().user_id)
    for status in (
        Agent4N3ExecutionStatus.QUEUED, Agent4N3ExecutionStatus.RUNNING,
        Agent4N3ExecutionStatus.WAITING_FOR_HUMAN, Agent4N3ExecutionStatus.FAILED,
        Agent4N3ExecutionStatus.INTERRUPTED,
    ):
        changed = record.model_copy(deep=True)
        changed.n3_executions[-1].status = status
        service._workflows.save(changed)
        with pytest.raises(Agent4TraceabilityGateError, match="completed Testing Intelligence"):
            service.build(project_id, user())
    service._workflows.save(record)
    assert service.build(project_id, user()).n3_execution_id == record.current_n3_execution_id


def test_service_manifest_cache_force_and_all_upstream_evidence_are_immutable(n2_context):
    project_id = completed_project(n2_context)
    root, runs = n2_context[3], n2_context[5]
    service = trace_service(n2_context)
    upstream = {
        path: path.read_bytes() for path in (root / project_id).rglob("*")
        if path.is_file()
    }
    first = service.build(project_id, user())
    path = root / project_id / "context-testability" / "traceability.json"
    raw = path.read_bytes()
    cached = service.build(project_id, user())
    forced = service.build(project_id, user(), force=True)
    assert cached.built_at == first.built_at and raw == path.read_bytes()
    assert [item.node_id for item in forced.nodes] == [item.node_id for item in first.nodes]
    assert [item.traceability_link_id for item in forced.links] == [item.traceability_link_id for item in first.links]
    assert all(existing.read_bytes() == content for existing, content in upstream.items())
    workflow = load(n2_context[0], project_id)
    assert [item["status"] for item in workflow["nodes"]] == [
        "COMPLETED", "COMPLETED", "COMPLETED", "NOT_STARTED", "LOCKED", "LOCKED",
    ]
    assert workflow["current_node_id"] == "CONTEXT_TESTABILITY"
    assert workflow["pipeline_status"] == "RUNNING"
    assert runs.documents == {}
    names = [item.name.casefold() for item in (root / project_id).rglob("*") if item.is_file()]
    assert not any(marker in name for name in names for marker in (
        "readiness", "feasibility", "clarification", "test-case-plan", "generated-test",
    ))


def test_stale_effective_semantic_or_chunk_evidence_is_rejected(n2_context):
    project_id = completed_project(n2_context)
    service = trace_service(n2_context)
    source_id = service._sources.list_for_project(
        agent_project_id=project_id, owner_user_id=user().user_id
    )[0].source_id
    semantic_path = n2_context[3] / project_id / "intelligence" / f"{source_id}.semantic-facts.json"
    document = json.loads(semantic_path.read_text(encoding="utf-8"))
    document["effective_manifest_fingerprint"] = "0" * 64
    semantic_path.write_text(json.dumps(document), encoding="utf-8")
    with pytest.raises(Agent4TraceabilityGateError, match="stale"):
        service.build(project_id, user())


def test_corrupt_traceability_cache_rebuilds_without_touching_evidence(n2_context):
    project_id = completed_project(n2_context)
    service = trace_service(n2_context)
    first = service.build(project_id, user())
    path = n2_context[3] / project_id / "context-testability" / "traceability.json"
    path.write_text("{corrupt", encoding="utf-8")
    rebuilt = service.build(project_id, user())
    assert [item.node_id for item in rebuilt.nodes] == [item.node_id for item in first.nodes]
    assert [item.traceability_link_id for item in rebuilt.links] == [
        item.traceability_link_id for item in first.links
    ]
    assert json.loads(path.read_text(encoding="utf-8"))["schema_version"] == "1"
