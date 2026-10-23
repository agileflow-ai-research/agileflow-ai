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

function n3Execution(status, id = 'N3-AAAAAAAAAAAAAAAA-001') {
  return {
    ...execution('COMPLETE'),
    n3_execution: { execution_id: id, attempt_number: 1, status },
  }
}

function n4Execution(status, n3Id = 'N3-AAAAAAAAAAAAAAAA-001') {
  return {
    ...n3Execution('COMPLETE', n3Id),
    n4_execution: {
      execution_id: 'N4-AAAAAAAAAAAAAAAA-001',
      attempt_number: 1,
      status,
    },
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

  it.each(['QUEUED', 'RUNNING'])('keeps the same poller active for N3 %s and stops when N4 is already terminal', async (n3Status) => {
    vi.useFakeTimers()
    const active = n3Execution(n3Status)
    const complete = n4Execution('COMPLETE')
    getRequirementWorkflow.mockResolvedValueOnce({ data: active }).mockResolvedValueOnce({ data: complete })
    try {
      const { result } = renderHook(() => useRequirementsWorkflow('AGP-001'))
      await act(async () => { await Promise.resolve(); await Promise.resolve() })
      expect(vi.getTimerCount()).toBe(1)
      await act(async () => { await vi.advanceTimersByTimeAsync(2000) })
      expect(result.current.workflowState.n3_execution.status).toBe('COMPLETE')
      expect(result.current.n3TerminalExecutionIdentity).toBe('N3-AAAAAAAAAAAAAAAA-001:1:COMPLETE')
      expect(vi.getTimerCount()).toBe(0)
    } finally {
      vi.useRealTimers()
    }
  })

  it('continues polling across N3 COMPLETE without N4 and observes terminal N4 without refresh', async () => {
    vi.useFakeTimers()
    getRequirementWorkflow
      .mockResolvedValueOnce({ data: n3Execution('RUNNING') })
      .mockResolvedValueOnce({ data: n3Execution('COMPLETE') })
      .mockResolvedValueOnce({ data: n4Execution('COMPLETE') })
    try {
      const { result } = renderHook(() => useRequirementsWorkflow('AGP-001'))
      await act(async () => { await Promise.resolve(); await Promise.resolve() })
      expect(result.current.workflowState.n3_execution.status).toBe('RUNNING')

      await act(async () => { await vi.advanceTimersByTimeAsync(2000) })
      expect(result.current.workflowState.n3_execution.status).toBe('COMPLETE')
      expect(result.current.workflowState.n4_execution).toBeUndefined()
      expect(vi.getTimerCount()).toBe(1)

      await act(async () => { await vi.advanceTimersByTimeAsync(2000) })
      expect(result.current.workflowState.n4_execution.status).toBe('COMPLETE')
      expect(getRequirementWorkflow).toHaveBeenCalledTimes(3)
      expect(vi.getTimerCount()).toBe(0)
    } finally {
      vi.useRealTimers()
    }
  })

  it('hands off from absent N4 through QUEUED and RUNNING to COMPLETE on one poll chain', async () => {
    vi.useFakeTimers()
    getRequirementWorkflow
      .mockResolvedValueOnce({ data: n3Execution('COMPLETE') })
      .mockResolvedValueOnce({ data: n4Execution('QUEUED') })
      .mockResolvedValueOnce({ data: n4Execution('RUNNING') })
      .mockResolvedValueOnce({ data: n4Execution('COMPLETE') })
    try {
      const { result } = renderHook(() => useRequirementsWorkflow('AGP-001'))
      await act(async () => { await Promise.resolve(); await Promise.resolve() })
      expect(vi.getTimerCount()).toBe(1)

      await act(async () => { await vi.advanceTimersByTimeAsync(2000) })
      expect(result.current.workflowState.n4_execution.status).toBe('QUEUED')
      expect(vi.getTimerCount()).toBe(1)

      await act(async () => { await vi.advanceTimersByTimeAsync(2000) })
      expect(result.current.workflowState.n4_execution.status).toBe('RUNNING')
      expect(vi.getTimerCount()).toBe(1)

      await act(async () => { await vi.advanceTimersByTimeAsync(2000) })
      expect(result.current.workflowState.n4_execution.status).toBe('COMPLETE')
      expect(getRequirementWorkflow).toHaveBeenCalledTimes(4)
      expect(vi.getTimerCount()).toBe(0)
    } finally {
      vi.useRealTimers()
    }
  })

  it('bounds an unresolved N4 handoff to four normal polling attempts', async () => {
    vi.useFakeTimers()
    getRequirementWorkflow.mockResolvedValue({ data: n3Execution('COMPLETE') })
    try {
      const { result } = renderHook(() => useRequirementsWorkflow('AGP-001'))
      await act(async () => { await Promise.resolve(); await Promise.resolve() })
      await act(async () => { await vi.advanceTimersByTimeAsync(20000) })

      expect(getRequirementWorkflow).toHaveBeenCalledTimes(5)
      expect(result.current.workflowState.n4_execution).toBeUndefined()
      expect(vi.getTimerCount()).toBe(0)
    } finally {
      vi.useRealTimers()
    }
  })

  it('discards N4 handoff polling when the project changes', async () => {
    vi.useFakeTimers()
    getRequirementWorkflow.mockImplementation((projectId) => Promise.resolve({
      data: projectId === 'AGP-A'
        ? n3Execution('COMPLETE', 'N3-AAAAAAAAAAAAAAAA-001')
        : n4Execution('COMPLETE', 'N3-BBBBBBBBBBBBBBBB-001'),
    }))
    try {
      const { result, rerender } = renderHook(
        ({ projectId }) => useRequirementsWorkflow(projectId),
        { initialProps: { projectId: 'AGP-A' } },
      )
      await act(async () => { await Promise.resolve(); await Promise.resolve() })
      expect(vi.getTimerCount()).toBe(1)

      rerender({ projectId: 'AGP-B' })
      await act(async () => { await Promise.resolve(); await Promise.resolve() })
      expect(result.current.workflowState.n3_execution.execution_id).toBe('N3-BBBBBBBBBBBBBBBB-001')
      expect(result.current.workflowState.n4_execution.status).toBe('COMPLETE')

      await act(async () => { await vi.advanceTimersByTimeAsync(10000) })
      expect(getRequirementWorkflow.mock.calls.filter(([projectId]) => projectId === 'AGP-A')).toHaveLength(1)
      expect(vi.getTimerCount()).toBe(0)
    } finally {
      vi.useRealTimers()
    }
  })

  it('resets the bounded N4 handoff when the N3 execution identity changes', async () => {
    vi.useFakeTimers()
    let requestCount = 0
    getRequirementWorkflow.mockImplementation(() => {
      requestCount += 1
      const n3Id = requestCount <= 4
        ? 'N3-AAAAAAAAAAAAAAAA-001'
        : 'N3-BBBBBBBBBBBBBBBB-001'
      return Promise.resolve({ data: n3Execution('COMPLETE', n3Id) })
    })
    try {
      const { result } = renderHook(() => useRequirementsWorkflow('AGP-001'))
      await act(async () => { await Promise.resolve(); await Promise.resolve() })
      await act(async () => { await vi.advanceTimersByTimeAsync(30000) })

      expect(result.current.workflowState.n3_execution.execution_id).toBe('N3-BBBBBBBBBBBBBBBB-001')
      expect(vi.getTimerCount()).toBe(1)
      await act(async () => { await vi.advanceTimersByTimeAsync(20000) })
      expect(getRequirementWorkflow).toHaveBeenCalledTimes(9)
      expect(vi.getTimerCount()).toBe(0)
    } finally {
      vi.useRealTimers()
    }
  })

  it('restarts bounded handoff polling after reloadSequence changes', async () => {
    vi.useFakeTimers()
    getRequirementWorkflow.mockResolvedValue({ data: n3Execution('COMPLETE') })
    try {
      const { rerender } = renderHook(
        ({ reloadSequence }) => useRequirementsWorkflow('AGP-001', reloadSequence),
        { initialProps: { reloadSequence: 0 } },
      )
      await act(async () => { await Promise.resolve(); await Promise.resolve() })
      await act(async () => { await vi.advanceTimersByTimeAsync(20000) })
      expect(getRequirementWorkflow).toHaveBeenCalledTimes(5)
      expect(vi.getTimerCount()).toBe(0)

      rerender({ reloadSequence: 1 })
      await act(async () => { await Promise.resolve(); await Promise.resolve() })
      expect(vi.getTimerCount()).toBe(1)
      await act(async () => { await vi.advanceTimersByTimeAsync(20000) })
      expect(getRequirementWorkflow).toHaveBeenCalledTimes(10)
      expect(vi.getTimerCount()).toBe(0)
    } finally {
      vi.useRealTimers()
    }
  })

  it.each(['COMPLETE', 'FAILED', 'BLOCKED'])('does not handoff-poll after terminal N4 %s', async (status) => {
    vi.useFakeTimers()
    getRequirementWorkflow.mockResolvedValue({ data: n4Execution(status) })
    try {
      const { result } = renderHook(() => useRequirementsWorkflow('AGP-001'))
      await act(async () => { await Promise.resolve(); await Promise.resolve() })
      expect(result.current.workflowState.n4_execution.status).toBe(status)
      expect(vi.getTimerCount()).toBe(0)

      await act(async () => { await vi.advanceTimersByTimeAsync(10000) })
      expect(getRequirementWorkflow).toHaveBeenCalledTimes(1)
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
