import { act, renderHook, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { getTestGenerationWorkflow } from '../testingValidationAgentService.js'
import useTestingValidationWorkflow from './useTestingValidationWorkflow.js'

vi.mock('../testingValidationAgentService.js', () => ({
  getTestGenerationWorkflow: vi.fn(),
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
    nodes: nodeIds.map((nodeId, index) => ({
      node_id: nodeId, status: index === 0 ? 'WAITING_FOR_HUMAN' : 'LOCKED',
    })),
  }
}

function deferred() {
  let resolve
  const promise = new Promise((next) => { resolve = next })
  return { promise, resolve }
}

describe('useTestingValidationWorkflow', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    getTestGenerationWorkflow.mockResolvedValue({ data: workflow() })
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
})
