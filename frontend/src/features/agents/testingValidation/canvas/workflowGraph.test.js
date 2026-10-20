import { MarkerType } from '@xyflow/react'
import { describe, expect, it } from 'vitest'

import { WORKFLOW_NODE_STATES } from '../../../../components/agents/workflowState.js'
import { TESTING_VALIDATION_NODE_REGISTRY } from '../workflow/nodeDefinitions.js'
import { createTestingValidationShellPresentation } from '../workflow/presentation.js'
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
  'CONTEXT_TESTABILITY',
  'TEST_PLANNING_REVIEW',
  'TEST_GENERATION_RESULTS',
]

describe('Agent 4 Test Generation workflow graph', () => {
  it('defines the frozen six-node order and linear graph', () => {
    expect(TESTING_VALIDATION_NODE_REGISTRY.map((node) => node.id)).toEqual(expectedIds)
    expect(TESTING_VALIDATION_NODE_REGISTRY.map((node) => node.sequence)).toEqual([1, 2, 3, 4, 5, 6])
    expect(TESTING_VALIDATION_EDGE_PAIRS).toEqual(expectedIds.slice(0, -1).map(
      (id, index) => [id, expectedIds[index + 1]],
    ))
    expect(TESTING_VALIDATION_WORKFLOW_EDGES).toHaveLength(5)
    expect(TESTING_VALIDATION_WORKFLOW_EDGES.every(
      (edge) => edge.type === 'floating' && edge.markerEnd.type === MarkerType.ArrowClosed,
    )).toBe(true)
  })

  it('uses presentation-only availability without inventing backend workflow state', () => {
    const presentation = createTestingValidationShellPresentation()
    const nodes = createTestingValidationWorkflowNodes(presentation)

    expect(nodes).toHaveLength(6)
    expect(nodes.map((node) => node.position)).toEqual(
      expectedIds.map((id) => TESTING_VALIDATION_DEFAULT_NODE_POSITIONS[id]),
    )
    expect(nodes[0].data).toMatchObject({
      status: WORKFLOW_NODE_STATES.NOT_STARTED,
      statusLabel: 'Available · Current',
      locked: false,
    })
    expect(nodes.slice(1).every((node) => (
      node.data.status === WORKFLOW_NODE_STATES.LOCKED
      && node.data.statusLabel === 'Locked · Not Available Yet'
      && node.data.locked
    ))).toBe(true)
  })

  it('keeps all modal and canvas metadata in the central registry', () => {
    expect(TESTING_VALIDATION_NODE_REGISTRY.every((node) => (
      node.title && node.shortTitle && node.purpose && node.summary
      && node.panelKey && node.futureStages.length > 0
    ))).toBe(true)
  })
})
