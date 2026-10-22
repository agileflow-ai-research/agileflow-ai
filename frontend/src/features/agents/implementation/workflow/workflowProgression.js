import { WORKFLOW_NODE_IDS } from '../constants/workflow.js'
import { deriveWorkflowGates } from './workflowGates.js'

function transition(nodeId, key, requiresUserAction = false) {
  return { nodeId, key, requiresUserAction }
}

export function deriveWorkflowTransition(snapshot) {
  const preparation = snapshot?.preparationState?.result?.status
  const specification = snapshot?.specificationState?.result?.status
  const consolidation = snapshot?.consolidationState?.result?.status
  const readinessState = snapshot?.readinessState
  const readiness = readinessState?.result?.status
  const gates = deriveWorkflowGates(snapshot)

  if (['FAILED', 'PARTIAL_FAILURE'].includes(preparation)) {
    return transition(WORKFLOW_NODE_IDS.INPUT_ANALYSIS, `preparation:${preparation}`, true)
  }
  if (preparation === 'RUNNING') {
    return transition(WORKFLOW_NODE_IDS.INPUT_ANALYSIS, 'preparation:RUNNING')
  }
  if (gates.pending.artifactReviewPending) {
    return transition(WORKFLOW_NODE_IDS.SPECIFICATION_VERIFICATION, 'review:artifact', true)
  }
  if (gates.pending.semanticReviewPending) {
    return transition(WORKFLOW_NODE_IDS.SPECIFICATION_VERIFICATION, 'review:semantic', true)
  }
  if (gates.pending.conflictReviewPending) {
    return transition(WORKFLOW_NODE_IDS.SPECIFICATION_VERIFICATION, 'review:consolidation', true)
  }
  if (
    specification === 'PREPARING_SPECIFICATION'
    || consolidation === 'CONSOLIDATING'
  ) {
    return transition(
      WORKFLOW_NODE_IDS.SPECIFICATION_VERIFICATION,
      `specification:${specification ?? ''}:${consolidation ?? ''}`,
    )
  }
  if (gates.SPECIFICATION_GATE.satisfied) {
    if (readinessState?.status === 'error') {
      return transition(WORKFLOW_NODE_IDS.IMPLEMENTATION_READINESS, 'readiness:error', true)
    }
    if (readinessState?.stale) {
      return transition(WORKFLOW_NODE_IDS.IMPLEMENTATION_READINESS, 'readiness:stale', true)
    }
    if (readiness === 'NOT_READY') {
      return transition(WORKFLOW_NODE_IDS.IMPLEMENTATION_READINESS, 'readiness:not-ready', true)
    }
    if (readiness === 'READY_WITH_WARNINGS' && !gates.READINESS_GATE.satisfied) {
      return transition(WORKFLOW_NODE_IDS.IMPLEMENTATION_READINESS, 'readiness:warning-approval', true)
    }
    if (readinessState?.status === 'evaluating' || !readiness) {
      return transition(WORKFLOW_NODE_IDS.IMPLEMENTATION_READINESS, 'readiness:checking')
    }
    if (gates.READINESS_GATE.satisfied && gates.DELIVERY_GATE.waiting_for_human) {
      return transition(WORKFLOW_NODE_IDS.DELIVERY_SETUP, `delivery:${readiness}`, true)
    }
    if (gates.FINAL_APPROVAL_GATE.waiting_for_human) {
      return transition(WORKFLOW_NODE_IDS.GENERATE_IMPLEMENTATION, `approval:${readiness}`, true)
    }
  }
  return null
}
