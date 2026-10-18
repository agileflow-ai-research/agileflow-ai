from dataclasses import dataclass
from typing import Any

from .evidence import validate_evidence
from .schemas import (
    EvidenceSpan, FactRejection, SemanticConflict,
    SemanticExtractionProposal, SemanticExtractionRequest,
)


@dataclass(frozen=True)
class GroundedFact:
    field_path: str
    value: Any
    evidence: list[EvidenceSpan]


@dataclass(frozen=True)
class GroundingResult:
    facts: list[GroundedFact]
    rejections: list[FactRejection]
    semantic_conflicts: list[SemanticConflict]


def ground_proposal(
    request: SemanticExtractionRequest, proposal: SemanticExtractionProposal
) -> GroundingResult:
    raw = proposal.model_dump(mode="python", by_alias=True)
    raw.pop("artifact_type", None)
    if proposal.artifact_type.value == "TECHNOLOGY_STACK":
        raw = raw["stack"]
    facts: list[GroundedFact] = []
    rejections: list[FactRejection] = []
    _visit(raw, "", None, request, facts, rejections)
    return GroundingResult(
        facts=facts,
        rejections=rejections,
        semantic_conflicts=_proposal_conflicts(proposal),
    )


def _visit(value, path, inherited_evidence, request, facts, rejections):
    if isinstance(value, dict):
        evidence = inherited_evidence
        if "evidence" in value:
            evidence = _valid_evidence(value["evidence"], request)
        for key, child in value.items():
            if key == "evidence" or child is None:
                continue
            child_path = f"{path}.{key}" if path else key
            _visit(child, child_path, evidence, request, facts, rejections)
        return
    if isinstance(value, list):
        for index, child in enumerate(value):
            _visit(child, f"{path}[{index}]", inherited_evidence,
                   request, facts, rejections)
        return
    if inherited_evidence and _fact_supported(path, value, inherited_evidence):
        facts.append(GroundedFact(path, value, inherited_evidence))
        return
    rejections.append(FactRejection(
        code="UNSUPPORTED_BY_SOURCE", field_path=path,
        proposed_value=value,
        reason="No valid source evidence directly supports the proposed value",
    ))


def _valid_evidence(values, request):
    validated = [
        validate_evidence(
            EvidenceSpan.model_validate(value),
            trusted_chunk_id=request.chunk_id,
            trusted_source_text=request.source_text,
        )
        for value in values
    ]
    return [item.evidence for item in validated if item.valid and item.evidence]


def _fact_supported(path: str, value: Any, evidence: list[EvidenceSpan]) -> bool:
    quotes = [item.quote for item in evidence]
    field = path.rsplit(".", 1)[-1].split("[", 1)[0]
    if isinstance(value, bool):
        phrases = {
            "primary_key": ("primary key",) if value else ("not a primary key",),
            "nullable": ("nullable", "may be null", "null allowed") if value
            else ("not null", "required"),
        }.get(field, (str(value).lower(),))
        return any(any(phrase in quote.lower() for phrase in phrases) for quote in quotes)
    text = str(value)
    if any(text in quote for quote in quotes):
        return True
    if field == "method":
        return any(text.upper() in quote.upper().split() for quote in quotes)
    if field == "category":
        indicators = {
            "PERFORMANCE": ("performance", "response time", "latency", "throughput", "fast"),
            "SECURITY": ("security", "secure", "encrypt", "authentication", "authorization"),
            "AVAILABILITY": ("availability", "uptime"),
            "USABILITY": ("usability", "accessible", "user experience"),
            "SCALABILITY": ("scalable", "scalability"),
            "RELIABILITY": ("reliable", "reliability", "fault tolerance"),
            "MAINTAINABILITY": ("maintainable", "maintainability"),
            "COMPATIBILITY": ("compatible", "compatibility"),
        }.get(text, ())
        return any(any(term in quote.lower() for term in indicators) for quote in quotes)
    if field == "constraint_type":
        indicators = {
            "PROHIBITION": ("must not", "prohibited", "do not"),
            "RUNTIME": ("runtime",), "DEPLOYMENT": ("deploy",),
            "BROWSER": ("browser",),
        }.get(text, ())
        return any(any(term in quote.lower() for term in indicators) for quote in quotes)
    return False


def _proposal_conflicts(proposal):
    conflicts = []
    collection_identity = {
        "FUNCTIONAL_REQUIREMENTS": ("requirements", "id"),
        "NON_FUNCTIONAL_REQUIREMENTS": ("requirements", "id"),
        "USER_STORIES": ("stories", "id"),
        "ACCEPTANCE_CRITERIA": ("criteria", "id"),
        "API_SPECIFICATION": ("endpoints", "path"),
        "DATABASE_SCHEMA": ("entities", "name"),
        "SYSTEM_ARCHITECTURE": ("components", "name"),
        "UI_FLOW": ("flows", "name"),
        "TECHNICAL_CONSTRAINTS": ("constraints", "id"),
        "IMPLEMENTATION_TASKS": ("tasks", "id"),
        "TEST_CASES": ("test_cases", "id"),
    }.get(proposal.artifact_type.value)
    if collection_identity:
        collection_name, identity_name = collection_identity
        seen = {}
        for item in getattr(proposal, collection_name):
            identity = getattr(item, identity_name)
            if identity is None:
                continue
            prior = seen.get(identity)
            current_value = item.model_dump(mode="python", exclude={"evidence"})
            if prior and prior[0] != current_value:
                conflicts.append(SemanticConflict(
                    code="CONFLICTING_SEMANTIC_FACTS",
                    field_path=f"{collection_name}[{identity_name}={identity}]",
                    semantic_value=[prior[0], current_value],
                    semantic_evidence=prior[1] + item.evidence,
                ))
            else:
                seen[identity] = (current_value, item.evidence)
    if proposal.artifact_type.value == "DATABASE_SCHEMA":
        for entity in proposal.entities:
            seen_fields = {}
            for field in entity.fields:
                current = field.model_dump(mode="python", exclude={"evidence"})
                prior = seen_fields.get(field.name)
                if prior and prior[0] != current:
                    conflicts.append(SemanticConflict(
                        code="CONFLICTING_SEMANTIC_FACTS",
                        field_path=f"entities[name={entity.name}].fields[name={field.name}]",
                        semantic_value=[prior[0], current],
                        semantic_evidence=prior[1] + field.evidence,
                    ))
                else:
                    seen_fields[field.name] = (current, field.evidence)
    return conflicts
