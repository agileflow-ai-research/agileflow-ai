import { MarkerType } from '@xyflow/react'

import { DESIGN_PLANNING_NODE_IDS, WORKFLOW_NODE_STATES } from '../constants/workflow.js'
import { DESIGN_PLANNING_NODE_REGISTRY } from '../workflow/nodeDefinitions.js'
import { DESIGN_PLANNING_DEFAULT_NODE_POSITIONS } from './layout.js'

export const DESIGN_PLANNING_EDGE_PAIRS = Object.freeze([
  [DESIGN_PLANNING_NODE_IDS.PROJECT_SPECIFICATIONS, DESIGN_PLANNING_NODE_IDS.OUTPUT_SELECTION],
  [DESIGN_PLANNING_NODE_IDS.OUTPUT_SELECTION, DESIGN_PLANNING_NODE_IDS.TECHNICAL_PLANNING],
  [DESIGN_PLANNING_NODE_IDS.TECHNICAL_PLANNING, DESIGN_PLANNING_NODE_IDS.HUMAN_REVIEW],
  [DESIGN_PLANNING_NODE_IDS.HUMAN_REVIEW, DESIGN_PLANNING_NODE_IDS.GENERATE_DESIGN_PLANNING],
  [DESIGN_PLANNING_NODE_IDS.GENERATE_DESIGN_PLANNING, DESIGN_PLANNING_NODE_IDS.DESIGN_RESULTS],
  [DESIGN_PLANNING_NODE_IDS.DESIGN_RESULTS, DESIGN_PLANNING_NODE_IDS.PLANNING_RESULTS],
  [DESIGN_PLANNING_NODE_IDS.PLANNING_RESULTS, DESIGN_PLANNING_NODE_IDS.VALIDATION_TRACEABILITY],
])

export const DESIGN_PLANNING_WORKFLOW_EDGES = Object.freeze(DESIGN_PLANNING_EDGE_PAIRS.map(([source, target]) => ({
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

export function createDesignPlanningWorkflowNodes(presentation = {}) {
  return DESIGN_PLANNING_NODE_REGISTRY.map((definition) => {
    const current = presentation[definition.id]
    return {
      id: definition.id,
      type: 'workflow',
      draggable: true,
      position: { ...DESIGN_PLANNING_DEFAULT_NODE_POSITIONS[definition.id] },
      data: {
        title: definition.title,
        summary: current?.summary ?? definition.summary,
        status: definition.active ? current?.status ?? WORKFLOW_NODE_STATES.NOT_STARTED : WORKFLOW_NODE_STATES.LOCKED,
        statusLabel: current?.statusLabel,
        attentionCount: current?.attentionCount,
        locked: !definition.active,
      },
    }
  })
}
