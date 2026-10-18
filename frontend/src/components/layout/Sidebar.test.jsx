import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { getAgentProjects } from '../../services/agentProjectService.js'
import { getProjects } from '../../services/projectService.js'
import Sidebar from './Sidebar.jsx'

vi.mock('../../services/projectService.js', () => ({ getProjects: vi.fn() }))
vi.mock('../../services/agentProjectService.js', () => ({ getAgentProjects: vi.fn() }))

const projects = [
  { project_id: 'PRJ-001', name: 'Real Full Project', status: 'ACTIVE' },
]
const agentProjects = [
  { agent_project_id: 'AGP-101', agent_type: 'REQUIREMENTS', name: 'Requirements Alpha', status: 'ACTIVE' },
  { agent_project_id: 'AGP-201', agent_type: 'DESIGN_PLANNING', name: 'Design Alpha', status: 'ACTIVE' },
  { agent_project_id: 'AGP-301', agent_type: 'IMPLEMENTATION', name: 'Implementation Alpha', status: 'ACTIVE' },
  { agent_project_id: 'AGP-401', agent_type: 'TESTING_VALIDATION', name: 'Testing Alpha', status: 'ARCHIVED' },
]

function renderSidebar(path = '/agent-projects/AGP-301', props = {}) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Sidebar
        isOpen={false}
        isCollapsed={false}
        onClose={vi.fn()}
        onNavigate={vi.fn()}
        onToggleCollapse={vi.fn()}
        user={{ name: 'Ada Lovelace', email: 'ada@example.com' }}
        onLogout={vi.fn()}
        {...props}
      />
      <Routes>
        <Route path="/agent-projects/:agentProjectId" element={<p>Agent project route</p>} />
      </Routes>
    </MemoryRouter>,
  )
}

describe('global project sidebar', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    getProjects.mockResolvedValue({ data: projects })
    getAgentProjects.mockResolvedValue({ data: agentProjects })
  })

  it('renders exactly the project and standalone-agent information groups from real services', async () => {
    renderSidebar()
    expect(await screen.findByRole('heading', { name: 'Projects' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Standalone Agents' })).toBeInTheDocument()
    expect(getProjects).toHaveBeenCalledOnce()
    expect(getAgentProjects).toHaveBeenCalledWith()
    expect(screen.getByRole('link', { name: /Real Full Project/ })).toHaveAttribute('href', '/projects/PRJ-001')
    expect(screen.queryByText(/QuickBook|POS/i)).not.toBeInTheDocument()
  })

  it('renders all four expandable agents and groups projects by AgentType', async () => {
    const user = userEvent.setup()
    renderSidebar('/projects')
    await screen.findByRole('heading', { name: 'Standalone Agents' })

    const expected = [
      ['Agent 1 — Requirements & Analysis', 'Requirements Alpha'],
      ['Agent 2 — Design & Planning', 'Design Alpha'],
      ['Agent 3 — Implementation', 'Implementation Alpha'],
      ['Agent 4 — Testing & Validation', 'Testing Alpha'],
    ]
    for (const [agentName, projectName] of expected) {
      const toggle = screen.getByRole('button', { name: agentName })
      expect(toggle).toHaveAttribute('aria-expanded', 'false')
      await user.click(toggle)
      expect(toggle).toHaveAttribute('aria-expanded', 'true')
      expect(screen.getByRole('link', { name: new RegExp(projectName) })).toBeInTheDocument()
      await user.click(toggle)
      expect(screen.queryByRole('link', { name: new RegExp(projectName) })).not.toBeInTheDocument()
    }
  })

  it('marks the selected standalone project and preserves project and create routes', async () => {
    renderSidebar()
    const selected = await screen.findByRole('link', { name: /Implementation Alpha/ })
    expect(selected).toHaveAttribute('aria-current', 'page')
    expect(selected).toHaveAttribute('href', '/agent-projects/AGP-301')
    expect(screen.getByRole('link', { name: '+ New Implementation Project' })).toHaveAttribute('href', '/agents/implementation/new')
    expect(screen.getByRole('link', { name: '+ New Requirements Project' })).toHaveAttribute('href', '/agents/requirements/new')
    expect(screen.getByRole('link', { name: '+ New Design Project' })).toHaveAttribute('href', '/agents/design-planning/new')
    expect(screen.getByRole('link', { name: '+ New Testing Project' })).toHaveAttribute('href', '/agents/testing-validation/new')
  })

  it('navigates through the existing standalone project route', async () => {
    const user = userEvent.setup()
    renderSidebar()
    await user.click(await screen.findByRole('link', { name: /Implementation Alpha/ }))
    expect(screen.getByText('Agent project route')).toBeInTheDocument()
  })

  it('preserves Agent 1, Agent 2, and Agent 4 project navigation', async () => {
    renderSidebar()

    expect(await screen.findByRole('link', { name: /Requirements Alpha/ })).toHaveAttribute('href', '/agent-projects/AGP-101')
    expect(screen.getByRole('link', { name: /Design Alpha/ })).toHaveAttribute('href', '/agent-projects/AGP-201')
    expect(screen.getByRole('link', { name: /Testing Alpha/ })).toHaveAttribute('href', '/agent-projects/AGP-401')
  })

  it('shows an honest full-project empty state and supports the existing mobile drawer', async () => {
    getProjects.mockResolvedValue({ data: [] })
    renderSidebar('/projects', { isOpen: true })
    const mobile = await screen.findByRole('complementary', { name: 'Mobile navigation' })
    expect(within(mobile).getByText('No full-workflow projects yet.')).toBeInTheDocument()
    await waitFor(() => expect(getAgentProjects).toHaveBeenCalledOnce())
  })
})
