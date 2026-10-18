import { describe, expect, it, vi } from 'vitest'

import { DEFAULT_NODE_POSITIONS } from './layout.js'
import {
  createWorkflowNodes,
  deriveWorkflowPresentation,
  IMPLEMENTATION_NODE_REGISTRY,
  IMPLEMENTATION_WORKFLOW_EDGES,
} from './nodeRegistry.js'

describe('implementation workflow registry', () => {
  it('defines the fixed nine-node workflow and eight immutable forward edges', () => {
    expect(IMPLEMENTATION_NODE_REGISTRY).toHaveLength(9)
    expect(IMPLEMENTATION_WORKFLOW_EDGES).toHaveLength(8)
    expect(IMPLEMENTATION_WORKFLOW_EDGES.map(({ source, target }) => [source, target])).toEqual([
      ['PROJECT_SOURCES', 'INPUT_ANALYSIS'],
      ['INPUT_ANALYSIS', 'SPECIFICATION_VERIFICATION'],
      ['SPECIFICATION_VERIFICATION', 'IMPLEMENTATION_READINESS'],
      ['IMPLEMENTATION_READINESS', 'DELIVERY_SETUP'],
      ['DELIVERY_SETUP', 'GENERATE_IMPLEMENTATION'],
      ['GENERATE_IMPLEMENTATION', 'BUILD_EXECUTE'],
      ['BUILD_EXECUTE', 'CORRECTION_VALIDATION'],
      ['CORRECTION_VALIDATION', 'DELIVERY'],
    ])
    expect(IMPLEMENTATION_WORKFLOW_EDGES.every((edge) => edge.selectable === false)).toBe(true)
  })

  it('creates reusable nodes with default visual positions and locks future stages', () => {
    const openNode = vi.fn()
    const nodes = createWorkflowNodes(deriveWorkflowPresentation(null), openNode)

    expect(nodes).toHaveLength(9)
    expect(nodes.map((node) => node.id)).toEqual(IMPLEMENTATION_NODE_REGISTRY.map((node) => node.id))
    expect(nodes[0].position).toEqual(DEFAULT_NODE_POSITIONS.PROJECT_SOURCES)
    expect(nodes.slice(5).every((node) => node.data.status === 'LOCKED' && node.data.locked)).toBe(true)
    nodes[0].data.onOpen()
    expect(openNode).toHaveBeenCalledWith('PROJECT_SOURCES')
  })

  it('derives only conservative summaries from existing workspace state', () => {
    const presentation = deriveWorkflowPresentation({
      inputs: [{ source_type: 'TEXT', content: 'Build it', chunks: { status: 'SUCCESS' } }],
      selectedOutputs: ['BACKEND_CODE'],
      readinessState: { status: 'idle', result: null, error: '', stale: false },
      githubState: { status: 'connected', connection: { connected: true } },
      repositoryState: { status: 'ready', repository: null },
    })

    expect(presentation.PROJECT_SOURCES).toMatchObject({ status: 'RUNNING', summary: '1 source · 1 selected output' })
    expect(presentation.INPUT_ANALYSIS).toMatchObject({ status: 'RUNNING', summary: '1 source prepared · 0 pending' })
    expect(presentation.SPECIFICATION_VERIFICATION.status).toBe('WAITING_FOR_HUMAN')
    expect(presentation.IMPLEMENTATION_READINESS.status).toBe('NOT_STARTED')
    expect(presentation.DELIVERY_SETUP.status).toBe('RUNNING')
  })

  it('maps authoritative preparation and human-review states into workflow nodes', () => {
    const presentation = deriveWorkflowPresentation({
      inputs: [],
      selectedOutputs: [],
      preparationState: {
        result: {
          status: 'WAITING_FOR_HUMAN', processed_source_count: 3,
          eligible_source_count: 3, failed_source_count: 0,
          human_review_source_count: 2,
          requires_human_review: true,
        },
      },
    })

    expect(presentation.INPUT_ANALYSIS).toMatchObject({
      status: 'WAITING_FOR_HUMAN', summary: '3 / 3 eligible sources processed',
    })
    expect(presentation.SPECIFICATION_VERIFICATION).toMatchObject({
      status: 'WAITING_FOR_HUMAN', summary: '2 sources awaiting verification',
    })
  })

  it('maps authoritative specification preparation and semantic decisions', () => {
    const presentation = deriveWorkflowPresentation({
      inputs: [],
      selectedOutputs: [],
      specificationState: {
        result: {
          status: 'WAITING_FOR_SEMANTIC_REVIEW', ready_source_count: 2,
          applicable_source_count: 3, failed_source_count: 0,
          pending_semantic_decision_count: 3,
        },
      },
    })
    expect(presentation.SPECIFICATION_VERIFICATION).toMatchObject({
      status: 'WAITING_FOR_HUMAN',
      summary: '3 semantic decisions required',
      attentionCount: 3,
    })
  })
})
