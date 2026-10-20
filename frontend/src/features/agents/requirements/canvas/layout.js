import { positionWorkflowNodes } from '../../../../components/agents/workflow/layout.js'
import { REQUIREMENTS_NODE_IDS } from '../workflow/nodeDefinitions.js'

export const REQUIREMENTS_DEFAULT_NODE_POSITIONS = Object.freeze({
  [REQUIREMENTS_NODE_IDS.INPUT_COLLECTION]: Object.freeze({ x: 0, y: 20 }),
  [REQUIREMENTS_NODE_IDS.PROCESSING_AND_CHUNKING]: Object.freeze({ x: 270, y: 20 }),
  [REQUIREMENTS_NODE_IDS.DISCOVERY_AND_STRUCTURING]: Object.freeze({ x: 540, y: 20 }),
  [REQUIREMENTS_NODE_IDS.QUALITY_ENGINEERING]: Object.freeze({ x: 810, y: 20 }),
  [REQUIREMENTS_NODE_IDS.CLARIFICATION_AND_REFINEMENT]: Object.freeze({ x: 810, y: 250 }),
  [REQUIREMENTS_NODE_IDS.QUALITY_RECHECK_AND_ARTIFACTS]: Object.freeze({ x: 540, y: 250 }),
  [REQUIREMENTS_NODE_IDS.REVIEW_AND_BASELINE]: Object.freeze({ x: 270, y: 250 }),
})

export function positionRequirementsNodes(nodes) {
  return positionWorkflowNodes(nodes, REQUIREMENTS_DEFAULT_NODE_POSITIONS)
}
