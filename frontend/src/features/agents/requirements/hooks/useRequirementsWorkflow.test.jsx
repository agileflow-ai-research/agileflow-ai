import { act, renderHook, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import {
  continueRequirementN1,
  getRequirementWorkflow,
  retryRequirementN2,
  updateRequirementOutputs,
} from '../requirementsAgentService.js'
import useRequirementsWorkflow from './useRequirementsWorkflow.js'

vi.mock('../requirementsAgentService.js', () => ({
  continueRequirementN1: vi.fn(),
  getRequirementWorkflow: vi.fn(),
  retryRequirementN2: vi.fn(),
  updateRequirementOutputs: vi.fn(),
}))

const baseWorkflow = {
  n1_state: 'WAITING_FOR_HUMAN', selected_outputs: ['SRS'], selection_revision: 1,
}

function execution(status, id = 'N2-AAAAAAAAAAAAAAAA-001') {
  return {
    ...baseWorkflow,
    n1_state: 'COMPLETE',
    n2_is_current: true,
    n2_execution: { execution_id: id, attempt_number: 1, status, source_progress: [] },
  }
}

function deferred() {
  let resolve
  const promise = new Promise((next) => { resolve = next })
  return { promise, resolve }
}

describe('useRequirementsWorkflow', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    getRequirementWorkflow.mockResolvedValue({ data: baseWorkflow })
    updateRequirementOutputs.mockResolvedValue({ data: { ...baseWorkflow, selected_outputs: ['SRS', 'FR'] } })
    continueRequirementN1.mockResolvedValue({ data: execution('QUEUED') })
    retryRequirementN2.mockResolvedValue({ data: execution('QUEUED', 'N2-AAAAAAAAAAAAAAAA-002') })
  })

  it('loads the authoritative workflow and runs output, Continue, and Retry commands', async () => {
    const { result } = renderHook(() => useRequirementsWorkflow('AGP-001'))
    await waitFor(() => expect(result.current.workflowLoadStatus).toBe('success'))
    expect(result.current.workflowState).toEqual(baseWorkflow)

    await act(() => result.current.changeSelectedOutputs(['SRS', 'FR']))
    expect(updateRequirementOutputs).toHaveBeenCalledWith('AGP-001', ['SRS', 'FR'])
    expect(result.current.workflowState.selected_outputs).toEqual(['SRS', 'FR'])

    await act(() => result.current.continueN1())
    expect(continueRequirementN1).toHaveBeenCalledWith('AGP-001')
    expect(result.current.workflowState.n2_execution.status).toBe('QUEUED')

    await act(() => result.current.retryN2())
    expect(retryRequirementN2).toHaveBeenCalledWith('AGP-001')
    expect(result.current.workflowState.n2_execution.execution_id).toContain('-002')
  })

  it('uses one sequential poll loop while QUEUED/RUNNING and stops at COMPLETE', async () => {
    vi.useFakeTimers()
    getRequirementWorkflow
      .mockResolvedValueOnce({ data: execution('QUEUED') })
      .mockResolvedValueOnce({ data: execution('RUNNING') })
      .mockResolvedValueOnce({ data: execution('COMPLETE') })
    try {
      const { result } = renderHook(() => useRequirementsWorkflow('AGP-001'))
      await act(async () => { await Promise.resolve(); await Promise.resolve() })
      expect(result.current.workflowState.n2_execution.status).toBe('QUEUED')
      expect(vi.getTimerCount()).toBe(1)

      await act(async () => { await vi.advanceTimersByTimeAsync(2000) })
      expect(result.current.workflowState.n2_execution.status).toBe('RUNNING')
      expect(vi.getTimerCount()).toBe(1)

      await act(async () => { await vi.advanceTimersByTimeAsync(2000) })
      expect(result.current.workflowState.n2_execution.status).toBe('COMPLETE')
      expect(result.current.terminalExecutionIdentity).toBe('N2-AAAAAAAAAAAAAAAA-001:1:COMPLETE')
      expect(vi.getTimerCount()).toBe(0)
      await act(async () => { await vi.advanceTimersByTimeAsync(10000) })
      expect(getRequirementWorkflow).toHaveBeenCalledTimes(3)
    } finally {
      vi.useRealTimers()
    }
  })

  it.each(['FAILED', 'BLOCKED'])('stops polling at %s and exposes one stable terminal identity', async (status) => {
    vi.useFakeTimers()
    getRequirementWorkflow
      .mockResolvedValueOnce({ data: execution('RUNNING') })
      .mockResolvedValueOnce({ data: execution(status) })
    try {
      const { result, rerender } = renderHook(() => useRequirementsWorkflow('AGP-001'))
      await act(async () => { await Promise.resolve(); await Promise.resolve() })
      await act(async () => { await vi.advanceTimersByTimeAsync(2000) })
      const identity = result.current.terminalExecutionIdentity
      expect(identity).toBe(`N2-AAAAAAAAAAAAAAAA-001:1:${status}`)
      rerender()
      expect(result.current.terminalExecutionIdentity).toBe(identity)
      await act(async () => { await vi.advanceTimersByTimeAsync(10000) })
      expect(getRequirementWorkflow).toHaveBeenCalledTimes(2)
    } finally {
      vi.useRealTimers()
    }
  })

  it('does not accept an older RUNNING response after COMPLETE', async () => {
    vi.useFakeTimers()
    const oldPoll = deferred()
    getRequirementWorkflow
      .mockResolvedValueOnce({ data: execution('RUNNING') })
      .mockReturnValueOnce(oldPoll.promise)
    try {
      const { result } = renderHook(() => useRequirementsWorkflow('AGP-001'))
      await act(async () => { await Promise.resolve(); await Promise.resolve() })
      await act(async () => { await vi.advanceTimersByTimeAsync(2000) })
      retryRequirementN2.mockResolvedValueOnce({ data: execution('COMPLETE') })
      await act(() => result.current.retryN2())
      oldPoll.resolve({ data: execution('RUNNING') })
      await act(async () => { await Promise.resolve(); await Promise.resolve() })
      expect(result.current.workflowState.n2_execution.status).toBe('COMPLETE')
    } finally {
      vi.useRealTimers()
    }
  })

  it('invalidates an old project request when the project changes', async () => {
    const oldRequest = deferred()
    getRequirementWorkflow.mockImplementation((projectId) => (
      projectId === 'AGP-OLD' ? oldRequest.promise : Promise.resolve({ data: execution('COMPLETE', 'N2-NEW-001') })
    ))
    const { result, rerender } = renderHook(
      ({ projectId }) => useRequirementsWorkflow(projectId),
      { initialProps: { projectId: 'AGP-OLD' } },
    )
    rerender({ projectId: 'AGP-NEW' })
    await waitFor(() => expect(result.current.workflowState?.n2_execution.execution_id).toBe('N2-NEW-001'))
    oldRequest.resolve({ data: execution('RUNNING', 'N2-OLD-001') })
    await act(async () => { await Promise.resolve(); await Promise.resolve() })
    expect(result.current.workflowState.n2_execution.execution_id).toBe('N2-NEW-001')
  })

  it('cleans up the only pending poll on unmount and is independent of modal state', async () => {
    vi.useFakeTimers()
    getRequirementWorkflow.mockResolvedValue({ data: execution('RUNNING') })
    try {
      const { unmount } = renderHook(() => useRequirementsWorkflow('AGP-001'))
      await act(async () => { await Promise.resolve(); await Promise.resolve() })
      expect(vi.getTimerCount()).toBe(1)
      unmount()
      expect(vi.getTimerCount()).toBe(0)
      await act(async () => { await vi.advanceTimersByTimeAsync(10000) })
      expect(getRequirementWorkflow).toHaveBeenCalledTimes(1)
    } finally {
      vi.useRealTimers()
    }
  })
})
