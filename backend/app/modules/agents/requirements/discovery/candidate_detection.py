"""Deterministic, evidence-grounded requirement candidate discovery."""

import re

from app.modules.agents.requirements.discovery.contracts import (
    CandidateDiscoverySignal,
    RequirementCandidate,
    RequirementCandidateSet,
    ValidatedDiscoveryInput,
)
from app.modules.agents.requirements.infrastructure.digests import stable_json_sha256
from app.modules.agents.requirements.processing.preparation.chunker import SentenceSegmenter


CANDIDATE_CONTRACT_VERSION = "1"

_SIGNAL_PATTERNS: tuple[tuple[CandidateDiscoverySignal, re.Pattern[str]], ...] = (
    (CandidateDiscoverySignal.MODAL_SHALL, re.compile(r"\bshall\b", re.I)),
    (CandidateDiscoverySignal.MODAL_MUST, re.compile(r"\bmust\b", re.I)),
    (CandidateDiscoverySignal.MODAL_SHOULD, re.compile(r"\bshould\b", re.I)),
    (CandidateDiscoverySignal.MODAL_MAY, re.compile(r"\bmay\b", re.I)),
    (CandidateDiscoverySignal.MODAL_CAN, re.compile(r"\bcan\b", re.I)),
    (CandidateDiscoverySignal.NEED_OBLIGATION, re.compile(r"\bneeds?\s+to\b", re.I)),
    (CandidateDiscoverySignal.REQUIRED_OBLIGATION, re.compile(r"\brequired\s+to\b", re.I)),
    (
        CandidateDiscoverySignal.CAPABILITY_PATTERN,
        re.compile(
            r"\b(?:users?|administrators?|customers?|operators?)\s+"
            r"(?:can|may|shall|must|should|(?:is|are)\s+able\s+to)\b|"
            r"\b(?:system|application|platform|service)\s+"
            r"(?:allows?|provides?|supports?|enables?)\b",
            re.I,
        ),
    ),
    (
        CandidateDiscoverySignal.SYSTEM_BEHAVIOR_PATTERN,
        re.compile(
            r"\b(?:the\s+)?(?:system|application|platform|service|users?|"
            r"administrators?)\s+(?:sends?|validates?|stores?|selects?|manages?|"
            r"creates?|updates?|deletes?|displays?|records?|notifies?|calculates?|"
            r"generates?|prevents?|accepts?|rejects?)\b",
            re.I,
        ),
    ),
    (
        CandidateDiscoverySignal.PERFORMANCE_CONSTRAINT,
        re.compile(
            r"\b(?:within\s+(?:\w+|\d+(?:\.\d+)?)\s+"
            r"(?:milli)?seconds?|response\s+time|latency|availability|uptime)\b",
            re.I,
        ),
    ),
    (
        CandidateDiscoverySignal.SECURITY_CONSTRAINT,
        re.compile(r"\b(?:encrypt(?:ed|ion)?|security|secure|authentication|authorization)\b", re.I),
    ),
    (
        CandidateDiscoverySignal.CAPACITY_CONSTRAINT,
        re.compile(r"\b(?:maximum|minimum|concurrent\s+users?|at\s+least|no\s+more\s+than)\b", re.I),
    ),
    (
        CandidateDiscoverySignal.COMPATIBILITY_CONSTRAINT,
        re.compile(r"\b(?:browsers?|devices?|mobile|desktop|operating\s+systems?)\b", re.I),
    ),
    (
        CandidateDiscoverySignal.EXPLICIT_REQUIREMENT,
        re.compile(
            r"\b(?:functional|non-functional|system)\s+requirements?\b|"
            r"\brequirements?\s*:",
            re.I,
        ),
    ),
)

_NOISE = re.compile(
    r"^(?:hello|hi|thanks?|thank\s+you|okay|ok|yes|no|copyright|all\s+rights\s+reserved)\b",
    re.I,
)
_PAGE_NUMBER = re.compile(r"^(?:page\s+)?\d+(?:\s+of\s+\d+)?$", re.I)


class RequirementCandidateDetector:
    """Find candidate spans without classifying, rewriting, or persisting them."""

    def __init__(self, segmenter: SentenceSegmenter | None = None) -> None:
        self._segmenter = segmenter or SentenceSegmenter()

    def discover(self, value: ValidatedDiscoveryInput) -> RequirementCandidateSet:
        candidates: list[RequirementCandidate] = []
        for validated_chunk in value.chunks:
            chunk = validated_chunk.chunk
            seen_spans: set[tuple[int, int]] = set()
            for span in self._segmenter.segment(chunk.content):
                start, end = self._trimmed_span(chunk.content, span.start, span.end)
                if start >= end or (start, end) in seen_spans:
                    continue
                text = chunk.content[start:end]
                signals = self._signals(text)
                if not signals or self._is_obvious_noise(text):
                    continue
                seen_spans.add((start, end))
                identity = stable_json_sha256(
                    {
                        "agent_project_id": value.agent_project_id,
                        "candidate_contract_version": CANDIDATE_CONTRACT_VERSION,
                        "discovery_input_identity": value.input_identity,
                        "chunk_id": chunk.chunk_id,
                        "span": [start, end],
                        "text": text,
                    }
                )
                candidates.append(
                    RequirementCandidate(
                        candidate_id=f"RC-{identity[:16].upper()}",
                        candidate_identity=identity,
                        agent_project_id=value.agent_project_id,
                        n2_execution_id=value.reference.n2_execution_id,
                        chunk_set_digest=value.reference.chunk_set_digest,
                        chunk_id=chunk.chunk_id,
                        source_id=validated_chunk.source_id,
                        source_type=validated_chunk.source_type,
                        text=text,
                        start_offset=start,
                        end_offset=end,
                        discovery_signals=signals,
                        provenance=tuple(chunk.provenance),
                    )
                )
        return RequirementCandidateSet(
            contract_version=CANDIDATE_CONTRACT_VERSION,
            agent_project_id=value.agent_project_id,
            n2_execution_id=value.reference.n2_execution_id,
            chunk_set_digest=value.reference.chunk_set_digest,
            discovery_input_identity=value.input_identity,
            candidates=tuple(candidates),
        )

    @staticmethod
    def _signals(text: str) -> tuple[CandidateDiscoverySignal, ...]:
        return tuple(signal for signal, pattern in _SIGNAL_PATTERNS if pattern.search(text))

    @staticmethod
    def _trimmed_span(text: str, start: int, end: int) -> tuple[int, int]:
        while start < end and text[start].isspace():
            start += 1
        while end > start and text[end - 1].isspace():
            end -= 1
        return start, end

    @staticmethod
    def _is_obvious_noise(text: str) -> bool:
        stripped = text.strip()
        words = re.findall(r"[A-Za-z0-9]+", stripped)
        if len(stripped) < 8 or len(words) < 3:
            return True
        if _NOISE.match(stripped) or _PAGE_NUMBER.fullmatch(stripped):
            return True
        return False
