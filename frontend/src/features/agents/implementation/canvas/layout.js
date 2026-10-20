import { positionWorkflowNodes as applyWorkflowPositions } from '../../../../components/agents/workflow/layout.js'

export const DEFAULT_NODE_POSITIONS = Object.freeze({
  PROJECT_SOURCES: Object.freeze({ x: 0, y: 20 }),
  INPUT_ANALYSIS: Object.freeze({ x: 270, y: 20 }),
  SPECIFICATION_VERIFICATION: Object.freeze({ x: 540, y: 20 }),
  IMPLEMENTATION_READINESS: Object.freeze({ x: 810, y: 20 }),
  DELIVERY_SETUP: Object.freeze({ x: 1080, y: 20 }),
  GENERATE_IMPLEMENTATION: Object.freeze({ x: 1080, y: 250 }),
  BUILD_EXECUTE: Object.freeze({ x: 810, y: 250 }),
  CORRECTION_VALIDATION: Object.freeze({ x: 540, y: 250 }),
  DELIVERY: Object.freeze({ x: 270, y: 250 }),
})

export function positionWorkflowNodes(nodes) {
  return applyWorkflowPositions(nodes, DEFAULT_NODE_POSITIONS)
}
