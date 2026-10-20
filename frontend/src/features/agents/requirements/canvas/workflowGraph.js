import { MarkerType } from '@xyflow/react'

import { WORKFLOW_NODE_STATES } from '../../../../components/agents/workflowState.js'
import { REQUIREMENTS_NODE_IDS, REQUIREMENTS_NODE_REGISTRY } from '../workflow/nodeDefinitions.js'
import { REQUIREMENTS_DEFAULT_NODE_POSITIONS } from './layout.js'

export const REQUIREMENTS_EDGE_PAIRS = Object.freeze([
  [REQUIREMENTS_NODE_IDS.INPUT_COLLECTION, REQUIREMENTS_NODE_IDS.PROCESSING_AND_CHUNKING],
  [REQUIREMENTS_NODE_IDS.PROCESSING_AND_CHUNKING, REQUIREMENTS_NODE_IDS.DISCOVERY_AND_STRUCTURING],
  [REQUIREMENTS_NODE_IDS.DISCOVERY_AND_STRUCTURING, REQUIREMENTS_NODE_IDS.QUALITY_ENGINEERING],
  [REQUIREMENTS_NODE_IDS.QUALITY_ENGINEERING, REQUIREMENTS_NODE_IDS.CLARIFICATION_AND_REFINEMENT],
  [REQUIREMENTS_NODE_IDS.CLARIFICATION_AND_REFINEMENT, REQUIREMENTS_NODE_IDS.QUALITY_RECHECK_AND_ARTIFACTS],
  [REQUIREMENTS_NODE_IDS.QUALITY_RECHECK_AND_ARTIFACTS, REQUIREMENTS_NODE_IDS.REVIEW_AND_BASELINE],
])

export const REQUIREMENTS_WORKFLOW_EDGES = Object.freeze(REQUIREMENTS_EDGE_PAIRS.map(([source, target]) => ({
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

export function createRequirementsWorkflowNodes(presentation) {
  return REQUIREMENTS_NODE_REGISTRY.map((definition) => ({
    id: definition.id,
    type: 'workflow',
    draggable: true,
    position: { ...REQUIREMENTS_DEFAULT_NODE_POSITIONS[definition.id] },
    data: {
      title: definition.title,
      summary: presentation[definition.id]?.summary ?? definition.summary,
      status: definition.active
        ? presentation[definition.id]?.status ?? WORKFLOW_NODE_STATES.NOT_STARTED
        : WORKFLOW_NODE_STATES.LOCKED,
      statusLabel: presentation[definition.id]?.statusLabel,
      locked: !definition.active,
    },
  }))
}
