import { renderHook } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import useEvidenceDetails from './useEvidenceDetails.js'
import useRequirementSources from './useRequirementSources.js'
import useRequirementsWorkflow from './useRequirementsWorkflow.js'
import useRequirementsWorkspace from './useRequirementsWorkspace.js'

vi.mock('./useEvidenceDetails.js', () => ({ default: vi.fn() }))
vi.mock('./useRequirementSources.js', () => ({ default: vi.fn() }))
vi.mock('./useRequirementsWorkflow.js', () => ({ default: vi.fn() }))

const noop = () => {}

describe('useRequirementsWorkspace', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    useRequirementsWorkflow.mockReturnValue({
      changeSelectedOutputs: noop,
      continueN1: noop,
      continueSubmitting: false,
      n2Retrying: false,
      outputSaving: false,
      refreshWorkflow: noop,
      retryN2: noop,
      terminalExecutionIdentity: null,
      workflowError: '',
      workflowLoadError: '',
      workflowLoadStatus: 'success',
      workflowState: { n1_state: 'WAITING_FOR_HUMAN' },
    })
    useRequirementSources.mockReturnValue({
      addFiles: noop,
      removeSource: noop,
      removingId: null,
      sourceError: '',
      sourceLoadStatus: 'success',
      sources: [{ source_id: 'DOC-001', source_type: 'DOCUMENT' }],
      uploadingType: null,
    })
    useEvidenceDetails.mockReturnValue({
      detailsLoading: false,
      evidenceLoadStatus: 'success',
      loadPreparedEvidence: noop,
      loadProcessingResult: noop,
      preparationStates: { 'DOC-001': { status: 'READY' } },
      prepareSource: noop,
      processingStates: { 'DOC-001': { status: 'READY' } },
      processSource: noop,
    })
  })

  it('is a thin composition layer that preserves the legacy public interface', () => {
    const { result } = renderHook(() => useRequirementsWorkspace('AGP-001'))
    expect(Object.keys(result.current).sort()).toEqual([
      'addFiles', 'changeSelectedOutputs', 'continueN1', 'continueSubmitting',
      'detailsLoading', 'error', 'loadPreparedEvidence', 'loadProcessingResult',
      'loadStatus', 'n2Retrying', 'outputSaving', 'preparationStates', 'prepareSource',
      'processSource', 'processingStates', 'reload', 'removeSource', 'removingId',
      'retryN2', 'sources', 'uploadingType', 'workflowError', 'workflowState',
    ].sort())
    expect(result.current.loadStatus).toBe('success')
    expect(useRequirementSources).toHaveBeenCalledWith('AGP-001', expect.objectContaining({
      onSourcesChanged: noop,
    }))
    expect(useEvidenceDetails).toHaveBeenCalledWith(expect.objectContaining({
      sourcesReady: true,
      workflowReady: true,
    }))
  })

  it('does not publish success until workflow, sources, and evidence are ready', () => {
    useEvidenceDetails.mockReturnValue({
      detailsLoading: false, evidenceLoadStatus: 'loading', preparationStates: {}, processingStates: {},
    })
    const { result } = renderHook(() => useRequirementsWorkspace('AGP-001'))
    expect(result.current.loadStatus).toBe('loading')
  })
})
