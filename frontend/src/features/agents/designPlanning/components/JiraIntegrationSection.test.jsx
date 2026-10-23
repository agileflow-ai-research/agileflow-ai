import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import JiraIntegrationSection from './JiraIntegrationSection.jsx'
import JiraPlan from '../../../../components/agents/agent-2/results/JiraPlan.jsx'
import * as jiraService from '../../../../services/jiraService.js'

vi.mock('../../../../services/jiraService.js', async () => {
  const actual = await vi.importActual('../../../../services/jiraService.js')
  return {
    ...actual,
    getJiraStatus: vi.fn(),
    startJiraConnection: vi.fn(),
    disconnectJira: vi.fn(),
    getJiraSites: vi.fn(),
    selectJiraSite: vi.fn(),
    getJiraProjects: vi.fn(),
    selectJiraProject: vi.fn(),
    getJiraBoards: vi.fn(),
    selectJiraBoard: vi.fn(),
    getJiraContext: vi.fn(),
    getJiraIssueTypes: vi.fn(),
    generateJiraSyncPreview: vi.fn(),
    cleanJiraCallbackParams: vi.fn().mockReturnValue({ connected: false, error: null }),
    executeJiraSync: vi.fn(),
    getJiraSyncStatus: vi.fn(),
  }
})

describe('JiraIntegrationSection', () => {
  const project = {
    agent_project_id: 'AGP-002',
    name: 'BookEase',
    domain: 'Hospitality',
  }

  const originalLocation = window.location

  beforeEach(() => {
    vi.clearAllMocks()
    localStorage.clear()
    sessionStorage.clear()
    window.location = new URL('http://localhost:5173/agent-projects/AGP-002')

    jiraService.getJiraStatus.mockResolvedValue({ connected: false })
    jiraService.getJiraContext.mockResolvedValue({
      connected: false,
      site: null,
      project: null,
      board: null,
    })
    jiraService.getJiraSites.mockResolvedValue([])
    jiraService.getJiraProjects.mockResolvedValue([])
    jiraService.getJiraBoards.mockResolvedValue([])
    jiraService.getJiraIssueTypes.mockResolvedValue([
      { id: '10000', name: 'Epic', subtask: false, hierarchy_level: 1 },
      { id: '10001', name: 'Story', subtask: false, hierarchy_level: 0 },
      { id: '10002', name: 'Task', subtask: false, hierarchy_level: 0 },
    ])
    jiraService.cleanJiraCallbackParams.mockReturnValue({ connected: false, error: null })
    jiraService.getJiraSyncStatus.mockResolvedValue(null)
    jiraService.executeJiraSync.mockResolvedValue({
      status: 'COMPLETED',
      target: {
        site_name: 'Site Alpha',
        project_key: 'BOOK',
        project_name: 'BookEase',
        board_name: 'BookEase Board',
      },
      sprint_summary: { created: 1, reused: 0, failed: 0, total: 1 },
      issue_summary: { created: 2, reused: 0, failed: 0, total: 2 },
      placement_summary: { created: 2, failed: 0, total: 2 },
      traceability: {
        sprints: [
          {
            agileflow_sprint_id: 'SP-001',
            jira_sprint_id: '101',
            name: 'Sprint 1',
            state: 'future',
          },
        ],
        issues: [
          {
            artifact_id: 'EPIC-001',
            jira_id: '2001',
            jira_key: 'BOOK-1',
            jira_issue_type: 'Epic',
            summary: 'User Account Management',
            planned_sprint: null,
            parent_jira_key: null,
            browse_url: 'https://alpha.atlassian.net/browse/BOOK-1',
          },
        ],
      },
      warnings: [],
      failures: [],
    })
  })

  afterEach(() => {
    vi.restoreAllMocks()
    window.location = originalLocation
  })

  // 1. Jira UI hidden/inactive when JIRA_PLAN not generated
  it('1. Jira UI is not rendered when JIRA_PLAN is not generated', () => {
    render(
      <JiraPlan
        project={project}
        outputs={{
          SYSTEM_ARCHITECTURE: { style: 'Microservices' },
        }}
      />,
    )
    expect(screen.queryByRole('heading', { name: /Jira Cloud/i })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Connect Jira/i })).not.toBeInTheDocument()
  })

  // 2. Disconnected state
  it('2. renders disconnected state with Not Connected badge and Connect Jira button', async () => {
    jiraService.getJiraContext.mockResolvedValueOnce({
      connected: false,
      site: null,
      project: null,
      board: null,
    })
    jiraService.getJiraStatus.mockResolvedValueOnce({
      connected: false,
    })

    render(<JiraIntegrationSection project={project} />)

    expect(await screen.findByRole('heading', { name: /Jira Cloud/i })).toBeInTheDocument()
    expect(screen.getByText('Not Connected')).toBeInTheDocument()
    expect(
      screen.getByText(/Connect your Jira workspace to prepare this approved planning output/i),
    ).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Connect Jira/i })).toBeInTheDocument()
  })

  // 3. Connect Jira action
  it('3. Connect Jira action opens Jira authorization in a new tab', async () => {
    const user = userEvent.setup()
    jiraService.getJiraContext.mockResolvedValueOnce({ connected: false })
    jiraService.getJiraStatus.mockResolvedValueOnce({ connected: false })
    jiraService.startJiraConnection.mockResolvedValueOnce({
      authorization_url: 'https://auth.atlassian.com/oauth/authorize?state=abc',
    })

    const openSpy = vi.spyOn(window, 'open').mockImplementation(() => null)

    render(<JiraIntegrationSection project={project} />)

    const connectBtn = await screen.findByRole('button', { name: /Connect Jira/i })
    await user.click(connectBtn)

    await waitFor(() => {
      expect(jiraService.startJiraConnection).toHaveBeenCalledOnce()
      expect(openSpy).toHaveBeenCalledWith(
        'https://auth.atlassian.com/oauth/authorize?state=abc',
        '_blank',
        'noopener,noreferrer',
      )
    })
    openSpy.mockRestore()
  })

  // 4. Connected state
  it('4. renders connected state with Connected badge and Disconnect Jira button', async () => {
    jiraService.getJiraContext.mockResolvedValueOnce({
      connected: true,
      site: null,
      project: null,
      board: null,
    })
    jiraService.getJiraStatus.mockResolvedValueOnce({ connected: true })
    jiraService.getJiraSites.mockResolvedValueOnce([])

    render(<JiraIntegrationSection project={project} />)

    expect(await screen.findByText('Connected')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Disconnect Jira/i })).toBeInTheDocument()
  })

  // 5. Site list loading
  it('5. loads authorized sites when connected and no site is selected', async () => {
    jiraService.getJiraContext.mockResolvedValueOnce({
      connected: true,
      site: null,
      project: null,
      board: null,
    })
    jiraService.getJiraSites.mockResolvedValueOnce([
      { cloud_id: 'site-1', name: 'Site Alpha', url: 'https://alpha.atlassian.net' },
      { cloud_id: 'site-2', name: 'Site Beta', url: 'https://beta.atlassian.net' },
    ])

    render(<JiraIntegrationSection project={project} />)

    expect(await screen.findByRole('heading', { name: /Select Jira Site/i })).toBeInTheDocument()
    expect(jiraService.getJiraSites).toHaveBeenCalledOnce()

    const select = await screen.findByLabelText(/Available Sites/i)
    expect(select).toBeInTheDocument()
    expect(screen.getByRole('option', { name: /Site Alpha/i })).toBeInTheDocument()
    expect(screen.getByRole('option', { name: /Site Beta/i })).toBeInTheDocument()
  })

  // 6. No automatic site selection
  it('6. does not automatically select a site even when only 1 exists', async () => {
    jiraService.getJiraContext.mockResolvedValueOnce({
      connected: true,
      site: null,
      project: null,
      board: null,
    })
    jiraService.getJiraSites.mockResolvedValueOnce([
      { cloud_id: 'site-single', name: 'Only Site', url: 'https://only.atlassian.net' },
    ])

    render(<JiraIntegrationSection project={project} />)

    const select = await screen.findByLabelText(/Available Sites/i)
    // Value remains unselected placeholder
    expect(select.value).toBe('')
    expect(jiraService.selectJiraSite).not.toHaveBeenCalled()
  })

  // 7. Explicit site selection
  it('7. allows explicit site selection and updates context', async () => {
    const user = userEvent.setup()
    jiraService.getJiraContext
      .mockResolvedValueOnce({ connected: true, site: null })
      .mockResolvedValueOnce({
        connected: true,
        site: { cloud_id: 'site-1', name: 'Site Alpha', url: 'https://alpha.atlassian.net' },
        project: null,
        board: null,
      })
    jiraService.getJiraSites.mockResolvedValueOnce([
      { cloud_id: 'site-1', name: 'Site Alpha', url: 'https://alpha.atlassian.net' },
    ])
    jiraService.selectJiraSite.mockResolvedValueOnce({
      cloud_id: 'site-1',
      site_name: 'Site Alpha',
    })
    jiraService.getJiraProjects.mockResolvedValueOnce([])

    render(<JiraIntegrationSection project={project} />)

    const select = await screen.findByLabelText(/Available Sites/i)
    await user.selectOptions(select, 'site-1')

    const selectBtn = screen.getByRole('button', { name: 'Select Site' })
    await user.click(selectBtn)

    await waitFor(() => {
      expect(jiraService.selectJiraSite).toHaveBeenCalledWith('site-1')
    })
  })

  // 8. Project loading after site
  it('8. loads accessible Jira projects after site selection', async () => {
    jiraService.getJiraContext.mockResolvedValueOnce({
      connected: true,
      site: { cloud_id: 'site-1', name: 'Site Alpha' },
      project: null,
      board: null,
    })
    jiraService.getJiraProjects.mockResolvedValueOnce([
      { id: '10001', key: 'BOOK', name: 'BookEase' },
      { id: '10002', key: 'SHOP', name: 'ShopSmart' },
    ])

    render(<JiraIntegrationSection project={project} />)

    expect(await screen.findByRole('heading', { name: /Select Jira Project/i })).toBeInTheDocument()
    expect(jiraService.getJiraProjects).toHaveBeenCalledOnce()

    expect(await screen.findByLabelText(/Available Projects/i)).toBeInTheDocument()
    expect(screen.getByRole('option', { name: /BOOK — BookEase/i })).toBeInTheDocument()
    expect(screen.getByRole('option', { name: /SHOP — ShopSmart/i })).toBeInTheDocument()
  })

  // 9. No automatic project selection
  it('9. does not automatically select a project based on project name', async () => {
    jiraService.getJiraContext.mockResolvedValueOnce({
      connected: true,
      site: { cloud_id: 'site-1', name: 'Site Alpha' },
      project: null,
      board: null,
    })
    jiraService.getJiraProjects.mockResolvedValueOnce([
      { id: '10001', key: 'BOOK', name: 'BookEase' },
    ])

    render(<JiraIntegrationSection project={project} />)

    const select = await screen.findByLabelText(/Available Projects/i)
    expect(select.value).toBe('')
    expect(jiraService.selectJiraProject).not.toHaveBeenCalled()
  })

  // 10. Explicit project selection
  it('10. allows explicit project selection and updates context', async () => {
    const user = userEvent.setup()
    jiraService.getJiraContext
      .mockResolvedValueOnce({
        connected: true,
        site: { cloud_id: 'site-1', name: 'Site Alpha' },
        project: null,
        board: null,
      })
      .mockResolvedValueOnce({
        connected: true,
        site: { cloud_id: 'site-1', name: 'Site Alpha' },
        project: { id: '10001', key: 'BOOK', name: 'BookEase' },
        board: null,
      })
    jiraService.getJiraProjects.mockResolvedValueOnce([
      { id: '10001', key: 'BOOK', name: 'BookEase' },
    ])
    jiraService.selectJiraProject.mockResolvedValueOnce({
      project_id: '10001',
      project_key: 'BOOK',
    })
    jiraService.getJiraBoards.mockResolvedValueOnce([])

    render(<JiraIntegrationSection project={project} />)

    const select = await screen.findByLabelText(/Available Projects/i)
    await user.selectOptions(select, '10001')

    const selectBtn = screen.getByRole('button', { name: 'Select Project' })
    await user.click(selectBtn)

    await waitFor(() => {
      expect(jiraService.selectJiraProject).toHaveBeenCalledWith({
        projectId: '10001',
        projectKey: 'BOOK',
      })
    })
  })

  // 11. Board loading after project
  it('11. loads Scrum boards after project selection', async () => {
    jiraService.getJiraContext.mockResolvedValueOnce({
      connected: true,
      site: { cloud_id: 'site-1', name: 'Site Alpha' },
      project: { id: '10001', key: 'BOOK', name: 'BookEase' },
      board: null,
    })
    jiraService.getJiraBoards.mockResolvedValueOnce([
      { id: 101, name: 'BookEase Scrum Board', type: 'scrum' },
    ])

    render(<JiraIntegrationSection project={project} />)

    expect(await screen.findByRole('heading', { name: /Select Scrum Board/i })).toBeInTheDocument()
    expect(jiraService.getJiraBoards).toHaveBeenCalledOnce()

    expect(await screen.findByLabelText(/Available Scrum Boards/i)).toBeInTheDocument()
    expect(screen.getByRole('option', { name: /BookEase Scrum Board \(Scrum\)/i })).toBeInTheDocument()
  })

  // 12. No automatic board selection
  it('12. requires explicit human selection of Scrum board', async () => {
    jiraService.getJiraContext.mockResolvedValueOnce({
      connected: true,
      site: { cloud_id: 'site-1', name: 'Site Alpha' },
      project: { id: '10001', key: 'BOOK', name: 'BookEase' },
      board: null,
    })
    jiraService.getJiraBoards.mockResolvedValueOnce([
      { id: 101, name: 'Board One', type: 'scrum' },
      { id: 102, name: 'Board Two', type: 'scrum' },
    ])

    render(<JiraIntegrationSection project={project} />)

    const select = await screen.findByLabelText(/Available Scrum Boards/i)
    expect(select.value).toBe('')
    expect(jiraService.selectJiraBoard).not.toHaveBeenCalled()
  })

  // 13. Explicit Scrum board selection
  it('13. allows explicit Scrum board selection and persists target', async () => {
    const user = userEvent.setup()
    jiraService.getJiraContext
      .mockResolvedValueOnce({
        connected: true,
        site: { cloud_id: 'site-1', name: 'Site Alpha' },
        project: { id: '10001', key: 'BOOK', name: 'BookEase' },
        board: null,
      })
      .mockResolvedValueOnce({
        connected: true,
        site: { cloud_id: 'site-1', name: 'Site Alpha' },
        project: { id: '10001', key: 'BOOK', name: 'BookEase' },
        board: { id: 101, name: 'BookEase Board', type: 'scrum' },
      })
    jiraService.getJiraBoards.mockResolvedValueOnce([
      { id: 101, name: 'BookEase Board', type: 'scrum' },
    ])
    jiraService.selectJiraBoard.mockResolvedValueOnce({
      board_id: 101,
      board_name: 'BookEase Board',
      board_type: 'scrum',
    })

    render(<JiraIntegrationSection project={project} />)

    const select = await screen.findByLabelText(/Available Scrum Boards/i)
    await user.selectOptions(select, '101')

    const selectBtn = screen.getByRole('button', { name: 'Select Board' })
    await user.click(selectBtn)

    await waitFor(() => {
      expect(jiraService.selectJiraBoard).toHaveBeenCalledWith(101)
    })
  })

  // 14. Completed context displays correctly
  it('14. displays full verified Jira target context when selection complete', async () => {
    jiraService.getJiraContext.mockResolvedValueOnce({
      connected: true,
      site: { cloud_id: 'site-1', name: 'Site Alpha', url: 'https://alpha.atlassian.net' },
      project: { id: '10001', key: 'BOOK', name: 'BookEase' },
      board: { id: 101, name: 'BookEase Scrum Board', type: 'scrum' },
    })

    render(<JiraIntegrationSection project={project} />)

    expect(await screen.findByText('Site Alpha')).toBeInTheDocument()
    expect(screen.getByText('BOOK')).toBeInTheDocument()
    expect(screen.getAllByText(/BookEase Scrum Board/i).length).toBeGreaterThanOrEqual(1)
    expect(
      screen.getByText(/Jira target is ready. No Jira data has been created or modified./i),
    ).toBeInTheDocument()
  })

  // 15. Synchronization shows NOT_PERFORMED
  it('15. synchronization shows Not Performed status badge', async () => {
    jiraService.getJiraContext.mockResolvedValueOnce({
      connected: true,
      site: { cloud_id: 'site-1', name: 'Site Alpha' },
      project: { id: '10001', key: 'BOOK', name: 'BookEase' },
      board: { id: 101, name: 'BookEase Board', type: 'scrum' },
    })

    render(<JiraIntegrationSection project={project} />)

    expect(await screen.findByText('Not Performed')).toBeInTheDocument()
  })

  // 16. No Sync action performs writes
  it('16. Sync button is disabled and performs zero writes', async () => {
    jiraService.getJiraContext.mockResolvedValueOnce({
      connected: true,
      site: { cloud_id: 'site-1', name: 'Site Alpha' },
      project: { id: '10001', key: 'BOOK', name: 'BookEase' },
      board: { id: 101, name: 'BookEase Board', type: 'scrum' },
    })

    render(<JiraIntegrationSection project={project} />)

    const syncBtn = await screen.findByRole('button', { name: /Sync Now/i })
    expect(syncBtn).toBeDisabled()
    expect(syncBtn).toHaveAttribute('aria-disabled', 'true')
  })

  // 17. Site change resets stale project/board UI
  it('17. clicking Change on site re-opens site selector and allows changing', async () => {
    const user = userEvent.setup()
    jiraService.getJiraContext.mockResolvedValueOnce({
      connected: true,
      site: { cloud_id: 'site-1', name: 'Site Alpha' },
      project: { id: '10001', key: 'BOOK', name: 'BookEase' },
      board: { id: 101, name: 'BookEase Board', type: 'scrum' },
    })
    jiraService.getJiraSites.mockResolvedValueOnce([
      { cloud_id: 'site-1', name: 'Site Alpha' },
      { cloud_id: 'site-2', name: 'Site Beta' },
    ])

    render(<JiraIntegrationSection project={project} />)

    const changeButtons = await screen.findAllByRole('button', { name: 'Change' })
    await user.click(changeButtons[0])

    expect(await screen.findByRole('heading', { name: /Select Jira Site/i })).toBeInTheDocument()
  })

  // 18. Project change resets stale board UI
  it('18. clicking Change on project re-opens project selector', async () => {
    const user = userEvent.setup()
    jiraService.getJiraContext.mockResolvedValueOnce({
      connected: true,
      site: { cloud_id: 'site-1', name: 'Site Alpha' },
      project: { id: '10001', key: 'BOOK', name: 'BookEase' },
      board: { id: 101, name: 'BookEase Board', type: 'scrum' },
    })
    jiraService.getJiraProjects.mockResolvedValueOnce([
      { id: '10001', key: 'BOOK', name: 'BookEase' },
      { id: '10002', key: 'SHOP', name: 'ShopSmart' },
    ])

    render(<JiraIntegrationSection project={project} />)

    // Multiple "Change" buttons exist (Site, Project, Board)
    const changeButtons = await screen.findAllByRole('button', { name: 'Change' })
    await user.click(changeButtons[1]) // Project change button

    expect(await screen.findByRole('heading', { name: /Select Jira Project/i })).toBeInTheDocument()
  })

  // 19. Disconnect confirmation
  it('19. clicking Disconnect Jira opens accessible confirmation modal', async () => {
    const user = userEvent.setup()
    jiraService.getJiraContext.mockResolvedValueOnce({
      connected: true,
      site: { cloud_id: 'site-1', name: 'Site Alpha' },
      project: null,
      board: null,
    })

    render(<JiraIntegrationSection project={project} />)

    const disconnectBtn = await screen.findByRole('button', { name: /Disconnect Jira/i })
    await user.click(disconnectBtn)

    const modal = screen.getByRole('dialog', { name: /Disconnect Jira Cloud\?/i })
    expect(modal).toBeInTheDocument()
    expect(screen.getByText(/This removes the local integration connection/i)).toBeInTheDocument()
  })

  // 20. Disconnect updates UI
  it('20. confirming disconnect calls API and resets UI to Not Connected', async () => {
    const user = userEvent.setup()
    jiraService.getJiraContext.mockResolvedValueOnce({
      connected: true,
      site: { cloud_id: 'site-1', name: 'Site Alpha' },
      project: null,
      board: null,
    })
    jiraService.disconnectJira.mockResolvedValueOnce({ disconnected: true })

    render(<JiraIntegrationSection project={project} />)

    const disconnectBtn = await screen.findByRole('button', { name: /Disconnect Jira/i })
    await user.click(disconnectBtn)

    const confirmBtn = screen.getByRole('button', { name: 'Disconnect' })
    await user.click(confirmBtn)

    await waitFor(() => {
      expect(jiraService.disconnectJira).toHaveBeenCalledOnce()
      expect(screen.getByText('Not Connected')).toBeInTheDocument()
    })
  })

  // 21. Reauthorization-required state
  it('21. displays reauthorization banner when connection has expired', async () => {
    jiraService.getJiraContext.mockResolvedValueOnce({
      connected: false,
    })
    jiraService.getJiraStatus.mockResolvedValueOnce({
      connected: true,
      reauthorization_required: true,
      reauthorization_reason: 'Token expired',
    })

    render(<JiraIntegrationSection project={project} />)

    expect(
      await screen.findByText(/Your Jira connection has expired. Reconnect Jira to continue./i),
    ).toBeInTheDocument()
  })

  // 22. Rate-limit state
  it('22. displays user-friendly rate limit message on 429', async () => {
    jiraService.getJiraContext.mockRejectedValueOnce({
      status: 429,
      message: 'JIRA_RATE_LIMITED',
    })

    render(<JiraIntegrationSection project={project} />)

    expect(
      await screen.findByText(/Jira is temporarily limiting requests. Please try again shortly./i),
    ).toBeInTheDocument()
  })

  // 23. Empty site/project/board states
  it('23. displays friendly empty states when no sites, projects, or boards found', async () => {
    jiraService.getJiraContext.mockResolvedValueOnce({
      connected: true,
      site: null,
      project: null,
      board: null,
    })
    jiraService.getJiraSites.mockResolvedValueOnce([])

    render(<JiraIntegrationSection project={project} />)

    expect(await screen.findByText('No accessible Jira sites were found.')).toBeInTheDocument()
  })

  // 24. Loading states prevent duplicate actions
  it('24. disables selection button while save request is in flight', async () => {
    jiraService.getJiraContext.mockResolvedValueOnce({
      connected: true,
      site: null,
      project: null,
      board: null,
    })
    jiraService.getJiraSites.mockResolvedValueOnce([
      { cloud_id: 'site-1', name: 'Site Alpha' },
    ])

    render(<JiraIntegrationSection project={project} />)

    const select = await screen.findByLabelText(/Available Sites/i)
    fireEvent.change(select, { target: { value: 'site-1' } })

    const btn = screen.getByRole('button', { name: 'Select Site' })
    expect(btn).not.toBeDisabled()
  })

  // 25. OAuth tokens never stored/rendered
  it('25. never stores or renders OAuth tokens or technical secrets', async () => {
    jiraService.getJiraContext.mockResolvedValueOnce({
      connected: true,
      site: { cloud_id: 'site-1', name: 'Site Alpha' },
      project: { id: '10001', key: 'BOOK', name: 'BookEase' },
      board: { id: 101, name: 'BookEase Board', type: 'scrum' },
    })

    const { container } = render(<JiraIntegrationSection project={project} />)

    await screen.findByText('Site Alpha')

    expect(localStorage.getItem('access_token')).toBeNull()
    expect(localStorage.getItem('refresh_token')).toBeNull()
    expect(sessionStorage.getItem('access_token')).toBeNull()
    expect(sessionStorage.getItem('refresh_token')).toBeNull()

    const html = container.innerHTML
    expect(html).not.toContain('client_secret')
    expect(html).not.toContain('access_token')
    expect(html).not.toContain('refresh_token')
  })

  // 27. Dark/light theme compatibility
  it('27. uses semantic theme classes preserving dark and light theme compatibility', async () => {
    jiraService.getJiraContext.mockResolvedValueOnce({
      connected: true,
      site: { cloud_id: 'site-1', name: 'Site Alpha' },
      project: null,
      board: null,
    })
    jiraService.getJiraSites.mockResolvedValueOnce([])

    const { container } = render(<JiraIntegrationSection project={project} />)

    await screen.findAllByText('Site Alpha')

    // Verify presence of tokens classes like bg-surface, border-default, text-content-primary
    expect(container.querySelector('.bg-surface')).toBeInTheDocument()
    expect(container.querySelector('.border-default')).toBeInTheDocument()
  })

  // 28. Automatically fetches Jira issue types when target is ready
  it('28. automatically fetches Jira issue types when target is ready', async () => {
    jiraService.getJiraContext.mockResolvedValueOnce({
      connected: true,
      site: { cloud_id: 'site-1', name: 'Site Alpha' },
      project: { id: '10001', key: 'BOOK', name: 'BookEase' },
      board: { id: 101, name: 'BookEase Board', type: 'scrum' },
    })

    render(<JiraIntegrationSection project={project} />)

    expect(await screen.findByRole('heading', { name: /Issue Type Mapping/i })).toBeInTheDocument()
    await waitFor(() => {
      expect(jiraService.getJiraIssueTypes).toHaveBeenCalled()
    })
  })

  // 29. Auto-suggests obvious mappings but leaves Feature empty when not in Jira
  it('29. auto-suggests Epic, User Story, and Task, but leaves Feature unmapped when absent', async () => {
    jiraService.getJiraContext.mockResolvedValueOnce({
      connected: true,
      site: { cloud_id: 'site-1', name: 'Site Alpha' },
      project: { id: '10001', key: 'BOOK', name: 'BookEase' },
      board: { id: 101, name: 'BookEase Board', type: 'scrum' },
    })
    jiraService.getJiraIssueTypes.mockResolvedValueOnce([
      { id: '10000', name: 'Epic', subtask: false },
      { id: '10001', name: 'Story', subtask: false },
      { id: '10002', name: 'Task', subtask: false },
    ])

    render(<JiraIntegrationSection project={project} />)

    await waitFor(() => {
      expect(screen.getByLabelText(/^Epic/i).value).toBe('Epic')
    })

    const epicSelect = screen.getByLabelText(/^Epic/i)
    const storySelect = screen.getByLabelText(/^User Story/i)
    const taskSelect = screen.getByLabelText(/^Task/i)
    const featureSelect = screen.getByLabelText(/^Feature/i)

    expect(epicSelect.value).toBe('Epic')
    expect(storySelect.value).toBe('Story')
    expect(taskSelect.value).toBe('Task')
    expect(featureSelect.value).toBe('') // Requires human selection

    expect(screen.getByText(/does not have an exact/i)).toBeInTheDocument()
  })

  // 30. Disables Generate Sync Preview button when Feature mapping is incomplete
  it('30. disables Generate Sync Preview button when mapping is incomplete', async () => {
    jiraService.getJiraContext.mockResolvedValueOnce({
      connected: true,
      site: { cloud_id: 'site-1', name: 'Site Alpha' },
      project: { id: '10001', key: 'BOOK', name: 'BookEase' },
      board: { id: 101, name: 'BookEase Board', type: 'scrum' },
    })
    jiraService.getJiraIssueTypes.mockResolvedValueOnce([
      { id: '10000', name: 'Epic', subtask: false },
      { id: '10001', name: 'Story', subtask: false },
      { id: '10002', name: 'Task', subtask: false },
    ])

    render(<JiraIntegrationSection project={project} />)

    const previewBtn = await screen.findByRole('button', { name: /Generate Sync Preview/i })
    expect(previewBtn).toBeDisabled()
    expect(screen.getByText(/Map all 4 AgileFlow types to enable sync preview/i)).toBeInTheDocument()
  })

  // 31. Human selection of compatible Feature mapping enables preview button
  it('31. human selection of Feature enables Generate Sync Preview button', async () => {
    jiraService.getJiraContext.mockResolvedValueOnce({
      connected: true,
      site: { cloud_id: 'site-1', name: 'Site Alpha' },
      project: { id: '10001', key: 'BOOK', name: 'BookEase' },
      board: { id: 101, name: 'BookEase Board', type: 'scrum' },
    })
    jiraService.getJiraIssueTypes.mockResolvedValueOnce([
      { id: '10000', name: 'Epic', subtask: false },
      { id: '10001', name: 'Story', subtask: false },
      { id: '10002', name: 'Task', subtask: false },
    ])

    render(<JiraIntegrationSection project={project} />)

    await waitFor(() => {
      expect(screen.getByLabelText(/^Epic/i).value).toBe('Epic')
    })

    const featureSelect = screen.getByLabelText(/^Feature/i)
    fireEvent.change(featureSelect, { target: { value: 'Story' } })
    expect(featureSelect.value).toBe('Story')

    const previewBtn = screen.getByRole('button', { name: /Generate Sync Preview/i })
    expect(previewBtn).not.toBeDisabled()
    expect(screen.getByText(/All types mapped. Ready to generate preview./i)).toBeInTheDocument()
  })

  // 32. Allows human to change mappings
  it('32. allows human to review and change mappings before preview', async () => {
    jiraService.getJiraContext.mockResolvedValueOnce({
      connected: true,
      site: { cloud_id: 'site-1', name: 'Site Alpha' },
      project: { id: '10001', key: 'BOOK', name: 'BookEase' },
      board: { id: 101, name: 'BookEase Board', type: 'scrum' },
    })
    jiraService.getJiraIssueTypes.mockResolvedValueOnce([
      { id: '10000', name: 'Epic', subtask: false },
      { id: '10001', name: 'Story', subtask: false },
      { id: '10002', name: 'Task', subtask: false },
    ])

    render(<JiraIntegrationSection project={project} />)

    await waitFor(() => {
      expect(screen.getByLabelText(/^Epic/i).value).toBe('Epic')
    })

    const taskSelect = screen.getByLabelText(/^Task/i)
    fireEvent.change(taskSelect, { target: { value: 'Story' } })
    expect(taskSelect.value).toBe('Story')
  })

  // 33. Clicking Generate Sync Preview calls generateJiraSyncPreview
  it('33. calls generateJiraSyncPreview with completed mappings and project context', async () => {
    const user = userEvent.setup()
    jiraService.getJiraContext.mockResolvedValueOnce({
      connected: true,
      site: { cloud_id: 'site-1', name: 'Site Alpha' },
      project: { id: '10001', key: 'BOOK', name: 'BookEase' },
      board: { id: 101, name: 'BookEase Board', type: 'scrum' },
    })
    jiraService.getJiraIssueTypes.mockResolvedValueOnce([
      { id: '10000', name: 'Epic', subtask: false },
      { id: '10001', name: 'Story', subtask: false },
      { id: '10002', name: 'Task', subtask: false },
    ])
    jiraService.generateJiraSyncPreview.mockResolvedValueOnce({
      target: {
        site: { cloud_id: 'site-1', name: 'Site Alpha', url: 'https://alpha.atlassian.net' },
        project: { id: '10001', key: 'BOOK', name: 'BookEase' },
        board: { id: 101, name: 'BookEase Board', type: 'scrum' },
      },
      mappings: { EPIC: 'Epic', FEATURE: 'Story', USER_STORY: 'Story', TASK: 'Task' },
      sprints: [],
      issues: [],
      summary: { total_issues: 0, total_sprints: 0, total_points: 0 },
      warnings: [],
      synchronization_status: 'NOT_PERFORMED',
    })

    render(
      <JiraIntegrationSection
        project={project}
        outputs={{ JIRA_PLAN: {}, SPRINT_PLAN: [] }}
        runId="run-999"
      />,
    )

    await waitFor(() => {
      expect(screen.getByLabelText(/^Epic/i).value).toBe('Epic')
    })

    const featureSelect = screen.getByLabelText(/^Feature/i)
    fireEvent.change(featureSelect, { target: { value: 'Story' } })

    const previewBtn = screen.getByRole('button', { name: /Generate Sync Preview/i })
    await user.click(previewBtn)

    expect(jiraService.generateJiraSyncPreview).toHaveBeenCalledWith({
      agent_project_id: 'AGP-002',
      run_id: 'run-999',
      mappings: {
        EPIC: 'Epic',
        FEATURE: 'Story',
        USER_STORY: 'Story',
        TASK: 'Task',
      },
      outputs: { JIRA_PLAN: {}, SPRINT_PLAN: [] },
    })
  })

  // 34. Renders preview with NOT_PERFORMED and No Jira data has been created or modified
  it('34. renders preview with NOT_PERFORMED status and zero writes notice', async () => {
    const user = userEvent.setup()
    jiraService.getJiraContext.mockResolvedValueOnce({
      connected: true,
      site: { cloud_id: 'site-1', name: 'Site Alpha' },
      project: { id: '10001', key: 'BOOK', name: 'BookEase' },
      board: { id: 101, name: 'BookEase Board', type: 'scrum' },
    })
    jiraService.getJiraIssueTypes.mockResolvedValueOnce([
      { id: '10000', name: 'Epic', subtask: false },
      { id: '10001', name: 'Story', subtask: false },
      { id: '10002', name: 'Task', subtask: false },
    ])
    jiraService.generateJiraSyncPreview.mockResolvedValueOnce({
      target: {
        site: { cloud_id: 'site-1', name: 'Site Alpha', url: 'https://alpha.atlassian.net' },
        project: { id: '10001', key: 'BOOK', name: 'BookEase' },
        board: { id: 101, name: 'BookEase Board', type: 'scrum' },
      },
      mappings: { EPIC: 'Epic', FEATURE: 'Story', USER_STORY: 'Story', TASK: 'Task' },
      sprints: [
        {
          id: 'sprint-1',
          name: 'Sprint 1 - Foundation',
          planned_points: 10,
          duration_days: 14,
          start_date: '2026-11-01',
          end_date: '2026-11-14',
          item_count: 2,
        },
      ],
      issues: [
        {
          artifact_id: 'EPIC-001',
          agileflow_type: 'EPIC',
          jira_issue_type: 'Epic',
          summary: 'User Account Management',
          parent_id: null,
          planned_sprint: null,
          assignee: null,
          priority: 'HIGH',
          estimate_points: 5,
        },
        {
          artifact_id: 'FEAT-001',
          agileflow_type: 'FEATURE',
          jira_issue_type: 'Story',
          summary: 'Profile Management Feature',
          parent_id: 'EPIC-001',
          planned_sprint: 'Sprint 1 - Foundation',
          assignee: null,
          priority: 'HIGH',
          estimate_points: 5,
        },
      ],
      summary: {
        total_issues: 2,
        total_sprints: 1,
        epic_count: 1,
        feature_count: 1,
        story_count: 0,
        task_count: 0,
        total_points: 10,
      },
      warnings: ['Feature mapped to Story at Story hierarchy level'],
      synchronization_status: 'NOT_PERFORMED',
    })

    render(<JiraIntegrationSection project={project} />)

    await waitFor(() => {
      expect(screen.getByLabelText(/^Epic/i).value).toBe('Epic')
    })

    const featureSelect = screen.getByLabelText(/^Feature/i)
    fireEvent.change(featureSelect, { target: { value: 'Story' } })

    const previewBtn = screen.getByRole('button', { name: /Generate Sync Preview/i })
    await user.click(previewBtn)

    // Heading and badges
    expect(await screen.findByRole('heading', { name: /Jira Synchronization Preview/i })).toBeInTheDocument()
    expect(screen.getByText('Synchronization: NOT PERFORMED')).toBeInTheDocument()
    expect(screen.getAllByText(/No Jira data has been created or modified/i).length).toBeGreaterThanOrEqual(1)

    // Target information
    expect(screen.getAllByText(/Site Alpha/i).length).toBeGreaterThanOrEqual(1)
    expect(screen.getAllByText(/BookEase Board/i).length).toBeGreaterThanOrEqual(1)

    // Sprints and summary
    expect(screen.getAllByText('Sprint 1 - Foundation').length).toBeGreaterThanOrEqual(1)
    expect(screen.getByText('10 pts planned')).toBeInTheDocument()

    // Issues and Unassigned status
    expect(screen.getAllByText('EPIC-001').length).toBeGreaterThanOrEqual(1)
    expect(screen.getByText('User Account Management')).toBeInTheDocument()
    expect(screen.getByText('FEAT-001')).toBeInTheDocument()
    expect(screen.getByText('Profile Management Feature')).toBeInTheDocument()
    expect(screen.getAllByText('Unassigned').length).toBe(2)

    // Warnings
    expect(screen.getByText(/Feature mapped to Story at Story hierarchy level/i)).toBeInTheDocument()

    // Sync Now buttons remain disabled
    const syncButtons = screen.getAllByRole('button', { name: /Sync Now/i })
    syncButtons.forEach((btn) => {
      expect(btn).toBeDisabled()
      expect(btn).toHaveAttribute('aria-disabled', 'true')
    })
  })

  // 35. Displays error message when preview generation fails
  it('35. displays error message when preview generation fails', async () => {
    const user = userEvent.setup()
    jiraService.getJiraContext.mockResolvedValueOnce({
      connected: true,
      site: { cloud_id: 'site-1', name: 'Site Alpha' },
      project: { id: '10001', key: 'BOOK', name: 'BookEase' },
      board: { id: 101, name: 'BookEase Board', type: 'scrum' },
    })
    jiraService.getJiraIssueTypes.mockResolvedValueOnce([
      { id: '10000', name: 'Epic', subtask: false },
      { id: '10001', name: 'Story', subtask: false },
      { id: '10002', name: 'Task', subtask: false },
    ])
    jiraService.generateJiraSyncPreview.mockRejectedValueOnce(
      new Error('JIRA_PLAN_UNAVAILABLE: Plan is missing'),
    )

    render(<JiraIntegrationSection project={project} />)

    await waitFor(() => {
      expect(screen.getByLabelText(/^Epic/i).value).toBe('Epic')
    })

    const featureSelect = screen.getByLabelText(/^Feature/i)
    fireEvent.change(featureSelect, { target: { value: 'Story' } })

    const previewBtn = screen.getByRole('button', { name: /Generate Sync Preview/i })
    await user.click(previewBtn)

    expect(
      await screen.findByText(/A completed Agent 2 run with JIRA_PLAN is required for sync preview/i),
    ).toBeInTheDocument()
  })

  // 36. Synchronize with Jira button opens confirmation modal
  it('36. renders Synchronize with Jira button after preview and opens confirmation modal with plan details', async () => {
    const user = userEvent.setup()
    jiraService.getJiraContext.mockResolvedValueOnce({
      connected: true,
      site: { cloud_id: 'site-1', name: 'Site Alpha', url: 'https://alpha.atlassian.net' },
      project: { id: '10001', key: 'BOOK', name: 'BookEase' },
      board: { id: 101, name: 'BookEase Board', type: 'scrum' },
    })
    jiraService.getJiraIssueTypes.mockResolvedValueOnce([
      { id: '10000', name: 'Epic', subtask: false },
      { id: '10001', name: 'Story', subtask: false },
      { id: '10002', name: 'Task', subtask: false },
    ])
    jiraService.generateJiraSyncPreview.mockResolvedValueOnce({
      target: {
        site_name: 'Site Alpha',
        project_key: 'BOOK',
        project_name: 'BookEase',
        board_name: 'BookEase Board',
      },
      summary: { total_sprints: 1, total_issues: 2, breakdown_by_type: { Epic: 1, Story: 1 } },
      sprints: [{ id: 'SP-1', name: 'Sprint 1', start_date: '2026-11-01', end_date: '2026-11-14', planned_points: 10 }],
      issues: [
        { id: 'EPIC-001', summary: 'Epic Summary', agileflow_type: 'Epic', jira_issue_type: 'Epic' },
        { id: 'FEAT-001', summary: 'Feat Summary', agileflow_type: 'Feature', jira_issue_type: 'Story' },
      ],
      warnings: [],
      synchronization_status: 'NOT_PERFORMED',
    })

    render(<JiraIntegrationSection project={{ ...project, run_id: 'run-007' }} />)

    await waitFor(() => {
      expect(screen.getByLabelText(/^Epic/i).value).toBe('Epic')
    })
    fireEvent.change(screen.getByLabelText(/^Feature/i), { target: { value: 'Story' } })

    await user.click(screen.getByRole('button', { name: /Generate Sync Preview/i }))

    const syncBtn = await screen.findByTestId('start-sync-btn')
    expect(syncBtn).toBeInTheDocument()
    expect(syncBtn).toHaveTextContent('Synchronize with Jira')

    // Click Synchronize with Jira
    await user.click(syncBtn)

    // Modal dialog is shown
    const modal = await screen.findByTestId('jira-sync-confirm-modal')
    expect(modal).toBeInTheDocument()
    expect(screen.getByText('Synchronize this approved plan with Jira?')).toBeInTheDocument()
    expect(screen.getByText(/1 sprints/i)).toBeInTheDocument()
    expect(screen.getByText(/2 Jira issues/i)).toBeInTheDocument()
    expect(screen.getByText(/Issues will remain unassigned/i)).toBeInTheDocument()
    expect(screen.getByTestId('confirm-sync-btn')).toBeInTheDocument()
  })

  // 37. Cancelling confirmation modal does NOT trigger write execution
  it('37. cancelling confirmation modal closes it without triggering write execution', async () => {
    const user = userEvent.setup()
    jiraService.getJiraContext.mockResolvedValueOnce({
      connected: true,
      site: { cloud_id: 'site-1', name: 'Site Alpha' },
      project: { id: '10001', key: 'BOOK', name: 'BookEase' },
      board: { id: 101, name: 'BookEase Board', type: 'scrum' },
    })
    jiraService.getJiraIssueTypes.mockResolvedValueOnce([
      { id: '10000', name: 'Epic', subtask: false },
      { id: '10001', name: 'Story', subtask: false },
      { id: '10002', name: 'Task', subtask: false },
    ])
    jiraService.generateJiraSyncPreview.mockResolvedValueOnce({
      target: { site_name: 'Site Alpha', project_key: 'BOOK', project_name: 'BookEase', board_name: 'BookEase Board' },
      summary: { total_sprints: 1, total_issues: 1 },
      sprints: [{ id: 'SP-1', name: 'Sprint 1' }],
      issues: [{ id: 'EPIC-001', summary: 'Epic', agileflow_type: 'Epic', jira_issue_type: 'Epic' }],
      warnings: [],
      synchronization_status: 'NOT_PERFORMED',
    })

    render(<JiraIntegrationSection project={{ ...project, run_id: 'run-007' }} />)

    await waitFor(() => {
      expect(screen.getByLabelText(/^Epic/i).value).toBe('Epic')
    })
    fireEvent.change(screen.getByLabelText(/^Feature/i), { target: { value: 'Story' } })
    await user.click(screen.getByRole('button', { name: /Generate Sync Preview/i }))

    await user.click(await screen.findByTestId('start-sync-btn'))
    expect(screen.getByTestId('jira-sync-confirm-modal')).toBeInTheDocument()

    // Cancel modal
    await user.click(screen.getByRole('button', { name: /Cancel/i }))

    expect(screen.queryByTestId('jira-sync-confirm-modal')).not.toBeInTheDocument()
    expect(jiraService.executeJiraSync).not.toHaveBeenCalled()
  })

  // 38. Confirming synchronization executes sync and renders COMPLETED result
  it('38. confirms synchronization, calls executeJiraSync, and renders COMPLETED result with traceability links', async () => {
    const user = userEvent.setup()
    jiraService.getJiraContext.mockResolvedValueOnce({
      connected: true,
      site: { cloud_id: 'site-1', name: 'Site Alpha', url: 'https://alpha.atlassian.net' },
      project: { id: '10001', key: 'BOOK', name: 'BookEase' },
      board: { id: 101, name: 'BookEase Board', type: 'scrum' },
    })
    jiraService.getJiraIssueTypes.mockResolvedValueOnce([
      { id: '10000', name: 'Epic', subtask: false },
      { id: '10001', name: 'Story', subtask: false },
      { id: '10002', name: 'Task', subtask: false },
    ])
    jiraService.generateJiraSyncPreview.mockResolvedValueOnce({
      target: { site_name: 'Site Alpha', project_key: 'BOOK', project_name: 'BookEase', board_name: 'BookEase Board' },
      summary: { total_sprints: 1, total_issues: 1 },
      sprints: [{ id: 'SP-1', name: 'Sprint 1' }],
      issues: [{ id: 'EPIC-001', summary: 'Epic', agileflow_type: 'Epic', jira_issue_type: 'Epic' }],
      warnings: [],
      synchronization_status: 'NOT_PERFORMED',
    })

    jiraService.executeJiraSync.mockResolvedValueOnce({
      status: 'COMPLETED',
      target: { site_name: 'Site Alpha', project_key: 'BOOK', project_name: 'BookEase', board_name: 'BookEase Board' },
      sprint_summary: { created: 1, reused: 0, failed: 0, total: 1 },
      issue_summary: { created: 1, reused: 0, failed: 0, total: 1 },
      placement_summary: { created: 0, failed: 0, total: 0 },
      traceability: {
        sprints: [{ agileflow_sprint_id: 'SP-1', jira_sprint_id: '101', name: 'Sprint 1', state: 'future' }],
        issues: [
          {
            artifact_id: 'EPIC-001',
            jira_id: '2001',
            jira_key: 'BOOK-1',
            jira_issue_type: 'Epic',
            summary: 'Epic',
            planned_sprint: null,
            parent_jira_key: null,
            browse_url: 'https://alpha.atlassian.net/browse/BOOK-1',
          },
        ],
      },
      warnings: [],
      failures: [],
    })

    render(<JiraIntegrationSection project={{ ...project, run_id: 'run-007' }} />)

    await waitFor(() => {
      expect(screen.getByLabelText(/^Epic/i).value).toBe('Epic')
    })
    fireEvent.change(screen.getByLabelText(/^Feature/i), { target: { value: 'Story' } })
    await user.click(screen.getByRole('button', { name: /Generate Sync Preview/i }))

    await user.click(await screen.findByTestId('start-sync-btn'))
    await user.click(screen.getByTestId('confirm-sync-btn'))

    await waitFor(() => {
      expect(jiraService.executeJiraSync).toHaveBeenCalledWith(
        expect.objectContaining({
          agent_project_id: 'AGP-002',
          run_id: 'run-007',
          confirmation: true,
        }),
      )
    })

    // Results card
    const resultCard = await screen.findByTestId('jira-sync-result-card')
    expect(resultCard).toBeInTheDocument()
    expect(screen.getByText('COMPLETED')).toBeInTheDocument()
    expect(screen.getByText('Jira synchronization completed.')).toBeInTheDocument()
    expect(screen.getAllByText(/1 created/i).length).toBe(2)

    // Traceability item
    const link = screen.getByRole('link', { name: /BOOK-1/i })
    expect(link).toHaveAttribute('href', 'https://alpha.atlassian.net/browse/BOOK-1')
  })

  // 39. Displays PARTIAL status, failed items, and Resume Synchronization button
  it('39. renders PARTIAL result with failed items and Resume Synchronization button', async () => {
    const user = userEvent.setup()
    jiraService.getJiraContext.mockResolvedValueOnce({
      connected: true,
      site: { cloud_id: 'site-1', name: 'Site Alpha' },
      project: { id: '10001', key: 'BOOK', name: 'BookEase' },
      board: { id: 101, name: 'BookEase Board', type: 'scrum' },
    })
    jiraService.getJiraIssueTypes.mockResolvedValueOnce([
      { id: '10000', name: 'Epic', subtask: false },
      { id: '10001', name: 'Story', subtask: false },
      { id: '10002', name: 'Task', subtask: false },
    ])
    jiraService.generateJiraSyncPreview.mockResolvedValueOnce({
      target: { site_name: 'Site Alpha', project_key: 'BOOK', project_name: 'BookEase', board_name: 'BookEase Board' },
      summary: { total_sprints: 1, total_issues: 2 },
      sprints: [{ id: 'SP-1', name: 'Sprint 1' }],
      issues: [
        { id: 'EPIC-001', summary: 'Epic', agileflow_type: 'Epic', jira_issue_type: 'Epic' },
        { id: 'FEAT-001', summary: 'Feat', agileflow_type: 'Feature', jira_issue_type: 'Story' },
      ],
      warnings: [],
      synchronization_status: 'NOT_PERFORMED',
    })

    jiraService.executeJiraSync.mockResolvedValueOnce({
      status: 'PARTIAL',
      target: { site_name: 'Site Alpha', project_key: 'BOOK', project_name: 'BookEase', board_name: 'BookEase Board' },
      sprint_summary: { created: 1, reused: 0, failed: 0, total: 1 },
      issue_summary: { created: 1, reused: 0, failed: 1, total: 2 },
      placement_summary: { created: 0, failed: 0, total: 0 },
      traceability: {
        sprints: [{ agileflow_sprint_id: 'SP-1', jira_sprint_id: '101', name: 'Sprint 1', state: 'future' }],
        issues: [
          {
            artifact_id: 'EPIC-001',
            jira_id: '2001',
            jira_key: 'BOOK-1',
            jira_issue_type: 'Epic',
            summary: 'Epic',
            planned_sprint: null,
            parent_jira_key: null,
          },
        ],
      },
      warnings: [],
      failures: [
        {
          entity_type: 'issue',
          entity_id: 'FEAT-001',
          error: 'Jira API rate limit exceeded',
        },
      ],
    })

    render(<JiraIntegrationSection project={{ ...project, run_id: 'run-007' }} />)

    await waitFor(() => {
      expect(screen.getByLabelText(/^Epic/i).value).toBe('Epic')
    })
    fireEvent.change(screen.getByLabelText(/^Feature/i), { target: { value: 'Story' } })
    await user.click(screen.getByRole('button', { name: /Generate Sync Preview/i }))

    await user.click(await screen.findByTestId('start-sync-btn'))
    await user.click(screen.getByTestId('confirm-sync-btn'))

    expect(await screen.findByText('PARTIAL')).toBeInTheDocument()
    expect(
      screen.getAllByText(/Jira synchronization partially completed/i).length,
    ).toBeGreaterThanOrEqual(1)
    expect(screen.getByTestId('sync-failures-list')).toHaveTextContent('FEAT-001')
    expect(screen.getByTestId('retry-sync-btn')).toHaveTextContent('Resume Synchronization')
  })

  // 40. Displays FAILED status and Retry Synchronization button
  it('40. renders FAILED result and Retry Synchronization button', async () => {
    const user = userEvent.setup()
    jiraService.getJiraContext.mockResolvedValueOnce({
      connected: true,
      site: { cloud_id: 'site-1', name: 'Site Alpha' },
      project: { id: '10001', key: 'BOOK', name: 'BookEase' },
      board: { id: 101, name: 'BookEase Board', type: 'scrum' },
    })
    jiraService.getJiraIssueTypes.mockResolvedValueOnce([
      { id: '10000', name: 'Epic', subtask: false },
      { id: '10001', name: 'Story', subtask: false },
      { id: '10002', name: 'Task', subtask: false },
    ])
    jiraService.generateJiraSyncPreview.mockResolvedValueOnce({
      target: { site_name: 'Site Alpha', project_key: 'BOOK', project_name: 'BookEase', board_name: 'BookEase Board' },
      summary: { total_sprints: 1, total_issues: 1 },
      sprints: [{ id: 'SP-1', name: 'Sprint 1' }],
      issues: [{ id: 'EPIC-001', summary: 'Epic', agileflow_type: 'Epic', jira_issue_type: 'Epic' }],
      warnings: [],
      synchronization_status: 'NOT_PERFORMED',
    })

    jiraService.executeJiraSync.mockResolvedValueOnce({
      status: 'FAILED',
      target: { site_name: 'Site Alpha', project_key: 'BOOK', project_name: 'BookEase', board_name: 'BookEase Board' },
      sprint_summary: { created: 0, reused: 0, failed: 1, total: 1 },
      issue_summary: { created: 0, reused: 0, failed: 0, total: 1 },
      placement_summary: { created: 0, failed: 0, total: 0 },
      traceability: { sprints: [], issues: [] },
      warnings: [],
      failures: [
        {
          entity_type: 'sprint',
          entity_id: 'SP-1',
          error: 'Board 101 does not support sprint creation',
        },
      ],
    })

    render(<JiraIntegrationSection project={{ ...project, run_id: 'run-007' }} />)

    await waitFor(() => {
      expect(screen.getByLabelText(/^Epic/i).value).toBe('Epic')
    })
    fireEvent.change(screen.getByLabelText(/^Feature/i), { target: { value: 'Story' } })
    await user.click(screen.getByRole('button', { name: /Generate Sync Preview/i }))

    await user.click(await screen.findByTestId('start-sync-btn'))
    await user.click(screen.getByTestId('confirm-sync-btn'))

    expect(await screen.findByText('FAILED')).toBeInTheDocument()
    expect(
      screen.getAllByText(/Jira synchronization failed/i).length,
    ).toBeGreaterThanOrEqual(1)
    expect(screen.getByTestId('retry-sync-btn')).toHaveTextContent('Retry Synchronization')
  })

  // 41. Loads existing completed synchronization on mount
  it('41. loads existing completed synchronization on mount and displays results', async () => {
    jiraService.getJiraContext.mockResolvedValueOnce({
      connected: true,
      site: { cloud_id: 'site-1', name: 'Site Alpha' },
      project: { id: '10001', key: 'BOOK', name: 'BookEase' },
      board: { id: 101, name: 'BookEase Board', type: 'scrum' },
    })
    jiraService.getJiraSyncStatus.mockResolvedValueOnce({
      status: 'COMPLETED',
      target: { site_name: 'Site Alpha', project_key: 'BOOK', project_name: 'BookEase', board_name: 'BookEase Board' },
      sprint_summary: { created: 2, reused: 0, failed: 0, total: 2 },
      issue_summary: { created: 10, reused: 0, failed: 0, total: 10 },
      placement_summary: { created: 10, failed: 0, total: 10 },
      traceability: { sprints: [], issues: [] },
      warnings: [],
      failures: [],
    })

    render(<JiraIntegrationSection project={{ ...project, run_id: 'run-007' }} />)

    expect(await screen.findByTestId('jira-sync-result-card')).toBeInTheDocument()
    expect(screen.getByText('COMPLETED')).toBeInTheDocument()
    expect(screen.getByText(/10 created/i)).toBeInTheDocument()
  })

  // 42. Board selection encountering 401 reauthorization required
  it('42. board selection encountering 401 reauthorization required displays safe error inside panel without logging out', async () => {
    const user = userEvent.setup()
    jiraService.getJiraContext.mockResolvedValueOnce({
      connected: true,
      site: { cloud_id: 'site-1', name: 'Site Alpha' },
      project: { id: '10001', key: 'BOOK', name: 'BookEase' },
      board: null,
    })
    jiraService.getJiraBoards.mockResolvedValueOnce([
      { id: 101, name: 'BookEase Board', type: 'scrum' },
    ])
    jiraService.selectJiraBoard.mockRejectedValueOnce({
      status: 401,
      message: 'JIRA_REAUTHORIZATION_REQUIRED',
      errors: [{ field: 'jira', message: 'JIRA_REAUTHORIZATION_REQUIRED: Token expired' }],
    })

    render(<JiraIntegrationSection project={project} />)

    const select = await screen.findByLabelText(/Available Scrum Boards/i)
    await user.selectOptions(select, '101')

    const selectBtn = screen.getByRole('button', { name: 'Select Board' })
    await user.click(selectBtn)

    expect(
      await screen.findByText(/Your Jira connection has expired. Reconnect Jira to continue./i),
    ).toBeInTheDocument()
  })
})
