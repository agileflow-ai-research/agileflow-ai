import { TESTING_VALIDATION_NODE_IDS, TESTING_VALIDATION_NODE_REGISTRY } from './nodeDefinitions.js'

function frontendWorkflowStatus(status) {
  return status === 'COMPLETED' ? 'COMPLETE' : status
}

export function createTestingValidationWorkflowPresentation(workflow) {
  const stateByNodeId = new Map(workflow.nodes.map((node) => [node.node_id, node]))
  return Object.fromEntries(TESTING_VALIDATION_NODE_REGISTRY.map((definition) => {
    const state = stateByNodeId.get(definition.id)
    if (!state) throw new Error(`Missing Agent 4 workflow node: ${definition.id}`)
    const current = definition.id === workflow.current_node_id
    return [definition.id, {
      status: frontendWorkflowStatus(state.status),
      statusLabel: (
        current
        && definition.id === TESTING_VALIDATION_NODE_IDS.INPUT_OUTPUT_SETUP
        && state.status === 'WAITING_FOR_HUMAN'
      ) ? 'Available - Waiting for Setup' : undefined,
      summary: definition.summary,
      locked: state.status === 'LOCKED',
      current,
    }]
  }))
}
