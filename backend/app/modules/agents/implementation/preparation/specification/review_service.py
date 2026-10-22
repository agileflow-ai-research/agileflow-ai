import copy
import hashlib
import json
import re
from datetime import datetime, timezone
from threading import RLock
from typing import Any

from pydantic import ValidationError

from app.modules.agents.implementation.infrastructure.storage import (
    ImplementationUploadStorage,
)
from app.modules.agents.implementation.preparation.canonical.schemas import (
    CanonicalArtifact,
    DocumentCanonicalArtifactResult,
)
from app.modules.agents.implementation.preparation.canonical.service import (
    CanonicalArtifactService,
)
from app.modules.agents.implementation.preparation.semantic_extraction.artifact_service import (
    SemanticArtifactService,
)
from app.modules.agents.implementation.preparation.semantic_extraction.schemas import (
    DocumentSemanticArtifactResult,
    FieldOrigin,
    SemanticArtifactRunStatus,
)
from app.modules.auth.schemas import UserPublicResponse

from .constants import (
    FINAL_TRUSTED_SCHEMA_VERSION,
    SEMANTIC_REVIEW_SCHEMA_VERSION,
    FinalArtifactStatus,
    FinalFieldOrigin,
    SemanticDecisionAction,
    SemanticDecisionKind,
    SemanticReviewStatus,
)
from .schemas import (
    DocumentFinalTrustedArtifacts,
    DocumentSemanticReviewState,
    FinalFieldProvenance,
    FinalTrustedArtifact,
    SemanticDecisionUpdate,
    SemanticReviewItem,
)


_TOKEN = re.compile(r"([^.\[\]]+)|\[(\d+)\]")


class SemanticReviewNotFoundError(LookupError):
    pass


class SemanticDecisionNotFoundError(LookupError):
    pass


class SemanticDecisionValidationError(ValueError):
    pass


class StaleSemanticReviewError(ValueError):
    pass


class FinalTrustedArtifactsNotFoundError(LookupError):
    pass


class FinalTrustedArtifactsNotReadyError(ValueError):
    pass


class SemanticReviewStorageError(RuntimeError):
    pass


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class SemanticReviewService:
    """Validates semantic decisions against current grounded server output."""

    _lock = RLock()

    def __init__(
        self,
        storage: ImplementationUploadStorage,
        canonical_service: CanonicalArtifactService,
        semantic_service: SemanticArtifactService,
        *,
        clock=utc_now,
    ) -> None:
        self._storage = storage
        self._canonical = canonical_service
        self._semantic = semantic_service
        self._clock = clock

    def prepare(
        self,
        agent_project_id: str,
        upload_id: str,
        current_user: UserPublicResponse,
    ) -> DocumentSemanticReviewState:
        canonical = self._canonical.get_existing(
            agent_project_id, upload_id, current_user
        )
        semantic = self._semantic.get_existing(
            agent_project_id, upload_id, current_user
        )
        if any(
            item.status in {
                SemanticArtifactRunStatus.MODEL_ERROR,
                SemanticArtifactRunStatus.MODEL_OUTPUT_INVALID,
            }
            for item in semantic.results
        ):
            raise SemanticReviewNotFoundError(
                "Semantic preparation did not produce a reviewable result"
            )
        staged = self._storage.locate(
            agent_project_id=agent_project_id,
            owner_user_id=current_user.user_id,
            upload_id=upload_id,
        )
        semantic_digest = self._digest(staged.semantic_artifacts_path)
        fresh = self._fresh_state(canonical, semantic, semantic_digest)
        with self._lock:
            saved = self._load_review(staged.semantic_reviews_path)
            if saved is not None and self._same_identity(saved, fresh):
                decisions = {
                    item.decision_id: (
                        item.decision,
                        item.reviewer_owner_id,
                        item.decided_at,
                    )
                    for item in saved.items
                    if item.decision is not None
                }
                for item in fresh.items:
                    decision = decisions.get(item.decision_id)
                    if decision and decision[0] in item.allowed_actions:
                        (
                            item.decision,
                            item.reviewer_owner_id,
                            item.decided_at,
                        ) = decision
                self._finish_state(fresh)
            self._persist(staged.semantic_reviews_partial_path,
                          staged.semantic_reviews_path, fresh)
            if fresh.status is SemanticReviewStatus.COMPLETE:
                self._build_final(staged, canonical, semantic, fresh)
        return fresh

    def get_state(self, agent_project_id, upload_id, current_user):
        return self.prepare(agent_project_id, upload_id, current_user)

    def save_decision(
        self,
        agent_project_id: str,
        upload_id: str,
        decision_id: str,
        request: SemanticDecisionUpdate,
        current_user: UserPublicResponse,
    ) -> DocumentSemanticReviewState:
        with self._lock:
            state = self.prepare(agent_project_id, upload_id, current_user)
            if request.expected_review_fingerprint != state.review_fingerprint:
                raise StaleSemanticReviewError("STALE_SEMANTIC_REVIEW")
            item = next(
                (candidate for candidate in state.items
                 if candidate.decision_id == decision_id),
                None,
            )
            if item is None:
                raise SemanticDecisionNotFoundError(decision_id)
            if request.action not in item.allowed_actions:
                raise SemanticDecisionValidationError(
                    "Decision is not allowed for this grounded proposal"
                )
            item.decision = request.action
            item.reviewer_owner_id = current_user.user_id
            item.decided_at = self._clock()
            self._finish_state(state)
            canonical = self._canonical.get_existing(
                agent_project_id, upload_id, current_user
            )
            semantic = self._semantic.get_existing(
                agent_project_id, upload_id, current_user
            )
            staged = self._storage.locate(
                agent_project_id=agent_project_id,
                owner_user_id=current_user.user_id,
                upload_id=upload_id,
            )
            self._persist(staged.semantic_reviews_partial_path,
                          staged.semantic_reviews_path, state)
            if state.status is SemanticReviewStatus.COMPLETE:
                self._build_final(staged, canonical, semantic, state)
        return state

    def build_deterministic_final(
        self,
        canonical: DocumentCanonicalArtifactResult,
        current_user: UserPublicResponse,
    ) -> DocumentFinalTrustedArtifacts:
        staged = self._storage.locate(
            agent_project_id=canonical.agent_project_id,
            owner_user_id=current_user.user_id,
            upload_id=canonical.upload_id,
        )
        result = self._final_result(
            canonical,
            None,
            None,
            canonical_digest=self._digest(staged.canonical_artifacts_path),
        )
        with self._lock:
            return self._persist_final_if_changed(staged, result)

    def get_final(self, agent_project_id, upload_id, current_user):
        canonical = self._canonical.get_existing(
            agent_project_id, upload_id, current_user
        )
        staged = self._storage.locate(
            agent_project_id=agent_project_id,
            owner_user_id=current_user.user_id,
            upload_id=upload_id,
        )
        try:
            result = DocumentFinalTrustedArtifacts.model_validate_json(
                staged.trusted_artifacts_path.read_text(encoding="utf-8")
            )
        except (FileNotFoundError, OSError, ValidationError) as exc:
            raise FinalTrustedArtifactsNotFoundError(upload_id) from exc
        canonical_digest = self._digest(staged.canonical_artifacts_path)
        if (
            result.agent_project_id != canonical.agent_project_id
            or result.upload_id != canonical.upload_id
            or result.source_sha256 != canonical.source_sha256
            or result.human_review_fingerprint
            != canonical.human_review_fingerprint
            or result.canonical_artifact_digest != canonical_digest
            or result.schema_version != FINAL_TRUSTED_SCHEMA_VERSION
        ):
            raise FinalTrustedArtifactsNotFoundError(upload_id)
        if result.semantic_artifact_digest is not None:
            semantic = self._semantic.get_existing(
                agent_project_id, upload_id, current_user
            )
            semantic_digest = self._digest(staged.semantic_artifacts_path)
            state = self.prepare(agent_project_id, upload_id, current_user)
            if (
                semantic.source_sha256 != canonical.source_sha256
                or result.semantic_artifact_digest != semantic_digest
                or result.semantic_review_fingerprint
                != state.review_fingerprint
                or result.human_decision_digest
                != self._decision_digest(state.items)
                or state.status is not SemanticReviewStatus.COMPLETE
            ):
                raise FinalTrustedArtifactsNotFoundError(upload_id)
        return result

    def _fresh_state(self, canonical, semantic, semantic_digest):
        items = []
        for result in semantic.results:
            preview = result.merged_preview
            if preview is None:
                continue
            for provenance in preview.field_provenance:
                if provenance.origin is not FieldOrigin.SEMANTIC:
                    continue
                value = self._get(preview.data, provenance.field_path)
                if value is _MISSING:
                    continue
                items.append(self._review_item(
                    semantic_digest, result.artifact_id,
                    result.artifact_type, SemanticDecisionKind.ADDITION,
                    provenance.field_path, None, value,
                    provenance.evidence,
                    [SemanticDecisionAction.APPROVE_ADDITION,
                     SemanticDecisionAction.REJECT_ADDITION],
                ))
            for conflict in preview.conflicts:
                allowed = [SemanticDecisionAction.KEEP_DETERMINISTIC]
                if conflict.deterministic_value is not None:
                    allowed.append(
                        SemanticDecisionAction.ACCEPT_SEMANTIC_OVERRIDE
                    )
                items.append(self._review_item(
                    semantic_digest, result.artifact_id,
                    result.artifact_type, SemanticDecisionKind.CONFLICT,
                    conflict.field_path, conflict.deterministic_value,
                    conflict.semantic_value, conflict.semantic_evidence,
                    allowed,
                ))
        items.sort(key=lambda item: item.decision_id)
        review_fingerprint = self._review_fingerprint(
            canonical, semantic_digest, items
        )
        state = DocumentSemanticReviewState(
            agent_project_id=canonical.agent_project_id,
            upload_id=canonical.upload_id,
            original_filename=canonical.original_filename,
            source_sha256=canonical.source_sha256,
            human_review_fingerprint=canonical.human_review_fingerprint,
            canonical_artifact_digest=semantic.canonical_artifact_digest,
            semantic_artifact_digest=semantic_digest,
            review_fingerprint=review_fingerprint,
            schema_version=SEMANTIC_REVIEW_SCHEMA_VERSION,
            status=SemanticReviewStatus.PENDING,
            items=items,
            updated_at=self._clock(),
        )
        self._finish_state(state)
        return state

    def _review_item(
        self, semantic_digest, artifact_id, artifact_type, kind,
        field_path, deterministic_value, semantic_value, evidence, allowed,
    ):
        identity = self._stable_json({
            "semantic_digest": semantic_digest,
            "artifact_id": artifact_id,
            "kind": kind.value,
            "field_path": field_path,
            "deterministic_value": deterministic_value,
            "semantic_value": semantic_value,
            "evidence": [item.model_dump(mode="json") for item in evidence],
        })
        decision_id = "SRD-" + hashlib.sha256(
            identity.encode("utf-8")
        ).hexdigest()[:24].upper()
        return SemanticReviewItem(
            decision_id=decision_id,
            artifact_id=artifact_id,
            artifact_type=artifact_type,
            kind=kind,
            field_path=field_path,
            deterministic_value=deterministic_value,
            semantic_value=semantic_value,
            evidence=evidence,
            allowed_actions=allowed,
        )

    def _build_final(self, staged, canonical, semantic, review):
        result = self._final_result(canonical, semantic, review)
        return self._persist_final_if_changed(staged, result)

    def _persist_final_if_changed(self, staged, result):
        try:
            current = DocumentFinalTrustedArtifacts.model_validate_json(
                staged.trusted_artifacts_path.read_text(encoding="utf-8")
            )
        except (FileNotFoundError, OSError, ValidationError):
            current = None
        if current is not None and self._same_final_identity(current, result):
            return current
        self._persist(
            staged.trusted_artifacts_partial_path,
            staged.trusted_artifacts_path,
            result,
        )
        return result

    @staticmethod
    def _same_final_identity(current, fresh):
        return (
            current.agent_project_id == fresh.agent_project_id
            and current.upload_id == fresh.upload_id
            and current.source_sha256 == fresh.source_sha256
            and current.human_review_fingerprint
            == fresh.human_review_fingerprint
            and current.canonical_artifact_digest
            == fresh.canonical_artifact_digest
            and current.semantic_artifact_digest
            == fresh.semantic_artifact_digest
            and current.semantic_review_fingerprint
            == fresh.semantic_review_fingerprint
            and current.human_decision_digest == fresh.human_decision_digest
            and current.schema_version == fresh.schema_version
        )

    @classmethod
    def _decision_digest(cls, items):
        value = cls._stable_json([
            {
                "decision_id": item.decision_id,
                "decision": item.decision.value if item.decision else None,
                "reviewer_owner_id": item.reviewer_owner_id,
                "decided_at": (
                    item.decided_at.isoformat() if item.decided_at else None
                ),
            }
            for item in items
        ])
        return hashlib.sha256(value.encode("utf-8")).hexdigest()

    def _final_result(
        self, canonical, semantic, review, *, canonical_digest=None
    ):
        semantic_digest = (
            review.semantic_artifact_digest if review is not None else None
        )
        canonical_digest = review.canonical_artifact_digest if review else (
            canonical_digest or self._canonical_digest_from_result(canonical)
        )
        semantic_results = {
            item.artifact_id: item for item in semantic.results
        } if semantic is not None else {}
        decisions = review.items if review is not None else []
        artifacts = [
            self._final_artifact(
                artifact,
                semantic_results.get(artifact.artifact_id),
                [item for item in decisions
                 if item.artifact_id == artifact.artifact_id],
                semantic_digest,
            )
            for artifact in canonical.artifacts
        ]
        return DocumentFinalTrustedArtifacts(
            agent_project_id=canonical.agent_project_id,
            upload_id=canonical.upload_id,
            original_filename=canonical.original_filename,
            source_sha256=canonical.source_sha256,
            human_review_fingerprint=canonical.human_review_fingerprint,
            canonical_artifact_digest=canonical_digest,
            semantic_artifact_digest=semantic_digest,
            semantic_review_fingerprint=(
                review.review_fingerprint if review is not None else None
            ),
            human_decision_digest=(
                self._decision_digest(review.items)
                if review is not None else None
            ),
            schema_version=FINAL_TRUSTED_SCHEMA_VERSION,
            artifacts=artifacts,
            created_at=self._clock(),
        )

    def _final_artifact(
        self, canonical: CanonicalArtifact, semantic_result,
        decisions, semantic_digest,
    ):
        data = copy.deepcopy(canonical.data.model_dump(
            mode="python", by_alias=True
        ))
        provenance = self._deterministic_provenance(
            data, canonical.source_refs
        )
        for item in decisions:
            if item.decision is SemanticDecisionAction.APPROVE_ADDITION:
                self._set(data, item.field_path, copy.deepcopy(item.semantic_value))
                self._replace_provenance(
                    provenance, item, FinalFieldOrigin.SEMANTIC_HUMAN_APPROVED,
                    canonical.source_refs,
                )
            elif item.decision is SemanticDecisionAction.ACCEPT_SEMANTIC_OVERRIDE:
                self._set(data, item.field_path, copy.deepcopy(item.semantic_value))
                self._replace_provenance(
                    provenance, item, FinalFieldOrigin.SEMANTIC_HUMAN_OVERRIDE,
                    canonical.source_refs,
                )
        identity = self._stable_json({
            "canonical_artifact_id": canonical.artifact_id,
            "semantic_digest": semantic_digest,
            "decisions": [item.model_dump(mode="json") for item in decisions],
            "schema_version": FINAL_TRUSTED_SCHEMA_VERSION,
        })
        return FinalTrustedArtifact(
            final_artifact_id="FTA-" + hashlib.sha256(
                identity.encode("utf-8")
            ).hexdigest()[:24].upper(),
            artifact_type=canonical.artifact_type,
            status=FinalArtifactStatus.TRUSTED,
            data=data,
            field_provenance=provenance,
            source_refs=canonical.source_refs,
            human_decisions=decisions,
            canonical_artifact_id=canonical.artifact_id,
            semantic_preview_id=(
                f"{semantic_digest}:{semantic_result.artifact_id}"
                if semantic_digest and semantic_result else None
            ),
            schema_version=FINAL_TRUSTED_SCHEMA_VERSION,
            created_at=self._clock(),
        )

    def _finish_state(self, state):
        state.status = (
            SemanticReviewStatus.COMPLETE
            if all(item.decision is not None for item in state.items)
            else SemanticReviewStatus.PENDING
        )
        state.updated_at = self._clock()

    @staticmethod
    def _same_identity(saved, fresh):
        return (
            saved.agent_project_id == fresh.agent_project_id
            and saved.upload_id == fresh.upload_id
            and saved.source_sha256 == fresh.source_sha256
            and saved.human_review_fingerprint
            == fresh.human_review_fingerprint
            and saved.canonical_artifact_digest
            == fresh.canonical_artifact_digest
            and saved.semantic_artifact_digest
            == fresh.semantic_artifact_digest
            and saved.review_fingerprint == fresh.review_fingerprint
            and saved.schema_version == fresh.schema_version
        )

    @staticmethod
    def _review_fingerprint(canonical, semantic_digest, items):
        value = SemanticReviewService._stable_json({
            "source_sha256": canonical.source_sha256,
            "human_review_fingerprint": canonical.human_review_fingerprint,
            "semantic_digest": semantic_digest,
            "schema_version": SEMANTIC_REVIEW_SCHEMA_VERSION,
            "items": [item.model_dump(
                mode="json",
                exclude={"decision", "reviewer_owner_id", "decided_at"},
            ) for item in items],
        })
        return hashlib.sha256(value.encode("utf-8")).hexdigest()

    @staticmethod
    def _load_review(path):
        try:
            return DocumentSemanticReviewState.model_validate_json(
                path.read_text(encoding="utf-8")
            )
        except (FileNotFoundError, OSError, ValidationError):
            return None

    @staticmethod
    def _persist(partial, destination, value):
        try:
            partial.write_text(value.model_dump_json(by_alias=True),
                               encoding="utf-8")
            partial.replace(destination)
        except OSError as exc:
            try:
                partial.unlink(missing_ok=True)
            except OSError:
                pass
            raise SemanticReviewStorageError(
                "Semantic review state could not be stored"
            ) from exc

    @staticmethod
    def _digest(path):
        try:
            return hashlib.sha256(path.read_bytes()).hexdigest()
        except OSError as exc:
            raise SemanticReviewStorageError(
                "Semantic review dependency is unavailable"
            ) from exc

    @staticmethod
    def _canonical_digest_from_result(canonical):
        return hashlib.sha256(
            canonical.model_dump_json(by_alias=True).encode("utf-8")
        ).hexdigest()

    @staticmethod
    def _stable_json(value):
        return json.dumps(value, sort_keys=True, separators=(",", ":"),
                          ensure_ascii=False)

    @staticmethod
    def _tokens(path):
        tokens = [
            int(index) if index else name
            for name, index in _TOKEN.findall(path)
        ]
        if not tokens or "=" in path:
            raise SemanticDecisionValidationError(
                "Semantic field path cannot be safely applied"
            )
        return tokens

    @classmethod
    def _get(cls, root, path):
        try:
            current = root
            for token in cls._tokens(path):
                current = current[token]
            return current
        except (KeyError, IndexError, TypeError,
                SemanticDecisionValidationError):
            return _MISSING

    @classmethod
    def _set(cls, root, path, value):
        tokens = cls._tokens(path)
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

    @staticmethod
    def _deterministic_provenance(data, source_refs):
        result = []

        def visit(value: Any, path: str):
            if isinstance(value, dict):
                for key, child in value.items():
                    if key != "source_refs":
                        visit(child, f"{path}.{key}" if path else key)
            elif isinstance(value, list):
                for index, child in enumerate(value):
                    visit(child, f"{path}[{index}]")
            elif value is not None:
                result.append(FinalFieldProvenance(
                    field_path=path,
                    origin=FinalFieldOrigin.DETERMINISTIC,
                    source_refs=source_refs,
                ))

        visit(data, "")
        return result

    @staticmethod
    def _replace_provenance(provenance, item, origin, source_refs):
        provenance[:] = [
            value for value in provenance
            if value.field_path != item.field_path
        ]
        provenance.append(FinalFieldProvenance(
            field_path=item.field_path,
            origin=origin,
            source_refs=source_refs,
            evidence=item.evidence,
            decision_id=item.decision_id,
        ))


_MISSING = object()
