from app.modules.agents.requirements.quality.input import QualityInputError
from app.modules.agents.requirements.quality.storage import QualityStorageError
from app.modules.agents.requirements.workflow.contracts.n4 import RequirementN4ResultSummary, RequirementN4Status
from app.modules.agents.requirements.workflow.orchestration.n4_transitions import blocked, complete, failed, n4_by_id, running
from app.modules.agents.requirements.workflow.storage import WORKFLOW_STATE_LOCK


class RequirementN4Runner:
    def __init__(self, states, inputs, exact, semantic, conflicts, clarity, findings, artifacts, *, clock):
        self._states=states; self._inputs=inputs; self._exact=exact; self._semantic=semantic
        self._conflicts=conflicts; self._clarity=clarity; self._findings=findings
        self._artifacts=artifacts; self._clock=clock

    def run(self, project, owner, execution_id):
        stage="input"
        try:
            with WORKFLOW_STATE_LOCK:
                record=self._require(project,owner); execution=n4_by_id(record,execution_id)
                if execution is None or execution.status is not RequirementN4Status.QUEUED: return
                running(record,execution,at=self._clock()); self._states.save(record)
            value=self._inputs.load(agent_project_id=project,owner_user_id=owner)
            if value.input_identity != execution.quality_input_identity: self._block(project,owner,execution_id); return
            digests={"quality_input":self._artifacts.save_input(project,execution_id,value)}
            stage="exact"; exact=self._exact.detect(value); digests["exact"]=self._artifacts.save_exact(project,execution_id,exact)
            stage="semantic"; semantic=self._semantic.detect(value,exact); digests["semantic"]=self._artifacts.save_semantic(project,execution_id,semantic)
            stage="conflict"; conflicts=self._conflicts.detect(value,exact,semantic); digests["conflicts"]=self._artifacts.save_conflicts(project,execution_id,conflicts)
            stage="clarity"; clarity=self._clarity.analyze(value); digests["clarity"]=self._artifacts.save_clarity(project,execution_id,clarity)
            stage="findings"; findings=self._findings.consolidate(value,exact,semantic,conflicts,clarity); digests["findings"]=self._artifacts.save_findings(project,execution_id,findings)
            summary=RequirementN4ResultSummary(
                quality_input_identity=value.input_identity, analyzed_requirement_count=len(value.requirements),
                exact_duplicate_group_count=exact.duplicate_group_count,
                exact_duplicate_affected_requirement_count=exact.affected_requirement_count,
                semantic_duplicate_pair_count=semantic.pair_count,
                potential_pair_count=conflicts.total_potential_pair_count,
                nli_evaluated_pair_count=conflicts.nli_evaluated_pair_count,
                conflict_count=conflicts.conflict_count, ambiguity_count=clarity.ambiguity_count,
                missing_information_count=clarity.missing_information_count,
                clarity_affected_requirement_count=clarity.affected_requirement_count,
                total_finding_count=findings.total_findings,
                clarification_candidate_count=findings.clarification_candidate_count,
                total_affected_requirement_count=findings.affected_requirement_count,
                finding_counts={"EXACT_DUPLICATE":findings.exact_duplicate_findings,"SEMANTIC_DUPLICATE":findings.semantic_duplicate_findings,"CONFLICT":findings.conflict_findings,"AMBIGUITY":findings.ambiguity_findings,"MISSING_INFORMATION":findings.missing_information_findings},
                artifact_digests=digests, execution_configuration_fingerprint=execution.configuration_fingerprint,
                detector_fingerprints={"exact":exact.detector_fingerprint,"semantic":semantic.detector_fingerprint,"conflict":conflicts.detector_fingerprint,"clarity":clarity.detector_fingerprint,"findings":findings.consolidation_fingerprint},
            )
            with WORKFLOW_STATE_LOCK:
                record=self._require(project,owner); persisted=n4_by_id(record,execution_id)
                complete(record,persisted,summary,at=self._clock()); self._states.save(record)
        except QualityInputError: self._block(project,owner,execution_id)
        except Exception: self._fail(project,owner,execution_id,"QUALITY_EXECUTION_"+stage.upper()+"_FAILED","Quality execution failed safely.")

    def _require(self,p,o):
        r=self._states.load(agent_project_id=p,owner_user_id=o)
        if r is None: raise RuntimeError("Workflow unavailable")
        return r
    def _block(self,p,o,i):
        with WORKFLOW_STATE_LOCK:
            r=self._require(p,o); e=n4_by_id(r,i)
            if e and e.status not in {RequirementN4Status.COMPLETE,RequirementN4Status.BLOCKED}: blocked(r,e,at=self._clock()); self._states.save(r)
    def _fail(self,p,o,i,code,message):
        with WORKFLOW_STATE_LOCK:
            r=self._require(p,o); e=n4_by_id(r,i)
            if e and e.status not in {RequirementN4Status.COMPLETE,RequirementN4Status.BLOCKED}: failed(r,e,code,message,at=self._clock()); self._states.save(r)
