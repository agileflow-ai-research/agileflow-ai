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
    expect(nodes[5].data).toMatchObject({ status: 'NOT_STARTED', locked: false })
    expect(nodes.slice(6).every((node) => node.data.status === 'LOCKED' && node.data.locked)).toBe(true)
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
    expect(presentation.GENERATE_IMPLEMENTATION.status).toBe('NOT_STARTED')
  })

  it('maps final approval honestly without claiming code generation', () => {
    const waiting = deriveWorkflowPresentation({
      consolidationState: { result: { status: 'READY' } },
      readinessState: { result: { status: 'READY', current: true }, stale: false },
      runState: { status: 'loaded', runs: [] },
    })
    expect(waiting.GENERATE_IMPLEMENTATION).toMatchObject({
      status: 'WAITING_FOR_HUMAN', summary: 'Final implementation approval required',
    })

    const approved = deriveWorkflowPresentation({
      consolidationState: { result: { status: 'STALE' } },
      readinessState: { result: { status: 'NOT_READY', current: false }, stale: true },
      runState: { status: 'loaded', runs: [{ run_id: 'RUN-012' }] },
    })
    expect(approved.GENERATE_IMPLEMENTATION).toMatchObject({
      status: 'COMPLETE', summary: 'RUN-012 ready for future generation',
    })
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

  it('maps real consolidation states onto the existing specification node', () => {
    const review = deriveWorkflowPresentation({
      inputs: [], selectedOutputs: [],
      consolidationState: { result: { status: 'WAITING_FOR_HUMAN', pending_conflict_count: 2, issue_count: 0 } },
    })
    expect(review.SPECIFICATION_VERIFICATION).toMatchObject({
      status: 'WAITING_FOR_HUMAN', summary: '2 cross-source decisions required', attentionCount: 2,
    })

    const ready = deriveWorkflowPresentation({
      inputs: [], selectedOutputs: [], consolidationState: { result: { status: 'READY', pending_conflict_count: 0, issue_count: 0 } },
    })
    expect(ready.SPECIFICATION_VERIFICATION).toMatchObject({
      status: 'COMPLETE', summary: 'Project specification ready',
    })
  })
})
