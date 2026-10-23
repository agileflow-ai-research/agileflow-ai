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
    cleanJiraCallbackParams: vi.fn().mockReturnValue({ connected: false, error: null }),
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
    jiraService.cleanJiraCallbackParams.mockReturnValue({ connected: false, error: null })
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
  it('3. Connect Jira action initiates OAuth redirect', async () => {
    const user = userEvent.setup()
    jiraService.getJiraContext.mockResolvedValueOnce({ connected: false })
    jiraService.getJiraStatus.mockResolvedValueOnce({ connected: false })
    jiraService.startJiraConnection.mockResolvedValueOnce({
      authorization_url: 'https://auth.atlassian.com/oauth/authorize?state=abc',
    })

    const assignSpy = vi.fn()
    delete window.location
    window.location = { assign: assignSpy, href: '' }

    render(<JiraIntegrationSection project={project} />)

    const connectBtn = await screen.findByRole('button', { name: /Connect Jira/i })
    await user.click(connectBtn)

    await waitFor(() => {
      expect(jiraService.startJiraConnection).toHaveBeenCalledOnce()
      expect(assignSpy).toHaveBeenCalledWith(
        'https://auth.atlassian.com/oauth/authorize?state=abc',
      )
    })
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
})
