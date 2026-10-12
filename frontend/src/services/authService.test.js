import { beforeEach, describe, expect, it, vi } from 'vitest'

import { apiClient } from './apiClient.js'
import { getCurrentUser, login, register } from './authService.js'

vi.mock('./apiClient.js', () => ({
  apiClient: {
    get: vi.fn(),
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

  it('logs in through the public auth endpoint with the exact payload', async () => {
    const payload = {
      email: 'ada@example.com',
      password: 'secret',
    }
    const response = {
      status: 200,
      data: { access_token: 'jwt-token', token_type: 'bearer' },
    }
    apiClient.post.mockResolvedValue(response)

    await expect(login(payload)).resolves.toBe(response)
    expect(apiClient.post).toHaveBeenCalledWith(
      '/auth/login',
      payload,
      { authenticated: false },
    )
  })

  it('gets the current user through the authenticated auth endpoint', async () => {
    const response = { status: 200, data: { user_id: 'USR-001' } }
    apiClient.get.mockResolvedValue(response)

    await expect(getCurrentUser()).resolves.toBe(response)
    expect(apiClient.get).toHaveBeenCalledWith(
      '/auth/me',
      { authenticated: true },
    )
  })
})
