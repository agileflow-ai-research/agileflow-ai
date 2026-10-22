import { TESTING_VALIDATION_NODE_IDS, TESTING_VALIDATION_NODE_REGISTRY } from './nodeDefinitions.js'

function frontendWorkflowStatus(status) {
  return status === 'COMPLETED' ? 'COMPLETE' : status
}

const friendlyStatusLabels = Object.freeze({
  NOT_STARTED: 'Not started',
  LOCKED: 'Available after previous step',
  QUEUED: 'Preparing to start',
  RUNNING: 'In progress',
  WAITING_FOR_HUMAN: 'Needs your review',
  READY: 'Ready',
  READY_WITH_WARNINGS: 'Ready with limitations',
  BLOCKED: 'Cannot continue',
  FAILED: 'Could not complete',
  INTERRUPTED: 'Interrupted — retry available',
  COMPLETED: 'Complete',
  NOT_APPLICABLE: 'Not required',
})

const intelligenceNodeByStage = Object.freeze({
  TI_RULE_ANALYSIS: TESTING_VALIDATION_NODE_IDS.TESTING_INTELLIGENCE,
  TI_AI_CLASSIFICATION: TESTING_VALIDATION_NODE_IDS.TESTING_INTELLIGENCE,
  TI_HYBRID_DECISION: TESTING_VALIDATION_NODE_IDS.TESTING_INTELLIGENCE,
  TI_HUMAN_REVIEW: TESTING_VALIDATION_NODE_IDS.HUMAN_APPROVAL,
  TI_EFFECTIVE_CLASSIFICATION: TESTING_VALIDATION_NODE_IDS.HUMAN_APPROVAL,
  TI_FACT_EXTRACTION: TESTING_VALIDATION_NODE_IDS.TESTING_FACT_EXTRACTION,
})

const activityTextByStage = Object.freeze({
  TI_RULE_ANALYSIS: 'Analyzing requirement patternsâ€¦',
  TI_AI_CLASSIFICATION: 'Classifying testing concernsâ€¦',
  TI_HYBRID_DECISION: 'Combining rules and AI evidenceâ€¦',
  TI_HUMAN_REVIEW: 'Waiting for your classification review',
  TI_EFFECTIVE_CLASSIFICATION: 'Applying your review decisionsâ€¦',
  TI_FACT_EXTRACTION: 'Extracting grounded testing factsâ€¦',
})

function activeLocation(workflow) {
  const n3 = workflow.n3_execution
  if (n3 && ['QUEUED', 'RUNNING', 'WAITING_FOR_HUMAN'].includes(n3.status)) {
    if (n3.status === 'WAITING_FOR_HUMAN') {
      return { id: TESTING_VALIDATION_NODE_IDS.HUMAN_APPROVAL, human: true, text: 'Waiting for your classification review' }
    }
    const stage = n3.sub_stages?.find((item) => ['RUNNING', 'WAITING_FOR_HUMAN'].includes(item.status))
      || n3.sub_stages?.find((item) => item.status === 'QUEUED')
    if (stage) return {
      id: intelligenceNodeByStage[stage.stage] || TESTING_VALIDATION_NODE_IDS.TESTING_INTELLIGENCE,
      human: stage.status === 'WAITING_FOR_HUMAN',
      queued: stage.status === 'QUEUED',
      text: activityTextByStage[stage.stage] || 'Processing persisted workflow evidenceâ€¦',
    }
  }
  const n4 = workflow.n4_execution
  if (n4 && ['QUEUED', 'RUNNING', 'WAITING_FOR_HUMAN'].includes(n4.status)) {
    return {
      id: TESTING_VALIDATION_NODE_IDS.CONTEXT_TESTABILITY,
      human: n4.status === 'WAITING_FOR_HUMAN',
      queued: n4.status === 'QUEUED',
      text: n4.status === 'WAITING_FOR_HUMAN' ? 'Waiting for your acknowledgement' : 'Assessing context and test readinessâ€¦',
    }
  }
  const n2 = workflow.n2_execution
  if (n2 && ['QUEUED', 'RUNNING'].includes(n2.status)) {
    return { id: TESTING_VALIDATION_NODE_IDS.INPUT_PREPARATION, human: false, queued: n2.status === 'QUEUED', text: 'Preparing confirmed source evidenceâ€¦' }
  }
  if (workflow.current_node_id === TESTING_VALIDATION_NODE_IDS.INPUT_OUTPUT_SETUP) {
    return { id: TESTING_VALIDATION_NODE_IDS.INPUT_OUTPUT_SETUP, human: true, text: 'Waiting for setup confirmation' }
  }
  return null
}

export function createTestingValidationWorkflowPresentation(workflow) {
  const stateByNodeId = new Map(workflow.nodes.map((node) => [node.node_id, node]))
  const active = activeLocation(workflow)
  return Object.fromEntries(TESTING_VALIDATION_NODE_REGISTRY.map((definition) => {
    const state = stateByNodeId.get(definition.id)
    if (!state) throw new Error(`Missing Agent 4 workflow node: ${definition.id}`)
    const current = definition.id === workflow.current_node_id
    const reserved = [
      TESTING_VALIDATION_NODE_IDS.TEST_PLANNING_REVIEW,
      TESTING_VALIDATION_NODE_IDS.TEST_GENERATION_RESULTS,
    ].includes(definition.id)
    const isActive = active?.id === definition.id
    const displayStatus = isActive ? (active.human ? 'WAITING_FOR_HUMAN' : 'RUNNING') : frontendWorkflowStatus(state.status)
    return [definition.id, {
      status: displayStatus,
      statusLabel: reserved
        ? (definition.id === TESTING_VALIDATION_NODE_IDS.TEST_PLANNING_REVIEW
          ? 'Reserved — not implemented in PP1'
          : 'Reserved — future development')
        : isActive && definition.id === TESTING_VALIDATION_NODE_IDS.INPUT_OUTPUT_SETUP
          ? 'Ready for setup'
          : isActive
          ? (active.human ? 'Needs your review' : active.queued ? 'Preparing to start' : 'Processing')
          : current
          && definition.id === TESTING_VALIDATION_NODE_IDS.INPUT_OUTPUT_SETUP
          && state.status === 'WAITING_FOR_HUMAN'
          ? 'Ready for setup'
          : friendlyStatusLabels[state.status],
      summary: definition.summary,
      locked: state.status === 'LOCKED' || reserved,
      current,
      active: isActive,
      activityText: isActive ? active.text : null,
    }]
  }))
}
