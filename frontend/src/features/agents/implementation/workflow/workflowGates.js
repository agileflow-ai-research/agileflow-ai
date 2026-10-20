import { inputHasSource } from './sourceState.js'
import { WORKFLOW_NODE_IDS } from '../constants/workflow.js'

export const WORKFLOW_GATE_STATUS = Object.freeze({
  SATISFIED: 'SATISFIED',
  BLOCKED: 'BLOCKED',
  WAITING_FOR_HUMAN: 'WAITING_FOR_HUMAN',
  FAILED: 'FAILED',
})

function gate(status, blockingReason = '', blockingNodeId = null) {
  return Object.freeze({
    status,
    satisfied: status === WORKFLOW_GATE_STATUS.SATISFIED,
    blocked: status === WORKFLOW_GATE_STATUS.BLOCKED,
    waiting_for_human: status === WORKFLOW_GATE_STATUS.WAITING_FOR_HUMAN,
    failed: status === WORKFLOW_GATE_STATUS.FAILED,
    blocking_reason: blockingReason,
    blocking_node_id: blockingNodeId,
  })
}

function currentApprovedRun(runs, readiness) {
  if (!readiness?.readiness_id) return null
  const candidates = [runs?.current, ...(runs?.runs ?? [])].filter(Boolean)
  return candidates.find((run) => (
    run.readiness_id === readiness.readiness_id
    && (!readiness.readiness_fingerprint || run.readiness_fingerprint === readiness.readiness_fingerprint)
    && run.run_status === 'READY_FOR_GENERATION'
  )) ?? null
}

export function deriveWorkflowGates(snapshot) {
  const inputs = snapshot?.inputs ?? []
  const selectedOutputs = snapshot?.selectedOutputs ?? []
  const preparation = snapshot?.preparationState?.result
  const specification = snapshot?.specificationState?.result
  const consolidation = snapshot?.consolidationState?.result
  const readinessState = snapshot?.readinessState
  const readiness = readinessState?.result
  const repository = snapshot?.repositoryState
  const deliveryDecision = snapshot?.deliveryDecision
  const runs = snapshot?.runState

  const sourcesSatisfied = inputs.some(inputHasSource) && selectedOutputs.length > 0
  const sourcesGate = sourcesSatisfied
    ? gate(WORKFLOW_GATE_STATUS.SATISFIED)
    : gate(WORKFLOW_GATE_STATUS.BLOCKED, 'Add project sources and select outputs', WORKFLOW_NODE_IDS.PROJECT_SOURCES)

  let analysisGate
  if (['FAILED', 'PARTIAL_FAILURE'].includes(preparation?.status)) {
    analysisGate = gate(WORKFLOW_GATE_STATUS.FAILED, 'Input analysis needs attention', WORKFLOW_NODE_IDS.INPUT_ANALYSIS)
  } else if (['ANALYSIS_READY', 'WAITING_FOR_HUMAN'].includes(preparation?.status)) {
    analysisGate = gate(WORKFLOW_GATE_STATUS.SATISFIED)
  } else {
    analysisGate = gate(WORKFLOW_GATE_STATUS.BLOCKED, preparation?.status === 'RUNNING' ? 'Input analysis is still running' : 'Analyze project inputs first', WORKFLOW_NODE_IDS.INPUT_ANALYSIS)
  }

  const artifactReviewPending = preparation?.status === 'WAITING_FOR_HUMAN'
    || specification?.status === 'WAITING_FOR_ARTIFACT_REVIEW'
  const semanticReviewPending = specification?.status === 'WAITING_FOR_SEMANTIC_REVIEW'
  const conflictReviewPending = consolidation?.status === 'WAITING_FOR_HUMAN'
  const specificationFailed = ['FAILED', 'PARTIAL_FAILURE'].includes(specification?.status)
    || ['FAILED', 'PARTIAL_FAILURE', 'STALE'].includes(consolidation?.status)
    || ['FAILED', 'PARTIAL_FAILURE'].includes(preparation?.status)

  let specificationGate
  if (artifactReviewPending || semanticReviewPending || conflictReviewPending) {
    const reason = artifactReviewPending
      ? 'Complete input classification review'
      : semanticReviewPending
        ? 'Complete semantic review'
        : 'Resolve project specification conflicts'
    specificationGate = gate(WORKFLOW_GATE_STATUS.WAITING_FOR_HUMAN, reason, WORKFLOW_NODE_IDS.SPECIFICATION_VERIFICATION)
  } else if (specificationFailed) {
    specificationGate = gate(WORKFLOW_GATE_STATUS.FAILED, 'Project specification needs attention', WORKFLOW_NODE_IDS.SPECIFICATION_VERIFICATION)
  } else if (
    preparation?.status === 'ANALYSIS_READY'
    && specification?.status === 'SPECIFICATION_READY'
    && consolidation?.status === 'READY'
  ) {
    specificationGate = gate(WORKFLOW_GATE_STATUS.SATISFIED)
  } else {
    specificationGate = gate(WORKFLOW_GATE_STATUS.BLOCKED, 'Waiting for specification review', WORKFLOW_NODE_IDS.SPECIFICATION_VERIFICATION)
  }

  const readinessCurrent = readiness?.current !== false && !readinessState?.stale
  const readinessAllowed = specificationGate.satisfied
  let readinessGate
  if (!readinessAllowed) {
    readinessGate = gate(
      specificationGate.failed ? WORKFLOW_GATE_STATUS.FAILED : WORKFLOW_GATE_STATUS.BLOCKED,
      'Waiting for specification review',
      WORKFLOW_NODE_IDS.SPECIFICATION_VERIFICATION,
    )
  } else if (readinessState?.status === 'error') {
    readinessGate = gate(WORKFLOW_GATE_STATUS.FAILED, 'Implementation readiness evaluation failed', WORKFLOW_NODE_IDS.IMPLEMENTATION_READINESS)
  } else if (!readinessCurrent || readiness?.status === 'NOT_READY') {
    readinessGate = gate(WORKFLOW_GATE_STATUS.BLOCKED, 'Resolve implementation readiness findings', WORKFLOW_NODE_IDS.IMPLEMENTATION_READINESS)
  } else if (readiness?.status === 'READY') {
    readinessGate = gate(WORKFLOW_GATE_STATUS.SATISFIED)
  } else if (readiness?.status === 'READY_WITH_WARNINGS') {
    readinessGate = readiness?.continuation_approved
      ? gate(WORKFLOW_GATE_STATUS.SATISFIED)
      : gate(
          WORKFLOW_GATE_STATUS.WAITING_FOR_HUMAN,
          'Approve readiness warnings before continuing',
          WORKFLOW_NODE_IDS.IMPLEMENTATION_READINESS,
        )
  } else {
    readinessGate = gate(WORKFLOW_GATE_STATUS.BLOCKED, 'Implementation readiness is required', WORKFLOW_NODE_IDS.IMPLEMENTATION_READINESS)
  }

  const deliveryConfigured = repository?.status === 'created' && Boolean(repository.repository)
  const deliverySkipped = deliveryDecision === 'SKIPPED'
  let deliveryGate
  if (!readinessGate.satisfied) {
    const warningApprovalPending = readinessGate.waiting_for_human
    deliveryGate = gate(
      WORKFLOW_GATE_STATUS.BLOCKED,
      warningApprovalPending
        ? 'Waiting for readiness approval'
        : readinessAllowed
          ? 'Waiting for implementation readiness'
          : 'Complete specification review first',
      readinessAllowed ? WORKFLOW_NODE_IDS.IMPLEMENTATION_READINESS : WORKFLOW_NODE_IDS.SPECIFICATION_VERIFICATION,
    )
  } else if (deliveryConfigured || deliverySkipped) {
    deliveryGate = gate(WORKFLOW_GATE_STATUS.SATISFIED)
  } else {
    deliveryGate = gate(WORKFLOW_GATE_STATUS.WAITING_FOR_HUMAN, 'Configure delivery or continue without repository delivery', WORKFLOW_NODE_IDS.DELIVERY_SETUP)
  }

  const approvedRun = currentApprovedRun(runs, readiness)
  let finalApprovalGate
  if (!deliveryGate.satisfied) {
    finalApprovalGate = gate(
      WORKFLOW_GATE_STATUS.BLOCKED,
      deliveryGate.blocking_reason === 'Complete specification review first'
        ? 'Waiting for specification review'
        : deliveryGate.blocking_reason,
      deliveryGate.blocking_node_id,
    )
  } else if (approvedRun) {
    finalApprovalGate = gate(WORKFLOW_GATE_STATUS.SATISFIED)
  } else {
    finalApprovalGate = gate(WORKFLOW_GATE_STATUS.WAITING_FOR_HUMAN, 'Final implementation approval required', WORKFLOW_NODE_IDS.GENERATE_IMPLEMENTATION)
  }

  return Object.freeze({
    SOURCES_GATE: sourcesGate,
    ANALYSIS_GATE: analysisGate,
    SPECIFICATION_GATE: specificationGate,
    READINESS_GATE: readinessGate,
    DELIVERY_GATE: deliveryGate,
    FINAL_APPROVAL_GATE: finalApprovalGate,
    automation: Object.freeze({
      specification_preparation_allowed: preparation?.status === 'ANALYSIS_READY',
      consolidation_allowed: preparation?.status === 'ANALYSIS_READY' && specification?.status === 'SPECIFICATION_READY',
      readiness_evaluation_allowed: readinessAllowed,
    }),
    pending: Object.freeze({ artifactReviewPending, semanticReviewPending, conflictReviewPending }),
    approvedRun,
  })
}
