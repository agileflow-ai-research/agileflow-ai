import { preparationToWorkflowState } from '../constants/preparation.js'
import { WORKFLOW_NODE_STATES } from '../constants/workflow.js'
import { deriveWorkflowGates } from './workflowGates.js'
import { inputHasSource } from './sourceState.js'

export function deriveWorkflowPresentation(snapshot) {
  const inputs = snapshot?.inputs ?? []
  const sourceCount = inputs.filter(inputHasSource).length
  const preparedCount = inputs.filter((item) => ['SUCCESS', 'PARTIAL'].includes(item.chunks?.status)).length
  const verifiedSourceCount = inputs.filter((item) => item.humanReviews?.review?.review_status === 'COMPLETE').length
  const attentionCount = inputs.filter((item) => item.error || item.extraction?.status === 'FAILED' || item.chunks?.status === 'FAILED').length
  const outputCount = snapshot?.selectedOutputs?.length ?? 0
  const readiness = snapshot?.readinessState
  const github = snapshot?.githubState
  const repository = snapshot?.repositoryState
  const preparation = snapshot?.preparationState?.result
  const specification = snapshot?.specificationState?.result
  const consolidation = snapshot?.consolidationState?.result
  const runs = snapshot?.runState
  const gates = deriveWorkflowGates(snapshot)

  let readinessStatus = WORKFLOW_NODE_STATES.BLOCKED
  if (gates.SPECIFICATION_GATE.satisfied) {
    if (readiness?.status === 'evaluating') readinessStatus = WORKFLOW_NODE_STATES.RUNNING
    else if (readiness?.error) readinessStatus = WORKFLOW_NODE_STATES.FAILED
    else if (readiness?.stale) readinessStatus = WORKFLOW_NODE_STATES.BLOCKED
    else if (readiness?.result?.status === 'READY') readinessStatus = WORKFLOW_NODE_STATES.COMPLETE
    else if (readiness?.result?.status === 'READY_WITH_WARNINGS') {
      readinessStatus = readiness.result.continuation_approved
        ? WORKFLOW_NODE_STATES.COMPLETE
        : WORKFLOW_NODE_STATES.WAITING_FOR_HUMAN
    }
    else if (readiness?.result?.status === 'NOT_READY') readinessStatus = WORKFLOW_NODE_STATES.BLOCKED
    else readinessStatus = WORKFLOW_NODE_STATES.QUEUED
  }

  let deliveryStatus = WORKFLOW_NODE_STATES.BLOCKED
  if (gates.READINESS_GATE.satisfied) {
    if (repository?.status === 'creating') deliveryStatus = WORKFLOW_NODE_STATES.RUNNING
    else if (github?.status === 'loading' || repository?.status === 'loading') deliveryStatus = WORKFLOW_NODE_STATES.QUEUED
    else if (github?.status === 'error' || repository?.status === 'error') deliveryStatus = WORKFLOW_NODE_STATES.FAILED
    else if (gates.DELIVERY_GATE.satisfied) deliveryStatus = WORKFLOW_NODE_STATES.COMPLETE
    else deliveryStatus = WORKFLOW_NODE_STATES.WAITING_FOR_HUMAN
  }

  let generationStatus = WORKFLOW_NODE_STATES.BLOCKED
  if (gates.FINAL_APPROVAL_GATE.satisfied) generationStatus = WORKFLOW_NODE_STATES.COMPLETE
  else if (gates.FINAL_APPROVAL_GATE.waiting_for_human) {
    if (runs?.status === 'creating') generationStatus = WORKFLOW_NODE_STATES.QUEUED
    else if (runs?.error) generationStatus = WORKFLOW_NODE_STATES.FAILED
    else generationStatus = WORKFLOW_NODE_STATES.WAITING_FOR_HUMAN
  }

  let specificationStatus = WORKFLOW_NODE_STATES.BLOCKED
  if (gates.SPECIFICATION_GATE.satisfied) specificationStatus = WORKFLOW_NODE_STATES.COMPLETE
  else if (gates.SPECIFICATION_GATE.waiting_for_human) specificationStatus = WORKFLOW_NODE_STATES.WAITING_FOR_HUMAN
  else if (gates.SPECIFICATION_GATE.failed) specificationStatus = WORKFLOW_NODE_STATES.FAILED
  else if (specification?.status === 'PREPARING_SPECIFICATION' || consolidation?.status === 'CONSOLIDATING') specificationStatus = WORKFLOW_NODE_STATES.RUNNING

  return {
    PROJECT_SOURCES: {
      status: preparation?.status && preparation.status !== 'NOT_STARTED'
        ? WORKFLOW_NODE_STATES.COMPLETE
        : sourceCount > 0 || outputCount > 0 ? WORKFLOW_NODE_STATES.RUNNING : WORKFLOW_NODE_STATES.NOT_STARTED,
      summary: `${sourceCount} ${sourceCount === 1 ? 'source' : 'sources'} · ${outputCount} selected ${outputCount === 1 ? 'output' : 'outputs'}`,
      attentionCount,
    },
    INPUT_ANALYSIS: {
      status: preparation?.status === 'WAITING_FOR_HUMAN'
        ? WORKFLOW_NODE_STATES.COMPLETE
        : preparation ? preparationToWorkflowState(preparation.status) : preparedCount > 0 ? WORKFLOW_NODE_STATES.RUNNING : attentionCount > 0 ? WORKFLOW_NODE_STATES.NEEDS_ATTENTION : WORKFLOW_NODE_STATES.NOT_STARTED,
      summary: preparation
        ? `${preparation.processed_source_count} / ${preparation.eligible_source_count} eligible sources processed${preparation.failed_source_count ? ` · ${preparation.failed_source_count} failed` : ''}`
        : `${preparedCount} ${preparedCount === 1 ? 'source' : 'sources'} prepared · ${Math.max(sourceCount - preparedCount, 0)} pending`,
      attentionCount: preparation?.failed_source_count ?? attentionCount,
    },
    SPECIFICATION_VERIFICATION: {
      status: specificationStatus,
      summary: preparation?.status === 'WAITING_FOR_HUMAN'
        ? `${preparation.human_review_source_count} ${preparation.human_review_source_count === 1 ? 'source needs' : 'sources need'} review`
        : consolidation?.status === 'READY'
        ? 'Project specification ready'
        : consolidation?.status === 'WAITING_FOR_HUMAN'
          ? `${consolidation.pending_conflict_count} cross-source ${consolidation.pending_conflict_count === 1 ? 'decision' : 'decisions'} required`
          : consolidation?.status === 'CONSOLIDATING'
            ? 'Consolidating trusted project sources'
            : consolidation?.status === 'STALE'
              ? 'Trusted sources changed · consolidation is stale'
              : specification
        ? specification.status === 'WAITING_FOR_SEMANTIC_REVIEW'
          ? `${specification.pending_semantic_decision_count} semantic ${specification.pending_semantic_decision_count === 1 ? 'decision' : 'decisions'} required`
          : `${specification.ready_source_count} / ${specification.applicable_source_count} source specifications prepared${specification.failed_source_count ? ` · ${specification.failed_source_count} failed` : ''}`
        : preparation?.requires_human_review
        ? `${preparation.human_review_source_count} ${preparation.human_review_source_count === 1 ? 'source' : 'sources'} awaiting verification`
        : `${verifiedSourceCount} ${verifiedSourceCount === 1 ? 'source' : 'sources'} verified · ${Math.max(preparedCount - verifiedSourceCount, 0)} awaiting review`,
      attentionCount: preparation?.human_review_source_count
        || consolidation?.pending_conflict_count || consolidation?.issue_count
        || specification?.pending_semantic_decision_count || specification?.failed_source_count,
    },
    IMPLEMENTATION_READINESS: {
      status: readinessStatus,
      statusLabel: readiness?.result?.status === 'READY_WITH_WARNINGS'
        ? readiness.result.continuation_approved
          ? 'Approved with Warnings'
          : 'Needs Your Approval'
        : undefined,
      summary: !gates.SPECIFICATION_GATE.satisfied
        ? 'Waiting for specification review'
        : readiness?.result?.status === 'READY_WITH_WARNINGS'
          ? readiness.result.continuation_approved
            ? 'Approved with warnings'
            : 'Needs your approval'
          : readiness?.result ? `Latest result: ${readiness.result.status.replaceAll('_', ' ').toLowerCase()}` : 'Checking implementation readiness',
    },
    DELIVERY_SETUP: {
      status: deliveryStatus,
      summary: !gates.READINESS_GATE.satisfied
        ? gates.DELIVERY_GATE.blocking_reason
        : gates.DELIVERY_GATE.satisfied
          ? repository?.repository?.full_name ?? 'Continuing without repository delivery'
          : github?.connection?.connected ? 'GitHub connected · choose repository delivery or continue without it' : 'Configure delivery or continue without repository delivery',
    },
    GENERATE_IMPLEMENTATION: {
      status: generationStatus,
      summary: gates.approvedRun
        ? `${gates.approvedRun.run_id} ready for future generation`
        : generationStatus === WORKFLOW_NODE_STATES.WAITING_FOR_HUMAN
          ? 'Final implementation approval required'
          : generationStatus === WORKFLOW_NODE_STATES.BLOCKED
            ? gates.FINAL_APPROVAL_GATE.blocking_reason
            : 'No approved implementation run yet.',
    },
  }
}
