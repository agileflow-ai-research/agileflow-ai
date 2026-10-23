import { apiClient } from './apiClient.js'

const JIRA_BASE_PATH = '/integrations/jira'

/**
 * Retrieve current Jira connection status for the authenticated user.
 */
export async function getJiraStatus() {
  const response = await apiClient.get(`${JIRA_BASE_PATH}/status`, {
    authenticated: true,
  })
  return response.data ?? response.payload ?? null
}

/**
 * Initiate Jira Cloud OAuth 2.0 flow and obtain safe authorization URL.
 */
export async function startJiraConnection() {
  const response = await apiClient.get(`${JIRA_BASE_PATH}/connect`, {
    authenticated: true,
  })
  return response.data ?? response.payload ?? null
}

/**
 * Disconnect Jira for the authenticated user by removing local connection.
 */
export async function disconnectJira() {
  const response = await apiClient.delete(`${JIRA_BASE_PATH}/connection`, {
    authenticated: true,
  })
  return response.data ?? response.payload ?? null
}

/**
 * Fetch authorized Jira Cloud sites without credentials.
 */
export async function getJiraSites() {
  const response = await apiClient.get(`${JIRA_BASE_PATH}/sites`, {
    authenticated: true,
  })
  const data = response.data ?? response.payload
  return Array.isArray(data) ? data : []
}

/**
 * Select an authorized Jira Cloud site.
 * Server verifies cloud_id is accessible.
 */
export async function selectJiraSite(cloudId) {
  if (!cloudId) {
    throw new Error('A valid Jira site cloud_id is required')
  }
  const response = await apiClient.put(
    `${JIRA_BASE_PATH}/site`,
    { cloud_id: cloudId },
    { authenticated: true },
  )
  return response.data ?? response.payload ?? null
}

/**
 * Fetch accessible Jira Software projects for the selected site.
 */
export async function getJiraProjects({ startAt = 0, maxResults = 50 } = {}) {
  const query = new URLSearchParams()
  if (startAt !== undefined) query.set('start_at', String(startAt))
  if (maxResults !== undefined) query.set('max_results', String(maxResults))
  const suffix = query.size > 0 ? `?${query.toString()}` : ''

  const response = await apiClient.get(`${JIRA_BASE_PATH}/projects${suffix}`, {
    authenticated: true,
  })
  const data = response.data ?? response.payload
  return Array.isArray(data) ? data : []
}

/**
 * Select an accessible Jira project on the selected site.
 */
export async function selectJiraProject({ projectId, projectKey } = {}) {
  if (!projectId && !projectKey) {
    throw new Error('Either projectId or projectKey must be provided')
  }
  const response = await apiClient.put(
    `${JIRA_BASE_PATH}/project`,
    {
      project_id: projectId || undefined,
      project_key: projectKey || undefined,
    },
    { authenticated: true },
  )
  return response.data ?? response.payload ?? null
}

/**
 * Fetch Scrum boards for the selected project.
 */
export async function getJiraBoards({ startAt = 0, maxResults = 50 } = {}) {
  const query = new URLSearchParams()
  if (startAt !== undefined) query.set('start_at', String(startAt))
  if (maxResults !== undefined) query.set('max_results', String(maxResults))
  const suffix = query.size > 0 ? `?${query.toString()}` : ''

  const response = await apiClient.get(`${JIRA_BASE_PATH}/boards${suffix}`, {
    authenticated: true,
  })
  const data = response.data ?? response.payload
  return Array.isArray(data) ? data : []
}

/**
 * Select a Scrum board for the selected project.
 */
export async function selectJiraBoard(boardId) {
  if (!boardId && boardId !== 0) {
    throw new Error('A valid boardId is required')
  }
  const response = await apiClient.put(
    `${JIRA_BASE_PATH}/board`,
    { board_id: Number(boardId) },
    { authenticated: true },
  )
  return response.data ?? response.payload ?? null
}

/**
 * Retrieve current Jira connection and selection context.
 */
export async function getJiraContext() {
  const response = await apiClient.get(`${JIRA_BASE_PATH}/context`, {
    authenticated: true,
  })
  return response.data ?? response.payload ?? null
}

/**
 * Clean temporary Jira callback query parameters from the browser URL.
 */
export function cleanJiraCallbackParams() {
  if (typeof window === 'undefined' || !window.location) {
    return { connected: false, error: null }
  }

  let url
  try {
    const rawHref = window.location.href || (window.location.pathname ? `http://localhost${window.location.pathname}` : 'http://localhost/')
    url = new URL(rawHref)
  } catch {
    return { connected: false, error: null }
  }
  const connected =
    url.searchParams.get('jira_connected') === 'true' ||
    url.searchParams.get('jira') === 'connected'
  const error =
    url.searchParams.get('jira_error') ||
    (url.searchParams.get('jira') === 'error' ? 'connection_failed' : null)

  let changed = false
  ;['jira_connected', 'jira_error', 'jira'].forEach((param) => {
    if (url.searchParams.has(param)) {
      url.searchParams.delete(param)
      changed = true
    }
  })

  if (changed) {
    const cleanPath = url.pathname + (url.search ? url.search : '') + url.hash
    window.history.replaceState({}, document.title, cleanPath)
  }

  return { connected, error }
}

/**
 * Normalize Jira error response into user-friendly message.
 */
export function normalizeJiraError(error) {
  if (!error) return 'An unexpected error occurred'

  const messageText = String(
    error.message ||
      error.errors?.[0]?.message ||
      error.data?.message ||
      '',
  )

  if (messageText.includes('JIRA_NOT_CONNECTED')) {
    return 'Jira is not connected'
  }
  if (messageText.includes('JIRA_REAUTHORIZATION_REQUIRED')) {
    return 'Your Jira connection has expired. Reconnect Jira to continue.'
  }
  if (messageText.includes('JIRA_SITE_NOT_SELECTED')) {
    return 'Please select an authorized Jira site.'
  }
  if (messageText.includes('JIRA_SITE_NOT_ACCESSIBLE')) {
    return 'The selected Jira site is no longer accessible. Please reselect a site.'
  }
  if (messageText.includes('JIRA_PROJECT_NOT_SELECTED')) {
    return 'Please select a Jira project.'
  }
  if (messageText.includes('JIRA_PROJECT_NOT_ACCESSIBLE')) {
    return 'The selected project could not be accessed. Please choose another project.'
  }
  if (messageText.includes('JIRA_BOARD_NOT_ACCESSIBLE')) {
    return 'The selected board could not be accessed for this project.'
  }
  if (messageText.includes('JIRA_BOARD_NOT_SCRUM')) {
    return 'Only Scrum boards are supported for sprint synchronization.'
  }
  if (messageText.includes('JIRA_RATE_LIMITED') || error.status === 429) {
    return 'Jira is temporarily limiting requests. Please try again shortly.'
  }
  if (
    messageText.includes('JIRA_UPSTREAM_ERROR') ||
    error.status === 502 ||
    error.status === 504
  ) {
    return 'Jira could not be reached. Your Agent 2 results are unchanged.'
  }

  return 'Jira could not be reached. Your Agent 2 results are unchanged.'
}
