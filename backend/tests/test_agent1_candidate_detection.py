from app.modules.agents.requirements.contracts.schemas import RequirementSourceType
from app.modules.agents.requirements.discovery.candidate_detection import RequirementCandidateDetector
from app.modules.agents.requirements.discovery.contracts import (
    CandidateDiscoverySignal,
    DiscoveryInputReference,
    ValidatedDiscoveryChunk,
    ValidatedDiscoveryInput,
)
from app.modules.agents.requirements.processing.preparation.schemas import (
    EvidenceChunk,
    MediaSegmentReference,
    NormalizedProvenanceSpan,
)


def validated_input(*chunks):
    wrapped = []
    for index, (text, source_type, provenance) in enumerate(chunks, start=1):
        prefix = {
            RequirementSourceType.DOCUMENT: "DOC",
            RequirementSourceType.AUDIO: "AUD",
            RequirementSourceType.VIDEO: "VID",
        }[source_type]
        wrapped.append(
            ValidatedDiscoveryChunk(
                source_id=f"{prefix}-{index:03d}",
                source_type=source_type,
                source_sha256="a" * 64,
                parent_result_fingerprint="b" * 64,
                normalizer_version="1",
                chunker_fingerprint="c" * 64,
                chunk=EvidenceChunk(
                    chunk_id=f"CHK-{index:016X}",
                    content=text,
                    normalized_start_offset=0,
                    normalized_end_offset=len(text),
                    provenance=[provenance],
                ),
            )
        )
    return ValidatedDiscoveryInput(
        contract_version="1",
        agent_project_id="AGP-020",
        reference=DiscoveryInputReference(
            n2_execution_id="N2-AAAAAAAAAAAAAAAA-001",
            n2_attempt=1,
            chunk_set_digest="d" * 64,
            confirmed_source_set_digest="e" * 64,
        ),
        chunks=tuple(wrapped),
        input_identity="f" * 64,
    )


def document_provenance(length):
    return NormalizedProvenanceSpan(
        normalized_start_offset=0,
        normalized_end_offset=length,
        parent_start_offset=10,
        parent_end_offset=10 + length,
        page_numbers=[3],
    )


def media_provenance(length, start=4.5, end=8.5):
    return NormalizedProvenanceSpan(
        normalized_start_offset=0,
        normalized_end_offset=length,
        parent_start_offset=20,
        parent_end_offset=20 + length,
        media_segments=[
            MediaSegmentReference(
                segment_index=2,
                start_seconds=start,
                end_seconds=end,
                parent_start_offset=20,
                parent_end_offset=20 + length,
            )
        ],
    )


def discover(text):
    value = validated_input(
        (text, RequirementSourceType.DOCUMENT, document_provenance(len(text)))
    )
    return RequirementCandidateDetector().discover(value)


def test_discovers_modal_capability_behavior_and_constraint_examples():
    examples = {
        "The system must allow users to register.": CandidateDiscoverySignal.MODAL_MUST,
        "Users can reset their password.": CandidateDiscoverySignal.CAPABILITY_PATTERN,
        "The system sends a confirmation email.": CandidateDiscoverySignal.SYSTEM_BEHAVIOR_PATTERN,
        "The page should respond within three seconds.": CandidateDiscoverySignal.PERFORMANCE_CONSTRAINT,
    }
    for text, expected_signal in examples.items():
        result = discover(text)
        assert [candidate.text for candidate in result.candidates] == [text]
        assert expected_signal in result.candidates[0].discovery_signals


def test_filters_greeting_heading_and_supports_valid_empty_set():
    text = "Hello, thanks for meeting with us. Registration"
    result = discover(text)
    assert result.candidates == ()


def test_multi_sentence_chunk_preserves_only_exact_requirement_spans():
    text = "Thanks for joining us. The system must save drafts. Okay, that is all."
    result = discover(text)
    assert [candidate.text for candidate in result.candidates] == [
        "The system must save drafts."
    ]
    candidate = result.candidates[0]
    assert text[candidate.start_offset : candidate.end_offset] == candidate.text


def test_repeated_discovery_has_stable_ids_and_order():
    text = "Users can register. The system sends an email."
    value = validated_input(
        (text, RequirementSourceType.DOCUMENT, document_provenance(len(text)))
    )
    detector = RequirementCandidateDetector()
    first = detector.discover(value)
    second = detector.discover(value)
    assert first == second
    assert [item.text for item in first.candidates] == [
        "Users can register.",
        "The system sends an email.",
    ]


def test_same_text_in_different_chunks_remains_two_traceable_candidates():
    text = "The system must encrypt stored data."
    value = validated_input(
        (text, RequirementSourceType.DOCUMENT, document_provenance(len(text))),
        (text, RequirementSourceType.AUDIO, media_provenance(len(text))),
    )
    candidates = RequirementCandidateDetector().discover(value).candidates
    assert len(candidates) == 2
    assert candidates[0].candidate_id != candidates[1].candidate_id
    assert [item.source_id for item in candidates] == ["DOC-001", "AUD-002"]


def test_document_audio_and_video_provenance_is_retained():
    document = "The system must store records."
    audio = "Users can replay the recording."
    video = "The application should support mobile devices."
    value = validated_input(
        (document, RequirementSourceType.DOCUMENT, document_provenance(len(document))),
        (audio, RequirementSourceType.AUDIO, media_provenance(len(audio), 2.0, 3.0)),
        (video, RequirementSourceType.VIDEO, media_provenance(len(video), 7.0, 9.0)),
    )
    candidates = RequirementCandidateDetector().discover(value).candidates
    assert candidates[0].provenance[0].page_numbers == [3]
    assert candidates[1].provenance[0].media_segments[0].start_seconds == 2.0
    assert candidates[2].provenance[0].media_segments[0].end_seconds == 9.0


def test_overlapping_rules_create_one_candidate_with_controlled_signals():
    text = "The system must respond within three seconds."
    candidate = discover(text).candidates[0]
    assert candidate.discovery_signals == (
        CandidateDiscoverySignal.MODAL_MUST,
        CandidateDiscoverySignal.PERFORMANCE_CONSTRAINT,
    )
    assert candidate.candidate_id.startswith("RC-")
    assert len(candidate.candidate_identity) == 64
