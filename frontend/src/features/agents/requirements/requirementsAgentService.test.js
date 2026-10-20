import { beforeEach, describe, expect, it, vi } from 'vitest'

import { apiClient } from '../../../services/apiClient.js'
import * as requirementsAgentService from './requirementsAgentService.js'
import {
  deleteRequirementSource,
  getRequirementAudioProcessingResult,
  getRequirementAudioProcessingStatus,
  getRequirementDocumentProcessingResult,
  getRequirementDocumentProcessingStatus,
  getNormalizedRequirementEvidence,
  getRequirementEvidenceChunks,
  getRequirementPreparationStatus,
  getRequirementVideoProcessingResult,
  getRequirementVideoProcessingStatus,
  listRequirementSources,
  processRequirementDocument,
  processRequirementAudio,
  processRequirementVideo,
  prepareRequirementEvidence,
  uploadRequirementSource,
} from './requirementsAgentService.js'

vi.mock('../../../services/apiClient.js', () => ({
  apiClient: { delete: vi.fn(), get: vi.fn(), post: vi.fn() },
}))

describe('requirementsAgentService source collection', () => {
  beforeEach(() => vi.clearAllMocks())

  it('does not expose the retired direct run client', () => {
    expect(requirementsAgentService).not.toHaveProperty('runRequirementsAgent')
  })

  it('lists persisted project sources with authentication', () => {
    listRequirementSources('AGP-007')
    expect(apiClient.get).toHaveBeenCalledWith('/agents/requirements/AGP-007/sources', { authenticated: true })
  })

  it('uploads a typed source as multipart form data', () => {
    const file = new File(['requirements'], 'requirements.txt', { type: 'text/plain' })
    uploadRequirementSource('AGP-007', 'DOCUMENT', file)
    const [path, body, options] = apiClient.post.mock.calls[0]
    expect(path).toBe('/agents/requirements/AGP-007/sources')
    expect(body).toBeInstanceOf(FormData)
    expect(body.get('source_type')).toBe('DOCUMENT')
    expect(body.get('file')).toBe(file)
    expect(options).toEqual({ authenticated: true })
  })

  it('removes one independently traceable source', () => {
    deleteRequirementSource('AGP-007', 'AUD-001')
    expect(apiClient.delete).toHaveBeenCalledWith(
      '/agents/requirements/AGP-007/sources/AUD-001', { authenticated: true },
    )
  })

  it('processes, checks status, and retrieves results through explicit endpoints', () => {
    processRequirementDocument('AGP-007', 'DOC-001', { force: true })
    getRequirementDocumentProcessingStatus('AGP-007', 'DOC-001')
    getRequirementDocumentProcessingResult('AGP-007', 'DOC-001')

    expect(apiClient.post).toHaveBeenCalledWith(
      '/agents/requirements/AGP-007/sources/DOC-001/processing?force=true',
      undefined,
      { authenticated: true },
    )
    expect(apiClient.get).toHaveBeenNthCalledWith(
      1,
      '/agents/requirements/AGP-007/sources/DOC-001/processing/status',
      { authenticated: true },
    )
    expect(apiClient.get).toHaveBeenNthCalledWith(
      2,
      '/agents/requirements/AGP-007/sources/DOC-001/processing/result',
      { authenticated: true },
    )
  })

  it('uses the shared processing endpoints for audio sources', () => {
    processRequirementAudio('AGP-007', 'AUD-001')
    getRequirementAudioProcessingStatus('AGP-007', 'AUD-001')
    getRequirementAudioProcessingResult('AGP-007', 'AUD-001')

    expect(apiClient.post).toHaveBeenCalledWith(
      '/agents/requirements/AGP-007/sources/AUD-001/processing',
      undefined,
      { authenticated: true },
    )
    expect(apiClient.get).toHaveBeenNthCalledWith(
      1,
      '/agents/requirements/AGP-007/sources/AUD-001/processing/status',
      { authenticated: true },
    )
    expect(apiClient.get).toHaveBeenNthCalledWith(
      2,
      '/agents/requirements/AGP-007/sources/AUD-001/processing/result',
      { authenticated: true },
    )
  })

  it('uses the shared processing endpoints for video sources', () => {
    processRequirementVideo('AGP-007', 'VID-001', { force: true })
    getRequirementVideoProcessingStatus('AGP-007', 'VID-001')
    getRequirementVideoProcessingResult('AGP-007', 'VID-001')

    expect(apiClient.post).toHaveBeenCalledWith(
      '/agents/requirements/AGP-007/sources/VID-001/processing?force=true',
      undefined,
      { authenticated: true },
    )
    expect(apiClient.get).toHaveBeenNthCalledWith(
      1,
      '/agents/requirements/AGP-007/sources/VID-001/processing/status',
      { authenticated: true },
    )
    expect(apiClient.get).toHaveBeenNthCalledWith(
      2,
      '/agents/requirements/AGP-007/sources/VID-001/processing/result',
      { authenticated: true },
    )
  })

  it('prepares evidence and retrieves normalized and chunk artifacts', () => {
    prepareRequirementEvidence('AGP-007', 'VID-001', { force: true })
    getRequirementPreparationStatus('AGP-007', 'VID-001')
    getNormalizedRequirementEvidence('AGP-007', 'VID-001')
    getRequirementEvidenceChunks('AGP-007', 'VID-001')

    expect(apiClient.post).toHaveBeenCalledWith(
      '/agents/requirements/AGP-007/sources/VID-001/preparation?force=true',
      undefined,
      { authenticated: true },
    )
    expect(apiClient.get).toHaveBeenNthCalledWith(
      1,
      '/agents/requirements/AGP-007/sources/VID-001/preparation/status',
      { authenticated: true },
    )
    expect(apiClient.get).toHaveBeenNthCalledWith(
      2,
      '/agents/requirements/AGP-007/sources/VID-001/preparation/normalized',
      { authenticated: true },
    )
    expect(apiClient.get).toHaveBeenNthCalledWith(
      3,
      '/agents/requirements/AGP-007/sources/VID-001/preparation/chunks',
      { authenticated: true },
    )
  })
})
