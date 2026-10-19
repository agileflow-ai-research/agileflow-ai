from datetime import datetime, timezone

from app.modules.agents.implementation.inputs.upload.service import require_implementation_project
from app.modules.agents.implementation.preparation.consolidation.constants import ConsolidationStatus
from app.modules.agents.implementation.preparation.readiness.schemas import FindingSeverity, ReadinessStatus
from app.modules.agents.implementation.preparation.schemas import ArtifactDetectionLabel

from .constants import (EFFECTIVE_STACK, OUTPUT_POLICY,
                        TRUSTED_READINESS_POLICY_VERSION,
                        TRUSTED_READINESS_SCHEMA_VERSION)
from .policy import digest, evaluate_output_policy, evaluate_stack, finding
from .schemas import (TrustedCoverageItem, TrustedOutputReadiness,
                      TrustedReadinessSnapshot, TrustedStackAdaptation)


class StaleStackAdaptationError(ValueError):
    pass


class TrustedReadinessNotFoundError(LookupError):
    pass


def utc_now():
    return datetime.now(timezone.utc)


class TrustedReadinessService:
    def __init__(self, standalone_service, consolidation_service, storage, *, clock=utc_now):
        self._standalone = standalone_service
        self._consolidation = consolidation_service
        self._storage = storage
        self._clock = clock

    def evaluate(self, project_id, request, current_user):
        require_implementation_project(self._standalone, project_id, current_user)
        status = self._consolidation.get_status(project_id, current_user)
        outputs_digest = digest(sorted(item.value for item in request.selected_outputs))
        if status.status is not ConsolidationStatus.READY:
            result = self._blocked_precondition(project_id, status.status,
                                                request.selected_outputs,
                                                outputs_digest)
            self._storage.save(result)
            return result

        specification = self._consolidation.get_final(project_id, current_user)
        if (
            specification.status is not ConsolidationStatus.READY
            or not self._valid_specification(project_id, specification)
        ):
            result = self._blocked_precondition(project_id, specification.status,
                                                request.selected_outputs,
                                                outputs_digest)
            self._storage.save(result)
            return result

        categories = {category: list(items) for category, items in specification.categories.items()}
        findings = evaluate_output_policy(request.selected_outputs, categories)
        stack_findings = evaluate_stack(
            categories.get(ArtifactDetectionLabel.TECHNOLOGY_STACK, [])
        )
        adaptation_fp = digest({
            "project_id": project_id,
            "project_specification_id": specification.project_specification_id,
            "decision_digest": specification.decision_digest,
            "policy_version": TRUSTED_READINESS_POLICY_VERSION,
            "stack_findings": [(item.provided_value, item.supported_value,
                                item.related_project_item_ids)
                               for item in stack_findings],
        })
        adaptation = None
        if request.stack_adaptation is not None:
            if not stack_findings:
                raise StaleStackAdaptationError("STACK_ADAPTATION_NOT_REQUIRED")
            if request.stack_adaptation.expected_fingerprint != adaptation_fp:
                raise StaleStackAdaptationError("STALE_STACK_ADAPTATION")
            adaptation = TrustedStackAdaptation(
                decision=request.stack_adaptation.decision,
                fingerprint=adaptation_fp, approved=True,
                note=request.stack_adaptation.note, approved_at=self._clock(),
            )
            for item in stack_findings:
                item.resolved = True
        elif stack_findings:
            adaptation = TrustedStackAdaptation(
                decision="ADAPT_TO_SUPPORTED_STACK", fingerprint=adaptation_fp,
                approved=False,
            )
        findings.extend(stack_findings)
        result = self._snapshot(
            project_id, request.selected_outputs, outputs_digest, findings,
            categories, specification=specification, adaptation=adaptation,
        )
        self._storage.save(result)
        return result

    def get(self, project_id, current_user):
        require_implementation_project(self._standalone, project_id, current_user)
        result = self._storage.load(project_id)
        if result is None:
            raise TrustedReadinessNotFoundError(project_id)
        status = self._consolidation.get_status(project_id, current_user)
        current = (
            result.policy_version == TRUSTED_READINESS_POLICY_VERSION
            and status.status is ConsolidationStatus.READY
            and status.source_set_digest == result.source_set_digest
        )
        if current:
            try:
                specification = self._consolidation.get_final(project_id, current_user)
                current = (
                    self._valid_specification(project_id, specification)
                    and
                    specification.project_specification_id == result.project_specification_id
                    and specification.decision_digest == result.project_specification_decision_digest
                )
            except Exception:
                current = False
        if not current:
            return result.model_copy(update={"current": False})
        return result

    @staticmethod
    def _valid_specification(project_id, specification):
        expected_id = "TPS-" + digest([
            project_id,
            specification.source_set_digest,
            specification.decision_digest,
        ])[:24].upper()
        return (
            specification.agent_project_id == project_id
            and specification.project_specification_id == expected_id
        )

    def _blocked_precondition(self, project_id, status, outputs, outputs_digest):
        mapping = {
            ConsolidationStatus.STALE: ("PROJECT_SPECIFICATION_STALE", "Project specification is stale"),
            ConsolidationStatus.WAITING_FOR_HUMAN: ("PROJECT_SPECIFICATION_REVIEW_REQUIRED", "Project specification review required"),
            ConsolidationStatus.FAILED: ("PROJECT_SPECIFICATION_FAILED", "Project specification failed"),
            ConsolidationStatus.PARTIAL_FAILURE: ("PROJECT_SPECIFICATION_FAILED", "Project specification is incomplete"),
        }
        code, title = mapping.get(status, ("PROJECT_SPECIFICATION_NOT_READY", "Project specification is not ready"))
        issue = finding(code, FindingSeverity.ERROR, title,
                        "A current READY trusted project specification is required before implementation readiness can be trusted.",
                        outputs=outputs)
        return self._snapshot(project_id, outputs, outputs_digest, [issue], {})

    def _snapshot(self, project_id, outputs, outputs_digest, findings, categories,
                  *, specification=None, adaptation=None):
        unresolved_errors = [item for item in findings if item.severity is FindingSeverity.ERROR and not item.resolved]
        unresolved_warnings = [item for item in findings if item.severity is FindingSeverity.WARNING and not item.resolved]
        status = (ReadinessStatus.NOT_READY if unresolved_errors else
                  ReadinessStatus.READY_WITH_WARNINGS if unresolved_warnings else
                  ReadinessStatus.READY)
        relevant_categories = sorted({category for output in outputs
                                      for group in OUTPUT_POLICY[output]["required"]
                                      for category in group} |
                                     {category for output in outputs
                                      for category in OUTPUT_POLICY[output]["recommended"]},
                                     key=lambda item: item.value)
        coverage = [TrustedCoverageItem(
            category=category, present=bool(categories.get(category)),
            project_item_ids=[item.project_item_id for item in categories.get(category, [])],
        ) for category in relevant_categories]
        output_readiness = []
        for output in outputs:
            related = [item for item in findings if not item.related_selected_outputs or output in item.related_selected_outputs]
            blocked = any(item.severity is FindingSeverity.ERROR and not item.resolved for item in related)
            warned = any(item.severity is FindingSeverity.WARNING and not item.resolved for item in related)
            output_readiness.append(TrustedOutputReadiness(
                output=output,
                status=ReadinessStatus.NOT_READY if blocked else ReadinessStatus.READY_WITH_WARNINGS if warned else ReadinessStatus.READY,
                finding_ids=[item.finding_id for item in related],
            ))
        identity = {
            "project_id": project_id,
            "project_specification_id": getattr(specification, "project_specification_id", None),
            "decision_digest": getattr(specification, "decision_digest", None),
            "selected_outputs_digest": outputs_digest,
            "policy_version": TRUSTED_READINESS_POLICY_VERSION,
            "evaluated_at": self._clock().isoformat(),
        }
        return TrustedReadinessSnapshot(
            readiness_id="RDY-" + digest(identity)[:24].upper(),
            agent_project_id=project_id, status=status,
            selected_outputs=outputs,
            policy_version=TRUSTED_READINESS_POLICY_VERSION,
            schema_version=TRUSTED_READINESS_SCHEMA_VERSION,
            project_specification_id=getattr(specification, "project_specification_id", None),
            source_set_digest=getattr(specification, "source_set_digest", None),
            project_specification_decision_digest=getattr(specification, "decision_digest", None),
            selected_outputs_digest=outputs_digest,
            stack_adaptation=adaptation, coverage=coverage,
            output_readiness=output_readiness, findings=findings,
            effective_stack=EFFECTIVE_STACK, evaluated_at=self._clock(),
        )
