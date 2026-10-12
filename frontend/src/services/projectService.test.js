import { beforeEach, describe, expect, it, vi } from 'vitest'

import { apiClient } from './apiClient.js'
import { getProjects } from './projectService.js'

vi.mock('./apiClient.js', () => ({
  apiClient: { get: vi.fn() },
}))

describe('projectService', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('gets the owner-scoped project list as an authenticated request', async () => {
    const response = { status: 200, data: [] }
    apiClient.get.mockResolvedValue(response)

    await expect(getProjects()).resolves.toBe(response)
    expect(apiClient.get).toHaveBeenCalledWith('/projects', { authenticated: true })
    expect(apiClient.get).toHaveBeenCalledOnce()
  })
})
