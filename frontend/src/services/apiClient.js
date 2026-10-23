import { getAccessToken } from './tokenStorage.js'

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? '').replace(/\/$/, '')
let unauthorizedHandler = null

export function setUnauthorizedHandler(handler) {
  unauthorizedHandler = typeof handler === 'function' ? handler : null

  return () => {
    if (unauthorizedHandler === handler) {
      unauthorizedHandler = null
    }
  }
}

function notifyUnauthorized(error) {
  if (error && !isApplicationAuthError(error)) {
    return
  }
  try {
    unauthorizedHandler?.(error)
  } catch {
    // Session cleanup must not replace the original API error.
  }
}

export function isApplicationAuthError(error) {
  if (!error || error.status !== 401) {
    return false
  }

  // Third-party integration domain authentication failures (e.g. Jira OAuth reauthorization)
  // must NOT invalidate the AgileFlow application session.
  const message = typeof error.message === 'string' ? error.message : ''
  if (message.startsWith('JIRA_')) {
    return false
  }

  const errors = Array.isArray(error.errors) ? error.errors : []
  if (errors.some((err) => err?.field === 'jira')) {
    return false
  }

  return true
}

export class ApiError extends Error {
  constructor({ status, message, errors, data, workflow_stage, next_action, cause }) {
    super(message, { cause })
    this.name = 'ApiError'
    this.status = status
    this.errors = errors
    this.data = data
    this.workflow_stage = workflow_stage
    this.next_action = next_action
  }
}

function createApiError(status, payload, fallbackMessage, cause) {
  return new ApiError({
    status,
    message: payload?.message || fallbackMessage,
    errors: Array.isArray(payload?.errors) ? payload.errors : [],
    data: payload?.data ?? null,
    workflow_stage: payload?.workflow_stage ?? null,
    next_action: payload?.next_action ?? null,
    cause,
  })
}

function buildUrl(path) {
  if (!API_BASE_URL) {
    throw createApiError(0, null, 'The API base URL is not configured')
  }

  const normalizedPath = path.startsWith('/') ? path : `/${path}`
  return `${API_BASE_URL}${normalizedPath}`
}

async function parseResponse(response) {
  const contentType = response.headers.get('content-type') ?? ''
  if (!contentType.includes('application/json')) {
    return null
  }

  try {
    return await response.json()
  } catch {
    return null
  }
}

export async function request(
  path,
  { method = 'GET', body, headers = {}, signal, authenticated = true } = {},
) {
  const requestHeaders = new Headers(headers)
  const token = authenticated ? getAccessToken() : null
  const isFormData = typeof FormData !== 'undefined' && body instanceof FormData
  if (body !== undefined && !isFormData && !requestHeaders.has('Content-Type')) {
    requestHeaders.set('Content-Type', 'application/json')
  }
  if (token) {
    requestHeaders.set('Authorization', `Bearer ${token}`)
  }

  let response
  try {
    response = await fetch(buildUrl(path), {
      method,
      headers: requestHeaders,
      body: body === undefined ? undefined : isFormData ? body : JSON.stringify(body),
      signal,
    })
  } catch (error) {
    if (error instanceof ApiError) {
      throw error
    }
    throw createApiError(0, null, 'The API is unavailable', error)
  }

  const payload = await parseResponse(response)
  if (!response.ok || payload?.success === false) {
    const error = createApiError(
      response.status,
      payload,
      response.statusText || 'The request failed',
    )
    if (authenticated && response.status === 401 && isApplicationAuthError(error)) {
      notifyUnauthorized(error)
    }
    throw error
  }

  return {
    success: payload?.success ?? true,
    message: payload?.message ?? response.statusText,
    data: payload?.data !== undefined ? payload.data : (payload ?? null),
    payload: payload ?? null,
    errors: Array.isArray(payload?.errors) ? payload.errors : [],
    workflow_stage: payload?.workflow_stage ?? null,
    next_action: payload?.next_action ?? null,
    status: response.status,
  }
}

export const apiClient = {
  get(path, options) {
    return request(path, { ...options, method: 'GET' })
  },
  post(path, body, options) {
    return request(path, { ...options, method: 'POST', body })
  },
  put(path, body, options) {
    return request(path, { ...options, method: 'PUT', body })
  },
  patch(path, body, options) {
    return request(path, { ...options, method: 'PATCH', body })
  },
  delete(path, options) {
    return request(path, { ...options, method: 'DELETE' })
  },
}
