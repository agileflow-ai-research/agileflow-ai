import { beforeEach, describe, expect, it, vi } from 'vitest'

import { apiClient } from '../../../services/apiClient.js'
import {
  connectGitHub,
  createGitHubRepository,
  deleteImplementationInputFile,
  evaluateImplementationReadiness,
  extractImplementationDocument,
  getGitHubConnection,
  getImplementationDocumentChunks,
  getImplementationDocumentExtraction,
  getImplementationRuleDetections,
  getGitHubRepository,
  prepareImplementationDocumentChunks,
  runImplementationRuleDetector,
  uploadImplementationInputFile,
} from './implementationAgentService.js'

vi.mock('../../../services/apiClient.js', () => ({
  apiClient: { get: vi.fn(), post: vi.fn(), delete: vi.fn() },
}))

describe('implementationAgentService', () => {
  beforeEach(() => vi.clearAllMocks())

  it('sends upload fields as FormData without multipart headers', () => {
    const file = new File(['%PDF-test'], 'api.pdf', { type: 'application/pdf' })
    uploadImplementationInputFile('AGP-003', {
      source_type: 'DOCUMENT', artifact_type: 'API_SPECIFICATION', label: ' API ', file,
    })

    const [path, body, options] = apiClient.post.mock.calls[0]
    expect(path).toBe('/agents/implementation/AGP-003/input-files')
    expect(body).toBeInstanceOf(FormData)
    expect(body.get('source_type')).toBe('DOCUMENT')
    expect(body.get('artifact_type')).toBe('API_SPECIFICATION')
    expect(body.get('label')).toBe('API')
    expect(body.get('file')).toBe(file)
    expect(options).toEqual({ authenticated: true })
    expect(options.headers).toBeUndefined()
  })

  it('uses the authenticated scoped delete endpoint', () => {
    deleteImplementationInputFile('AGP-003', 'A3UP-abc')
    expect(apiClient.delete).toHaveBeenCalledWith(
      '/agents/implementation/AGP-003/input-files/A3UP-abc',
      { authenticated: true },
    )
  })

  it('uses authenticated extraction endpoints without forcing extraction by default', () => {
    extractImplementationDocument('AGP-003', 'A3UP-abc')
    getImplementationDocumentExtraction('AGP-003', 'A3UP-abc')
    expect(apiClient.post).toHaveBeenCalledWith(
      '/agents/implementation/AGP-003/input-files/A3UP-abc/extract',
      undefined,
      { authenticated: true },
    )
    expect(apiClient.get).toHaveBeenCalledWith(
      '/agents/implementation/AGP-003/input-files/A3UP-abc/extraction',
      { authenticated: true },
    )
  })

  it('posts readiness evaluation only to the AgileFlow backend', () => {
    const request = {
      selected_outputs: ['BACKEND_CODE'],
      text_inputs: [],
      document_upload_ids: [],
      image_upload_ids: [],
      human_resolutions: [],
    }
    evaluateImplementationReadiness('AGP-003', request)
    expect(apiClient.post).toHaveBeenCalledWith(
      '/agents/implementation/AGP-003/readiness/evaluate',
      request,
      { authenticated: true },
    )
  })

  it('adds the explicit force query only for extraction retries', () => {
    extractImplementationDocument('AGP-003', 'A3UP-abc', { force: true })
    expect(apiClient.post).toHaveBeenCalledWith(
      '/agents/implementation/AGP-003/input-files/A3UP-abc/extract?force=true',
      undefined,
      { authenticated: true },
    )
  })

  it('uses read-only and explicit build semantic chunk endpoints', () => {
    prepareImplementationDocumentChunks('AGP-003', 'A3UP-abc')
    getImplementationDocumentChunks('AGP-003', 'A3UP-abc')
    expect(apiClient.post).toHaveBeenCalledWith(
      '/agents/implementation/AGP-003/input-files/A3UP-abc/chunks',
      undefined,
      { authenticated: true },
    )
    expect(apiClient.get).toHaveBeenCalledWith(
      '/agents/implementation/AGP-003/input-files/A3UP-abc/chunks',
      { authenticated: true },
    )
    prepareImplementationDocumentChunks('AGP-003', 'A3UP-abc', { force: true })
    expect(apiClient.post).toHaveBeenLastCalledWith(
      '/agents/implementation/AGP-003/input-files/A3UP-abc/chunks?force=true',
      undefined,
      { authenticated: true },
    )
  })

  it('uses read-only and explicit rule-detection endpoints', () => {
    runImplementationRuleDetector('AGP-003', 'A3UP-abc')
    getImplementationRuleDetections('AGP-003', 'A3UP-abc')
    expect(apiClient.post).toHaveBeenCalledWith(
      '/agents/implementation/AGP-003/input-files/A3UP-abc/rule-detections',
      undefined,
      { authenticated: true },
    )
    expect(apiClient.get).toHaveBeenCalledWith(
      '/agents/implementation/AGP-003/input-files/A3UP-abc/rule-detections',
      { authenticated: true },
    )
    runImplementationRuleDetector('AGP-003', 'A3UP-abc', { force: true })
    expect(apiClient.post).toHaveBeenLastCalledWith(
      '/agents/implementation/AGP-003/input-files/A3UP-abc/rule-detections?force=true',
      undefined,
      { authenticated: true },
    )
  })

  it('uses backend-only GitHub connect and status endpoints', () => {
    connectGitHub('AGP-003')
    getGitHubConnection('AGP-003')
    expect(apiClient.post).toHaveBeenCalledWith(
      '/agents/implementation/AGP-003/github/connect',
      undefined,
      { authenticated: true },
    )
    expect(apiClient.get).toHaveBeenCalledWith(
      '/agents/implementation/AGP-003/github/connection',
      { authenticated: true },
    )
  })

  it('uses backend-only repository status and create endpoints', () => {
    getGitHubRepository('AGP-003')
    createGitHubRepository('AGP-003', {
      name: 'quickbook', description: 'Booking', visibility: 'PRIVATE',
    })
    expect(apiClient.get).toHaveBeenCalledWith(
      '/agents/implementation/AGP-003/github/repository',
      { authenticated: true },
    )
    expect(apiClient.post).toHaveBeenCalledWith(
      '/agents/implementation/AGP-003/github/repository',
      { name: 'quickbook', description: 'Booking', visibility: 'PRIVATE' },
      { authenticated: true },
    )
  })
})
