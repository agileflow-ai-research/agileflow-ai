import { beforeEach, describe, expect, it, vi } from 'vitest'

import { apiClient } from './apiClient.js'
import { createClientInput } from './inputService.js'

vi.mock('./apiClient.js', () => ({
  apiClient: { post: vi.fn() },
}))

describe('inputService', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('creates the first text ClientInput through the authenticated API client', async () => {
    const response = { status: 201, data: { input_type: 'TEXT' } }
    const input = { input_type: 'TEXT', content: 'A library lending workflow.' }
    apiClient.post.mockResolvedValue(response)

    await expect(createClientInput('PRJ-001', input)).resolves.toBe(response)

    expect(apiClient.post).toHaveBeenCalledWith(
      '/projects/PRJ-001/inputs',
      input,
      { authenticated: true },
    )
    expect(apiClient.post).toHaveBeenCalledOnce()
    expect(apiClient.post.mock.calls[0][1]).toEqual({
      input_type: 'TEXT',
      content: 'A library lending workflow.',
    })
    expect(apiClient.post.mock.calls[0][1]).not.toHaveProperty('owner_user_id')
    expect(apiClient.post.mock.calls[0][1]).not.toHaveProperty('created_by')
    expect(apiClient.post.mock.calls[0][0]).not.toContain('orchestrator')
  })
})
