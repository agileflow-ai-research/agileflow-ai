import { act, renderHook, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import {
  getRequirementAudioProcessingStatus,
  getRequirementDocumentProcessingStatus,
  getRequirementEvidenceChunks,
  getRequirementPreparationStatus,
  getRequirementVideoProcessingStatus,
} from '../requirementsAgentService.js'
import useEvidenceDetails from './useEvidenceDetails.js'

vi.mock('../requirementsAgentService.js', () => ({
  getNormalizedRequirementEvidence: vi.fn(),
  getRequirementAudioProcessingResult: vi.fn(),
  getRequirementAudioProcessingStatus: vi.fn(),
  getRequirementDocumentProcessingResult: vi.fn(),
  getRequirementDocumentProcessingStatus: vi.fn(),
  getRequirementEvidenceChunks: vi.fn(),
  getRequirementPreparationStatus: vi.fn(),
  getRequirementVideoProcessingResult: vi.fn(),
  getRequirementVideoProcessingStatus: vi.fn(),
  prepareRequirementEvidence: vi.fn(),
  processRequirementAudio: vi.fn(),
  processRequirementDocument: vi.fn(),
  processRequirementVideo: vi.fn(),
}))

const sources = [
  { source_id: 'DOC-001', source_type: 'DOCUMENT' },
  { source_id: 'AUD-001', source_type: 'AUDIO' },
  { source_id: 'VID-001', source_type: 'VIDEO' },
]
const runningWorkflow = {
  n1_state: 'COMPLETE', n2_is_current: true,
  n2_execution: {
    execution_id: 'N2-AAAAAAAAAAAAAAAA-001', attempt_number: 1, status: 'RUNNING',
    source_progress: sources.map((source) => ({
      source_id: source.source_id, processing_status: 'RUNNING', preparation_status: 'READY',
    })),
  },
}

function completedWorkflow(status = 'COMPLETE') {
  return {
    ...runningWorkflow,
    n2_execution: {
      ...runningWorkflow.n2_execution,
      status,
      source_progress: sources.map((source) => ({
        source_id: source.source_id, processing_status: 'COMPLETE', preparation_status: 'COMPLETE',
      })),
    },
  }
}

function deferred() {
  let resolve
  const promise = new Promise((next) => { resolve = next })
  return { promise, resolve }
}

function props(overrides = {}) {
  return {
    agentProjectId: 'AGP-001',
    sources,
    sourcesReady: true,
    terminalExecutionIdentity: null,
    workflowReady: true,
    workflowState: runningWorkflow,
    ...overrides,
  }
}

describe('useEvidenceDetails', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    getRequirementDocumentProcessingStatus.mockResolvedValue({ data: { status: 'COMPLETED' } })
    getRequirementAudioProcessingStatus.mockResolvedValue({ data: { status: 'COMPLETED' } })
    getRequirementVideoProcessingStatus.mockResolvedValue({ data: { status: 'COMPLETED' } })
    getRequirementPreparationStatus.mockImplementation((_, sourceId) => Promise.resolve({
      data: { source_id: sourceId, status: 'COMPLETED' },
    }))
    getRequirementEvidenceChunks.mockImplementation((_, sourceId) => Promise.resolve({ data: {
      source_id: sourceId,
      chunks: Array.from({ length: sourceId === 'AUD-001' ? 7 : 1 }, (__, index) => ({
        chunk_id: `${sourceId}-${index}`,
      })),
    } }))
  })

  it('hydrates processing, preparation, and chunks for document, audio, and video', async () => {
    const { result } = renderHook(() => useEvidenceDetails(props()))
    await waitFor(() => expect(result.current.evidenceLoadStatus).toBe('success'))
    expect(result.current.processingStates['DOC-001'].status).toBe('COMPLETED')
    expect(result.current.processingStates['AUD-001'].status).toBe('COMPLETED')
    expect(result.current.processingStates['VID-001'].status).toBe('COMPLETED')
    expect(result.current.preparationStates['AUD-001'].chunks.chunks).toHaveLength(7)
    expect(getRequirementDocumentProcessingStatus).toHaveBeenCalledTimes(1)
    expect(getRequirementAudioProcessingStatus).toHaveBeenCalledTimes(1)
    expect(getRequirementVideoProcessingStatus).toHaveBeenCalledTimes(1)
  })

  it('hydrates exactly once when a COMPLETE terminal attempt is published', async () => {
    const { result, rerender } = renderHook(
      (hookProps) => useEvidenceDetails(hookProps),
      { initialProps: props() },
    )
    await waitFor(() => expect(result.current.evidenceLoadStatus).toBe('success'))
    const terminalProps = props({
      terminalExecutionIdentity: 'N2-AAAAAAAAAAAAAAAA-001:1:COMPLETE',
      workflowState: completedWorkflow(),
    })
    rerender(terminalProps)
    await waitFor(() => expect(getRequirementPreparationStatus).toHaveBeenCalledTimes(6))
    await waitFor(() => expect(result.current.detailsLoading).toBe(false))
    rerender({ ...terminalProps })
    await act(async () => { await Promise.resolve(); await Promise.resolve() })
    expect(getRequirementPreparationStatus).toHaveBeenCalledTimes(6)
  })

  it.each(['FAILED', 'BLOCKED'])('retains current terminal hydration behavior for %s', async (status) => {
    const { result, rerender } = renderHook(
      (hookProps) => useEvidenceDetails(hookProps),
      { initialProps: props() },
    )
    await waitFor(() => expect(result.current.evidenceLoadStatus).toBe('success'))
    rerender(props({
      terminalExecutionIdentity: `N2-AAAAAAAAAAAAAAAA-001:1:${status}`,
      workflowState: completedWorkflow(status),
    }))
    await waitFor(() => expect(getRequirementPreparationStatus).toHaveBeenCalledTimes(6))
    await waitFor(() => expect(result.current.detailsLoading).toBe(false))
  })

  it('prevents older pre-terminal hydration from overwriting terminal details', async () => {
    const oldProcessing = deferred()
    const oldPreparation = deferred()
    getRequirementDocumentProcessingStatus
      .mockReturnValueOnce(oldProcessing.promise)
      .mockResolvedValue({ data: { status: 'COMPLETED' } })
    getRequirementPreparationStatus
      .mockReturnValueOnce(oldPreparation.promise)
      .mockResolvedValue({ data: { status: 'COMPLETED' } })
    const documentOnly = [sources[0]]
    const initialProps = props({ sources: documentOnly })
    const { result, rerender } = renderHook(
      (hookProps) => useEvidenceDetails(hookProps),
      { initialProps },
    )
    rerender(props({
      sources: documentOnly,
      terminalExecutionIdentity: 'N2-AAAAAAAAAAAAAAAA-001:1:COMPLETE',
      workflowState: completedWorkflow(),
    }))
    await waitFor(() => expect(result.current.processingStates['DOC-001']?.status).toBe('COMPLETED'))
    oldProcessing.resolve({ data: { status: 'READY' } })
    oldPreparation.resolve({ data: { status: 'READY' } })
    await act(async () => { await Promise.resolve(); await Promise.resolve() })
    expect(result.current.processingStates['DOC-001'].status).toBe('COMPLETED')
  })

  it('reconciles detail maps when the source set changes without rehydrating', async () => {
    const { result, rerender } = renderHook(
      (hookProps) => useEvidenceDetails(hookProps),
      { initialProps: props({ sources: [sources[0]] }) },
    )
    await waitFor(() => expect(result.current.evidenceLoadStatus).toBe('success'))
    rerender(props({ sources: [sources[1]] }))
    await waitFor(() => expect(result.current.processingStates['AUD-001']?.status).toBe('READY'))
    expect(result.current.processingStates['DOC-001']).toBeUndefined()
    expect(getRequirementAudioProcessingStatus).not.toHaveBeenCalled()
  })
})
