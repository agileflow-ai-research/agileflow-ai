from typing import Any

from app.modules.agents.implementation.infrastructure.digests import (
    stable_json_sha256,
)
from app.modules.agents.implementation.preparation.schemas import (
    ArtifactDetectionLabel,
)

from .constants import ConflictAction
from .schemas import (
    ConflictCandidate,
    ProjectConflict,
    ProjectSpecificationItem,
)


def _digest(value: Any) -> str:
    return stable_json_sha256(value)


def _id(prefix: str, value: Any) -> str:
    return f"{prefix}-{_digest(value)[:24].upper()}"


def _candidate(key, value, matching, *, label=None) -> ConflictCandidate:
    sources = []
    seen = set()
    for member in matching:
        for source in member.supporting_sources:
            identity = (source.source_id, source.final_artifact_id)
            if identity not in seen:
                sources.append(source)
                seen.add(identity)
    sources.sort(key=lambda item: (item.source_id, item.final_artifact_id or ""))
    return ConflictCandidate(
        candidate_id=_id("PCC", [key, _digest(value)]),
        label=label or _label(value),
        value=value,
        project_item_ids=sorted(item.project_item_id for item in matching),
        supporting_sources=sources,
    )


def _label(value: Any) -> str:
    if not isinstance(value, dict):
        return str(value)
    return str(
        value.get("statement")
        or value.get("method")
        or value.get("id")
        or value.get("type")
        or value
    )


def _conflict(conflict_type, artifact_type, key, grouped):
    candidates = [
        _candidate(key, entries[0][0], [entry[1] for entry in entries])
        for _, entries in sorted(grouped.items())
    ]
    fingerprint = _digest({
        "key": key,
        "candidates": [item.model_dump(mode="json") for item in candidates],
    })
    return ProjectConflict(
        conflict_id=_id("PCF", [conflict_type, key, fingerprint]),
        conflict_type=conflict_type,
        artifact_type=artifact_type,
        candidates=candidates,
        allowed_actions=[
            ConflictAction.SELECT_CANDIDATE,
            ConflictAction.KEEP_BOTH,
            ConflictAction.MARK_NOT_CONFLICTING,
            ConflictAction.EXCLUDE_CANDIDATE,
        ],
        fingerprint=fingerprint,
    )


def detect_conflicts(
    items: list[ProjectSpecificationItem],
) -> list[ProjectConflict]:
    """Detect only conflicts with a deterministic shared identity."""
    groups = {}
    for item in items:
        data = item.data
        if item.artifact_type is ArtifactDetectionLabel.TECHNOLOGY_STACK:
            category = data.get("category")
            if category not in {"database", "api_styles"}:
                continue
            key = (item.artifact_type, category)
            value = data.get("value")
        elif item.artifact_type is ArtifactDetectionLabel.API_SPECIFICATION \
                and data.get("id"):
            key = (item.artifact_type, "id", str(data["id"]).casefold())
            value = data
        elif item.artifact_type in {
            ArtifactDetectionLabel.FUNCTIONAL_REQUIREMENTS,
            ArtifactDetectionLabel.NON_FUNCTIONAL_REQUIREMENTS,
        } and data.get("id"):
            key = (item.artifact_type, "id", str(data["id"]).casefold())
            value = data
        else:
            continue
        groups.setdefault(key, []).append((item, value))

    conflicts = []
    for key, members in groups.items():
        values = {}
        for item, value in members:
            values.setdefault(_digest(value), []).append((value, item))
        if len(values) < 2:
            continue
        conflict_type = (
            "TECHNOLOGY_SELECTION"
            if key[0] is ArtifactDetectionLabel.TECHNOLOGY_STACK
            else "EXPLICIT_ID_MISMATCH"
        )
        conflicts.append(_conflict(conflict_type, key[0], key, values))

    fields = {}
    for item in items:
        if item.artifact_type is not ArtifactDetectionLabel.DATABASE_SCHEMA:
            continue
        entity = str(item.data.get("name") or "").casefold()
        for field in item.data.get("fields", []):
            if entity and field.get("name") and field.get("type") is not None:
                key = (entity, str(field["name"]).casefold())
                fields.setdefault(key, []).append((item, field["type"]))
    for key, entries in fields.items():
        grouped = {}
        for item, value in entries:
            grouped.setdefault(_digest(value), []).append((value, item))
        if len(grouped) >= 2:
            conflict = _conflict(
                "DATABASE_FIELD_TYPE",
                ArtifactDetectionLabel.DATABASE_SCHEMA,
                key,
                grouped,
            )
            for candidate in conflict.candidates:
                candidate.value = {
                    "entity": key[0], "field": key[1],
                    "type": candidate.value,
                }
                candidate.label = str(candidate.value["type"])
            # Candidate display enrichment must be fingerprinted too.
            conflict.fingerprint = _digest({
                "key": key,
                "candidates": [
                    candidate.model_dump(mode="json")
                    for candidate in conflict.candidates
                ],
            })
            conflict.conflict_id = _id(
                "PCF", ["DATABASE_FIELD_TYPE", key, conflict.fingerprint]
            )
            conflicts.append(conflict)
    return sorted(conflicts, key=lambda item: item.conflict_id)
