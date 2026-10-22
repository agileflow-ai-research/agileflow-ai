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
  'HUMAN_APPROVAL',
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
  it('defines the frozen eight-node order and linear graph', () => {
    expect(TESTING_VALIDATION_NODE_REGISTRY.map((node) => node.id)).toEqual(expectedIds)
    expect(TESTING_VALIDATION_NODE_REGISTRY.map((node) => node.sequence)).toEqual([1, 2, 3, 4, 5, 6, 7, 8])
    expect(TESTING_VALIDATION_EDGE_PAIRS).toEqual(expectedIds.slice(0, -1).map(
      (id, index) => [id, expectedIds[index + 1]],
    ))
    expect(TESTING_VALIDATION_WORKFLOW_EDGES).toHaveLength(7)
    expect(TESTING_VALIDATION_WORKFLOW_EDGES.every(
      (edge) => edge.type === 'floating' && edge.markerEnd.type === MarkerType.ArrowClosed,
    )).toBe(true)
  })

  it('projects authoritative backend node status and current-node state', () => {
    const presentation = createTestingValidationWorkflowPresentation(initialWorkflow)
    const nodes = createTestingValidationWorkflowNodes(presentation)

    expect(nodes).toHaveLength(8)
    expect(nodes.map((node) => node.position)).toEqual(
      expectedIds.map((id) => TESTING_VALIDATION_DEFAULT_NODE_POSITIONS[id]),
    )
    expect(nodes[0].data).toMatchObject({
      status: WORKFLOW_NODE_STATES.WAITING_FOR_HUMAN,
      statusLabel: 'Ready for setup',
      locked: false,
    })
    expect(nodes.slice(1, 6).every((node) => (
      node.data.status === WORKFLOW_NODE_STATES.LOCKED && node.data.locked
    ))).toBe(true)
    expect(nodes.slice(1, 6).every((node) => node.data.statusLabel === 'Available after previous step')).toBe(true)
    expect(nodes[6].data.statusLabel).toBe('Reserved — not implemented in PP1')
    expect(nodes[7].data.statusLabel).toBe('Reserved — future development')
    expect(nodes[3].data.lockedNote).toBe('Available when Testing Intelligence requires review.')
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

  it.each([
    ['TI_RULE_ANALYSIS', 'TESTING_INTELLIGENCE'],
    ['TI_AI_CLASSIFICATION', 'TESTING_INTELLIGENCE'],
    ['TI_HYBRID_DECISION', 'TESTING_INTELLIGENCE'],
    ['TI_EFFECTIVE_CLASSIFICATION', 'HUMAN_APPROVAL'],
    ['TI_FACT_EXTRACTION', 'TESTING_FACT_EXTRACTION'],
  ])('maps active N3 substage %s to visible node %s', (stage, expectedNode) => {
    const presentation = createTestingValidationWorkflowPresentation({
      ...initialWorkflow,
      pipeline_status: 'RUNNING',
      current_node_id: 'TESTING_INTELLIGENCE',
      n3_execution: {
        status: 'RUNNING',
        sub_stages: [{ stage, status: 'RUNNING' }],
      },
    })
    expect(presentation[expectedNode]).toMatchObject({ active: true, status: 'RUNNING', statusLabel: 'Processing' })
    expect(Object.values(presentation).filter((node) => node.active)).toHaveLength(1)
  })

  it('highlights Human Approval when N3 is waiting for review', () => {
    const presentation = createTestingValidationWorkflowPresentation({
      ...initialWorkflow,
      pipeline_status: 'WAITING_FOR_HUMAN',
      current_node_id: 'HUMAN_APPROVAL',
      n3_execution: { status: 'WAITING_FOR_HUMAN', sub_stages: [] },
    })
    expect(presentation.HUMAN_APPROVAL).toMatchObject({
      active: true, status: 'WAITING_FOR_HUMAN', statusLabel: 'Needs your review',
    })
  })

  it.each([
    ['INPUT_PREPARATION', { n2_execution: { status: 'RUNNING' } }],
    ['CONTEXT_TESTABILITY', { n4_execution: { status: 'RUNNING' } }],
  ])('highlights authoritative active node %s', (expectedNode, execution) => {
    const presentation = createTestingValidationWorkflowPresentation({
      ...initialWorkflow, current_node_id: expectedNode, ...execution,
    })
    expect(presentation[expectedNode]).toMatchObject({ active: true, status: 'RUNNING' })
    expect(Object.values(presentation).filter((node) => node.active)).toHaveLength(1)
  })

  it.each(['FAILED', 'INTERRUPTED', 'COMPLETED'])(
    'preserves the authoritative %s node state when no execution is active',
    (status) => {
      const nodes = initialWorkflow.nodes.map((node) => (
        node.node_id === 'TESTING_INTELLIGENCE' ? { ...node, status } : node
      ))
      const presentation = createTestingValidationWorkflowPresentation({
        ...initialWorkflow, current_node_id: 'TESTING_INTELLIGENCE', nodes,
      })
      expect(presentation.TESTING_INTELLIGENCE.status).toBe(status === 'COMPLETED' ? 'COMPLETE' : status)
      expect(presentation.TESTING_INTELLIGENCE.active).toBe(false)
    },
  )

  it('keeps all modal and canvas metadata in the central registry', () => {
    expect(TESTING_VALIDATION_NODE_REGISTRY.every((node) => (
      node.title && node.shortTitle && node.purpose && node.summary
      && node.panelKey && node.futureStages.length > 0
    ))).toBe(true)
  })
})
