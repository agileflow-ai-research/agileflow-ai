import { act, renderHook, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import {
  acknowledgeTestGenerationContextWarnings,
  confirmTestGenerationSetup,
  getTestGenerationIntelligenceReview,
  getTestGenerationWorkflow,
  getTestGenerationContextResult,
  retryTestGenerationPreparationSource,
  retryTestGenerationIntelligenceSource,
  retryTestGenerationContextAnalysis,
  startTestGenerationContextAnalysis,
  startTestGenerationIntelligence,
  startTestGenerationPreparation,
  submitTestGenerationIntelligenceReview,
  updateTestGenerationOutputs,
} from '../testingValidationAgentService.js'
import useTestingValidationWorkflow from './useTestingValidationWorkflow.js'

vi.mock('../testingValidationAgentService.js', () => ({
  acknowledgeTestGenerationContextWarnings: vi.fn(),
  confirmTestGenerationSetup: vi.fn(),
  getTestGenerationIntelligenceReview: vi.fn(),
  getTestGenerationWorkflow: vi.fn(),
  getTestGenerationContextResult: vi.fn(),
  retryTestGenerationPreparationSource: vi.fn(),
  retryTestGenerationIntelligenceSource: vi.fn(),
  retryTestGenerationContextAnalysis: vi.fn(),
  startTestGenerationContextAnalysis: vi.fn(),
  startTestGenerationIntelligence: vi.fn(),
  startTestGenerationPreparation: vi.fn(),
  submitTestGenerationIntelligenceReview: vi.fn(),
  updateTestGenerationOutputs: vi.fn(),
}))

const nodeIds = [
  'INPUT_OUTPUT_SETUP', 'INPUT_PREPARATION', 'TESTING_INTELLIGENCE',
  'CONTEXT_TESTABILITY', 'TEST_PLANNING_REVIEW', 'TEST_GENERATION_RESULTS',
]

function workflow(projectId = 'AGP-004') {
  return {
    agent_project_id: projectId,
    agent_stage: 'TEST_GENERATION',
    pipeline_status: 'WAITING_FOR_HUMAN',
    current_node_id: 'INPUT_OUTPUT_SETUP',
    selected_outputs: [],
    selection_revision: 0,
    selection_updated_at: null,
    n1_confirmation: null,
    nodes: nodeIds.map((nodeId, index) => ({
      node_id: nodeId, status: index === 0 ? 'WAITING_FOR_HUMAN' : 'LOCKED',
    })),
  }
}

function deferred() {
  let reject
  let resolve
  const promise = new Promise((next, fail) => { resolve = next; reject = fail })
  return { promise, reject, resolve }
}

function n2Workflow(status = 'RUNNING') {
  const terminal = ['COMPLETED', 'FAILED', 'INTERRUPTED'].includes(status)
  return {
    ...workflow(),
    pipeline_status: status === 'FAILED' ? 'FAILED' : 'RUNNING',
    current_node_id: status === 'COMPLETED' ? 'TESTING_INTELLIGENCE' : 'INPUT_PREPARATION',
    n1_confirmation: { confirmation_id: 'A4N1C-confirmed' },
    n2_execution: {
      execution_id: 'A4N2E-current',
      attempt_number: 1,
      status,
      total_chunks: terminal ? 2 : 0,
      sources: [],
    },
    nodes: nodeIds.map((nodeId, index) => ({
      node_id: nodeId,
      status: index === 0
        ? 'COMPLETED'
        : index === 1
          ? status
          : index === 2 && status === 'COMPLETED' ? 'NOT_STARTED' : 'LOCKED',
    })),
  }
}

function n3Workflow(status = 'RUNNING') {
  return {
    ...n2Workflow('COMPLETED'),
    pipeline_status: status === 'WAITING_FOR_HUMAN' ? 'WAITING_FOR_HUMAN' : status === 'FAILED' ? 'FAILED' : 'RUNNING',
    current_node_id: 'TESTING_INTELLIGENCE',
    n3_execution: { execution_id: 'A4N3E-current', attempt_number: 1, status, sources: [] },
    nodes: nodeIds.map((nodeId, index) => ({
      node_id: nodeId,
      status: index < 2 ? 'COMPLETED' : index === 2 ? status : 'LOCKED',
    })),
  }
}

function n4Workflow(status = 'RUNNING') {
  const terminal = ['WAITING_FOR_HUMAN', 'BLOCKED', 'COMPLETED', 'FAILED', 'INTERRUPTED'].includes(status)
  return {
    ...n3Workflow('COMPLETED'),
    pipeline_status: status === 'WAITING_FOR_HUMAN' ? 'WAITING_FOR_HUMAN' : status === 'FAILED' ? 'FAILED' : 'RUNNING',
    current_node_id: status === 'COMPLETED' ? 'TEST_PLANNING_REVIEW' : 'CONTEXT_TESTABILITY',
    n4_execution: {
      execution_id: 'A4N4E-current', attempt_number: 1, status,
      overall_decision: terminal && status !== 'FAILED' && status !== 'INTERRUPTED'
        ? status === 'BLOCKED' ? 'BLOCKED' : status === 'WAITING_FOR_HUMAN' ? 'PROCEED_WITH_WARNINGS' : 'PROCEED'
        : null,
      stages: ['TRACEABILITY', 'TESTABILITY', 'FEASIBILITY', 'CONTEXT_DECISION'].map((stage) => ({
        stage, status: terminal || status === 'RUNNING' ? 'COMPLETE' : 'NOT_RUN',
      })),
    },
    nodes: nodeIds.map((nodeId, index) => ({
      node_id: nodeId,
      status: index < 3
        ? 'COMPLETED'
        : index === 3
          ? status
          : index === 4 && status === 'COMPLETED' ? 'NOT_STARTED' : 'LOCKED',
    })),
  }
}

describe('useTestingValidationWorkflow', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    getTestGenerationWorkflow.mockResolvedValue({ data: workflow() })
    updateTestGenerationOutputs.mockResolvedValue({ data: workflow() })
    confirmTestGenerationSetup.mockResolvedValue({ data: workflow() })
    retryTestGenerationPreparationSource.mockResolvedValue({ data: workflow() })
    retryTestGenerationIntelligenceSource.mockResolvedValue({ data: workflow() })
    startTestGenerationIntelligence.mockResolvedValue({ data: workflow() })
    submitTestGenerationIntelligenceReview.mockResolvedValue({ data: workflow() })
    getTestGenerationIntelligenceReview.mockResolvedValue({
      data: { review_snapshot_fingerprint: 'a'.repeat(64), items: [] },
    })
    startTestGenerationPreparation.mockResolvedValue({ data: workflow() })
    startTestGenerationContextAnalysis.mockResolvedValue({ data: workflow() })
    retryTestGenerationContextAnalysis.mockResolvedValue({ data: workflow() })
    acknowledgeTestGenerationContextWarnings.mockResolvedValue({ data: workflow() })
    getTestGenerationContextResult.mockResolvedValue({ data: null })
  })

  it('loads and explicitly refreshes authoritative workflow state without polling', async () => {
    const { result } = renderHook(() => useTestingValidationWorkflow('AGP-004'))
    expect(result.current.loadStatus).toBe('loading')
    await waitFor(() => expect(result.current.loadStatus).toBe('success'))
    expect(result.current.workflowState).toEqual(workflow())
    expect(getTestGenerationWorkflow).toHaveBeenCalledTimes(1)

    getTestGenerationWorkflow.mockResolvedValueOnce({ data: {
      ...workflow(), pipeline_status: 'RUNNING',
    } })
    await act(() => result.current.refresh())
    expect(result.current.workflowState.pipeline_status).toBe('RUNNING')
    expect(getTestGenerationWorkflow).toHaveBeenCalledTimes(2)
  })

  it('exposes a safe load error and explicit retry', async () => {
    getTestGenerationWorkflow
      .mockRejectedValueOnce({ status: 503, errors: [{ message: 'Workflow unavailable' }] })
      .mockResolvedValueOnce({ data: workflow() })
    const { result } = renderHook(() => useTestingValidationWorkflow('AGP-004'))
    await waitFor(() => expect(result.current.loadStatus).toBe('error'))
    expect(result.current.loadError).toBe('Workflow unavailable')

    act(() => result.current.retry())
    expect(result.current.loadStatus).toBe('loading')
    await waitFor(() => expect(result.current.loadStatus).toBe('success'))
    expect(getTestGenerationWorkflow).toHaveBeenCalledTimes(2)
  })

  it('prevents a stale project response from replacing newer state', async () => {
    const oldRequest = deferred()
    getTestGenerationWorkflow.mockImplementation((projectId) => (
      projectId === 'AGP-004'
        ? oldRequest.promise
        : Promise.resolve({ data: workflow('AGP-005') })
    ))
    const { result, rerender } = renderHook(
      ({ projectId }) => useTestingValidationWorkflow(projectId),
      { initialProps: { projectId: 'AGP-004' } },
    )

    rerender({ projectId: 'AGP-005' })
    await waitFor(() => expect(result.current.workflowState?.agent_project_id).toBe('AGP-005'))
    oldRequest.resolve({ data: workflow('AGP-004') })
    await act(async () => { await Promise.resolve(); await Promise.resolve() })
    expect(result.current.workflowState.agent_project_id).toBe('AGP-005')
  })

  it('rejects malformed projections instead of deriving fallback node state', async () => {
    getTestGenerationWorkflow.mockResolvedValueOnce({ data: {
      ...workflow(), nodes: workflow().nodes.slice(0, 5),
    } })
    const { result } = renderHook(() => useTestingValidationWorkflow('AGP-004'))
    await waitFor(() => expect(result.current.loadStatus).toBe('error'))
    expect(result.current.workflowState).toBeNull()
  })

  it('saves outputs explicitly and adopts the authoritative response', async () => {
    const saved = {
      ...workflow(),
      selected_outputs: ['UNIT_TEST_CASES', 'API_TEST_CASES'],
      selection_revision: 1,
      selection_updated_at: '2026-10-21T01:00:00Z',
    }
    updateTestGenerationOutputs.mockResolvedValueOnce({ data: saved })
    const { result } = renderHook(() => useTestingValidationWorkflow('AGP-004'))
    await waitFor(() => expect(result.current.loadStatus).toBe('success'))

    let returned
    await act(async () => {
      returned = await result.current.saveOutputs(['API_TEST_CASES', 'UNIT_TEST_CASES'])
    })

    expect(updateTestGenerationOutputs).toHaveBeenCalledWith(
      'AGP-004', ['API_TEST_CASES', 'UNIT_TEST_CASES'],
    )
    expect(returned).toEqual(saved)
    expect(result.current.workflowState).toEqual(saved)
    expect(result.current.outputSaveError).toBe('')
    expect(result.current.outputSaving).toBe(false)
  })

  it('exposes save loading and a safe error without discarding loaded workflow', async () => {
    const pending = deferred()
    updateTestGenerationOutputs.mockReturnValueOnce(pending.promise)
    const { result } = renderHook(() => useTestingValidationWorkflow('AGP-004'))
    await waitFor(() => expect(result.current.loadStatus).toBe('success'))

    let savePromise
    act(() => { savePromise = result.current.saveOutputs(['SECURITY_TEST_CASES']) })
    expect(result.current.outputSaving).toBe(true)
    pending.reject({ status: 503, errors: [{ message: 'Output selection is unavailable' }] })
    await act(async () => { await savePromise })

    expect(result.current.outputSaving).toBe(false)
    expect(result.current.outputSaveError).toBe('Output selection is unavailable')
    expect(result.current.workflowState).toEqual(workflow())
  })

  it('ignores a stale output save after the active project changes', async () => {
    const oldSave = deferred()
    updateTestGenerationOutputs.mockReturnValueOnce(oldSave.promise)
    const { result, rerender } = renderHook(
      ({ projectId }) => useTestingValidationWorkflow(projectId),
      { initialProps: { projectId: 'AGP-004' } },
    )
    await waitFor(() => expect(result.current.loadStatus).toBe('success'))
    let oldPromise
    act(() => { oldPromise = result.current.saveOutputs(['UNIT_TEST_CASES']) })

    getTestGenerationWorkflow.mockResolvedValueOnce({ data: workflow('AGP-005') })
    rerender({ projectId: 'AGP-005' })
    await waitFor(() => expect(result.current.workflowState?.agent_project_id).toBe('AGP-005'))
    oldSave.resolve({ data: {
      ...workflow('AGP-004'),
      selected_outputs: ['UNIT_TEST_CASES'],
      selection_revision: 1,
      selection_updated_at: '2026-10-21T01:00:00Z',
    } })

    await act(async () => { expect(await oldPromise).toBeNull() })
    expect(result.current.workflowState.agent_project_id).toBe('AGP-005')
    expect(result.current.outputSaveError).toBe('')
  })

  it('confirms N1 and adopts the authoritative workflow transition', async () => {
    const confirmation = {
      confirmation_id: `A4N1C-${'a'.repeat(32)}`,
      source_count: 1,
      selected_output_count: 1,
      selected_outputs: ['UNIT_TEST_CASES'],
      source_ids: [`A4SRC-${'b'.repeat(32)}`],
      source_set_digest: 'c'.repeat(64),
      selection_digest: 'd'.repeat(64),
      selection_revision: 1,
      confirmed_at: '2026-10-21T02:00:00Z',
    }
    const confirmed = {
      ...workflow(),
      pipeline_status: 'RUNNING',
      current_node_id: 'INPUT_PREPARATION',
      selected_outputs: ['UNIT_TEST_CASES'],
      selection_revision: 1,
      selection_updated_at: '2026-10-21T01:00:00Z',
      n1_confirmation: confirmation,
      nodes: nodeIds.map((nodeId, index) => ({
        node_id: nodeId,
        status: index === 0 ? 'COMPLETED' : index === 1 ? 'NOT_STARTED' : 'LOCKED',
      })),
    }
    confirmTestGenerationSetup.mockResolvedValueOnce({ data: confirmed })
    const { result } = renderHook(() => useTestingValidationWorkflow('AGP-004'))
    await waitFor(() => expect(result.current.loadStatus).toBe('success'))

    let returned
    await act(async () => { returned = await result.current.confirmN1() })

    expect(confirmTestGenerationSetup).toHaveBeenCalledWith('AGP-004')
    expect(returned).toEqual(confirmed)
    expect(result.current.workflowState).toEqual(confirmed)
    expect(result.current.confirmationSubmitting).toBe(false)
    expect(result.current.confirmationError).toBe('')
  })

  it('preserves workflow state and exposes a safe confirmation error', async () => {
    confirmTestGenerationSetup.mockRejectedValueOnce({
      status: 409,
      errors: [{ message: 'Add at least one primary functional source.' }],
    })
    const { result } = renderHook(() => useTestingValidationWorkflow('AGP-004'))
    await waitFor(() => expect(result.current.loadStatus).toBe('success'))

    await act(async () => { await result.current.confirmN1() })

    expect(result.current.workflowState).toEqual(workflow())
    expect(result.current.confirmationError).toBe(
      'Add at least one primary functional source.',
    )
  })

  it('polls while N2 is active and stops after completion', async () => {
    vi.useFakeTimers()
    getTestGenerationWorkflow
      .mockResolvedValueOnce({ data: n2Workflow('QUEUED') })
      .mockResolvedValueOnce({ data: n2Workflow('RUNNING') })
      .mockResolvedValueOnce({ data: n2Workflow('COMPLETED') })
    try {
      const { result } = renderHook(() => useTestingValidationWorkflow('AGP-004'))
      await act(async () => { await Promise.resolve(); await Promise.resolve() })
      expect(result.current.workflowState.n2_execution.status).toBe('QUEUED')
      expect(vi.getTimerCount()).toBe(1)
      await act(async () => { await vi.advanceTimersByTimeAsync(2000) })
      expect(result.current.workflowState.n2_execution.status).toBe('RUNNING')
      await act(async () => { await vi.advanceTimersByTimeAsync(2000) })
      expect(result.current.workflowState.n2_execution.status).toBe('COMPLETED')
      expect(vi.getTimerCount()).toBe(0)
    } finally {
      vi.useRealTimers()
    }
  })

  it('starts an exact legacy confirmed NOT_STARTED workflow once', async () => {
    const legacy = {
      ...workflow(),
      pipeline_status: 'RUNNING',
      current_node_id: 'INPUT_PREPARATION',
      n1_confirmation: { confirmation_id: 'A4N1C-confirmed' },
      n2_execution: null,
      nodes: nodeIds.map((nodeId, index) => ({
        node_id: nodeId,
        status: index === 0 ? 'COMPLETED' : index === 1 ? 'NOT_STARTED' : 'LOCKED',
      })),
    }
    getTestGenerationWorkflow.mockResolvedValueOnce({ data: legacy })
    startTestGenerationPreparation.mockResolvedValueOnce({ data: n2Workflow('QUEUED') })
    const { result } = renderHook(() => useTestingValidationWorkflow('AGP-004'))
    await waitFor(() => expect(result.current.workflowState?.n2_execution?.status).toBe('QUEUED'))
    expect(startTestGenerationPreparation).toHaveBeenCalledTimes(1)
  })

  it('retries one failed source and adopts the queued attempt', async () => {
    const failed = n2Workflow('FAILED')
    failed.n2_execution.sources = [{ source_id: 'A4SRC-one', status: 'FAILED' }]
    const queued = n2Workflow('QUEUED')
    queued.n2_execution.attempt_number = 2
    getTestGenerationWorkflow.mockResolvedValueOnce({ data: failed })
    retryTestGenerationPreparationSource.mockResolvedValueOnce({ data: queued })
    const { result } = renderHook(() => useTestingValidationWorkflow('AGP-004'))
    await waitFor(() => expect(result.current.loadStatus).toBe('success'))
    await act(() => result.current.retryPreparationSource('A4SRC-one'))
    expect(retryTestGenerationPreparationSource).toHaveBeenCalledWith('AGP-004', 'A4SRC-one')
    expect(result.current.workflowState.n2_execution.attempt_number).toBe(2)
  })

  it('starts a legacy N3 NOT_STARTED workflow exactly once', async () => {
    const legacy = { ...n2Workflow('COMPLETED'), n3_execution: null }
    const queued = n3Workflow('QUEUED')
    getTestGenerationWorkflow.mockResolvedValueOnce({ data: legacy })
    startTestGenerationIntelligence.mockResolvedValueOnce({ data: queued })
    const { result } = renderHook(() => useTestingValidationWorkflow('AGP-004'))
    await waitFor(() => expect(result.current.workflowState?.n3_execution?.status).toBe('QUEUED'))
    expect(startTestGenerationIntelligence).toHaveBeenCalledTimes(1)
  })

  it('loads review evidence and does not poll while waiting for a human', async () => {
    getTestGenerationWorkflow.mockResolvedValueOnce({ data: n3Workflow('WAITING_FOR_HUMAN') })
    const { result } = renderHook(() => useTestingValidationWorkflow('AGP-004'))
    await waitFor(() => expect(result.current.intelligenceReview).not.toBeNull())
    expect(getTestGenerationIntelligenceReview).toHaveBeenCalledWith('AGP-004')
    expect(getTestGenerationWorkflow).toHaveBeenCalledTimes(1)
  })

  it('polls N3 through queued and running then stops on completion', async () => {
    vi.useFakeTimers()
    getTestGenerationWorkflow
      .mockResolvedValueOnce({ data: n3Workflow('QUEUED') })
      .mockResolvedValueOnce({ data: n3Workflow('RUNNING') })
      .mockResolvedValueOnce({ data: n3Workflow('COMPLETED') })
    try {
      const { result } = renderHook(() => useTestingValidationWorkflow('AGP-004'))
      await act(async () => { await Promise.resolve(); await Promise.resolve() })
      expect(result.current.workflowState.n3_execution.status).toBe('QUEUED')
      expect(vi.getTimerCount()).toBe(1)
      await act(async () => { await vi.advanceTimersByTimeAsync(2000) })
      expect(result.current.workflowState.n3_execution.status).toBe('RUNNING')
      await act(async () => { await vi.advanceTimersByTimeAsync(2000) })
      expect(result.current.workflowState.n3_execution.status).toBe('COMPLETED')
      expect(vi.getTimerCount()).toBe(0)
    } finally {
      vi.useRealTimers()
    }
  })

  it.each(['FAILED', 'COMPLETED'])('does not poll terminal N3 status %s', async (status) => {
    vi.useFakeTimers()
    getTestGenerationWorkflow.mockResolvedValueOnce({ data: n3Workflow(status) })
    try {
      renderHook(() => useTestingValidationWorkflow('AGP-004'))
      await act(async () => { await Promise.resolve(); await Promise.resolve() })
      expect(vi.getTimerCount()).toBe(0)
      expect(getTestGenerationWorkflow).toHaveBeenCalledTimes(1)
    } finally {
      vi.useRealTimers()
    }
  })

  it('cleans an active N3 polling timer on unmount', async () => {
    vi.useFakeTimers()
    getTestGenerationWorkflow.mockResolvedValueOnce({ data: n3Workflow('RUNNING') })
    try {
      const { unmount } = renderHook(() => useTestingValidationWorkflow('AGP-004'))
      await act(async () => { await Promise.resolve(); await Promise.resolve() })
      expect(vi.getTimerCount()).toBe(1)
      unmount()
      expect(vi.getTimerCount()).toBe(0)
    } finally {
      vi.useRealTimers()
    }
  })

  it('submits the trusted snapshot, adopts continuation, and resumes polling', async () => {
    vi.useFakeTimers()
    const waiting = n3Workflow('WAITING_FOR_HUMAN')
    const queued = n3Workflow('QUEUED')
    getTestGenerationWorkflow.mockResolvedValueOnce({ data: waiting })
    submitTestGenerationIntelligenceReview.mockResolvedValueOnce({ data: queued })
    try {
      const { result } = renderHook(() => useTestingValidationWorkflow('AGP-004'))
      await act(async () => { await Promise.resolve(); await Promise.resolve() })
      await act(async () => { await Promise.resolve(); await Promise.resolve() })
      const resolutions = [{ chunk_id: 'A4CHK-one', label: 'AUTHORIZATION', decision: 'ACCEPT' }]
      await act(() => result.current.submitIntelligenceReview(resolutions))
      expect(submitTestGenerationIntelligenceReview).toHaveBeenCalledWith('AGP-004', {
        review_snapshot_fingerprint: 'a'.repeat(64), resolutions,
      })
      expect(result.current.workflowState.n3_execution.status).toBe('QUEUED')
      expect(result.current.intelligenceReview).toBeNull()
      expect(vi.getTimerCount()).toBe(1)
    } finally {
      vi.useRealTimers()
    }
  })

  it('retries one failed N3 source and exposes only a safe request error', async () => {
    const failed = n3Workflow('FAILED')
    failed.n3_execution.sources = [{ source_id: 'A4SRC-one', status: 'FAILED' }]
    getTestGenerationWorkflow.mockResolvedValueOnce({ data: failed })
    retryTestGenerationIntelligenceSource.mockRejectedValueOnce({
      status: 409, errors: [{ message: 'The source retry is no longer current.' }],
    })
    const { result } = renderHook(() => useTestingValidationWorkflow('AGP-004'))
    await waitFor(() => expect(result.current.loadStatus).toBe('success'))
    await act(() => result.current.retryIntelligenceSource('A4SRC-one'))
    expect(retryTestGenerationIntelligenceSource).toHaveBeenCalledWith('AGP-004', 'A4SRC-one')
    expect(result.current.intelligenceError).toBe('The source retry is no longer current.')
    expect(result.current.retryingIntelligenceSourceId).toBeNull()
  })

  it('starts an exact legacy N4 NOT_STARTED workflow once', async () => {
    const legacy = {
      ...n3Workflow('COMPLETED'), current_node_id: 'CONTEXT_TESTABILITY', n4_execution: null,
      nodes: nodeIds.map((nodeId, index) => ({
        node_id: nodeId, status: index < 3 ? 'COMPLETED' : index === 3 ? 'NOT_STARTED' : 'LOCKED',
      })),
    }
    getTestGenerationWorkflow.mockResolvedValueOnce({ data: legacy })
    startTestGenerationContextAnalysis.mockResolvedValueOnce({ data: n4Workflow('QUEUED') })
    const { result } = renderHook(() => useTestingValidationWorkflow('AGP-004'))
    await waitFor(() => expect(result.current.workflowState?.n4_execution?.status).toBe('QUEUED'))
    expect(startTestGenerationContextAnalysis).toHaveBeenCalledTimes(1)
  })

  it('polls N4 while active and stops after warning review is reached', async () => {
    vi.useFakeTimers()
    getTestGenerationWorkflow
      .mockResolvedValueOnce({ data: n4Workflow('QUEUED') })
      .mockResolvedValueOnce({ data: n4Workflow('RUNNING') })
      .mockResolvedValueOnce({ data: n4Workflow('WAITING_FOR_HUMAN') })
    getTestGenerationContextResult.mockResolvedValueOnce({ data: {
      overall_decision: 'PROCEED_WITH_WARNINGS', warning_snapshot_fingerprint: 'b'.repeat(64), outputs: [],
    } })
    try {
      const { result } = renderHook(() => useTestingValidationWorkflow('AGP-004'))
      await act(async () => { await Promise.resolve(); await Promise.resolve() })
      expect(result.current.workflowState.n4_execution.status).toBe('QUEUED')
      expect(vi.getTimerCount()).toBe(1)
      await act(async () => { await vi.advanceTimersByTimeAsync(2000) })
      expect(result.current.workflowState.n4_execution.status).toBe('RUNNING')
      await act(async () => { await vi.advanceTimersByTimeAsync(2000) })
      expect(result.current.workflowState.n4_execution.status).toBe('WAITING_FOR_HUMAN')
      expect(vi.getTimerCount()).toBe(0)
      expect(getTestGenerationContextResult).toHaveBeenCalledWith('AGP-004')
    } finally {
      vi.useRealTimers()
    }
  })

  it('cleans N4 polling on unmount and project change', async () => {
    vi.useFakeTimers()
    getTestGenerationWorkflow.mockImplementation((projectId) => Promise.resolve({
      data: projectId === 'AGP-004' ? n4Workflow('RUNNING') : workflow('AGP-005'),
    }))
    try {
      const { rerender, unmount } = renderHook(
        ({ projectId }) => useTestingValidationWorkflow(projectId),
        { initialProps: { projectId: 'AGP-004' } },
      )
      await act(async () => { await Promise.resolve(); await Promise.resolve() })
      expect(vi.getTimerCount()).toBe(1)
      rerender({ projectId: 'AGP-005' })
      await act(async () => { await Promise.resolve(); await Promise.resolve() })
      expect(vi.getTimerCount()).toBe(0)
      unmount()
      expect(vi.getTimerCount()).toBe(0)
    } finally {
      vi.useRealTimers()
    }
  })

  it('does not retain an N4 result when the active project changes', async () => {
    const secondWorkflow = { ...n4Workflow('COMPLETED'), agent_project_id: 'AGP-005' }
    getTestGenerationWorkflow.mockImplementation((projectId) => Promise.resolve({
      data: projectId === 'AGP-004' ? n4Workflow('COMPLETED') : secondWorkflow,
    }))
    getTestGenerationContextResult
      .mockResolvedValueOnce({ data: { overall_decision: 'PROCEED', outputs: [{ output_code: 'FIRST' }] } })
      .mockResolvedValueOnce({ data: { overall_decision: 'PROCEED', outputs: [{ output_code: 'SECOND' }] } })
    const { result, rerender } = renderHook(
      ({ projectId }) => useTestingValidationWorkflow(projectId),
      { initialProps: { projectId: 'AGP-004' } },
    )
    await waitFor(() => expect(result.current.contextResult?.outputs[0].output_code).toBe('FIRST'))
    rerender({ projectId: 'AGP-005' })
    await waitFor(() => expect(result.current.contextResult?.outputs[0].output_code).toBe('SECOND'))
    expect(getTestGenerationContextResult).toHaveBeenLastCalledWith('AGP-005')
  })

  it.each(['WAITING_FOR_HUMAN', 'BLOCKED', 'COMPLETED', 'FAILED'])('does not compatibility-start or poll terminal N4 status %s', async (status) => {
    vi.useFakeTimers()
    getTestGenerationWorkflow.mockResolvedValueOnce({ data: n4Workflow(status) })
    if (['WAITING_FOR_HUMAN', 'BLOCKED', 'COMPLETED'].includes(status)) {
      getTestGenerationContextResult.mockResolvedValueOnce({ data: { overall_decision: 'PROCEED', outputs: [] } })
    }
    try {
      renderHook(() => useTestingValidationWorkflow('AGP-004'))
      await act(async () => { await Promise.resolve(); await Promise.resolve(); await Promise.resolve() })
      expect(startTestGenerationContextAnalysis).not.toHaveBeenCalled()
      expect(vi.getTimerCount()).toBe(0)
      expect(getTestGenerationWorkflow).toHaveBeenCalledTimes(1)
    } finally {
      vi.useRealTimers()
    }
  })

  it('acknowledges the server warning snapshot and adopts the N5 handoff', async () => {
    const waiting = n4Workflow('WAITING_FOR_HUMAN')
    const completed = n4Workflow('COMPLETED')
    const decision = {
      overall_decision: 'PROCEED_WITH_WARNINGS', warning_snapshot_fingerprint: 'b'.repeat(64), outputs: [],
    }
    getTestGenerationWorkflow.mockResolvedValueOnce({ data: waiting })
    getTestGenerationContextResult.mockResolvedValue({ data: decision })
    acknowledgeTestGenerationContextWarnings.mockResolvedValueOnce({ data: completed })
    const { result } = renderHook(() => useTestingValidationWorkflow('AGP-004'))
    await waitFor(() => expect(result.current.contextResult).toEqual(decision))
    await act(() => result.current.acknowledgeContextWarnings(' Reviewed '))
    expect(acknowledgeTestGenerationContextWarnings).toHaveBeenCalledWith('AGP-004', {
      warning_snapshot_fingerprint: 'b'.repeat(64), optional_note: 'Reviewed',
    })
    expect(result.current.workflowState.current_node_id).toBe('TEST_PLANNING_REVIEW')
    expect(result.current.contextActionSubmitting).toBe(false)
  })

  it('retries an operational N4 failure and adopts the append-only queued attempt', async () => {
    const failed = n4Workflow('FAILED')
    const queued = n4Workflow('QUEUED')
    queued.n4_execution.attempt_number = 2
    getTestGenerationWorkflow.mockResolvedValueOnce({ data: failed })
    retryTestGenerationContextAnalysis.mockResolvedValueOnce({ data: queued })
    const { result } = renderHook(() => useTestingValidationWorkflow('AGP-004'))
    await waitFor(() => expect(result.current.loadStatus).toBe('success'))
    await act(() => result.current.retryContextAnalysis())
    expect(retryTestGenerationContextAnalysis).toHaveBeenCalledWith('AGP-004')
    expect(result.current.workflowState.n4_execution.attempt_number).toBe(2)
  })
})
