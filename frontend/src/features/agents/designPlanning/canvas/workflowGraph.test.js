import { describe, expect, it } from 'vitest'

import { DESIGN_PLANNING_NODE_IDS } from '../constants/workflow.js'
import { DESIGN_PLANNING_NODE_REGISTRY, getDesignPlanningNodeDefinition } from '../workflow/nodeDefinitions.js'
import { DESIGN_PLANNING_DEFAULT_NODE_POSITIONS, positionDesignPlanningNodes } from './layout.js'
import {
  createDesignPlanningWorkflowNodes,
  DESIGN_PLANNING_EDGE_PAIRS,
  DESIGN_PLANNING_WORKFLOW_EDGES,
} from './workflowGraph.js'

describe('Agent 2 Workflow Graph and Layout', () => {
  it('registers all 8 target nodes in logical SDLC workflow order', () => {
    expect(DESIGN_PLANNING_NODE_REGISTRY).toHaveLength(8)
    const expectedIds = [
      DESIGN_PLANNING_NODE_IDS.PROJECT_SPECIFICATIONS,
      DESIGN_PLANNING_NODE_IDS.TECHNICAL_PLANNING,
      DESIGN_PLANNING_NODE_IDS.OUTPUT_SELECTION,
      DESIGN_PLANNING_NODE_IDS.HUMAN_REVIEW,
      DESIGN_PLANNING_NODE_IDS.GENERATE_DESIGN_PLANNING,
      DESIGN_PLANNING_NODE_IDS.DESIGN_RESULTS,
      DESIGN_PLANNING_NODE_IDS.PLANNING_RESULTS,
      DESIGN_PLANNING_NODE_IDS.VALIDATION_TRACEABILITY,
    ]
    expect(DESIGN_PLANNING_NODE_REGISTRY.map((node) => node.id)).toEqual(expectedIds)
  })

  it('provides helper to lookup node definitions by ID', () => {
    const node = getDesignPlanningNodeDefinition(DESIGN_PLANNING_NODE_IDS.PROJECT_SPECIFICATIONS)
    expect(node).toBeDefined()
    expect(node?.title).toBe('Project & Specifications')
    expect(getDesignPlanningNodeDefinition('NON_EXISTENT')).toBeNull()
  })

  it('implements 5-node top row + 3-node return row snake layout coordinates', () => {
    const topRow = [
      DESIGN_PLANNING_NODE_IDS.PROJECT_SPECIFICATIONS,
      DESIGN_PLANNING_NODE_IDS.TECHNICAL_PLANNING,
      DESIGN_PLANNING_NODE_IDS.OUTPUT_SELECTION,
      DESIGN_PLANNING_NODE_IDS.HUMAN_REVIEW,
      DESIGN_PLANNING_NODE_IDS.GENERATE_DESIGN_PLANNING,
    ]
    const returnRow = [
      DESIGN_PLANNING_NODE_IDS.DESIGN_RESULTS,
      DESIGN_PLANNING_NODE_IDS.PLANNING_RESULTS,
      DESIGN_PLANNING_NODE_IDS.VALIDATION_TRACEABILITY,
    ]

    // Verify top row (left-to-right, y: 20)
    topRow.forEach((id, idx) => {
      const pos = DESIGN_PLANNING_DEFAULT_NODE_POSITIONS[id]
      expect(pos.y).toBe(20)
      expect(pos.x).toBe(idx * 270)
    })

    // Verify return row (right-to-left snake, y: 250)
    returnRow.forEach((id) => {
      expect(DESIGN_PLANNING_DEFAULT_NODE_POSITIONS[id].y).toBe(250)
    })
    expect(DESIGN_PLANNING_DEFAULT_NODE_POSITIONS[DESIGN_PLANNING_NODE_IDS.DESIGN_RESULTS].x).toBe(1080)
    expect(DESIGN_PLANNING_DEFAULT_NODE_POSITIONS[DESIGN_PLANNING_NODE_IDS.PLANNING_RESULTS].x).toBe(810)
    expect(DESIGN_PLANNING_DEFAULT_NODE_POSITIONS[DESIGN_PLANNING_NODE_IDS.VALIDATION_TRACEABILITY].x).toBe(540)
  })

  it('constructs 7 floating edges with closed arrow markers connecting consecutive nodes', () => {
    expect(DESIGN_PLANNING_EDGE_PAIRS).toHaveLength(7)
    expect(DESIGN_PLANNING_WORKFLOW_EDGES).toHaveLength(7)

    const nodeIds = new Set(DESIGN_PLANNING_NODE_REGISTRY.map((n) => n.id))

    DESIGN_PLANNING_WORKFLOW_EDGES.forEach((edge) => {
      expect(edge.type).toBe('floating')
      expect(edge.markerEnd.type).toBe('arrowclosed')
      expect(nodeIds.has(edge.source)).toBe(true)
      expect(nodeIds.has(edge.target)).toBe(true)
      expect(edge.id).toBe(`${edge.source}-${edge.target}`)
    })

    // Verify turn-around edge connects Node 5 to Node 6 vertically
    const turnEdge = DESIGN_PLANNING_WORKFLOW_EDGES.find(
      (e) => e.source === DESIGN_PLANNING_NODE_IDS.GENERATE_DESIGN_PLANNING,
    )
    expect(turnEdge?.target).toBe(DESIGN_PLANNING_NODE_IDS.DESIGN_RESULTS)
  })

  it('generates workflow node objects with titles, summaries, and default statuses', () => {
    const nodes = createDesignPlanningWorkflowNodes()
    expect(nodes).toHaveLength(8)
    nodes.forEach((node) => {
      expect(node.type).toBe('workflow')
      expect(node.draggable).toBe(true)
      expect(node.data.title).toBeTruthy()
      expect(node.data.summary).toBeTruthy()
      expect(node.data.status).toBe('NOT_STARTED')
      expect(node.position).toBeDefined()
    })
  })

  it('re-applies default positions with positionDesignPlanningNodes', () => {
    const nodes = [
      { id: DESIGN_PLANNING_NODE_IDS.PROJECT_SPECIFICATIONS, position: { x: 999, y: 999 } },
    ]
    const repositioned = positionDesignPlanningNodes(nodes)
    expect(repositioned[0].position).toEqual({ x: 0, y: 20 })
  })
})
