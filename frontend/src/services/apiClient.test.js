import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

function unauthorizedResponse() {
  return {
    ok: false,
    status: 401,
    statusText: 'Unauthorized',
    headers: { get: () => 'application/json' },
    json: async () => ({
      success: false,
      message: 'Authentication failed',
      errors: [],
    }),
  }
}

describe('apiClient unauthorized handling', () => {
  beforeEach(() => {
    vi.resetModules()
    vi.stubEnv('VITE_API_BASE_URL', 'http://api.test/api/v1')
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(unauthorizedResponse()))
    sessionStorage.clear()
  })

  afterEach(() => {
    vi.unstubAllEnvs()
    vi.unstubAllGlobals()
  })

  it('notifies the auth layer for an authenticated request returning 401', async () => {
    sessionStorage.setItem('agileflow_access_token', 'stored-token')
    const { request, setUnauthorizedHandler } = await import('./apiClient.js')
    const unauthorizedHandler = vi.fn()
    setUnauthorizedHandler(unauthorizedHandler)

    await expect(request('/projects')).rejects.toMatchObject({ status: 401 })

    expect(unauthorizedHandler).toHaveBeenCalledOnce()
  })

  it.each(['/auth/login', '/auth/register'])(
    'does not notify the auth layer for public request %s returning 401',
    async (path) => {
      const { request, setUnauthorizedHandler } = await import('./apiClient.js')
      const unauthorizedHandler = vi.fn()
      setUnauthorizedHandler(unauthorizedHandler)

      await expect(
        request(path, { method: 'POST', authenticated: false }),
      ).rejects.toMatchObject({ status: 401 })

      expect(unauthorizedHandler).not.toHaveBeenCalled()
    },
  )
})
