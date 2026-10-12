import { beforeEach, describe, expect, it, vi } from 'vitest'

import { apiClient } from './apiClient.js'
import { register } from './authService.js'

vi.mock('./apiClient.js', () => ({
  apiClient: {
    post: vi.fn(),
  },
}))

describe('authService', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('registers through the public auth endpoint with the exact payload', async () => {
    const payload = {
      name: 'Ada Lovelace',
      email: 'ada@example.com',
      password: 'secret',
    }
    const response = { status: 201, data: { user_id: 'USR-001' } }
    apiClient.post.mockResolvedValue(response)

    await expect(register(payload)).resolves.toBe(response)
    expect(apiClient.post).toHaveBeenCalledWith(
      '/auth/register',
      payload,
      { authenticated: false },
    )
  })
})
