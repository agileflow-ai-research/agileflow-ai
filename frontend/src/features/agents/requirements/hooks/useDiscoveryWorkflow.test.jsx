import { act, renderHook, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { getDiscoveryResults, retryDiscovery } from '../discovery/discoveryService.js'
import useDiscoveryWorkflow from './useDiscoveryWorkflow.js'

vi.mock('../discovery/discoveryService.js', () => ({
  getDiscoveryResults: vi.fn(),
  retryDiscovery: vi.fn(),
}))

const complete = {
  n3_execution: {
    execution_id: 'N3-AAAAAAAAAAAAAAAA-001', attempt_number: 1, status: 'COMPLETE',
  },
}

describe('useDiscoveryWorkflow', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    getDiscoveryResults.mockResolvedValue({ data: { execution_id: 'N3-AAAAAAAAAAAAAAAA-001' } })
  })

  it('hydrates completed persisted results exactly once across rerenders', async () => {
    const refreshWorkflow = vi.fn()
    const { result, rerender } = renderHook((props) => useDiscoveryWorkflow(props), {
      initialProps: { agentProjectId: 'AGP-001', n3TerminalExecutionIdentity: 'terminal-1', refreshWorkflow, workflowState: complete },
    })
    await waitFor(() => expect(result.current.discoveryLoadStatus).toBe('success'))
    rerender({ agentProjectId: 'AGP-001', n3TerminalExecutionIdentity: 'terminal-1', refreshWorkflow, workflowState: complete })
    expect(getDiscoveryResults).toHaveBeenCalledTimes(1)
  })

  it('invalidates stale hydration when the project changes', async () => {
    let resolveOld
    getDiscoveryResults.mockImplementationOnce(() => new Promise((resolve) => { resolveOld = resolve }))
      .mockResolvedValueOnce({ data: { execution_id: 'N3-BBBBBBBBBBBBBBBB-001' } })
    const refreshWorkflow = vi.fn()
    const { result, rerender } = renderHook((props) => useDiscoveryWorkflow(props), {
      initialProps: { agentProjectId: 'AGP-001', n3TerminalExecutionIdentity: 'old', refreshWorkflow, workflowState: complete },
    })
    await waitFor(() => expect(getDiscoveryResults).toHaveBeenCalledTimes(1))
    rerender({ agentProjectId: 'AGP-002', n3TerminalExecutionIdentity: 'new', refreshWorkflow, workflowState: { n3_execution: { ...complete.n3_execution, execution_id: 'N3-BBBBBBBBBBBBBBBB-001' } } })
    await waitFor(() => expect(result.current.discoveryArtifacts?.execution_id).toBe('N3-BBBBBBBBBBBBBBBB-001'))
    await act(async () => resolveOld({ data: { execution_id: 'STALE' } }))
    expect(result.current.discoveryArtifacts.execution_id).toBe('N3-BBBBBBBBBBBBBBBB-001')
  })

  it('does not pretend failed or blocked executions have results', () => {
    const { result, rerender } = renderHook((props) => useDiscoveryWorkflow(props), {
      initialProps: { agentProjectId: 'AGP-001', n3TerminalExecutionIdentity: 'failed', refreshWorkflow: vi.fn(), workflowState: { n3_execution: { ...complete.n3_execution, status: 'FAILED' } } },
    })
    expect(result.current.discoveryArtifacts).toBeNull()
    rerender({ agentProjectId: 'AGP-001', n3TerminalExecutionIdentity: 'blocked', refreshWorkflow: vi.fn(), workflowState: { n3_execution: { ...complete.n3_execution, status: 'BLOCKED' } } })
    expect(getDiscoveryResults).not.toHaveBeenCalled()
  })

  it('retries only retryable failed N3 and refreshes authoritative workflow', async () => {
    retryDiscovery.mockResolvedValue({ data: {} })
    const refreshWorkflow = vi.fn().mockResolvedValue({})
    const { result } = renderHook(() => useDiscoveryWorkflow({ agentProjectId: 'AGP-001', n3TerminalExecutionIdentity: 'failed', refreshWorkflow, workflowState: { n3_execution: { ...complete.n3_execution, status: 'FAILED', retryable: true } } }))
    await act(async () => result.current.retryN3())
    expect(retryDiscovery).toHaveBeenCalledWith('AGP-001')
    expect(refreshWorkflow).toHaveBeenCalledTimes(1)
  })
})
