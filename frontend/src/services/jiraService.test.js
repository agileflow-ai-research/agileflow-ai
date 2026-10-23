import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { apiClient } from './apiClient.js'
import {
  cleanJiraCallbackParams,
  disconnectJira,
  getJiraBoards,
  getJiraContext,
  getJiraProjects,
  getJiraSites,
  getJiraStatus,
  normalizeJiraError,
  selectJiraBoard,
  selectJiraProject,
  selectJiraSite,
  startJiraConnection,
} from './jiraService.js'

vi.mock('./apiClient.js', () => ({
  apiClient: {
    get: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
  },
}))

describe('jiraService', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('getJiraStatus calls GET /integrations/jira/status with authentication', async () => {
    const mockData = { connected: true, provider: 'JIRA' }
    apiClient.get.mockResolvedValueOnce({ data: mockData })

    const result = await getJiraStatus()
    expect(apiClient.get).toHaveBeenCalledWith('/integrations/jira/status', {
      authenticated: true,
    })
    expect(result).toEqual(mockData)
  })

  it('startJiraConnection calls GET /integrations/jira/connect', async () => {
    const mockData = { authorization_url: 'https://auth.atlassian.com/authorize?state=123' }
    apiClient.get.mockResolvedValueOnce({ data: mockData })

    const result = await startJiraConnection()
    expect(apiClient.get).toHaveBeenCalledWith('/integrations/jira/connect', {
      authenticated: true,
    })
    expect(result).toEqual(mockData)
  })

  it('disconnectJira calls DELETE /integrations/jira/connection', async () => {
    const mockData = { disconnected: true, message: 'Disconnected' }
    apiClient.delete.mockResolvedValueOnce({ data: mockData })

    const result = await disconnectJira()
    expect(apiClient.delete).toHaveBeenCalledWith('/integrations/jira/connection', {
      authenticated: true,
    })
    expect(result).toEqual(mockData)
  })

  it('getJiraSites calls GET /integrations/jira/sites and returns array', async () => {
    const mockSites = [{ cloud_id: 'c1', name: 'Site 1', url: 'https://site1.atlassian.net' }]
    apiClient.get.mockResolvedValueOnce({ data: mockSites })

    const result = await getJiraSites()
    expect(apiClient.get).toHaveBeenCalledWith('/integrations/jira/sites', {
      authenticated: true,
    })
    expect(result).toEqual(mockSites)
  })

  it('selectJiraSite calls PUT /integrations/jira/site with cloud_id', async () => {
    const mockSelected = { cloud_id: 'c1', site_name: 'Site 1' }
    apiClient.put.mockResolvedValueOnce({ data: mockSelected })

    const result = await selectJiraSite('c1')
    expect(apiClient.put).toHaveBeenCalledWith(
      '/integrations/jira/site',
      { cloud_id: 'c1' },
      { authenticated: true },
    )
    expect(result).toEqual(mockSelected)
  })

  it('selectJiraSite throws when cloudId is missing', async () => {
    await expect(selectJiraSite('')).rejects.toThrow('valid Jira site cloud_id is required')
  })

  it('getJiraProjects calls GET /integrations/jira/projects with query pagination', async () => {
    const mockProjects = [{ id: 'p1', key: 'BOOK', name: 'BookEase' }]
    apiClient.get.mockResolvedValueOnce({ data: mockProjects })

    const result = await getJiraProjects({ startAt: 10, maxResults: 25 })
    expect(apiClient.get).toHaveBeenCalledWith(
      '/integrations/jira/projects?start_at=10&max_results=25',
      { authenticated: true },
    )
    expect(result).toEqual(mockProjects)
  })

  it('selectJiraProject calls PUT /integrations/jira/project with identifier', async () => {
    const mockSelected = { project_id: '10001', project_key: 'BOOK' }
    apiClient.put.mockResolvedValueOnce({ data: mockSelected })

    const result = await selectJiraProject({ projectId: '10001', projectKey: 'BOOK' })
    expect(apiClient.put).toHaveBeenCalledWith(
      '/integrations/jira/project',
      { project_id: '10001', project_key: 'BOOK' },
      { authenticated: true },
    )
    expect(result).toEqual(mockSelected)
  })

  it('getJiraBoards calls GET /integrations/jira/boards with query pagination', async () => {
    const mockBoards = [{ id: 10, name: 'Scrum Board', type: 'scrum' }]
    apiClient.get.mockResolvedValueOnce({ data: mockBoards })

    const result = await getJiraBoards({ startAt: 0, maxResults: 50 })
    expect(apiClient.get).toHaveBeenCalledWith(
      '/integrations/jira/boards?start_at=0&max_results=50',
      { authenticated: true },
    )
    expect(result).toEqual(mockBoards)
  })

  it('selectJiraBoard calls PUT /integrations/jira/board with board_id', async () => {
    const mockSelected = { board_id: 10, board_name: 'Scrum Board', board_type: 'scrum' }
    apiClient.put.mockResolvedValueOnce({ data: mockSelected })

    const result = await selectJiraBoard(10)
    expect(apiClient.put).toHaveBeenCalledWith(
      '/integrations/jira/board',
      { board_id: 10 },
      { authenticated: true },
    )
    expect(result).toEqual(mockSelected)
  })

  it('getJiraContext calls GET /integrations/jira/context', async () => {
    const mockContext = {
      connected: true,
      site: { cloud_id: 'c1', name: 'Site 1' },
      project: { id: 'p1', key: 'BOOK', name: 'BookEase' },
      board: { id: 10, name: 'Scrum Board', type: 'scrum' },
    }
    apiClient.get.mockResolvedValueOnce({ data: mockContext })

    const result = await getJiraContext()
    expect(apiClient.get).toHaveBeenCalledWith('/integrations/jira/context', {
      authenticated: true,
    })
    expect(result).toEqual(mockContext)
  })

  describe('cleanJiraCallbackParams', () => {
    it('detects connected param and cleans URL without reload', () => {
      delete window.location
      window.location = new URL('http://localhost:5173/agent-projects/123?jira_connected=true')
      const replaceSpy = vi.spyOn(window.history, 'replaceState').mockImplementation(() => {})

      const res = cleanJiraCallbackParams()
      expect(res.connected).toBe(true)
      expect(res.error).toBeNull()
      expect(replaceSpy).toHaveBeenCalledWith({}, expect.any(String), '/agent-projects/123')
    })

    it('detects error param and cleans URL', () => {
      delete window.location
      window.location = new URL('http://localhost:5173/agent-projects/123?jira_error=access_denied')
      const replaceSpy = vi.spyOn(window.history, 'replaceState').mockImplementation(() => {})

      const res = cleanJiraCallbackParams()
      expect(res.connected).toBe(false)
      expect(res.error).toBe('access_denied')
      expect(replaceSpy).toHaveBeenCalled()
    })
  })

  describe('normalizeJiraError', () => {
    it('maps JIRA_REAUTHORIZATION_REQUIRED correctly', () => {
      const msg = normalizeJiraError({ message: 'JIRA_REAUTHORIZATION_REQUIRED: Expired' })
      expect(msg).toContain('Your Jira connection has expired')
    })

    it('maps JIRA_RATE_LIMITED and 429 correctly', () => {
      const msg1 = normalizeJiraError({ message: 'JIRA_RATE_LIMITED' })
      expect(msg1).toContain('temporarily limiting requests')
      const msg2 = normalizeJiraError({ status: 429 })
      expect(msg2).toContain('temporarily limiting requests')
    })

    it('maps JIRA_BOARD_NOT_SCRUM correctly', () => {
      const msg = normalizeJiraError({ message: 'JIRA_BOARD_NOT_SCRUM' })
      expect(msg).toContain('Only Scrum boards are supported')
    })

    it('maps JIRA_UPSTREAM_ERROR without leaking raw details', () => {
      const msg = normalizeJiraError({
        message: 'JIRA_UPSTREAM_ERROR: secret internal token failed at 123',
      })
      expect(msg).toBe('Jira could not be reached. Your Agent 2 results are unchanged.')
      expect(msg).not.toContain('secret')
    })
  })
})
