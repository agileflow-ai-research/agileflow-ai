import copy
import json
import re
from datetime import datetime, timezone
from threading import RLock
from typing import Any

from app.modules.agents.implementation.contracts.enums import (
    ImplementationArtifactType,
    ImplementationInputSourceType,
)
from app.modules.agents.implementation.inputs.upload.service import (
    require_implementation_project,
)
from app.modules.agents.implementation.infrastructure.digests import (
    stable_json_sha256,
)
from app.modules.agents.implementation.preparation.orchestration.constants import (
    SourcePreparationStatus,
)
from app.modules.agents.implementation.preparation.orchestration.storage import (
    ProjectPreparationStorage,
)
from app.modules.agents.implementation.preparation.schemas import (
    ArtifactDetectionLabel,
)

from .conflicts import detect_conflicts
from .constants import (
    PROJECT_SPECIFICATION_SCHEMA_VERSION,
    ConflictAction,
    ConflictStatus,
    ConsolidationSourceKind,
    ConsolidationStatus,
)
from .schemas import (
    ConflictCandidate,
    ConflictDecisionRequest,
    ConsolidationInput,
    ConsolidationIssue,
    ProjectConsolidationRecord,
    ProjectConsolidationStatusResponse,
    ProjectRelationship,
    ProjectConflict,
    ProjectSourceRef,
    ProjectSpecificationItem,
    TrustedProjectSpecification,
)


COLLECTION_KEYS = {
    ArtifactDetectionLabel.FUNCTIONAL_REQUIREMENTS: "requirements",
    ArtifactDetectionLabel.NON_FUNCTIONAL_REQUIREMENTS: "requirements",
    ArtifactDetectionLabel.USER_STORIES: "stories",
    ArtifactDetectionLabel.ACCEPTANCE_CRITERIA: "criteria",
    ArtifactDetectionLabel.API_SPECIFICATION: "endpoints",
    ArtifactDetectionLabel.DATABASE_SCHEMA: "entities",
    ArtifactDetectionLabel.UI_FLOW: "flows",
    ArtifactDetectionLabel.TECHNICAL_CONSTRAINTS: "constraints",
    ArtifactDetectionLabel.IMPLEMENTATION_TASKS: "tasks",
    ArtifactDetectionLabel.TEST_CASES: "test_cases",
    ArtifactDetectionLabel.OTHER_CONTEXT: "context_items",
}


class ConsolidationNotFoundError(LookupError):
    pass


class ConflictNotFoundError(LookupError):
    pass


class InvalidConflictDecisionError(ValueError):
    pass


class StaleConflictDecisionError(ValueError):
    pass


def _now():
    return datetime.now(timezone.utc)


def _digest(value: Any) -> str:
    return stable_json_sha256(value)


def _id(prefix, value):
    return f"{prefix}-{_digest(value)[:24].upper()}"


def _normalized(value):
    if isinstance(value, str):
        return " ".join(value.split()).casefold()
    if isinstance(value, list):
        return [_normalized(item) for item in value]
    if isinstance(value, dict):
        return {
            key: _normalized(item)
            for key, item in sorted(value.items())
            if key != "source_refs"
        }
    return value


def consolidate_inputs(inputs: list[ConsolidationInput]):
    expanded = []
    for source in inputs:
        data = copy.deepcopy(source.data)
        data.pop("source_refs", None)
        if source.artifact_type is ArtifactDetectionLabel.TECHNOLOGY_STACK:
            for category, values in data.items():
                if isinstance(values, list):
                    expanded.extend(
                        (source, {"category": category, "value": value})
                        for value in values
                    )
            continue
        if source.artifact_type is ArtifactDetectionLabel.SYSTEM_ARCHITECTURE:
            for key in (
                "components", "relationships", "raw_architecture_statements"
            ):
                for value in data.get(key, []):
                    expanded.append((source, {
                        "kind": key,
                        **{k: v for k, v in value.items() if k != "source_refs"},
                    }))
            continue
        key = COLLECTION_KEYS.get(source.artifact_type)
        values = data.get(key, [data]) if key else [data]
        for value in values:
            expanded.append((source, (
                {k: v for k, v in value.items() if k != "source_refs"}
                if isinstance(value, dict) else {"value": value}
            )))

    grouped = {}
    for source, data in expanded:
        identity = _digest([source.artifact_type, _normalized(data)])
        key = (source.artifact_type, identity)
        item = grouped.setdefault(key, ProjectSpecificationItem(
            project_item_id=_id("PSI", key),
            artifact_type=source.artifact_type,
            identity_key=identity,
            data=data,
            supporting_sources=[],
            source_artifact_ids=[],
        ))
        source_identity = (
            source.source.source_id, source.source.final_artifact_id
        )
        if source_identity not in {
            (ref.source_id, ref.final_artifact_id)
            for ref in item.supporting_sources
        }:
            item.supporting_sources.append(source.source)
        if source.source_artifact_id not in item.source_artifact_ids:
            item.source_artifact_ids.append(source.source_artifact_id)
    items = sorted(grouped.values(), key=lambda item: item.project_item_id)
    for item in items:
        item.supporting_sources.sort(
            key=lambda ref: (ref.source_id, ref.final_artifact_id or "")
        )
        item.source_artifact_ids.sort()
    return items, detect_conflicts(items), len(expanded) - len(items)


def explicit_relationships(items: list[ProjectSpecificationItem]):
    by_explicit_id = {
        str(item.data["id"]).casefold(): item
        for item in items if item.data.get("id")
    }
    relationships = []
    seen = set()
    for item in items:
        serialized = json.dumps(item.data, sort_keys=True).casefold()
        for explicit_id, target in by_explicit_id.items():
            identity = (item.project_item_id, target.project_item_id)
            if (
                target.project_item_id != item.project_item_id
                and re.search(rf"(?<![a-z0-9_-]){re.escape(explicit_id)}(?![a-z0-9_-])", serialized)
                and identity not in seen
            ):
                relationships.append(ProjectRelationship(
                    from_item_id=item.project_item_id,
                    to_item_id=target.project_item_id,
                    relationship_type="EXPLICIT_ID_REFERENCE",
                ))
                seen.add(identity)
    return relationships


class ProjectConsolidationService:
    _lock = RLock()

    def __init__(
        self,
        standalone_service,
        upload_storage,
        preparation_storage: ProjectPreparationStorage,
        semantic_reviews,
        storage,
        *,
        clock=_now,
    ):
        self._standalone = standalone_service
        self._uploads = upload_storage
        self._preparation = preparation_storage
        self._semantic_reviews = semantic_reviews
        self._storage = storage
        self._clock = clock

    def start(self, project_id, current_user):
        require_implementation_project(
            self._standalone, project_id, current_user
        )
        with self._lock:
            inputs, refs, issues, digest = self._discover(
                project_id, current_user
            )
            previous = self._storage.load_state(
                project_id, current_user.user_id
            )
            items, conflicts, deduplicated = consolidate_inputs(inputs)
            items, text_conflicts = self._text_confirmation_conflicts(
                inputs, items
            )
            conflicts = sorted(
                [*conflicts, *text_conflicts],
                key=lambda item: item.conflict_id,
            )
            if previous and previous.source_set_digest == digest:
                decisions = {
                    item.conflict_id: item for item in previous.conflicts
                    if item.status is ConflictStatus.RESOLVED
                }
                for conflict in conflicts:
                    saved = decisions.get(conflict.conflict_id)
                    if saved and saved.fingerprint == conflict.fingerprint:
                        conflict.status = saved.status
                        conflict.action = saved.action
                        conflict.selected_candidate_id = (
                            saved.selected_candidate_id
                        )
                        conflict.reviewer_owner_id = saved.reviewer_owner_id
                        conflict.decided_at = saved.decided_at
            status = self._status(inputs, conflicts, issues)
            now = self._clock()
            record = ProjectConsolidationRecord(
                agent_project_id=project_id,
                owner_user_id=current_user.user_id,
                status=status,
                source_set_digest=digest,
                source_refs=refs,
                items=items,
                conflicts=conflicts,
                issues=issues,
                deduplicated_item_count=deduplicated,
                created_at=previous.created_at if previous else now,
                updated_at=now,
            )
            self._storage.save_state(record)
            if status is ConsolidationStatus.READY:
                self._finalize(record)
            return self._public(record)

    def get_status(self, project_id, current_user):
        require_implementation_project(
            self._standalone, project_id, current_user
        )
        record = self._storage.load_state(project_id, current_user.user_id)
        if not record:
            return ProjectConsolidationStatusResponse(
                agent_project_id=project_id,
                status=ConsolidationStatus.NOT_STARTED,
                source_count=0,
                item_count=0,
                conflict_count=0,
                pending_conflict_count=0,
                issue_count=0,
            )
        _, _, _, current_digest = self._discover(project_id, current_user)
        if (
            current_digest != record.source_set_digest
            and record.status is not ConsolidationStatus.STALE
        ):
            record.status = ConsolidationStatus.STALE
            record.updated_at = self._clock()
            self._storage.save_state(record)
        return self._public(record)

    def get_conflicts(self, project_id, current_user):
        self.get_status(project_id, current_user)
        record = self._storage.load_state(project_id, current_user.user_id)
        if not record:
            raise ConsolidationNotFoundError(project_id)
        return record.conflicts

    def decide(self, project_id, conflict_id, request, current_user):
        with self._lock:
            status = self.get_status(project_id, current_user)
            if status.status is ConsolidationStatus.STALE:
                raise StaleConflictDecisionError(
                    "STALE_PROJECT_SPECIFICATION"
                )
            record = self._storage.load_state(
                project_id, current_user.user_id
            )
            conflict = next((
                item for item in record.conflicts
                if item.conflict_id == conflict_id
            ), None)
            if conflict is None:
                raise ConflictNotFoundError(conflict_id)
            if request.expected_fingerprint != conflict.fingerprint:
                raise StaleConflictDecisionError("STALE_CONFLICT")
            if request.action not in conflict.allowed_actions:
                raise InvalidConflictDecisionError(
                    "Action is not allowed for this conflict"
                )
            candidate_ids = {
                item.candidate_id for item in conflict.candidates
            }
            if request.candidate_id and request.candidate_id not in candidate_ids:
                raise InvalidConflictDecisionError(
                    "Candidate is not part of this stored conflict"
                )
            if request.action in {
                ConflictAction.SELECT_CANDIDATE,
                ConflictAction.EXCLUDE_CANDIDATE,
            } and request.candidate_id is None:
                raise InvalidConflictDecisionError(
                    "This action requires a stored candidate"
                )
            conflict.status = ConflictStatus.RESOLVED
            conflict.action = request.action
            conflict.selected_candidate_id = request.candidate_id
            conflict.reviewer_owner_id = current_user.user_id
            conflict.decided_at = self._clock()
            record.status = self._status(
                record.items, record.conflicts, record.issues
            )
            record.updated_at = self._clock()
            self._storage.save_state(record)
            if record.status is ConsolidationStatus.READY:
                self._finalize(record)
            return conflict

    def get_final(self, project_id, current_user):
        status = self.get_status(project_id, current_user)
        if status.status is not ConsolidationStatus.READY:
            raise ConsolidationNotFoundError(project_id)
        final = self._storage.load_final(project_id, current_user.user_id)
        if final is None or final.source_set_digest != status.source_set_digest:
            raise ConsolidationNotFoundError(project_id)
        return final

    def _discover(self, project_id, user):
        inputs, refs, issues, identities = [], [], [], []
        for upload in self._uploads.list_for_project(
            agent_project_id=project_id, owner_user_id=user.user_id
        ):
            if upload.source_type is ImplementationInputSourceType.IMAGE:
                continue
            try:
                final = self._semantic_reviews.get_final(
                    project_id, upload.upload_id, user
                )
            except Exception:
                issues.append(ConsolidationIssue(
                    source_id=upload.upload_id,
                    error_code="TRUSTED_ARTIFACT_REQUIRED",
                    message=(
                        "Current trusted artifacts are not ready for this source."
                    ),
                ))
                identities.append([
                    upload.upload_id, getattr(upload, "sha256", None),
                    "UNTRUSTED",
                ])
                continue
            identity = _digest(final.model_dump(mode="json"))
            identities.append([upload.upload_id, identity])
            for artifact in final.artifacts:
                chunks = sorted({ref.chunk_id for ref in artifact.source_refs})
                ref = ProjectSourceRef(
                    source_id=upload.upload_id,
                    source_kind=ConsolidationSourceKind.UPLOAD,
                    label=final.original_filename,
                    source_fingerprint=identity,
                    final_artifact_id=artifact.final_artifact_id,
                    canonical_artifact_id=artifact.canonical_artifact_id,
                    chunk_ids=chunks,
                    evidence_refs=[
                        item.model_dump(mode="json")
                        for item in artifact.source_refs
                    ],
                    field_provenance=[
                        item.model_dump(mode="json")
                        for item in artifact.field_provenance
                    ],
                )
                refs.append(ref)
                inputs.append(ConsolidationInput(
                    source=ref,
                    artifact_type=artifact.artifact_type,
                    data=artifact.data,
                    source_artifact_id=artifact.final_artifact_id,
                ))
        prep = self._preparation.load(
            agent_project_id=project_id, owner_user_id=user.user_id
        )
        if prep:
            for source in prep.sources:
                if source.source_kind is not ImplementationInputSourceType.TEXT:
                    continue
                content_hash = _digest(source.text_content or "")
                identities.append([
                    source.source_id, source.artifact_type, content_hash
                ])
                if (
                    source.status is not SourcePreparationStatus.READY
                    or not source.text_content
                ):
                    issues.append(ConsolidationIssue(
                        source_id=source.source_id,
                        error_code="TRUSTED_TEXT_REQUIRED",
                        message=(
                            "Manual text has not completed input preparation."
                        ),
                    ))
                    continue
                ref = ProjectSourceRef(
                    source_id=source.source_id,
                    source_kind=ConsolidationSourceKind.TEXT,
                    label=source.label or "Manual text",
                    source_fingerprint=content_hash,
                    declared_artifact_type=source.artifact_type.value,
                )
                refs.append(ref)
                inputs.append(ConsolidationInput(
                    source=ref,
                    # The client-declared type is provenance only. A server-owned
                    # confirmation conflict supplies the trusted category.
                    artifact_type=ArtifactDetectionLabel.OTHER_CONTEXT,
                    data={"context_items": [{"text": source.text_content}]},
                    source_artifact_id=(
                        f"TEXT-{content_hash[:24].upper()}"
                    ),
                ))
        inputs.sort(key=lambda item: (
            item.source.source_id, item.source_artifact_id,
            item.artifact_type.value,
        ))
        refs.sort(key=lambda item: (item.source_id, item.final_artifact_id or ""))
        identities.sort(
            key=lambda item: json.dumps(
                item, sort_keys=True, separators=(",", ":"), default=str
            )
        )
        return inputs, refs, issues, _digest(identities)

    def _text_confirmation_conflicts(self, inputs, items):
        """Replace untyped manual text with server-owned category candidates."""
        text_inputs = [
            item for item in inputs
            if item.source.source_kind is ConsolidationSourceKind.TEXT
        ]
        if not text_inputs:
            return items, []

        text_artifact_ids = {
            item.source_artifact_id for item in text_inputs
        }
        retained = [
            item for item in items
            if not text_artifact_ids.intersection(item.source_artifact_ids)
        ]
        conflicts = []
        for source in text_inputs:
            content = source.data["context_items"][0]["text"]
            candidates = []
            for category in ArtifactDetectionLabel:
                data = self._text_item_data(category, content)
                identity = _digest([category, _normalized(data)])
                item = ProjectSpecificationItem(
                    # Candidate items are source-scoped until confirmation so
                    # one TEXT decision cannot exclude another source's item.
                    project_item_id=_id("PSI", (
                        source.source.source_id, category, identity
                    )),
                    artifact_type=category,
                    identity_key=identity,
                    data=data,
                    supporting_sources=[source.source],
                    source_artifact_ids=[source.source_artifact_id],
                )
                retained.append(item)
                key = [source.source.source_id, category.value, identity]
                candidates.append(ConflictCandidate(
                    candidate_id=_id("PCC", key),
                    label=category.value.replace("_", " ").title(),
                    value={"artifact_type": category.value},
                    project_item_ids=[item.project_item_id],
                    supporting_sources=[source.source],
                ))
            candidates.sort(key=lambda item: item.candidate_id)
            fingerprint = _digest({
                "source_id": source.source.source_id,
                "source_fingerprint": source.source.source_fingerprint,
                "candidates": [
                    item.model_dump(mode="json") for item in candidates
                ],
            })
            conflicts.append(ProjectConflict(
                conflict_id=_id("PCF", [
                    "TEXT_ARTIFACT_TYPE_CONFIRMATION",
                    source.source.source_id,
                    fingerprint,
                ]),
                conflict_type="TEXT_ARTIFACT_TYPE_CONFIRMATION",
                artifact_type=ArtifactDetectionLabel.OTHER_CONTEXT,
                candidates=candidates,
                allowed_actions=[ConflictAction.SELECT_CANDIDATE],
                fingerprint=fingerprint,
            ))
        retained.sort(key=lambda item: item.project_item_id)
        return retained, sorted(conflicts, key=lambda item: item.conflict_id)

    @staticmethod
    def _text_item_data(kind, content):
        value = ProjectConsolidationService._text_data(kind, content)
        key = COLLECTION_KEYS.get(kind)
        if key and isinstance(value.get(key), list) and value[key]:
            return value[key][0]
        return value

    @staticmethod
    def _text_category(value):
        direct = ArtifactDetectionLabel._value2member_map_.get(value.value)
        if direct:
            return direct
        if value in {
            ImplementationArtifactType.UNIT_TEST_CASES,
            ImplementationArtifactType.API_TEST_CASES,
            ImplementationArtifactType.INTEGRATION_TEST_CASES,
            ImplementationArtifactType.FUNCTIONAL_TEST_CASES,
            ImplementationArtifactType.E2E_TEST_CASES,
            ImplementationArtifactType.SECURITY_TEST_CASES,
            ImplementationArtifactType.ACCEPTANCE_TEST_CASES,
        }:
            return ArtifactDetectionLabel.TEST_CASES
        if value is ImplementationArtifactType.UML_DIAGRAMS:
            return ArtifactDetectionLabel.SYSTEM_ARCHITECTURE
        if value is ImplementationArtifactType.UI_WIREFRAMES:
            return ArtifactDetectionLabel.UI_FLOW
        if value is ImplementationArtifactType.PRODUCT_BACKLOG:
            return ArtifactDetectionLabel.IMPLEMENTATION_TASKS
        return ArtifactDetectionLabel.OTHER_CONTEXT

    @staticmethod
    def _text_data(kind, content):
        key = COLLECTION_KEYS.get(kind)
        if kind in {
            ArtifactDetectionLabel.FUNCTIONAL_REQUIREMENTS,
            ArtifactDetectionLabel.NON_FUNCTIONAL_REQUIREMENTS,
            ArtifactDetectionLabel.ACCEPTANCE_CRITERIA,
            ArtifactDetectionLabel.TECHNICAL_CONSTRAINTS,
        }:
            value = {"statement": content}
        elif kind is ArtifactDetectionLabel.IMPLEMENTATION_TASKS:
            value = {"title": content}
        elif kind is ArtifactDetectionLabel.OTHER_CONTEXT:
            value = {"text": content}
        else:
            value = {"text": content}
        return {key: [value]} if key else value

    @staticmethod
    def _status(inputs, conflicts, issues):
        pending = any(
            item.status is ConflictStatus.PENDING for item in conflicts
        )
        if pending:
            return ConsolidationStatus.WAITING_FOR_HUMAN
        if issues and inputs:
            return ConsolidationStatus.PARTIAL_FAILURE
        if issues and not inputs:
            return ConsolidationStatus.FAILED
        if inputs:
            return ConsolidationStatus.READY
        return ConsolidationStatus.FAILED

    def _finalize(self, record):
        excluded = set()
        for conflict in record.conflicts:
            if conflict.action is ConflictAction.SELECT_CANDIDATE:
                excluded.update(
                    item
                    for candidate in conflict.candidates
                    if candidate.candidate_id != conflict.selected_candidate_id
                    for item in candidate.project_item_ids
                )
            elif conflict.action is ConflictAction.EXCLUDE_CANDIDATE:
                excluded.update(
                    item
                    for candidate in conflict.candidates
                    if candidate.candidate_id == conflict.selected_candidate_id
                    for item in candidate.project_item_ids
                )
        items = [
            item for item in record.items
            if item.project_item_id not in excluded
        ]
        categories = {}
        for item in items:
            categories.setdefault(item.artifact_type, []).append(item)
        decisions = [
            item for item in record.conflicts
            if item.status is ConflictStatus.RESOLVED
        ]
        decision_digest = _digest([
            item.model_dump(mode="json") for item in decisions
        ])
        final = TrustedProjectSpecification(
            project_specification_id=_id("TPS", [
                record.agent_project_id,
                record.source_set_digest,
                decision_digest,
            ]),
            agent_project_id=record.agent_project_id,
            status=ConsolidationStatus.READY,
            categories=categories,
            relationships=explicit_relationships(items),
            source_artifact_refs=sorted({
                ref for item in items for ref in item.source_artifact_ids
            }),
            conflict_decisions=decisions,
            traceability={
                item.project_item_id: item.supporting_sources for item in items
            },
            source_set_digest=record.source_set_digest,
            decision_digest=decision_digest,
            schema_version=PROJECT_SPECIFICATION_SCHEMA_VERSION,
            created_at=self._clock(),
        )
        self._storage.save_final(final)

    @staticmethod
    def _public(record):
        source_ids = (
            {ref.source_id for ref in record.source_refs}
            | {issue.source_id for issue in record.issues}
        )
        return ProjectConsolidationStatusResponse(
            agent_project_id=record.agent_project_id,
            status=record.status,
            source_count=len(source_ids),
            item_count=len(record.items),
            conflict_count=len(record.conflicts),
            pending_conflict_count=sum(
                item.status is ConflictStatus.PENDING
                for item in record.conflicts
            ),
            issue_count=len(record.issues),
            source_set_digest=record.source_set_digest,
            issues=record.issues,
            updated_at=record.updated_at,
        )
