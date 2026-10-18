import copy
import re
from typing import Any

from .grounding import GroundingResult
from .schemas import (
    FieldOrigin, MergedSemanticArtifact, SemanticConflict,
    SemanticExtractionRequest, SemanticFieldProvenance, SemanticResultStatus,
)


_TOKEN = re.compile(r"([^.\[\]]+)|\[(\d+)\]")
_ADDITIVE_LISTS = {
    "request_fields", "response_statuses", "preconditions",
    "frontend", "styling", "backend", "database", "languages",
    "api_styles", "other",
}


def merge_grounded(
    request: SemanticExtractionRequest, grounding: GroundingResult
) -> MergedSemanticArtifact:
    data = copy.deepcopy(request.deterministic_artifact.data.model_dump(
        mode="python", by_alias=True
    ))
    provenance = _deterministic_provenance(
        data, request.deterministic_artifact.source_refs
    )
    conflicts = list(grounding.semantic_conflicts)
    for fact in grounding.facts:
        tokens = _tokens(fact.field_path)
        exists, current = _get(data, tokens)
        list_name = _containing_list_name(fact.field_path)
        if list_name in _ADDITIVE_LISTS:
            parent_tokens = tokens[:-1]
            parent_exists, parent = _get(data, parent_tokens)
            if parent_exists and isinstance(parent, list):
                if fact.value in parent:
                    _support_existing(provenance, fact)
                else:
                    parent.append(copy.deepcopy(fact.value))
                    semantic_path = _replace_final_index(
                        fact.field_path, len(parent) - 1
                    )
                    provenance.append(SemanticFieldProvenance(
                        field_path=semantic_path, origin=FieldOrigin.SEMANTIC,
                        evidence=fact.evidence,
                    ))
                continue
        if not exists or current is None or current == "":
            _set(data, tokens, copy.deepcopy(fact.value))
            provenance.append(SemanticFieldProvenance(
                field_path=fact.field_path, origin=FieldOrigin.SEMANTIC,
                evidence=fact.evidence,
            ))
        elif current == fact.value:
            _support_existing(provenance, fact)
        else:
            conflicts.append(SemanticConflict(
                code="SEMANTIC_DETERMINISTIC_CONFLICT",
                field_path=fact.field_path,
                deterministic_value=current,
                semantic_value=fact.value,
                semantic_evidence=fact.evidence,
            ))
    if conflicts:
        status = SemanticResultStatus.HUMAN_REVIEW_REQUIRED
    elif grounding.facts and request.deterministic_artifact.status.value == "UNRESOLVED":
        status = SemanticResultStatus.PARTIAL
    else:
        status = SemanticResultStatus(request.deterministic_artifact.status.value)
    return MergedSemanticArtifact(
        artifact_id=request.deterministic_artifact.artifact_id,
        artifact_type=request.artifact_type,
        status=status, data=data,
        field_provenance=_dedupe_provenance(provenance),
        conflicts=conflicts,
    )


def _tokens(path):
    return [int(index) if index else name for name, index in _TOKEN.findall(path)]


def _get(root, tokens):
    current = root
    for token in tokens:
        if isinstance(token, int):
            if not isinstance(current, list) or token >= len(current):
                return False, None
            current = current[token]
        else:
            if not isinstance(current, dict) or token not in current:
                return False, None
            current = current[token]
    return True, current


def _set(root, tokens, value):
    current = root
    for position, token in enumerate(tokens[:-1]):
        next_token = tokens[position + 1]
        if isinstance(token, str):
            if token not in current or current[token] is None:
                current[token] = [] if isinstance(next_token, int) else {}
            current = current[token]
        else:
            while len(current) <= token:
                current.append({} if isinstance(next_token, str) else [])
            current = current[token]
    final = tokens[-1]
    if isinstance(final, int):
        while len(current) <= final:
            current.append(None)
        current[final] = value
    else:
        current[final] = value


def _deterministic_provenance(data, source_refs):
    result = []
    def visit(value: Any, path: str):
        if isinstance(value, dict):
            for key, child in value.items():
                if key == "source_refs":
                    continue
                visit(child, f"{path}.{key}" if path else key)
        elif isinstance(value, list):
            for index, child in enumerate(value):
                visit(child, f"{path}[{index}]")
        elif value is not None:
            result.append(SemanticFieldProvenance(
                field_path=path, origin=FieldOrigin.DETERMINISTIC,
                source_refs=source_refs,
            ))
    visit(data, "")
    return result


def _support_existing(provenance, fact):
    for item in provenance:
        if item.field_path == fact.field_path:
            item.evidence.extend(fact.evidence)
            return


def _containing_list_name(path):
    match = re.search(r"([A-Za-z_]+)\[\d+\]$", path)
    return match.group(1) if match else None


def _replace_final_index(path, index):
    return re.sub(r"\[\d+\]$", f"[{index}]", path)


def _dedupe_provenance(items):
    seen, result = set(), []
    for item in items:
        marker = (item.field_path, item.origin)
        if marker not in seen:
            seen.add(marker)
            result.append(item)
    return result
