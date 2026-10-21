"""Deterministic lexical exact-duplicate detection over validated N4 input."""

import re
import unicodedata

from app.modules.agents.requirements.infrastructure.digests import stable_json_sha256
from app.modules.agents.requirements.quality.contracts import (
    ExactDuplicateGroup,
    ExactDuplicateMember,
    ExactDuplicateResult,
    ValidatedQualityInput,
)


EXACT_DUPLICATE_CONTRACT_VERSION = "1"
EXACT_DUPLICATE_DETECTOR_VERSION = "1"
EXACT_DUPLICATE_NORMALIZATION_VERSION = "1"
_INTERNAL_WHITESPACE = re.compile(r"\s+")


class ExactDuplicateDetector:
    """Group exact lexical matches without changing authoritative statements.

    Comparison uses NFKC, newline-independent whitespace collapsing, outer
    trimming, and Unicode casefolding. Punctuation and word order are retained.
    """

    def __init__(self, *, normalization_version: str = EXACT_DUPLICATE_NORMALIZATION_VERSION) -> None:
        if not normalization_version:
            raise ValueError("Normalization version is required")
        self._normalization_version = normalization_version

    @property
    def configuration_fingerprint(self) -> str:
        return stable_json_sha256({
            "detector_type": "EXACT_DUPLICATE",
            "detector_version": EXACT_DUPLICATE_DETECTOR_VERSION,
            "normalization_version": self._normalization_version,
            "unicode_normalization": "NFKC",
            "newline_policy": "CRLF_AND_CR_TO_LF",
            "whitespace_policy": "TRIM_AND_COLLAPSE",
            "case_policy": "UNICODE_CASEFOLD",
            "punctuation_policy": "PRESERVE",
        })

    def detect(self, value: ValidatedQualityInput) -> ExactDuplicateResult:
        buckets: dict[str, list] = {}
        fingerprints: dict[str, str] = {}
        seen_ids: set[str] = set()
        for requirement in value.requirements:
            # A repeated reference to the same authoritative record is not a
            # second requirement and therefore cannot duplicate itself.
            if requirement.requirement_id in seen_ids:
                continue
            seen_ids.add(requirement.requirement_id)
            canonical = self._canonical(requirement.statement)
            comparison_fingerprint = stable_json_sha256({
                "normalization_version": self._normalization_version,
                "canonical_comparison_statement": canonical,
            })
            fingerprints[canonical] = comparison_fingerprint
            buckets.setdefault(canonical, []).append(requirement)

        groups: list[ExactDuplicateGroup] = []
        for canonical, requirements in buckets.items():
            if len(requirements) < 2:
                continue
            ordered_ids = [item.requirement_id for item in requirements]
            identity = stable_json_sha256({
                "contract_version": EXACT_DUPLICATE_CONTRACT_VERSION,
                "quality_input_identity": value.input_identity,
                "comparison_fingerprint": fingerprints[canonical],
                "ordered_requirement_ids": ordered_ids,
            })
            groups.append(ExactDuplicateGroup(
                duplicate_group_id=f"QDUP-{identity[:16].upper()}",
                comparison_fingerprint=fingerprints[canonical],
                members=tuple(ExactDuplicateMember(requirement=item)
                              for item in requirements),
                count=len(requirements),
            ))

        result_identity = stable_json_sha256({
            "quality_input_identity": value.input_identity,
            "contract_version": EXACT_DUPLICATE_CONTRACT_VERSION,
            "detector_fingerprint": self.configuration_fingerprint,
            "ordered_duplicate_group_ids": [item.duplicate_group_id for item in groups],
        })
        return ExactDuplicateResult(
            contract_version=EXACT_DUPLICATE_CONTRACT_VERSION,
            agent_project_id=value.agent_project_id,
            quality_input_identity=value.input_identity,
            detector_fingerprint=self.configuration_fingerprint,
            duplicate_groups=tuple(groups),
            duplicate_group_count=len(groups),
            affected_requirement_count=sum(item.count for item in groups),
            result_identity=result_identity,
        )

    @staticmethod
    def _canonical(statement: str) -> str:
        normalized = unicodedata.normalize("NFKC", statement)
        normalized = normalized.replace("\r\n", "\n").replace("\r", "\n")
        return _INTERNAL_WHITESPACE.sub(" ", normalized).strip().casefold()
