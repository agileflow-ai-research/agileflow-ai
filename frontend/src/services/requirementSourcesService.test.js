import { beforeEach, describe, expect, it, vi } from 'vitest'

import { apiClient } from './apiClient.js'
import {
  deleteRequirementSource,
  getRequirementSources,
  uploadRequirementSources,
  processRequirementSources,
} from './requirementSourcesService.js'

vi.mock('./apiClient.js', () => ({
  apiClient: {
    get: vi.fn(),
    post: vi.fn(),
    delete: vi.fn(),
  },
}))

describe('requirementSourcesService', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('getRequirementSources calls GET endpoint with encoded ID', async () => {
    apiClient.get.mockResolvedValue({ data: [] })
    await getRequirementSources('AGP-001')
    expect(apiClient.get).toHaveBeenCalledWith(
      '/agents/requirements/AGP-001/sources',
      { authenticated: true },
    )
  })

  it('uploadRequirementSources appends files and optional source_type to FormData', async () => {
    apiClient.post.mockResolvedValue({ data: [] })
    const file = new File(['content'], 'test.pdf', { type: 'application/pdf' })
    await uploadRequirementSources('AGP-001', [file], 'DOCUMENT')

    expect(apiClient.post).toHaveBeenCalledWith(
      '/agents/requirements/AGP-001/sources',
      expect.any(FormData),
      { authenticated: true },
    )
  })

  it('deleteRequirementSource calls DELETE endpoint with encoded IDs', async () => {
    apiClient.delete.mockResolvedValue({ data: null })
    await deleteRequirementSource('AGP-001', 'DOC-001')
    expect(apiClient.delete).toHaveBeenCalledWith(
      '/agents/requirements/AGP-001/sources/DOC-001',
      { authenticated: true },
    )
  })

  it('processRequirementSources calls the dedicated processing endpoint', async () => {
    apiClient.post.mockResolvedValue({ data: [] })
    await processRequirementSources('AGP-001')
    expect(apiClient.post).toHaveBeenCalledWith(
      '/agents/requirements/AGP-001/sources/process',
      undefined,
      { authenticated: true },
    )
  })
})
