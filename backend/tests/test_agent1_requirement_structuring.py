import pytest

from app.modules.agents.requirements.contracts.schemas import RequirementSourceType
from app.modules.agents.requirements.discovery.candidate_detection import CANDIDATE_CONTRACT_VERSION
from app.modules.agents.requirements.discovery.classification.transformer import (
    HYPOTHESIS_TEMPLATE,
    LABEL_DESCRIPTIONS,
)
from app.modules.agents.requirements.discovery.contracts import (
    CandidateDiscoverySignal,
    ClassificationPolicyReason,
    ClassificationScore,
    ClassifierModelIdentity,
    RequirementCandidate,
    RequirementCandidateSet,
    RequirementClassification,
    RequirementClassificationLabel,
    RequirementClassificationSet,
)
from app.modules.agents.requirements.discovery.structuring import (
    RequirementStructuringError,
    RequirementStructuringService,
)
from app.modules.agents.requirements.infrastructure.digests import stable_json_sha256
from app.modules.agents.requirements.processing.preparation.schemas import (
    MediaSegmentReference,
    NormalizedProvenanceSpan,
)


PROJECT = "AGP-020"
N2_EXECUTION = "N2-AAAAAAAAAAAAAAAA-001"
CHUNK_DIGEST = "d" * 64
INPUT_IDENTITY = "e" * 64


def provenance(source_type, length, index):
    values = {
        "normalized_start_offset": 0,
        "normalized_end_offset": length,
        "parent_start_offset": 10,
        "parent_end_offset": 10 + length,
    }
    if source_type is RequirementSourceType.DOCUMENT:
        values["page_numbers"] = [index]
    else:
        values["media_segments"] = [MediaSegmentReference(
            segment_index=index,
            start_seconds=float(index),
            end_seconds=float(index + 1),
            parent_start_offset=10,
            parent_end_offset=10 + length,
        )]
    return NormalizedProvenanceSpan(**values)


def candidate(index, text, source_type=RequirementSourceType.DOCUMENT, *, project=PROJECT):
    prefix = {
        RequirementSourceType.DOCUMENT: "DOC",
        RequirementSourceType.AUDIO: "AUD",
        RequirementSourceType.VIDEO: "VID",
    }[source_type]
    chunk_id = f"CHK-{index:016X}"
    identity = stable_json_sha256({
        "agent_project_id": project,
        "candidate_contract_version": CANDIDATE_CONTRACT_VERSION,
        "discovery_input_identity": INPUT_IDENTITY,
        "chunk_id": chunk_id,
        "span": [0, len(text)],
        "text": text,
    })
    return RequirementCandidate(
        candidate_id=f"RC-{identity[:16].upper()}",
        candidate_identity=identity,
        agent_project_id=project,
        n2_execution_id=N2_EXECUTION,
        chunk_set_digest=CHUNK_DIGEST,
        chunk_id=chunk_id,
        source_id=f"{prefix}-{index:03d}",
        source_type=source_type,
        text=text,
        start_offset=0,
        end_offset=len(text),
        discovery_signals=(CandidateDiscoverySignal.MODAL_MUST,),
        provenance=(provenance(source_type, len(text), index),),
    )


def model_identity():
    values = {
        "provider_type": "FAKE",
        "provider_version": "1.0",
        "model_id": "fake/model",
        "requested_revision": "revision-1",
        "resolved_revision": "revision-1",
        "task": "zero-shot-classification",
        "label_descriptions": {
            label.value: description for label, description in LABEL_DESCRIPTIONS.items()
        },
        "hypothesis_template": HYPOTHESIS_TEMPLATE,
        "minimum_confidence": 0.5,
        "minimum_margin": 0.1,
        "device": "cpu",
        "batch_size": 4,
        "local_files_only": True,
    }
    return ClassifierModelIdentity(
        **values,
        configuration_fingerprint=stable_json_sha256(values),
    )


def classification(item, label, confidence=0.8, *, reason=None):
    raw_winner = (
        RequirementClassificationLabel.FUNCTIONAL
        if reason is not None else label
    )
    values = {member: 0.05 for member in RequirementClassificationLabel}
    values[raw_winner] = confidence
    return RequirementClassification(
        candidate_id=item.candidate_id,
        candidate_identity=item.candidate_identity,
        label=label,
        confidence=confidence,
        scores=tuple(
            ClassificationScore(label=member, score=values[member])
            for member in RequirementClassificationLabel
        ),
        raw_winner=raw_winner,
        policy_reason=reason,
    )


def classification_set(items, labels):
    candidates = RequirementCandidateSet(
        contract_version="1",
        agent_project_id=PROJECT,
        n2_execution_id=N2_EXECUTION,
        chunk_set_digest=CHUNK_DIGEST,
        discovery_input_identity=INPUT_IDENTITY,
        candidates=tuple(items),
    )
    return RequirementClassificationSet(
        candidate_set=candidates,
        model=model_identity(),
        classifications=tuple(
            classification(item, label)
            for item, label in zip(items, labels, strict=True)
        ),
    )


def test_functional_and_non_functional_promotions_preserve_statement_and_confidence():
    functional = candidate(1, "The system must allow users to create an account.")
    non_functional = candidate(2, "The page should respond within three seconds.")
    result = RequirementStructuringService().structure(classification_set(
        [functional, non_functional],
        [RequirementClassificationLabel.FUNCTIONAL, RequirementClassificationLabel.NON_FUNCTIONAL],
    ))
    assert [item.statement for item in result.functional_requirements] == [functional.text]
    assert [item.statement for item in result.non_functional_requirements] == [non_functional.text]
    assert result.functional_requirements[0].requirement_id.startswith("FR-")
    assert result.non_functional_requirements[0].requirement_id.startswith("NFR-")
    assert result.functional_requirements[0].classification_confidence == 0.8
    assert result.functional_requirements[0].classifier_configuration_fingerprint == model_identity().configuration_fingerprint


def test_other_is_excluded_and_policy_reason_is_auditable():
    item = candidate(1, "The project was discussed during Monday's meeting.")
    values = classification_set([item], [RequirementClassificationLabel.OTHER])
    values = values.model_copy(update={"classifications": (
        classification(item, RequirementClassificationLabel.OTHER, 0.4,
                       reason=ClassificationPolicyReason.LOW_CONFIDENCE),
    )})
    result = RequirementStructuringService().structure(values)
    assert result.functional_requirements == ()
    assert result.non_functional_requirements == ()
    assert result.excluded_candidates[0].candidate_id == item.candidate_id
    assert result.excluded_candidates[0].policy_reason is ClassificationPolicyReason.LOW_CONFIDENCE


def test_mixed_output_preserves_relative_fr_nfr_and_excluded_order():
    items = [candidate(index, f"Exact statement number {index} must remain unchanged.") for index in range(1, 6)]
    labels = [
        RequirementClassificationLabel.NON_FUNCTIONAL,
        RequirementClassificationLabel.FUNCTIONAL,
        RequirementClassificationLabel.OTHER,
        RequirementClassificationLabel.FUNCTIONAL,
        RequirementClassificationLabel.NON_FUNCTIONAL,
    ]
    result = RequirementStructuringService().structure(classification_set(items, labels))
    assert [item.candidate_id for item in result.functional_requirements] == [items[1].candidate_id, items[3].candidate_id]
    assert [item.candidate_id for item in result.non_functional_requirements] == [items[0].candidate_id, items[4].candidate_id]
    assert [item.candidate_id for item in result.excluded_candidates] == [items[2].candidate_id]


def test_requirement_and_set_identities_are_deterministic_and_evidence_sensitive():
    first_item = candidate(1, "The system must create an account.")
    changed_item = candidate(1, "The system must create a customer account.")
    service = RequirementStructuringService()
    first = service.structure(classification_set([first_item], [RequirementClassificationLabel.FUNCTIONAL]))
    repeat = service.structure(classification_set([first_item], [RequirementClassificationLabel.FUNCTIONAL]))
    changed = service.structure(classification_set([changed_item], [RequirementClassificationLabel.FUNCTIONAL]))
    assert first == repeat
    assert first.functional_requirements[0].requirement_id == repeat.functional_requirements[0].requirement_id
    assert first.functional_requirements[0].requirement_identity != changed.functional_requirements[0].requirement_identity
    assert first.structured_set_identity != changed.structured_set_identity


def test_document_audio_and_video_provenance_is_retained():
    items = [
        candidate(1, "The system must store records.", RequirementSourceType.DOCUMENT),
        candidate(2, "Audio must be available.", RequirementSourceType.AUDIO),
        candidate(3, "Video must load quickly.", RequirementSourceType.VIDEO),
    ]
    result = RequirementStructuringService().structure(classification_set(
        items, [RequirementClassificationLabel.FUNCTIONAL] * 3
    ))
    assert result.functional_requirements[0].provenance[0].page_numbers == [1]
    assert result.functional_requirements[1].provenance[0].media_segments[0].start_seconds == 2.0
    assert result.functional_requirements[2].provenance[0].media_segments[0].end_seconds == 4.0


def test_unknown_missing_duplicate_and_reordered_classifications_are_rejected():
    first = candidate(1, "The system must create accounts.")
    second = candidate(2, "The system must delete accounts.")
    base = classification_set(
        [first, second],
        [RequirementClassificationLabel.FUNCTIONAL, RequirementClassificationLabel.FUNCTIONAL],
    )
    unknown = base.classifications[0].model_copy(
        update={"candidate_id": "RC-0000000000000000"}
    )
    cases = [
        ((unknown, base.classifications[1]), "unknown"),
        ((base.classifications[0],), "missing"),
        ((base.classifications[0], base.classifications[0]), "duplicated"),
        ((base.classifications[1], base.classifications[0]), "ordering"),
    ]
    for results, message in cases:
        with pytest.raises(RequirementStructuringError, match=message):
            RequirementStructuringService().structure(
                base.model_copy(update={"classifications": results})
            )


def test_cross_project_and_invalid_candidate_identity_are_rejected():
    valid = candidate(1, "The system must create accounts.")
    base = classification_set([valid], [RequirementClassificationLabel.FUNCTIONAL])
    foreign = valid.model_copy(update={"agent_project_id": "AGP-999"})
    invalid = valid.model_copy(update={"candidate_identity": "0" * 64})
    for item, message in [(foreign, "another discovery input"), (invalid, "identity is invalid")]:
        altered_candidates = base.candidate_set.model_copy(update={"candidates": (item,)})
        altered = base.model_copy(update={
            "candidate_set": altered_candidates,
            "classifications": (base.classifications[0].model_copy(
                update={"candidate_identity": item.candidate_identity}
            ),),
        })
        with pytest.raises(RequirementStructuringError, match=message):
            RequirementStructuringService().structure(altered)


def test_all_other_and_zero_candidates_are_valid_empty_requirement_sets():
    item = candidate(1, "The project must have a meeting.")
    all_other = RequirementStructuringService().structure(
        classification_set([item], [RequirementClassificationLabel.OTHER])
    )
    empty = RequirementStructuringService().structure(classification_set([], []))
    assert all_other.functional_requirements == all_other.non_functional_requirements == ()
    assert len(all_other.excluded_candidates) == 1
    assert empty.functional_requirements == empty.non_functional_requirements == ()
    assert empty.excluded_candidates == ()
    assert len(empty.structured_set_identity) == 64


def test_invalid_classifier_fingerprint_is_rejected_without_io_or_model_calls():
    item = candidate(1, "The system must create accounts.")
    base = classification_set([item], [RequirementClassificationLabel.FUNCTIONAL])
    broken = base.model_copy(update={
        "model": base.model.model_copy(update={"configuration_fingerprint": "0" * 64})
    })
    with pytest.raises(RequirementStructuringError, match="configuration identity"):
        RequirementStructuringService().structure(broken)
