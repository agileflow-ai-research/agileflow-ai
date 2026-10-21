from app.modules.agents.requirements.discovery.classification.service import RequirementClassificationError
from app.modules.agents.requirements.discovery.input import DiscoveryInputError
from app.modules.agents.requirements.discovery.storage import DiscoveryStorageError
from app.modules.agents.requirements.discovery.structuring import RequirementStructuringError
from app.modules.agents.requirements.workflow.contracts.n3 import RequirementN3ResultSummary, RequirementN3Status
from app.modules.agents.requirements.workflow.orchestration.n3_transitions import (
    mark_n3_blocked, mark_n3_complete, mark_n3_failed, mark_n3_running,
    n3_execution_by_id,
)
from app.modules.agents.requirements.workflow.storage import WORKFLOW_STATE_LOCK


class RequirementN3Runner:
    def __init__(self, workflow_storage, input_loader, detector, classifier,
                 structuring, discovery_storage, *, clock):
        self._states = workflow_storage
        self._inputs = input_loader
        self._detector = detector
        self._classifier = classifier
        self._structuring = structuring
        self._artifacts = discovery_storage
        self._clock = clock

    def run(self, agent_project_id, owner_user_id, execution_id):
        stage = "input"
        try:
            with WORKFLOW_STATE_LOCK:
                record = self._require_record(agent_project_id, owner_user_id)
                execution = self._require_execution(record, execution_id)
                if execution.status is not RequirementN3Status.QUEUED:
                    return
                mark_n3_running(record, execution, started_at=self._clock(), updated_at=self._clock())
                self._states.save(record)
            input_value = self._inputs.load(agent_project_id=agent_project_id, owner_user_id=owner_user_id)
            if (input_value.reference.n2_execution_id != execution.n2_execution_id
                    or input_value.reference.chunk_set_digest != execution.chunk_set_digest
                    or input_value.input_identity != execution.discovery_input_identity
                    or self._detector.configuration_fingerprint != execution.candidate_detector_fingerprint
                    or self._classifier.model_identity.configuration_fingerprint != execution.classifier_configuration_fingerprint):
                self._block(agent_project_id, owner_user_id, execution_id)
                return
            stage = "candidate"
            candidates = self._detector.discover(input_value)
            candidate_digest = self._artifacts.save_candidates(agent_project_id, execution_id, candidates)
            stage = "classification"
            classifications = self._classifier.classify(candidates)
            classification_digest = self._artifacts.save_classifications(agent_project_id, execution_id, classifications)
            stage = "structuring"
            structured = self._structuring.structure(classifications)
            structured_digest = self._artifacts.save_structured_requirements(agent_project_id, execution_id, structured)
            summary = RequirementN3ResultSummary(
                candidate_count=len(candidates.candidates),
                functional_requirement_count=len(structured.functional_requirements),
                non_functional_requirement_count=len(structured.non_functional_requirements),
                excluded_candidate_count=len(structured.excluded_candidates),
                candidate_artifact_digest=candidate_digest,
                classification_artifact_digest=classification_digest,
                structured_artifact_digest=structured_digest,
                structured_set_identity=structured.structured_set_identity,
                classifier_configuration_fingerprint=classifications.model.configuration_fingerprint,
            )
            with WORKFLOW_STATE_LOCK:
                record = self._require_record(agent_project_id, owner_user_id)
                persisted = self._require_execution(record, execution_id)
                mark_n3_complete(record, persisted, summary, completed_at=self._clock(), updated_at=self._clock())
                self._states.save(record)
        except DiscoveryInputError:
            self._block(agent_project_id, owner_user_id, execution_id)
        except RequirementClassificationError:
            self._fail(agent_project_id, owner_user_id, execution_id, "N3_CLASSIFICATION_FAILED", "Requirement classification failed safely.")
        except RequirementStructuringError:
            self._fail(agent_project_id, owner_user_id, execution_id, "N3_STRUCTURING_FAILED", "Requirement structuring failed safely.")
        except DiscoveryStorageError:
            self._fail(agent_project_id, owner_user_id, execution_id, "N3_ARTIFACT_PERSISTENCE_FAILED", "Discovery artifacts could not be persisted.")
        except Exception:
            code = "N3_CANDIDATE_DISCOVERY_FAILED" if stage == "candidate" else "N3_EXECUTION_FAILED"
            self._fail(agent_project_id, owner_user_id, execution_id, code, "Requirement discovery failed safely.")

    def _block(self, project, owner, execution_id):
        with WORKFLOW_STATE_LOCK:
            record = self._require_record(project, owner); execution = self._require_execution(record, execution_id)
            mark_n3_blocked(record, execution, failed_at=self._clock(), updated_at=self._clock()); self._states.save(record)

    def _fail(self, project, owner, execution_id, code, message):
        with WORKFLOW_STATE_LOCK:
            record = self._require_record(project, owner); execution = self._require_execution(record, execution_id)
            if execution.status in {RequirementN3Status.COMPLETE, RequirementN3Status.BLOCKED}: return
            mark_n3_failed(record, execution, code, message, failed_at=self._clock(), updated_at=self._clock()); self._states.save(record)

    def _require_record(self, project, owner):
        record = self._states.load(agent_project_id=project, owner_user_id=owner)
        if record is None: raise RuntimeError("Workflow unavailable")
        return record

    @staticmethod
    def _require_execution(record, execution_id):
        execution = n3_execution_by_id(record, execution_id)
        if execution is None: raise RuntimeError("N3 execution unavailable")
        return execution
