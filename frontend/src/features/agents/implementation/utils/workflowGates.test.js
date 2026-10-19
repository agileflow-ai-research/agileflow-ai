import { describe, expect, it } from 'vitest'

import { deriveWorkflowGates } from './workflowGates.js'

function readySnapshot(overrides = {}) {
  return {
    inputs: [{ source_type: 'TEXT', content: 'Build it' }],
    selectedOutputs: ['BACKEND_CODE'],
    preparationState: { result: { status: 'ANALYSIS_READY' } },
    specificationState: { result: { status: 'SPECIFICATION_READY' } },
    consolidationState: { result: { status: 'READY' } },
    readinessState: {
      status: 'complete', stale: false,
      result: { status: 'READY', current: true, readiness_id: 'RDY-1', readiness_fingerprint: 'a'.repeat(64) },
    },
    repositoryState: { status: 'idle', repository: null },
    deliveryDecision: 'PENDING',
    runState: { status: 'loaded', runs: [], current: null },
    ...overrides,
  }
}

describe('hard workflow gates', () => {
  it.each([
    ['artifact', { preparationState: { result: { status: 'WAITING_FOR_HUMAN' } } }],
    ['semantic', { specificationState: { result: { status: 'WAITING_FOR_SEMANTIC_REVIEW' } } }],
    ['cross-source', { consolidationState: { result: { status: 'WAITING_FOR_HUMAN' } } }],
  ])('%s review blocks readiness, delivery, and final approval', (_, override) => {
    const gates = deriveWorkflowGates(readySnapshot(override))
    expect(gates.SPECIFICATION_GATE.waiting_for_human).toBe(true)
    expect(gates.READINESS_GATE.satisfied).toBe(false)
    expect(gates.DELIVERY_GATE.satisfied).toBe(false)
    expect(gates.FINAL_APPROVAL_GATE.satisfied).toBe(false)
    expect(gates.automation.readiness_evaluation_allowed).toBe(false)
  })

  it('does not allow consolidation while semantic review is unresolved', () => {
    const gates = deriveWorkflowGates(readySnapshot({
      specificationState: { result: { status: 'WAITING_FOR_SEMANTIC_REVIEW' } },
      consolidationState: { result: { status: 'NOT_STARTED' } },
    }))
    expect(gates.automation.consolidation_allowed).toBe(false)
  })

  it('keeps configured raw delivery blocked behind specification review', () => {
    const gates = deriveWorkflowGates(readySnapshot({
      preparationState: { result: { status: 'WAITING_FOR_HUMAN' } },
      repositoryState: { status: 'created', repository: { full_name: 'octocat/app' } },
    }))
    expect(gates.DELIVERY_GATE.blocked).toBe(true)
    expect(gates.DELIVERY_GATE.blocking_reason).toBe('Complete specification review first')
  })

  it('blocks not-ready and unapproved warnings, then unblocks approved readiness', () => {
    const notReady = deriveWorkflowGates(readySnapshot({
      readinessState: { status: 'complete', stale: false, result: { status: 'NOT_READY', current: true, readiness_id: 'RDY-1' } },
    }))
    expect(notReady.DELIVERY_GATE.blocked).toBe(true)

    const warningPending = deriveWorkflowGates(readySnapshot({
      readinessState: { status: 'complete', stale: false, result: { status: 'READY_WITH_WARNINGS', current: true, readiness_id: 'RDY-1', continuation_approved: false } },
    }))
    expect(warningPending.READINESS_GATE.waiting_for_human).toBe(true)
    expect(warningPending.DELIVERY_GATE.blocking_reason).toBe('Waiting for readiness approval')

    for (const [status, continuationApproved] of [['READY', false], ['READY_WITH_WARNINGS', true]]) {
      const gates = deriveWorkflowGates(readySnapshot({
        readinessState: { status: 'complete', stale: false, result: { status, current: true, readiness_id: 'RDY-1', continuation_approved: continuationApproved } },
      }))
      expect(gates.READINESS_GATE.satisfied).toBe(true)
      expect(gates.DELIVERY_GATE.waiting_for_human).toBe(true)
    }
  })

  it('does not let configured GitHub bypass warning continuation approval', () => {
    const gates = deriveWorkflowGates(readySnapshot({
      readinessState: { status: 'complete', stale: false, result: { status: 'READY_WITH_WARNINGS', current: true, readiness_id: 'RDY-1', continuation_approved: false } },
      repositoryState: { status: 'created', repository: { full_name: 'octocat/app' } },
    }))
    expect(gates.READINESS_GATE.waiting_for_human).toBe(true)
    expect(gates.DELIVERY_GATE.blocked).toBe(true)
    expect(gates.FINAL_APPROVAL_GATE.blocked).toBe(true)
  })

  it('requires explicit delivery completion and ignores unrelated historical runs', () => {
    const historical = {
      run_id: 'ARUN-OLD', run_status: 'READY_FOR_GENERATION',
      readiness_id: 'RDY-OLD', readiness_fingerprint: 'b'.repeat(64),
    }
    const pending = deriveWorkflowGates(readySnapshot({ runState: { status: 'loaded', runs: [historical] } }))
    expect(pending.FINAL_APPROVAL_GATE.blocked).toBe(true)

    const skipped = deriveWorkflowGates(readySnapshot({
      deliveryDecision: 'SKIPPED', runState: { status: 'loaded', runs: [historical] },
    }))
    expect(skipped.FINAL_APPROVAL_GATE.waiting_for_human).toBe(true)
    expect(skipped.approvedRun).toBeNull()
  })

  it('recognizes only an AgentRun approved for the current readiness snapshot', () => {
    const currentRun = {
      run_id: 'ARUN-CURRENT', run_status: 'READY_FOR_GENERATION', readiness_id: 'RDY-1',
      readiness_fingerprint: 'a'.repeat(64),
    }
    const gates = deriveWorkflowGates(readySnapshot({
      deliveryDecision: 'SKIPPED', runState: { status: 'loaded', runs: [currentRun] },
    }))
    expect(gates.FINAL_APPROVAL_GATE.satisfied).toBe(true)
    expect(gates.approvedRun).toEqual(currentRun)
  })
})
