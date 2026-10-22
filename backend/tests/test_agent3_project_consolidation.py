from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from app.common.status import AgentType
from app.modules.agents.implementation.contracts.enums import (
    ImplementationArtifactType,
    ImplementationInputSourceType,
)
from app.modules.agents.implementation.preparation.consolidation.constants import (
    ConflictAction,
    ConsolidationSourceKind,
    ConsolidationStatus,
)
from app.modules.agents.implementation.preparation.consolidation.schemas import (
    ConflictDecisionRequest,
    ConsolidationInput,
    ProjectSourceRef,
)
from app.modules.agents.implementation.preparation.consolidation.service import (
    ConflictNotFoundError,
    ConsolidationNotFoundError,
    InvalidConflictDecisionError,
    ProjectConsolidationService,
    StaleConflictDecisionError,
    consolidate_inputs,
    explicit_relationships,
)
from app.modules.agents.implementation.preparation.consolidation.storage import (
    ConsolidationStorage,
    ConsolidationStorageError,
)
from app.modules.agents.implementation.preparation.orchestration.constants import (
    ProjectPreparationStatus,
    SourcePreparationStatus,
)
from app.modules.agents.implementation.preparation.orchestration.schemas import (
    PersistedPreparationSource,
    ProjectPreparationRecord,
)
from app.modules.agents.implementation.preparation.orchestration.storage import (
    ProjectPreparationStorage,
)
from app.modules.agents.implementation.preparation.schemas import (
    ArtifactDetectionLabel,
)


NOW = datetime(2026, 10, 19, tzinfo=timezone.utc)


def source(source_id, label=None, fingerprint=None):
    return ProjectSourceRef(
        source_id=source_id,
        source_kind=ConsolidationSourceKind.UPLOAD,
        label=label or f"{source_id}.pdf",
        source_fingerprint=fingerprint or source_id[-1].lower() * 64,
        final_artifact_id=f"FTA-{source_id[-1].upper() * 24}",
        canonical_artifact_id=f"CA-{source_id[-1].upper() * 24}",
        chunk_ids=[f"CHK-{source_id[-1].upper() * 20}"],
        evidence_refs=[{
            "upload_id": source_id,
            "original_filename": label or f"{source_id}.pdf",
        }],
        field_provenance=[{"field_path": "requirements[0].statement"}],
    )


def item(source_id, artifact_type, data, label=None):
    ref = source(source_id, label)
    return ConsolidationInput(
        source=ref,
        artifact_type=artifact_type,
        data=data,
        source_artifact_id=ref.final_artifact_id,
    )


def test_multiple_trusted_sources_deduplicate_identical_facts_and_keep_support():
    inputs = [
        item("UP-A", ArtifactDetectionLabel.FUNCTIONAL_REQUIREMENTS,
             {"requirements": [{"id": "FR-1", "statement": "Create booking"}]}),
        item("UP-B", ArtifactDetectionLabel.FUNCTIONAL_REQUIREMENTS,
             {"requirements": [{"id": "FR-1", "statement": "Create booking"}]}),
    ]
    items, conflicts, removed = consolidate_inputs(inputs)
    assert len(items) == 1
    assert removed == 1
    assert conflicts == []
    assert {ref.source_id for ref in items[0].supporting_sources} == {"UP-A", "UP-B"}


def test_similar_but_non_identical_facts_are_not_automatically_merged():
    inputs = [
        item("UP-A", ArtifactDetectionLabel.FUNCTIONAL_REQUIREMENTS,
             {"requirements": [{"statement": "User creates a booking"}]}),
        item("UP-B", ArtifactDetectionLabel.FUNCTIONAL_REQUIREMENTS,
             {"requirements": [{"statement": "Admin creates bookings"}]}),
    ]
    items, _, removed = consolidate_inputs(inputs)
    assert len(items) == 2
    assert removed == 0


def test_exact_text_is_not_deduplicated_across_artifact_categories():
    statement = "Booking can be cancelled."
    items, _, removed = consolidate_inputs([
        item("UP-A", ArtifactDetectionLabel.FUNCTIONAL_REQUIREMENTS,
             {"requirements": [{"statement": statement}]}),
        item("UP-B", ArtifactDetectionLabel.ACCEPTANCE_CRITERIA,
             {"criteria": [{"statement": statement}]}),
    ])
    assert len(items) == 2
    assert removed == 0
    assert {value.artifact_type for value in items} == {
        ArtifactDetectionLabel.FUNCTIONAL_REQUIREMENTS,
        ArtifactDetectionLabel.ACCEPTANCE_CRITERIA,
    }


@pytest.mark.parametrize(
    ("artifact_type", "first", "second", "conflict_type"),
    [
        (ArtifactDetectionLabel.TECHNOLOGY_STACK,
         {"database": ["MySQL"]}, {"database": ["PostgreSQL"]},
         "TECHNOLOGY_SELECTION"),
        (ArtifactDetectionLabel.API_SPECIFICATION,
         {"endpoints": [{"id": "create-booking", "method": "POST", "path": "/bookings"}]},
         {"endpoints": [{"id": "create-booking", "method": "PUT", "path": "/bookings"}]},
         "EXPLICIT_ID_MISMATCH"),
    ],
)
def test_deterministic_cross_source_conflicts(artifact_type, first, second, conflict_type):
    _, conflicts, _ = consolidate_inputs([
        item("UP-A", artifact_type, first), item("UP-B", artifact_type, second),
    ])
    assert len(conflicts) == 1
    assert conflicts[0].conflict_type == conflict_type
    assert len(conflicts[0].candidates) == 2
    assert all(candidate.supporting_sources for candidate in conflicts[0].candidates)


def test_database_field_type_conflict_is_detected_by_entity_and_field():
    _, conflicts, _ = consolidate_inputs([
        item("UP-A", ArtifactDetectionLabel.DATABASE_SCHEMA,
             {"entities": [{"name": "Booking", "fields": [{"name": "status", "type": "VARCHAR"}]}]}),
        item("UP-B", ArtifactDetectionLabel.DATABASE_SCHEMA,
             {"entities": [{"name": "Booking", "fields": [{"name": "status", "type": "INTEGER"}]}]}),
    ])
    assert conflicts[0].conflict_type == "DATABASE_FIELD_TYPE"


def test_nonexclusive_technology_and_unidentified_api_do_not_create_conflicts():
    _, conflicts, _ = consolidate_inputs([
        item("UP-A", ArtifactDetectionLabel.TECHNOLOGY_STACK,
             {"languages": ["Python"]}),
        item("UP-B", ArtifactDetectionLabel.TECHNOLOGY_STACK,
             {"languages": ["TypeScript"]}),
        item("UP-C", ArtifactDetectionLabel.API_SPECIFICATION,
             {"endpoints": [{"method": "POST", "path": "/bookings"}]}),
        item("UP-D", ArtifactDetectionLabel.API_SPECIFICATION,
             {"endpoints": [{"method": "PUT", "path": "/bookings"}]}),
    ])
    assert conflicts == []


def test_traceability_and_explicit_relationships_are_preserved():
    items, _, _ = consolidate_inputs([
        item("UP-A", ArtifactDetectionLabel.FUNCTIONAL_REQUIREMENTS,
             {"requirements": [{"id": "FR-001", "statement": "Create booking"}]}),
        item("UP-B", ArtifactDetectionLabel.ACCEPTANCE_CRITERIA,
             {"criteria": [{"id": "AC-1", "statement": "FR-001 succeeds"}]}),
    ])
    assert items[0].supporting_sources[0].chunk_ids
    assert items[0].supporting_sources[0].evidence_refs
    assert items[0].supporting_sources[0].field_provenance
    ref = items[0].supporting_sources[0]
    assert ref.final_artifact_id.startswith("FTA-")
    assert ref.canonical_artifact_id.startswith("CA-")
    assert ref.chunk_ids[0].startswith("CHK-")
    assert ref.evidence_refs[0]["upload_id"] == ref.source_id
    relationships = explicit_relationships(items)
    assert len(relationships) == 1
    assert relationships[0].relationship_type == "EXPLICIT_ID_REFERENCE"


class FakeStandalone:
    def require_active_project(self, owner_id, project_id):
        return SimpleNamespace(
            agent_project_id=project_id, agent_type=AgentType.IMPLEMENTATION
        )


class FakeUploads:
    uploads = []

    def list_for_project(self, **_):
        return self.uploads


class NoUploadArtifacts:
    def get_final(self, *_):
        raise AssertionError("manual text must not use upload artifacts")


def upload(upload_id, suffix):
    return SimpleNamespace(
        upload_id=upload_id,
        source_type=ImplementationInputSourceType.DOCUMENT,
        sha256=suffix.lower() * 64,
    )


def trusted_document(upload_id, suffix, version=1):
    source_ref = SimpleNamespace(
        chunk_id=f"CHK-{suffix * 20}",
        model_dump=lambda **_: {
            "upload_id": upload_id,
            "chunk_id": f"CHK-{suffix * 20}",
            "original_filename": f"{suffix}.pdf",
        },
    )
    provenance = SimpleNamespace(
        model_dump=lambda **_: {"field_path": "requirements[0].statement"}
    )
    artifact = SimpleNamespace(
        final_artifact_id=f"FTA-{suffix * 24}",
        canonical_artifact_id=f"CA-{suffix * 24}",
        artifact_type=ArtifactDetectionLabel.FUNCTIONAL_REQUIREMENTS,
        data={"requirements": [{"id": f"FR-{suffix}", "statement": f"Requirement {suffix}"}]},
        source_refs=[source_ref],
        field_provenance=[provenance],
    )
    return SimpleNamespace(
        original_filename=f"{suffix}.pdf",
        artifacts=[artifact],
        model_dump=lambda **_: {"upload_id": upload_id, "version": version},
    )


class MutableUploads:
    def __init__(self, uploads):
        self.uploads = uploads

    def list_for_project(self, **_):
        return self.uploads


class MutableTrustedArtifacts:
    def __init__(self, values):
        self.values = values

    def get_final(self, _project_id, upload_id, _user):
        return self.values[upload_id]


def upload_service(tmp_path, uploads, artifacts):
    upload_store = MutableUploads(uploads)
    reviews = MutableTrustedArtifacts(artifacts)
    service = ProjectConsolidationService(
        FakeStandalone(), upload_store, ProjectPreparationStorage(tmp_path),
        reviews, ConsolidationStorage(tmp_path), clock=lambda: NOW,
    )
    return service, upload_store, reviews, SimpleNamespace(user_id="USR-001")


def build_service(
    tmp_path, text="Use MySQL", status=SourcePreparationStatus.READY,
    declared_type=ImplementationArtifactType.TECHNICAL_CONSTRAINTS,
):
    preparation = ProjectPreparationStorage(tmp_path)
    preparation.save(ProjectPreparationRecord(
        agent_project_id="AGP-003",
        owner_user_id="USR-001",
        status=ProjectPreparationStatus.ANALYSIS_READY,
        sources=[PersistedPreparationSource(
            source_id="LOCAL-notes",
            source_kind=ImplementationInputSourceType.TEXT,
            artifact_type=declared_type,
            label="Architecture notes",
            status=status,
            text_content=text,
        )],
        started_at=NOW,
        updated_at=NOW,
    ))
    storage = ConsolidationStorage(tmp_path)
    service = ProjectConsolidationService(
        FakeStandalone(), FakeUploads(), preparation, NoUploadArtifacts(),
        storage, clock=lambda: NOW,
    )
    return service, preparation, storage, SimpleNamespace(user_id="USR-001")


def confirm_text_category(service, user, category):
    conflict = next(
        value for value in service.get_conflicts("AGP-003", user)
        if value.conflict_type == "TEXT_ARTIFACT_TYPE_CONFIRMATION"
    )
    candidate = next(
        value for value in conflict.candidates
        if value.value["artifact_type"] == category.value
    )
    service.decide("AGP-003", conflict.conflict_id, ConflictDecisionRequest(
        expected_fingerprint=conflict.fingerprint,
        action=ConflictAction.SELECT_CANDIDATE,
        candidate_id=candidate.candidate_id,
    ), user)
    return conflict, candidate


def test_declared_text_type_is_only_hint_and_verified_text_keeps_local_identity(tmp_path):
    service, preparation, _, user = build_service(
        tmp_path,
        text="Customers can cancel a booking.",
        declared_type=ImplementationArtifactType.API_SPECIFICATION,
    )
    result = service.start("AGP-003", user)
    assert result.status is ConsolidationStatus.WAITING_FOR_HUMAN
    with pytest.raises(ConsolidationNotFoundError):
        service.get_final("AGP-003", user)
    conflict, _ = confirm_text_category(
        service, user, ArtifactDetectionLabel.FUNCTIONAL_REQUIREMENTS
    )
    assert conflict.allowed_actions == [ConflictAction.SELECT_CANDIDATE]
    final = service.get_final("AGP-003", user)
    assert ArtifactDetectionLabel.API_SPECIFICATION not in final.categories
    assert ArtifactDetectionLabel.FUNCTIONAL_REQUIREMENTS in final.categories
    refs = next(iter(final.traceability.values()))
    assert refs[0].source_id == "LOCAL-notes"
    assert refs[0].source_kind is ConsolidationSourceKind.TEXT
    assert refs[0].final_artifact_id is None
    assert refs[0].declared_artifact_type == "API_SPECIFICATION"

    # Changing source content invalidates the verified category and final spec.
    record = preparation.load(
        agent_project_id="AGP-003", owner_user_id="USR-001"
    )
    record.sources[0].text_content = "Use PostgreSQL"
    preparation.save(record)
    assert service.get_status("AGP-003", user).status is ConsolidationStatus.STALE


def test_manual_text_decision_request_cannot_inject_category_or_fact(tmp_path):
    service, _, _, user = build_service(tmp_path)
    service.start("AGP-003", user)
    conflict = service.get_conflicts("AGP-003", user)[0]
    with pytest.raises(InvalidConflictDecisionError):
        service.decide("AGP-003", conflict.conflict_id,
                       ConflictDecisionRequest(
                           expected_fingerprint=conflict.fingerprint,
                           action=ConflictAction.KEEP_BOTH,
                       ), user)
    with pytest.raises(ValueError):
        ConflictDecisionRequest.model_validate({
            "expected_fingerprint": conflict.fingerprint,
            "action": "SELECT_CANDIDATE",
            "candidate_id": conflict.candidates[0].candidate_id,
            "artifact_type": "API_SPECIFICATION",
            "replacement": {"path": "/injected"},
        })


def test_untrusted_source_prevents_complete_project_specification(tmp_path):
    service, _, _, user = build_service(
        tmp_path, status=SourcePreparationStatus.FAILED
    )
    result = service.start("AGP-003", user)
    assert result.status is ConsolidationStatus.FAILED
    assert result.issues[0].error_code == "TRUSTED_TEXT_REQUIRED"


def test_source_addition_and_deletion_invalidate_without_mutating_trusted_inputs(tmp_path):
    up_a, up_b = upload("A3UP-" + "a" * 32, "A"), upload("A3UP-" + "b" * 32, "B")
    final_a = trusted_document(up_a.upload_id, "A")
    final_b = trusted_document(up_b.upload_id, "B")
    service, uploads, reviews, user = upload_service(
        tmp_path, [up_a], {up_a.upload_id: final_a, up_b.upload_id: final_b}
    )
    original = final_a.artifacts[0].data.copy()
    assert service.start("AGP-003", user).status is ConsolidationStatus.READY
    uploads.uploads.append(up_b)
    assert service.get_status("AGP-003", user).status is ConsolidationStatus.STALE
    service.start("AGP-003", user)
    uploads.uploads.remove(up_a)
    assert service.get_status("AGP-003", user).status is ConsolidationStatus.STALE
    assert final_a.artifacts[0].data == original


def test_semantic_decision_change_invalidates_source_set_digest(tmp_path):
    up_a = upload("A3UP-" + "a" * 32, "A")
    final_a = trusted_document(up_a.upload_id, "A", version=1)
    service, _, reviews, user = upload_service(
        tmp_path, [up_a], {up_a.upload_id: final_a}
    )
    assert service.start("AGP-003", user).status is ConsolidationStatus.READY
    reviews.values[up_a.upload_id] = trusted_document(
        up_a.upload_id, "A", version=2
    )
    assert service.get_status("AGP-003", user).status is ConsolidationStatus.STALE


def conflict_service(tmp_path):
    service, _, storage, user = build_service(tmp_path)
    inputs = [
        item("UP-A", ArtifactDetectionLabel.TECHNOLOGY_STACK,
             {"database": ["MySQL"]}),
        item("UP-B", ArtifactDetectionLabel.TECHNOLOGY_STACK,
             {"database": ["PostgreSQL"]}),
    ]
    items, conflicts, removed = consolidate_inputs(inputs)
    service._discover = lambda *_: (inputs, [i.source for i in inputs], [], "a" * 64)
    service.start("AGP-003", user)
    return service, storage, user, conflicts[0]


@pytest.mark.parametrize("action", [
    ConflictAction.KEEP_BOTH, ConflictAction.MARK_NOT_CONFLICTING,
])
def test_non_destructive_human_decisions_keep_both_candidates(tmp_path, action):
    service, _, user, conflict = conflict_service(tmp_path)
    service.decide("AGP-003", conflict.conflict_id, ConflictDecisionRequest(
        expected_fingerprint=conflict.fingerprint, action=action,
    ), user)
    final = service.get_final("AGP-003", user)
    assert len(final.categories[ArtifactDetectionLabel.TECHNOLOGY_STACK]) == 2


def test_selection_accepts_only_current_stored_candidate_and_fingerprint(tmp_path):
    service, _, user, conflict = conflict_service(tmp_path)
    with pytest.raises(InvalidConflictDecisionError):
        service.decide("AGP-003", conflict.conflict_id, ConflictDecisionRequest(
            expected_fingerprint=conflict.fingerprint,
            action=ConflictAction.SELECT_CANDIDATE,
            candidate_id="PCC-000000000000000000000000",
        ), user)
    with pytest.raises(StaleConflictDecisionError):
        service.decide("AGP-003", conflict.conflict_id, ConflictDecisionRequest(
            expected_fingerprint="0" * 64,
            action=ConflictAction.SELECT_CANDIDATE,
            candidate_id=conflict.candidates[0].candidate_id,
        ), user)
    service.decide("AGP-003", conflict.conflict_id, ConflictDecisionRequest(
        expected_fingerprint=conflict.fingerprint,
        action=ConflictAction.SELECT_CANDIDATE,
        candidate_id=conflict.candidates[0].candidate_id,
    ), user)
    final = service.get_final("AGP-003", user)
    assert len(final.categories[ArtifactDetectionLabel.TECHNOLOGY_STACK]) == 1


def test_exclude_candidate_and_unknown_conflict_security(tmp_path):
    service, _, user, conflict = conflict_service(tmp_path)
    with pytest.raises(ConflictNotFoundError):
        service.decide("AGP-003", "PCF-000000000000000000000000",
                       ConflictDecisionRequest(
                           expected_fingerprint=conflict.fingerprint,
                           action=ConflictAction.KEEP_BOTH,
                       ), user)
    service.decide("AGP-003", conflict.conflict_id, ConflictDecisionRequest(
        expected_fingerprint=conflict.fingerprint,
        action=ConflictAction.EXCLUDE_CANDIDATE,
        candidate_id=conflict.candidates[0].candidate_id,
    ), user)
    final = service.get_final("AGP-003", user)
    assert len(final.categories[ArtifactDetectionLabel.TECHNOLOGY_STACK]) == 1


def test_order_independent_ids_digests_and_decision_reuse_after_restart(tmp_path):
    inputs = [
        item("UP-A", ArtifactDetectionLabel.TECHNOLOGY_STACK,
             {"database": ["MySQL"]}),
        item("UP-B", ArtifactDetectionLabel.TECHNOLOGY_STACK,
             {"database": ["PostgreSQL"]}),
    ]
    service, _, storage, user = build_service(tmp_path)
    service._discover = lambda *_: (
        inputs, [value.source for value in inputs], [], "d" * 64
    )
    first_status = service.start("AGP-003", user)
    first_record = storage.load_state("AGP-003", user.user_id)
    first_conflict = first_record.conflicts[0]
    service.decide("AGP-003", first_conflict.conflict_id,
                   ConflictDecisionRequest(
                       expected_fingerprint=first_conflict.fingerprint,
                       action=ConflictAction.SELECT_CANDIDATE,
                       candidate_id=first_conflict.candidates[0].candidate_id,
                   ), user)
    first_final = service.get_final("AGP-003", user)

    restarted, _, _, _ = build_service(tmp_path)
    reversed_inputs = list(reversed(inputs))
    restarted._discover = lambda *_: (
        reversed_inputs, [value.source for value in reversed_inputs], [],
        "d" * 64,
    )
    second_status = restarted.start("AGP-003", user)
    second_record = storage.load_state("AGP-003", user.user_id)
    second_conflict = second_record.conflicts[0]
    second_final = restarted.get_final("AGP-003", user)

    assert first_status.source_set_digest == second_status.source_set_digest
    assert [value.project_item_id for value in first_record.items] == [
        value.project_item_id for value in second_record.items
    ]
    assert first_conflict.conflict_id == second_conflict.conflict_id
    assert first_conflict.fingerprint == second_conflict.fingerprint
    assert [value.candidate_id for value in first_conflict.candidates] == [
        value.candidate_id for value in second_conflict.candidates
    ]
    assert second_conflict.action is ConflictAction.SELECT_CANDIDATE
    assert first_final.project_specification_id == second_final.project_specification_id


def test_source_discovery_order_does_not_change_digest_items_or_project_id(tmp_path):
    up_a = upload("A3UP-" + "a" * 32, "A")
    up_b = upload("A3UP-" + "b" * 32, "B")
    service, uploads, _, user = upload_service(tmp_path, [up_a, up_b], {
        up_a.upload_id: trusted_document(up_a.upload_id, "A"),
        up_b.upload_id: trusted_document(up_b.upload_id, "B"),
    })
    first_status = service.start("AGP-003", user)
    first_record = service._storage.load_state("AGP-003", user.user_id)
    first_final = service.get_final("AGP-003", user)
    uploads.uploads.reverse()
    second_status = service.start("AGP-003", user)
    second_record = service._storage.load_state("AGP-003", user.user_id)
    second_final = service.get_final("AGP-003", user)
    assert first_status.source_set_digest == second_status.source_set_digest
    assert [value.project_item_id for value in first_record.items] == [
        value.project_item_id for value in second_record.items
    ]
    assert first_final.project_specification_id == second_final.project_specification_id


@pytest.mark.parametrize("state", [
    ConsolidationStatus.NOT_STARTED,
    ConsolidationStatus.CONSOLIDATING,
    ConsolidationStatus.WAITING_FOR_HUMAN,
    ConsolidationStatus.PARTIAL_FAILURE,
    ConsolidationStatus.FAILED,
    ConsolidationStatus.STALE,
])
def test_final_trust_gate_rejects_every_non_ready_state(tmp_path, state):
    up_a = upload("A3UP-" + "a" * 32, "A")
    service, _, _, user = upload_service(
        tmp_path, [up_a], {up_a.upload_id: trusted_document(up_a.upload_id, "A")}
    )
    service.start("AGP-003", user)
    record = service._storage.load_state("AGP-003", user.user_id)
    record.status = state
    service._storage.save_state(record)
    with pytest.raises(ConsolidationNotFoundError):
        service.get_final("AGP-003", user)


def test_final_trust_gate_returns_current_ready_specification(tmp_path):
    up_a = upload("A3UP-" + "a" * 32, "A")
    service, _, _, user = upload_service(
        tmp_path, [up_a], {up_a.upload_id: trusted_document(up_a.upload_id, "A")}
    )
    service.start("AGP-003", user)
    assert service.get_final("AGP-003", user).status is ConsolidationStatus.READY


def test_atomic_storage_ignores_orphan_part_and_rejects_malformed_state(tmp_path):
    storage = ConsolidationStorage(tmp_path)
    directory = tmp_path / "AGP-003"
    directory.mkdir()
    (directory / "project-consolidation.json.part").write_text(
        "{malformed", encoding="utf-8"
    )
    assert storage.load_state("AGP-003", "USR-001") is None
    (directory / "project-consolidation.json").write_text(
        "{malformed", encoding="utf-8"
    )
    with pytest.raises(ConsolidationStorageError):
        storage.load_state("AGP-003", "USR-001")


def test_malformed_final_sidecar_is_never_returned_as_trusted(tmp_path):
    up_a = upload("A3UP-" + "a" * 32, "A")
    service, _, _, user = upload_service(
        tmp_path, [up_a], {up_a.upload_id: trusted_document(up_a.upload_id, "A")}
    )
    service.start("AGP-003", user)
    path = tmp_path / "AGP-003" / "trusted-project-specification.json"
    path.write_text("{malformed", encoding="utf-8")
    with pytest.raises(ConsolidationStorageError):
        service.get_final("AGP-003", user)
