import { describe, expect, it } from 'vitest'

import { deriveWorkflowTransition } from './workflowProgression.js'

function snapshot({
  preparation,
  specification,
  consolidation,
  readiness,
  readinessStatus,
  stale = false,
  continuationApproved = false,
  deliveryDecision = 'PENDING',
  repository = null,
  runs = [],
} = {}) {
  const trustedReady = consolidation === 'READY'
  return {
    preparationState: { result: preparation || trustedReady ? { status: preparation ?? 'ANALYSIS_READY' } : null },
    specificationState: { result: specification || trustedReady ? { status: specification ?? 'SPECIFICATION_READY' } : null },
    consolidationState: { result: consolidation ? { status: consolidation } : null },
    readinessState: {
      status: readinessStatus ?? 'complete',
      result: readiness ? { status: readiness, continuation_approved: continuationApproved } : null,
      stale,
    },
    deliveryDecision,
    repositoryState: { status: repository ? 'created' : 'idle', repository },
    runState: { status: 'loaded', runs },
  }
}

describe('workflow progression presentation', () => {
  it('follows authoritative mechanical and human-review states', () => {
    expect(deriveWorkflowTransition(snapshot({ preparation: 'RUNNING' }))).toMatchObject({
      nodeId: 'INPUT_ANALYSIS', requiresUserAction: false,
    })
    expect(deriveWorkflowTransition(snapshot({ preparation: 'WAITING_FOR_HUMAN' }))).toMatchObject({
      nodeId: 'SPECIFICATION_VERIFICATION', requiresUserAction: true,
    })
    expect(deriveWorkflowTransition(snapshot({ specification: 'WAITING_FOR_SEMANTIC_REVIEW' })).nodeId).toBe('SPECIFICATION_VERIFICATION')
    expect(deriveWorkflowTransition(snapshot({ consolidation: 'CONSOLIDATING' })).nodeId).toBe('SPECIFICATION_VERIFICATION')
  })

  it('moves a ready specification through readiness without bypassing not-ready results', () => {
    expect(deriveWorkflowTransition(snapshot({ consolidation: 'READY', readinessStatus: 'evaluating' })).nodeId).toBe('IMPLEMENTATION_READINESS')
    expect(deriveWorkflowTransition(snapshot({ consolidation: 'READY', readiness: 'NOT_READY' })).nodeId).toBe('IMPLEMENTATION_READINESS')
    expect(deriveWorkflowTransition(snapshot({ consolidation: 'READY', readiness: 'READY' })).nodeId).toBe('DELIVERY_SETUP')
    expect(deriveWorkflowTransition(snapshot({ consolidation: 'READY', readiness: 'READY_WITH_WARNINGS' })).nodeId).toBe('IMPLEMENTATION_READINESS')
    expect(deriveWorkflowTransition(snapshot({ consolidation: 'READY', readiness: 'READY_WITH_WARNINGS', continuationApproved: true })).nodeId).toBe('DELIVERY_SETUP')
  })

  it('presents final approval only after delivery is satisfied and never creates a run', () => {
    const next = deriveWorkflowTransition(snapshot({
      consolidation: 'READY',
      readiness: 'READY',
      deliveryDecision: 'SKIPPED',
    }))
    expect(next).toMatchObject({
      nodeId: 'GENERATE_IMPLEMENTATION',
      requiresUserAction: true,
    })
    expect(next).not.toHaveProperty('action')
  })

  it('never navigates beyond an unresolved human gate even when raw downstream data is ready', () => {
    const next = deriveWorkflowTransition({
      preparationState: { result: { status: 'WAITING_FOR_HUMAN' } },
      specificationState: { result: { status: 'SPECIFICATION_READY' } },
      consolidationState: { result: { status: 'READY' } },
      readinessState: { status: 'complete', result: { status: 'READY', current: true } },
      repositoryState: { status: 'created', repository: { full_name: 'octocat/app' } },
    })
    expect(next).toMatchObject({ nodeId: 'SPECIFICATION_VERIFICATION', key: 'review:artifact' })
  })
})
