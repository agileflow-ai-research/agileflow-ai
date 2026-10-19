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
    return transition('INPUT_ANALYSIS', `preparation:${preparation}`, true)
  }
  if (preparation === 'RUNNING') {
    return transition('INPUT_ANALYSIS', 'preparation:RUNNING')
  }
  if (gates.pending.artifactReviewPending) {
    return transition('SPECIFICATION_VERIFICATION', 'review:artifact', true)
  }
  if (gates.pending.semanticReviewPending) {
    return transition('SPECIFICATION_VERIFICATION', 'review:semantic', true)
  }
  if (gates.pending.conflictReviewPending) {
    return transition('SPECIFICATION_VERIFICATION', 'review:consolidation', true)
  }
  if (
    specification === 'PREPARING_SPECIFICATION'
    || consolidation === 'CONSOLIDATING'
  ) {
    return transition(
      'SPECIFICATION_VERIFICATION',
      `specification:${specification ?? ''}:${consolidation ?? ''}`,
    )
  }
  if (gates.SPECIFICATION_GATE.satisfied) {
    if (readinessState?.status === 'error') {
      return transition('IMPLEMENTATION_READINESS', 'readiness:error', true)
    }
    if (readinessState?.stale) {
      return transition('IMPLEMENTATION_READINESS', 'readiness:stale', true)
    }
    if (readiness === 'NOT_READY') {
      return transition('IMPLEMENTATION_READINESS', 'readiness:not-ready', true)
    }
    if (readiness === 'READY_WITH_WARNINGS' && !gates.READINESS_GATE.satisfied) {
      return transition('IMPLEMENTATION_READINESS', 'readiness:warning-approval', true)
    }
    if (readinessState?.status === 'evaluating' || !readiness) {
      return transition('IMPLEMENTATION_READINESS', 'readiness:checking')
    }
    if (gates.READINESS_GATE.satisfied && gates.DELIVERY_GATE.waiting_for_human) {
      return transition('DELIVERY_SETUP', `delivery:${readiness}`, true)
    }
    if (gates.FINAL_APPROVAL_GATE.waiting_for_human) {
      return transition('GENERATE_IMPLEMENTATION', `approval:${readiness}`, true)
    }
  }
  return null
}
