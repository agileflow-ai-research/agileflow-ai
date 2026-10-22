import { MarkerType } from '@xyflow/react'

import { WORKFLOW_NODE_IDS, WORKFLOW_NODE_STATES } from '../constants/workflow.js'
import { IMPLEMENTATION_NODE_REGISTRY } from '../workflow/nodeDefinitions.js'
import { DEFAULT_NODE_POSITIONS } from './layout.js'

const edgePairs = [
  [WORKFLOW_NODE_IDS.PROJECT_SOURCES, WORKFLOW_NODE_IDS.INPUT_ANALYSIS],
  [WORKFLOW_NODE_IDS.INPUT_ANALYSIS, WORKFLOW_NODE_IDS.SPECIFICATION_VERIFICATION],
  [WORKFLOW_NODE_IDS.SPECIFICATION_VERIFICATION, WORKFLOW_NODE_IDS.IMPLEMENTATION_READINESS],
  [WORKFLOW_NODE_IDS.IMPLEMENTATION_READINESS, WORKFLOW_NODE_IDS.DELIVERY_SETUP],
  [WORKFLOW_NODE_IDS.DELIVERY_SETUP, WORKFLOW_NODE_IDS.GENERATE_IMPLEMENTATION],
  [WORKFLOW_NODE_IDS.GENERATE_IMPLEMENTATION, WORKFLOW_NODE_IDS.BUILD_EXECUTE],
  [WORKFLOW_NODE_IDS.BUILD_EXECUTE, WORKFLOW_NODE_IDS.CORRECTION_VALIDATION],
  [WORKFLOW_NODE_IDS.CORRECTION_VALIDATION, WORKFLOW_NODE_IDS.DELIVERY],
]

export const IMPLEMENTATION_WORKFLOW_EDGES = Object.freeze(edgePairs.map(([source, target]) => ({
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

export function createWorkflowNodes(presentation) {
  return IMPLEMENTATION_NODE_REGISTRY.map((definition) => {
    const current = presentation[definition.id]
    return {
      id: definition.id,
      type: 'workflow',
      draggable: true,
      position: { ...DEFAULT_NODE_POSITIONS[definition.id] },
      data: {
        title: definition.title,
        summary: current?.summary ?? definition.summary,
        status: definition.active ? current?.status ?? WORKFLOW_NODE_STATES.NOT_STARTED : WORKFLOW_NODE_STATES.LOCKED,
        statusLabel: definition.active ? current?.statusLabel : definition.reservedStatus,
        attentionCount: current?.attentionCount,
        locked: !definition.active,
        lockedNote: definition.active ? undefined : definition.summary,
      },
    }
  })
}
