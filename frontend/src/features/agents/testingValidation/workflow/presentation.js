import { WORKFLOW_NODE_STATES } from '../../../../components/agents/workflowState.js'
import { TESTING_VALIDATION_NODE_IDS, TESTING_VALIDATION_NODE_REGISTRY } from './nodeDefinitions.js'

export function createTestingValidationShellPresentation() {
  return Object.fromEntries(TESTING_VALIDATION_NODE_REGISTRY.map((definition) => {
    const available = definition.id === TESTING_VALIDATION_NODE_IDS.INPUT_OUTPUT_SETUP
    return [definition.id, {
      status: available ? WORKFLOW_NODE_STATES.NOT_STARTED : WORKFLOW_NODE_STATES.LOCKED,
      statusLabel: available ? 'Available · Current' : 'Locked · Not Available Yet',
      summary: definition.summary,
      locked: !available,
    }]
  }))
}
