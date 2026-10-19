import { deriveWorkflowGates } from './workflowGates.js'

function transition(nodeId, key) {
  return { nodeId, key }
}

export function deriveWorkflowTransition(snapshot) {
  const preparation = snapshot?.preparationState?.result?.status
  const specification = snapshot?.specificationState?.result?.status
  const consolidation = snapshot?.consolidationState?.result?.status
  const readinessState = snapshot?.readinessState
  const readiness = readinessState?.result?.status
  const gates = deriveWorkflowGates(snapshot)

  if (['FAILED', 'PARTIAL_FAILURE'].includes(preparation)) {
    return transition('INPUT_ANALYSIS', `preparation:${preparation}`)
  }
  if (preparation === 'RUNNING') {
    return transition('INPUT_ANALYSIS', 'preparation:RUNNING')
  }
  if (gates.pending.artifactReviewPending) {
    return transition('SPECIFICATION_VERIFICATION', 'review:artifact')
  }
  if (gates.pending.semanticReviewPending) {
    return transition('SPECIFICATION_VERIFICATION', 'review:semantic')
  }
  if (gates.pending.conflictReviewPending) {
    return transition('SPECIFICATION_VERIFICATION', 'review:consolidation')
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
      return transition('IMPLEMENTATION_READINESS', 'readiness:error')
    }
    if (readinessState?.stale) {
      return transition('IMPLEMENTATION_READINESS', 'readiness:stale')
    }
    if (readiness === 'NOT_READY') {
      return transition('IMPLEMENTATION_READINESS', 'readiness:not-ready')
    }
    if (readiness === 'READY_WITH_WARNINGS' && !gates.READINESS_GATE.satisfied) {
      return transition('IMPLEMENTATION_READINESS', 'readiness:warning-approval')
    }
    if (readinessState?.status === 'evaluating' || !readiness) {
      return transition('IMPLEMENTATION_READINESS', 'readiness:checking')
    }
    if (gates.READINESS_GATE.satisfied && ['READY', 'READY_WITH_WARNINGS'].includes(readiness)) {
      return transition('DELIVERY_SETUP', `delivery:${readiness}`)
    }
  }
  return null
}
