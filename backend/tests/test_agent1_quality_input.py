from types import SimpleNamespace

import pytest

from app.modules.agents.requirements.contracts.schemas import RequirementSourceType
from app.modules.agents.requirements.discovery.contracts import (
    ClassificationScore, RequirementClassificationLabel,
    StructuredRequirementType,
)
from app.modules.agents.requirements.discovery.structuring import RequirementStructuringService
from app.modules.agents.requirements.infrastructure.artifact_paths import (
    RequirementArtifactKind,
    RequirementArtifactPaths,
)
from app.modules.agents.requirements.infrastructure.artifact_store import JsonArtifactStore
from app.modules.agents.requirements.processing.preparation.schemas import (
    MediaSegmentReference,
)
from app.modules.agents.requirements.quality.input import (
    QualityInputError,
    QualityInputErrorCode,
    QualityInputLoader,
)
from app.modules.agents.requirements.workflow.contracts.n3 import RequirementN3Status
from test_agent1_n3_orchestration import InputLoader, context, current


def quality_context(tmp_path, *, label=RequirementClassificationLabel.FUNCTIONAL,
                    text="The system must create accounts."):
    service, states, upstream_loader, _, storage, _ = context(
        tmp_path, label=label, text=text
    )
    service.start("AGP-020", "USR-001")
    loader = QualityInputLoader(states, InputLoader(upstream_loader.value), storage)
    return loader, states, storage, upstream_loader.value


def test_complete_current_n3_produces_deterministic_exact_functional_input(tmp_path):
    loader, _, _, _ = quality_context(tmp_path)
    first = loader.load(agent_project_id="AGP-020", owner_user_id="USR-001")
    second = loader.load(agent_project_id="AGP-020", owner_user_id="USR-001")
    assert first == second
    assert first.input_identity == second.input_identity
    assert len(first.requirements) == 1
    requirement = first.requirements[0]
    assert requirement.requirement_type is StructuredRequirementType.FUNCTIONAL
    assert requirement.statement == "The system must create accounts."
    assert requirement.candidate_id.startswith("RC-")
    assert requirement.chunk_id == "CHK-0123456789ABCDEF"
    assert requirement.source_id == "DOC-001"
    assert requirement.source_type.value == "DOCUMENT"
    assert requirement.provenance[0].page_numbers == [1]
    assert requirement.classification_confidence == 0.8
    assert requirement.classifier_configuration_fingerprint == first.classifier_configuration_fingerprint


@pytest.mark.parametrize("source_type,source_id", [
    (RequirementSourceType.AUDIO, "AUD-001"),
    (RequirementSourceType.VIDEO, "VID-001"),
])
def test_preserves_typed_media_source_and_provenance(tmp_path, source_type, source_id):
    loader, states, storage, upstream = quality_context(tmp_path)
    record, execution = current(states)
    candidates = storage.load_candidates("AGP-020", execution.execution_id)
    provenance = candidates.candidates[0].provenance[0].model_copy(update={
        "page_numbers": [],
        "media_segments": [MediaSegmentReference(
            segment_index=0, start_seconds=1.0, end_seconds=2.5,
            parent_start_offset=0, parent_end_offset=32,
        )],
    })
    candidate = candidates.candidates[0].model_copy(update={
        "source_id": source_id, "source_type": source_type,
        "provenance": (provenance,),
    })
    changed_candidates = candidates.model_copy(update={"candidates": (candidate,)})
    classifications = storage.load_classifications("AGP-020", execution.execution_id)
    changed_classifications = classifications.model_copy(update={
        "candidate_set": changed_candidates
    })
    changed_structured = RequirementStructuringService().structure(changed_classifications)
    paths = RequirementArtifactPaths(tmp_path)
    for kind in (RequirementArtifactKind.DISCOVERY_CANDIDATES,
                 RequirementArtifactKind.DISCOVERY_CLASSIFICATIONS,
                 RequirementArtifactKind.DISCOVERY_STRUCTURED):
        paths.for_execution("AGP-020", execution.execution_id, kind).unlink()
    candidate_digest = storage.save_candidates(
        "AGP-020", execution.execution_id, changed_candidates
    )
    classification_digest = storage.save_classifications(
        "AGP-020", execution.execution_id, changed_classifications
    )
    structured_digest = storage.save_structured_requirements(
        "AGP-020", execution.execution_id, changed_structured
    )
    execution.result_summary = execution.result_summary.model_copy(update={
        "candidate_artifact_digest": candidate_digest,
        "classification_artifact_digest": classification_digest,
        "structured_artifact_digest": structured_digest,
        "structured_set_identity": changed_structured.structured_set_identity,
    })
    states.save(record)
    validated_chunk = upstream.chunks[0].model_copy(update={
        "source_id": source_id, "source_type": source_type,
        "chunk": upstream.chunks[0].chunk.model_copy(update={
            "provenance": [provenance]
        }),
    })
    loader._discovery_inputs.value = upstream.model_copy(update={
        "chunks": (validated_chunk,)
    })
    requirement = loader.load(
        agent_project_id="AGP-020", owner_user_id="USR-001"
    ).requirements[0]
    assert requirement.source_id == source_id
    assert requirement.source_type is source_type
    assert requirement.provenance[0].media_segments[0].end_seconds == 2.5


def test_non_functional_is_included_and_other_is_excluded(tmp_path):
    nfr, *_ = quality_context(tmp_path / "nfr",
                              label=RequirementClassificationLabel.NON_FUNCTIONAL)
    assert nfr.load(agent_project_id="AGP-020", owner_user_id="USR-001").requirements[0].requirement_type is StructuredRequirementType.NON_FUNCTIONAL
    other, *_ = quality_context(tmp_path / "other",
                                label=RequirementClassificationLabel.OTHER)
    assert other.load(agent_project_id="AGP-020", owner_user_id="USR-001").requirements == ()


def test_zero_promoted_requirements_is_valid(tmp_path):
    loader, *_ = quality_context(tmp_path, text="Hello, thanks for meeting with us.")
    value = loader.load(agent_project_id="AGP-020", owner_user_id="USR-001")
    assert value.requirements == ()
    assert len(value.input_identity) == 64


def test_mixed_requirements_preserve_candidate_evidence_order(tmp_path):
    text = "The system must create accounts. The application should respond within three seconds."
    loader, states, storage, _ = quality_context(tmp_path, text=text)
    record, execution = current(states)
    classifications = storage.load_classifications("AGP-020", execution.execution_id)
    second = classifications.classifications[1]
    scores = tuple(ClassificationScore(
        label=label,
        score=0.8 if label is RequirementClassificationLabel.NON_FUNCTIONAL else 0.1,
    ) for label in RequirementClassificationLabel)
    changed_second = second.model_copy(update={
        "label": RequirementClassificationLabel.NON_FUNCTIONAL,
        "raw_winner": RequirementClassificationLabel.NON_FUNCTIONAL,
        "scores": scores,
    })
    changed_classifications = classifications.model_copy(update={
        "classifications": (classifications.classifications[0], changed_second)
    })
    changed_structured = RequirementStructuringService().structure(changed_classifications)
    paths = RequirementArtifactPaths(tmp_path)
    for kind in (RequirementArtifactKind.DISCOVERY_CLASSIFICATIONS,
                 RequirementArtifactKind.DISCOVERY_STRUCTURED):
        paths.for_execution("AGP-020", execution.execution_id, kind).unlink()
    classification_digest = storage.save_classifications(
        "AGP-020", execution.execution_id, changed_classifications
    )
    structured_digest = storage.save_structured_requirements(
        "AGP-020", execution.execution_id, changed_structured
    )
    execution.result_summary = execution.result_summary.model_copy(update={
        "functional_requirement_count": 1,
        "non_functional_requirement_count": 1,
        "classification_artifact_digest": classification_digest,
        "structured_artifact_digest": structured_digest,
        "structured_set_identity": changed_structured.structured_set_identity,
    })
    states.save(record)
    value = loader.load(agent_project_id="AGP-020", owner_user_id="USR-001")
    assert [item.candidate_id for item in value.requirements] == [
        item.candidate_id for item in changed_classifications.candidate_set.candidates
    ]
    assert [item.requirement_type for item in value.requirements] == [
        StructuredRequirementType.FUNCTIONAL,
        StructuredRequirementType.NON_FUNCTIONAL,
    ]


@pytest.mark.parametrize("status", [
    RequirementN3Status.QUEUED, RequirementN3Status.RUNNING,
    RequirementN3Status.FAILED, RequirementN3Status.BLOCKED,
])
def test_rejects_non_complete_n3(tmp_path, status):
    loader, states, *_ = quality_context(tmp_path)
    record, execution = current(states)
    execution.status = status
    states.save(record)
    with pytest.raises(QualityInputError) as error:
        loader.load(agent_project_id="AGP-020", owner_user_id="USR-001")
    assert error.value.code is QualityInputErrorCode.QUALITY_N3_NOT_COMPLETE


def test_rejects_missing_and_historical_non_current_n3(tmp_path):
    loader, states, *_ = quality_context(tmp_path)
    record, execution = current(states)
    record.current_n3_execution_id = None
    states.save(record)
    with pytest.raises(QualityInputError) as error:
        loader.load(agent_project_id="AGP-020", owner_user_id="USR-001")
    assert error.value.code is QualityInputErrorCode.QUALITY_INPUT_UNAVAILABLE
    assert execution.status is RequirementN3Status.COMPLETE


@pytest.mark.parametrize("field", ["n2_execution_id", "chunk_set_digest", "input_identity"])
def test_rejects_changed_authoritative_upstream(tmp_path, field):
    loader, _, _, upstream = quality_context(tmp_path)
    if field == "n2_execution_id":
        reference = upstream.reference.model_copy(update={field: "N2-BBBBBBBBBBBBBBBB-001"})
        changed = upstream.model_copy(update={"reference": reference})
    elif field == "chunk_set_digest":
        reference = upstream.reference.model_copy(update={field: "9" * 64})
        changed = upstream.model_copy(update={"reference": reference})
    else:
        changed = upstream.model_copy(update={field: "9" * 64})
    loader._discovery_inputs.value = changed
    with pytest.raises(QualityInputError) as error:
        loader.load(agent_project_id="AGP-020", owner_user_id="USR-001")
    assert error.value.code is QualityInputErrorCode.QUALITY_INPUT_STALE


@pytest.mark.parametrize("kind", [
    RequirementArtifactKind.DISCOVERY_CANDIDATES,
    RequirementArtifactKind.DISCOVERY_CLASSIFICATIONS,
    RequirementArtifactKind.DISCOVERY_STRUCTURED,
])
def test_rejects_missing_artifact(tmp_path, kind):
    loader, states, *_ = quality_context(tmp_path)
    execution = current(states)[1]
    JsonArtifactStore(tmp_path).remove(agent_project_id="AGP-020",
                                       execution_id=execution.execution_id, kind=kind)
    with pytest.raises(QualityInputError) as error:
        loader.load(agent_project_id="AGP-020", owner_user_id="USR-001")
    assert error.value.code is QualityInputErrorCode.QUALITY_ARTIFACT_UNAVAILABLE


def test_rejects_malformed_artifact_without_exposing_path(tmp_path):
    loader, states, *_ = quality_context(tmp_path)
    execution = current(states)[1]
    path = RequirementArtifactPaths(tmp_path).for_execution(
        "AGP-020", execution.execution_id, RequirementArtifactKind.DISCOVERY_STRUCTURED
    )
    path.write_text("{bad", encoding="utf-8")
    with pytest.raises(QualityInputError) as error:
        loader.load(agent_project_id="AGP-020", owner_user_id="USR-001")
    assert error.value.code is QualityInputErrorCode.QUALITY_ARTIFACT_UNAVAILABLE
    assert str(tmp_path) not in str(error.value)


@pytest.mark.parametrize("artifact_name,summary_field", [
    ("load_candidates", "candidate_artifact_digest"),
    ("load_classifications", "classification_artifact_digest"),
    ("load_structured_requirements", "structured_artifact_digest"),
])
def test_rejects_each_artifact_digest_mismatch(tmp_path, artifact_name, summary_field):
    loader, states, *_ = quality_context(tmp_path)
    record, execution = current(states)
    execution.result_summary = execution.result_summary.model_copy(
        update={summary_field: "0" * 64}
    )
    states.save(record)
    with pytest.raises(QualityInputError) as error:
        loader.load(agent_project_id="AGP-020", owner_user_id="USR-001")
    assert error.value.code is QualityInputErrorCode.QUALITY_ARTIFACT_DIGEST_MISMATCH


def test_rejects_disconnected_candidate_traceability_even_with_matching_digest(tmp_path):
    loader, states, storage, _ = quality_context(tmp_path)
    record, execution = current(states)
    structured = storage.load_structured_requirements("AGP-020", execution.execution_id)
    requirement = structured.functional_requirements[0]
    changed_requirement = requirement.model_copy(update={"candidate_id": "RC-FFFFFFFFFFFFFFFF"})
    changed = structured.model_copy(update={"functional_requirements": (changed_requirement,)})
    path = RequirementArtifactPaths(tmp_path).for_execution(
        "AGP-020", execution.execution_id, RequirementArtifactKind.DISCOVERY_STRUCTURED
    )
    # The test fixture deliberately simulates a storage-level replacement; production storage is immutable.
    path.unlink()
    digest = storage.save_structured_requirements("AGP-020", execution.execution_id, changed)
    execution.result_summary = execution.result_summary.model_copy(
        update={"structured_artifact_digest": digest}
    )
    states.save(record)
    with pytest.raises(QualityInputError) as error:
        loader.load(agent_project_id="AGP-020", owner_user_id="USR-001")
    assert error.value.code in {
        QualityInputErrorCode.QUALITY_INPUT_IDENTITY_INVALID,
        QualityInputErrorCode.QUALITY_TRACEABILITY_INVALID,
    }


def test_boundary_needs_no_raw_upload_file(tmp_path):
    loader, *_ = quality_context(tmp_path)
    assert loader.load(agent_project_id="AGP-020", owner_user_id="USR-001")
    assert not list(tmp_path.rglob("*.pdf"))
    assert not list(tmp_path.rglob("*.wav"))
    assert not list(tmp_path.rglob("*.mp4"))
