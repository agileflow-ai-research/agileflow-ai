import { positionWorkflowNodes as applyWorkflowPositions } from '../../../../components/agents/workflow/layout.js'
import { DESIGN_PLANNING_NODE_IDS } from '../constants/workflow.js'

export const DESIGN_PLANNING_DEFAULT_NODE_POSITIONS = Object.freeze({
  [DESIGN_PLANNING_NODE_IDS.PROJECT_SPECIFICATIONS]: Object.freeze({ x: 0, y: 20 }),
  [DESIGN_PLANNING_NODE_IDS.OUTPUT_SELECTION]: Object.freeze({ x: 270, y: 20 }),
  [DESIGN_PLANNING_NODE_IDS.TECHNICAL_PLANNING]: Object.freeze({ x: 540, y: 20 }),
  [DESIGN_PLANNING_NODE_IDS.HUMAN_REVIEW]: Object.freeze({ x: 810, y: 20 }),
  [DESIGN_PLANNING_NODE_IDS.GENERATE_DESIGN_PLANNING]: Object.freeze({ x: 1080, y: 20 }),
  [DESIGN_PLANNING_NODE_IDS.DESIGN_RESULTS]: Object.freeze({ x: 1080, y: 250 }),
  [DESIGN_PLANNING_NODE_IDS.PLANNING_RESULTS]: Object.freeze({ x: 810, y: 250 }),
  [DESIGN_PLANNING_NODE_IDS.VALIDATION_TRACEABILITY]: Object.freeze({ x: 540, y: 250 }),
})

export function positionDesignPlanningNodes(nodes) {
  return applyWorkflowPositions(nodes, DESIGN_PLANNING_DEFAULT_NODE_POSITIONS)
}
