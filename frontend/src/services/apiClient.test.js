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

function jsonResponse(payload, { status = 200, statusText = 'OK' } = {}) {
  return {
    ok: status >= 200 && status < 300,
    status,
    statusText,
    headers: { get: () => 'application/json' },
    json: async () => payload,
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

  it('does NOT notify the auth layer when an integration request returns 401 with JIRA_REAUTHORIZATION_REQUIRED', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: false,
        status: 401,
        statusText: 'Unauthorized',
        headers: { get: () => 'application/json' },
        json: async () => ({
          success: false,
          message: 'JIRA_REAUTHORIZATION_REQUIRED',
          errors: [{ field: 'jira', message: 'JIRA_REAUTHORIZATION_REQUIRED: Token expired' }],
        }),
      }),
    )
    sessionStorage.setItem('agileflow_access_token', 'stored-token')
    const { request, setUnauthorizedHandler } = await import('./apiClient.js')
    const unauthorizedHandler = vi.fn()
    setUnauthorizedHandler(unauthorizedHandler)

    await expect(request('/integrations/jira/board', { method: 'PUT', body: { board_id: 101 } })).rejects.toMatchObject({
      status: 401,
      message: 'JIRA_REAUTHORIZATION_REQUIRED',
    })

    expect(unauthorizedHandler).not.toHaveBeenCalled()
  })

  it('does NOT notify the auth layer when an integration request returns 401 with field=jira', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: false,
        status: 401,
        statusText: 'Unauthorized',
        headers: { get: () => 'application/json' },
        json: async () => ({
          success: false,
          message: 'JIRA_UPSTREAM_ERROR',
          errors: [{ field: 'jira', message: 'Atlassian rejected token' }],
        }),
      }),
    )
    sessionStorage.setItem('agileflow_access_token', 'stored-token')
    const { request, setUnauthorizedHandler } = await import('./apiClient.js')
    const unauthorizedHandler = vi.fn()
    setUnauthorizedHandler(unauthorizedHandler)

    await expect(request('/integrations/jira/issue-types')).rejects.toMatchObject({
      status: 401,
    })

    expect(unauthorizedHandler).not.toHaveBeenCalled()
  })

  it('DOES notify the auth layer when request to /integrations/jira fails with genuine AgileFlow auth 401', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: false,
        status: 401,
        statusText: 'Unauthorized',
        headers: { get: () => 'application/json' },
        json: async () => ({
          success: false,
          message: 'Authentication failed',
          errors: [{ field: 'authorization', message: 'Authentication failed' }],
        }),
      }),
    )
    sessionStorage.setItem('agileflow_access_token', 'stored-token')
    const { request, setUnauthorizedHandler } = await import('./apiClient.js')
    const unauthorizedHandler = vi.fn()
    setUnauthorizedHandler(unauthorizedHandler)

    await expect(request('/integrations/jira/board', { method: 'PUT', body: { board_id: 101 } })).rejects.toMatchObject({
      status: 401,
      message: 'Authentication failed',
    })

    expect(unauthorizedHandler).toHaveBeenCalledOnce()
  })
})

describe('apiClient response contract', () => {
  beforeEach(() => {
    vi.resetModules()
    vi.stubEnv('VITE_API_BASE_URL', 'http://api.test/api/v1/')
    sessionStorage.clear()
  })

  afterEach(() => {
    vi.unstubAllEnvs()
    vi.unstubAllGlobals()
  })

  it('returns data from a canonical success envelope', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        jsonResponse({
          success: true,
          message: 'Project loaded',
          data: { project_id: 'PRJ-001' },
          errors: [],
        }),
      ),
    )
    const { request } = await import('./apiClient.js')

    await expect(request('/projects/PRJ-001')).resolves.toMatchObject({
      success: true,
      message: 'Project loaded',
      data: { project_id: 'PRJ-001' },
      status: 200,
    })
  })

  it('joins a trailing-slash base URL and relative path without duplicate slashes', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse({ success: true, message: 'OK', data: [] }),
    )
    vi.stubGlobal('fetch', fetchMock)
    const { request } = await import('./apiClient.js')

    await request('projects')

    expect(fetchMock).toHaveBeenCalledWith(
      'http://api.test/api/v1/projects',
      expect.any(Object),
    )
  })

  it('preserves field errors and workflow guidance from an API error', async () => {
    const errors = [{ field: 'body.name', message: 'Name is required' }]
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        jsonResponse(
          {
            success: false,
            message: 'Validation failed',
            errors,
            workflow_stage: 'PROJECT_CREATED',
            next_action: 'Correct the request',
          },
          { status: 422, statusText: 'Unprocessable Entity' },
        ),
      ),
    )
    const { request } = await import('./apiClient.js')

    await expect(request('/projects', { method: 'POST', body: {} })).rejects.toMatchObject({
      status: 422,
      errors,
      workflow_stage: 'PROJECT_CREATED',
      next_action: 'Correct the request',
    })
  })

  it('preserves safe reconciliation data from an API error', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        jsonResponse(
          {
            success: false,
            message: 'Repository created but binding failed',
            errors: [{ field: 'repository', message: 'Reconciliation required' }],
            data: { repository: { created: true, full_name: 'octocat/quickbook' } },
          },
          { status: 502, statusText: 'Bad Gateway' },
        ),
      ),
    )
    const { request } = await import('./apiClient.js')

    await expect(request('/repository')).rejects.toMatchObject({
      status: 502,
      data: { repository: { created: true, full_name: 'octocat/quickbook' } },
    })
  })

  it('wraps a network failure in a safe status-zero ApiError', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')))
    const { ApiError, request } = await import('./apiClient.js')

    const error = await request('/projects').catch((caughtError) => caughtError)

    expect(error).toBeInstanceOf(ApiError)
    expect(error).toMatchObject({
      status: 0,
      message: 'The API is unavailable',
      errors: [],
    })
  })

  it('handles a non-JSON HTTP error safely', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: false,
      status: 502,
      statusText: 'Bad Gateway',
      headers: { get: () => 'text/html' },
    }))
    const { request } = await import('./apiClient.js')

    await expect(request('/projects')).rejects.toMatchObject({
      status: 502,
      message: 'Bad Gateway',
      errors: [],
    })
  })

  it('passes FormData through without forcing a content type or JSON encoding', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse({ success: true, message: 'Uploaded', data: {} }),
    )
    vi.stubGlobal('fetch', fetchMock)
    const { request } = await import('./apiClient.js')
    const body = new FormData()
    body.append('source_type', 'DOCUMENT')

    await request('/uploads', { method: 'POST', body })

    const options = fetchMock.mock.calls[0][1]
    expect(options.body).toBe(body)
    expect(options.headers.has('Content-Type')).toBe(false)
  })

  it('sends JSON through the centralized PUT helper', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse({ success: true, message: 'Saved', data: {} }),
    )
    vi.stubGlobal('fetch', fetchMock)
    const { apiClient } = await import('./apiClient.js')

    await apiClient.put('/reviews/CHK-001', { action: 'ACCEPT' }, { authenticated: true })

    expect(fetchMock).toHaveBeenCalledWith(
      'http://api.test/api/v1/reviews/CHK-001',
      expect.objectContaining({
        method: 'PUT', body: JSON.stringify({ action: 'ACCEPT' }),
      }),
    )
  })
})
