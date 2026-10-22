import { MarkerType } from '@xyflow/react'
import { describe, expect, it } from 'vitest'

import { WORKFLOW_NODE_STATES } from '../../../../components/agents/workflowState.js'
import { TESTING_VALIDATION_NODE_REGISTRY } from '../workflow/nodeDefinitions.js'
import { createTestingValidationWorkflowPresentation } from '../workflow/presentation.js'
import { TESTING_VALIDATION_DEFAULT_NODE_POSITIONS } from './layout.js'
import {
  createTestingValidationWorkflowNodes,
  TESTING_VALIDATION_EDGE_PAIRS,
  TESTING_VALIDATION_WORKFLOW_EDGES,
} from './workflowGraph.js'

const expectedIds = [
  'INPUT_OUTPUT_SETUP',
  'INPUT_PREPARATION',
  'TESTING_INTELLIGENCE',
  'TESTING_FACT_EXTRACTION',
  'CONTEXT_TESTABILITY',
  'TEST_PLANNING_REVIEW',
  'TEST_GENERATION_RESULTS',
]
const initialWorkflow = {
  current_node_id: 'INPUT_OUTPUT_SETUP',
  nodes: expectedIds.map((nodeId, index) => ({
    node_id: nodeId,
    status: index === 0 ? 'WAITING_FOR_HUMAN' : 'LOCKED',
  })),
}

describe('Agent 4 Test Generation workflow graph', () => {
  it('defines the frozen seven-node order and linear graph', () => {
    expect(TESTING_VALIDATION_NODE_REGISTRY.map((node) => node.id)).toEqual(expectedIds)
    expect(TESTING_VALIDATION_NODE_REGISTRY.map((node) => node.sequence)).toEqual([1, 2, 3, 4, 5, 6, 7])
    expect(TESTING_VALIDATION_EDGE_PAIRS).toEqual(expectedIds.slice(0, -1).map(
      (id, index) => [id, expectedIds[index + 1]],
    ))
    expect(TESTING_VALIDATION_WORKFLOW_EDGES).toHaveLength(6)
    expect(TESTING_VALIDATION_WORKFLOW_EDGES.every(
      (edge) => edge.type === 'floating' && edge.markerEnd.type === MarkerType.ArrowClosed,
    )).toBe(true)
  })

  it('projects authoritative backend node status and current-node state', () => {
    const presentation = createTestingValidationWorkflowPresentation(initialWorkflow)
    const nodes = createTestingValidationWorkflowNodes(presentation)

    expect(nodes).toHaveLength(7)
    expect(nodes.map((node) => node.position)).toEqual(
      expectedIds.map((id) => TESTING_VALIDATION_DEFAULT_NODE_POSITIONS[id]),
    )
    expect(nodes[0].data).toMatchObject({
      status: WORKFLOW_NODE_STATES.WAITING_FOR_HUMAN,
      statusLabel: 'Available - Waiting for Setup',
      locked: false,
    })
    expect(nodes.slice(1).every((node) => (
      node.data.status === WORKFLOW_NODE_STATES.LOCKED && node.data.locked
    ))).toBe(true)
    expect(nodes[3].data.lockedNote).toBe('Available after Testing Intelligence.')
    expect(nodes[3].data.lockedNote).not.toMatch(/not implemented/i)
    expect(presentation.INPUT_OUTPUT_SETUP.current).toBe(true)
    expect(presentation.INPUT_PREPARATION.current).toBe(false)
  })

  it('uses backend current_node_id instead of deriving current from sequence', () => {
    const presentation = createTestingValidationWorkflowPresentation({
      ...initialWorkflow,
      current_node_id: 'CONTEXT_TESTABILITY',
    })

    expect(presentation.INPUT_OUTPUT_SETUP.current).toBe(false)
    expect(presentation.CONTEXT_TESTABILITY.current).toBe(true)
  })

  it('keeps all modal and canvas metadata in the central registry', () => {
    expect(TESTING_VALIDATION_NODE_REGISTRY.every((node) => (
      node.title && node.shortTitle && node.purpose && node.summary
      && node.panelKey && node.futureStages.length > 0
    ))).toBe(true)
  })
})
