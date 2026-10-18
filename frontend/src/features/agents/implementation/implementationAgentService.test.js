import { beforeEach, describe, expect, it, vi } from 'vitest'

import { apiClient } from '../../../services/apiClient.js'
import {
  buildImplementationCanonicalArtifacts,
  buildImplementationHybridDetections,
  connectGitHub,
  createGitHubRepository,
  deleteImplementationInputFile,
  evaluateImplementationReadiness,
  extractImplementationDocument,
  getGitHubConnection,
  getImplementationDocumentChunks,
  getImplementationDocumentExtraction,
  getImplementationRuleDetections,
  getImplementationZeroShotDetections,
  getImplementationHybridDetections,
  getImplementationHumanReviews,
  getImplementationCanonicalArtifacts,
  getGitHubRepository,
  prepareImplementationDocumentChunks,
  runImplementationRuleDetector,
  runImplementationZeroShotClassifier,
  saveImplementationHumanReview,
  uploadImplementationInputFile,
} from './implementationAgentService.js'

vi.mock('../../../services/apiClient.js', () => ({
  apiClient: { get: vi.fn(), post: vi.fn(), put: vi.fn(), delete: vi.fn() },
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

  it('uses read-only and explicit zero-shot classification endpoints', () => {
    runImplementationZeroShotClassifier('AGP-003', 'A3UP-abc')
    getImplementationZeroShotDetections('AGP-003', 'A3UP-abc')
    expect(apiClient.post).toHaveBeenCalledWith(
      '/agents/implementation/AGP-003/input-files/A3UP-abc/zero-shot-detections',
      undefined,
      { authenticated: true },
    )
    expect(apiClient.get).toHaveBeenCalledWith(
      '/agents/implementation/AGP-003/input-files/A3UP-abc/zero-shot-detections',
      { authenticated: true },
    )
    runImplementationZeroShotClassifier('AGP-003', 'A3UP-abc', { force: true })
    expect(apiClient.post).toHaveBeenLastCalledWith(
      '/agents/implementation/AGP-003/input-files/A3UP-abc/zero-shot-detections?force=true',
      undefined,
      { authenticated: true },
    )
  })

  it('uses read-only and explicit hybrid candidate endpoints', () => {
    buildImplementationHybridDetections('AGP-003', 'A3UP-abc')
    getImplementationHybridDetections('AGP-003', 'A3UP-abc')
    expect(apiClient.post).toHaveBeenCalledWith(
      '/agents/implementation/AGP-003/input-files/A3UP-abc/hybrid-detections',
      undefined,
      { authenticated: true },
    )
    expect(apiClient.get).toHaveBeenCalledWith(
      '/agents/implementation/AGP-003/input-files/A3UP-abc/hybrid-detections',
      { authenticated: true },
    )
    buildImplementationHybridDetections('AGP-003', 'A3UP-abc', { force: true })
    expect(apiClient.post).toHaveBeenLastCalledWith(
      '/agents/implementation/AGP-003/input-files/A3UP-abc/hybrid-detections?force=true',
      undefined,
      { authenticated: true },
    )
  })

  it('gets review state and incrementally saves decisions', () => {
    const request = {
      expected_review_fingerprint: 'a'.repeat(64),
      decisions: [{ action: 'ACCEPT', source_candidate_label: 'API_SPECIFICATION', final_label: 'API_SPECIFICATION', note: null }],
    }
    getImplementationHumanReviews('AGP-003', 'A3UP-abc')
    saveImplementationHumanReview('AGP-003', 'A3UP-abc', 'CHK-ABC', request)
    expect(apiClient.get).toHaveBeenCalledWith(
      '/agents/implementation/AGP-003/input-files/A3UP-abc/human-reviews',
      { authenticated: true },
    )
    expect(apiClient.put).toHaveBeenCalledWith(
      '/agents/implementation/AGP-003/input-files/A3UP-abc/human-reviews/CHK-ABC',
      request,
      { authenticated: true },
    )
  })

  it('uses read-only and explicit canonical artifact endpoints', () => {
    buildImplementationCanonicalArtifacts('AGP-003', 'A3UP-abc')
    getImplementationCanonicalArtifacts('AGP-003', 'A3UP-abc')
    expect(apiClient.post).toHaveBeenCalledWith(
      '/agents/implementation/AGP-003/input-files/A3UP-abc/canonical-artifacts',
      undefined,
      { authenticated: true },
    )
    expect(apiClient.get).toHaveBeenCalledWith(
      '/agents/implementation/AGP-003/input-files/A3UP-abc/canonical-artifacts',
      { authenticated: true },
    )
    buildImplementationCanonicalArtifacts('AGP-003', 'A3UP-abc', { force: true })
    expect(apiClient.post).toHaveBeenLastCalledWith(
      '/agents/implementation/AGP-003/input-files/A3UP-abc/canonical-artifacts?force=true',
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
