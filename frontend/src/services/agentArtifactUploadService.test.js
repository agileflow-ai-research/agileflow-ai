import { beforeEach, describe, expect, it, vi } from 'vitest'

import { apiClient } from './apiClient.js'
import {
  deleteStandaloneArtifact,
  extractStandaloneArtifactDocument,
  uploadStandaloneArtifact,
} from './agentArtifactUploadService.js'

vi.mock('./apiClient.js', () => ({
  apiClient: { post: vi.fn(), delete: vi.fn() },
}))

describe('agentArtifactUploadService', () => {
  beforeEach(() => vi.clearAllMocks())

  it('sends a multipart body with only the allowed fields and never a client path', () => {
    const file = new File(['AC-001'], 'acceptance.pdf', { type: 'application/pdf' })
    uploadStandaloneArtifact('AGP-001', { source_type: 'DOCUMENT', artifact_type: 'ACCEPTANCE_CRITERIA', label: '  Checkout  ', file })
    const [path, body, options] = apiClient.post.mock.calls[0]
    expect(path).toBe('/agent-projects/AGP-001/artifact-uploads')
    expect(body).toBeInstanceOf(FormData)
    expect(body.get('source_type')).toBe('DOCUMENT')
    expect(body.get('artifact_type')).toBe('ACCEPTANCE_CRITERIA')
    expect(body.get('label')).toBe('Checkout')
    expect(body.get('file')).toBe(file)
    expect([...body.keys()].sort()).toEqual(['artifact_type', 'file', 'label', 'source_type'])
    expect(options).toEqual({ authenticated: true })
  })

  it('omits a blank label', () => {
    const file = new File(['x'], 'wire.png', { type: 'image/png' })
    uploadStandaloneArtifact('AGP-001', { source_type: 'IMAGE', artifact_type: 'UI_SPECIFICATION', label: '   ', file })
    expect(apiClient.post.mock.calls[0][1].has('label')).toBe(false)
  })

  it('calls the extraction and delete endpoints for one upload only', () => {
    extractStandaloneArtifactDocument('AGP-001', 'SAUP-abc')
    expect(apiClient.post).toHaveBeenCalledWith('/agent-projects/AGP-001/artifact-uploads/SAUP-abc/extraction', undefined, { authenticated: true })

    deleteStandaloneArtifact('AGP-001', 'SAUP-abc')
    expect(apiClient.delete).toHaveBeenCalledWith('/agent-projects/AGP-001/artifact-uploads/SAUP-abc', { authenticated: true })
  })
})
