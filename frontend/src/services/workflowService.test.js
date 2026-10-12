import { beforeEach, describe, expect, it, vi } from 'vitest'

import { apiClient } from './apiClient.js'
import * as workflowService from './workflowService.js'

vi.mock('./apiClient.js', () => ({
  apiClient: { get: vi.fn() },
}))

describe('workflowService', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('gets an authenticated workflow snapshot without an ownership filter', async () => {
    const response = { status: 200, data: { project_id: 'PRJ-001' } }
    apiClient.get.mockResolvedValue(response)

    await expect(workflowService.getWorkflow('PRJ-001')).resolves.toBe(response)

    expect(apiClient.get).toHaveBeenCalledWith('/projects/PRJ-001/workflow', {
      authenticated: true,
    })
    expect(apiClient.get.mock.calls[0]).toHaveLength(2)
  })

  it('gets authenticated project events without an ownership filter', async () => {
    const response = { status: 200, data: [] }
    apiClient.get.mockResolvedValue(response)

    await expect(workflowService.getEvents('PRJ-001')).resolves.toBe(response)

    expect(apiClient.get).toHaveBeenCalledWith('/projects/PRJ-001/events', {
      authenticated: true,
    })
    expect(apiClient.get.mock.calls[0]).toHaveLength(2)
  })

  it('exposes no workflow mutation during F1.10', () => {
    expect(workflowService).not.toHaveProperty('nextStep')
    expect(apiClient).not.toHaveProperty('post')
  })
})
