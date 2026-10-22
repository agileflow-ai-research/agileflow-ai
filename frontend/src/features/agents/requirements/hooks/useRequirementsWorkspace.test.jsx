import { renderHook } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import useEvidenceDetails from './useEvidenceDetails.js'
import useRequirementSources from './useRequirementSources.js'
import useRequirementsWorkflow from './useRequirementsWorkflow.js'
import useDiscoveryWorkflow from './useDiscoveryWorkflow.js'
import useQualityWorkflow from './useQualityWorkflow.js'
import useRequirementsWorkspace from './useRequirementsWorkspace.js'

vi.mock('./useEvidenceDetails.js', () => ({ default: vi.fn() }))
vi.mock('./useRequirementSources.js', () => ({ default: vi.fn() }))
vi.mock('./useRequirementsWorkflow.js', () => ({ default: vi.fn() }))
vi.mock('./useDiscoveryWorkflow.js', () => ({ default: vi.fn() }))
vi.mock('./useQualityWorkflow.js', () => ({ default: vi.fn() }))

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
    useDiscoveryWorkflow.mockReturnValue({
      discoveryArtifacts: null,
      discoveryError: '',
      discoveryLoadStatus: 'idle',
      n3Retrying: false,
      refreshDiscovery: noop,
      retryN3: noop,
    })
    useQualityWorkflow.mockReturnValue({ error: '', loadStatus: 'idle', result: null, retry: noop, retrying: false })
  })

  it('is a thin composition layer that preserves the legacy public interface', () => {
    const { result } = renderHook(() => useRequirementsWorkspace('AGP-001'))
    expect(Object.keys(result.current).sort()).toEqual([
      'addFiles', 'changeSelectedOutputs', 'continueN1', 'continueSubmitting',
      'detailsLoading', 'discoveryArtifacts', 'discoveryError', 'discoveryLoadStatus',
      'error', 'loadPreparedEvidence', 'loadProcessingResult', 'loadStatus', 'n2Retrying',
      'n3Retrying', 'outputSaving', 'preparationStates', 'prepareSource', 'processSource',
      'processingStates', 'quality', 'refreshDiscovery', 'reload', 'removeSource', 'removingId',
      'retryN2', 'retryN3', 'sources', 'uploadingType', 'workflowError', 'workflowState',
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
