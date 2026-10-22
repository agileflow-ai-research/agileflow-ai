import { MarkerType } from '@xyflow/react'

import { WORKFLOW_NODE_STATES } from '../../../../components/agents/workflowState.js'
import { TESTING_VALIDATION_NODE_IDS, TESTING_VALIDATION_NODE_REGISTRY } from '../workflow/nodeDefinitions.js'
import { TESTING_VALIDATION_DEFAULT_NODE_POSITIONS } from './layout.js'

export const TESTING_VALIDATION_EDGE_PAIRS = Object.freeze([
  [TESTING_VALIDATION_NODE_IDS.INPUT_OUTPUT_SETUP, TESTING_VALIDATION_NODE_IDS.INPUT_PREPARATION],
  [TESTING_VALIDATION_NODE_IDS.INPUT_PREPARATION, TESTING_VALIDATION_NODE_IDS.TESTING_INTELLIGENCE],
  [TESTING_VALIDATION_NODE_IDS.TESTING_INTELLIGENCE, TESTING_VALIDATION_NODE_IDS.TESTING_FACT_EXTRACTION],
  [TESTING_VALIDATION_NODE_IDS.TESTING_FACT_EXTRACTION, TESTING_VALIDATION_NODE_IDS.CONTEXT_TESTABILITY],
  [TESTING_VALIDATION_NODE_IDS.CONTEXT_TESTABILITY, TESTING_VALIDATION_NODE_IDS.TEST_PLANNING_REVIEW],
  [TESTING_VALIDATION_NODE_IDS.TEST_PLANNING_REVIEW, TESTING_VALIDATION_NODE_IDS.TEST_GENERATION_RESULTS],
])

export const TESTING_VALIDATION_WORKFLOW_EDGES = Object.freeze(TESTING_VALIDATION_EDGE_PAIRS.map(([source, target]) => ({
  id: `${source}-${target}`,
  source,
  target,
  type: 'floating',
  selectable: false,
  deletable: false,
  reconnectable: false,
  focusable: false,
  markerEnd: { type: MarkerType.ArrowClosed, width: 16, height: 16 },
})))

export function createTestingValidationWorkflowNodes(presentation) {
  return TESTING_VALIDATION_NODE_REGISTRY.map((definition) => {
    const current = presentation[definition.id]
    return {
      id: definition.id,
      type: 'workflow',
      draggable: true,
      position: { ...TESTING_VALIDATION_DEFAULT_NODE_POSITIONS[definition.id] },
      data: {
        title: definition.title,
        summary: current?.summary ?? definition.summary,
        status: current?.status ?? WORKFLOW_NODE_STATES.LOCKED,
        statusLabel: current?.statusLabel,
        locked: current?.locked ?? true,
        lockedNote: definition.lockedNote,
      },
    }
  })
}
