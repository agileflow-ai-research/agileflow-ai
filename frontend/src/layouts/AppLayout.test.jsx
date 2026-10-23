import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { MemoryRouter, Route, Routes } from 'react-router-dom'

import AppLayout from './AppLayout.jsx'
import CreateAgentProjectPage from '../pages/CreateAgentProjectPage.jsx'
import { createAgentProject, getAgentProjects } from '../services/agentProjectService.js'
import { getProjects } from '../services/projectService.js'

const logout = vi.fn()

vi.mock('../features/auth/useAuth.js', () => ({
  useAuth: () => ({
    user: {
      user_id: 'USR-001',
      name: 'Ada Lovelace',
      email: 'ada@example.com',
      is_active: true,
    },
    logout,
  }),
}))

vi.mock('../services/projectService.js', () => ({ getProjects: vi.fn() }))
vi.mock('../services/agentProjectService.js', () => ({
  createAgentProject: vi.fn(),
  getAgentProjects: vi.fn(),
}))

function renderLayout(path = '/projects') {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route element={<AppLayout />}>
          <Route path="/projects" element={<h1>Protected projects</h1>} />
          <Route path="/projects/new" element={<h1>Create project</h1>} />
          <Route path="/agents" element={<h1>AI agents</h1>} />
          <Route path="/agents/:agentSlug/new" element={<CreateAgentProjectPage />} />
          <Route path="/agents/:agentSlug" element={<h1>Agent projects</h1>} />
          <Route path="/agent-projects/:agentProjectId" element={<h1>Agent project</h1>} />
        </Route>
      </Routes>
    </MemoryRouter>,
  )
}

describe('AppLayout', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    getProjects.mockResolvedValue({ data: [] })
    getAgentProjects.mockResolvedValue({ data: [] })
  })

  it('renders the reusable shell, two navigation groups, and real user', async () => {
    renderLayout('/projects/new')

    expect(screen.getAllByRole('img', { name: 'AgileFlow AI' }).length).toBeGreaterThan(0)
    expect(await screen.findByRole('heading', { name: 'Projects' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Standalone Agents' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: '+ New Project' })).toHaveAttribute('href', '/projects/new')
    expect(screen.getByText('Ada Lovelace')).toBeInTheDocument()
    expect(screen.getByText('ada@example.com')).toBeInTheDocument()
    expect(screen.queryByText(/reviewer|administrator|role/i)).not.toBeInTheDocument()
  })

  it('shows all four standalone agent groups for project workspaces', async () => {
    renderLayout('/agent-projects/AGP-001')
    expect(await screen.findByRole('button', { name: 'Requirements' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Design' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Implementation' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Testing' })).toBeInTheDocument()
  })

  it('uses AuthContext logout from the visible logout control', async () => {
    const user = userEvent.setup()
    renderLayout()

    await user.click(screen.getByRole('button', { name: 'Log out' }))

    expect(logout).toHaveBeenCalledOnce()
  })

  it('supports desktop collapse without creating another navigation system', async () => {
    const user = userEvent.setup()
    renderLayout()
    const collapse = screen.getByRole('button', { name: 'Collapse sidebar' })
    await user.click(collapse)
    expect(screen.getByRole('button', { name: 'Expand sidebar' })).toBeInTheDocument()
  })

  it('keeps mobile navigation out of the accessibility tree while closed', () => {
    renderLayout()

    expect(
      screen.queryByRole('complementary', { name: 'Mobile navigation' }),
    ).not.toBeInTheDocument()
    expect(
      screen.getByRole('complementary', { name: 'Application sidebar' }),
    ).toBeInTheDocument()
  })

  it('opens mobile navigation and closes it with Escape while restoring focus', async () => {
    const user = userEvent.setup()
    renderLayout()
    const trigger = screen.getByRole('button', { name: 'Open navigation' })

    await user.click(trigger)

    const mobileNavigation = screen.getByRole('complementary', {
      name: 'Mobile navigation',
    })
    expect(
      within(mobileNavigation).getByRole('navigation', { name: 'Primary navigation' }),
    ).toBeInTheDocument()

    await user.keyboard('{Escape}')

    await waitFor(() => {
      expect(
        screen.queryByRole('complementary', { name: 'Mobile navigation' }),
      ).not.toBeInTheDocument()
    })
    expect(trigger).toHaveFocus()
  })

  it('closes mobile navigation after selecting the existing new-project route', async () => {
    const user = userEvent.setup()
    renderLayout('/projects/new')

    await user.click(screen.getByRole('button', { name: 'Open navigation' }))
    const mobileNavigation = screen.getByRole('complementary', {
      name: 'Mobile navigation',
    })
    await user.click(within(mobileNavigation).getByRole('link', { name: '+ New Project' }))

    expect(screen.getByRole('heading', { name: 'Create project' })).toBeInTheDocument()
    expect(
      screen.queryByRole('complementary', { name: 'Mobile navigation' }),
    ).not.toBeInTheDocument()
  })

  it.each([
    ['requirements', 'REQUIREMENTS', 'Agent 1 Created'],
    ['design-planning', 'DESIGN_PLANNING', 'Agent 2 Created'],
    ['implementation', 'IMPLEMENTATION', 'Agent 3 Created'],
    ['testing-validation', 'TESTING_VALIDATION', 'Agent 4 Created'],
  ])('refreshes the shared sidebar after creating a %s project', async (slug, agentType, name) => {
    const user = userEvent.setup()
    const existing = {
      agent_project_id: 'AGP-001', agent_type: agentType, name: 'Existing Project', status: 'ACTIVE',
    }
    const created = {
      agent_project_id: 'AGP-009', agent_type: agentType, name, status: 'ACTIVE',
    }
    getAgentProjects
      .mockResolvedValueOnce({ data: [existing] })
      .mockResolvedValue({ data: [existing, created] })
    createAgentProject.mockResolvedValue({ data: created })
    renderLayout(`/agents/${slug}/new`)
    await screen.findByRole('link', { name: /Existing Project/ })

    await user.type(screen.getByRole('textbox', { name: /project name/i }), name)
    await user.type(screen.getByRole('textbox', { name: /domain/i }), 'SaaS')
    if (agentType === 'TESTING_VALIDATION') {
      await user.click(screen.getByRole('radio', { name: /Test Generation/i }))
    }
    await user.click(screen.getByRole('button', { name: 'Create Project' }))

    expect(await screen.findByRole('heading', { name: 'Agent project' })).toBeInTheDocument()
    expect(createAgentProject).toHaveBeenCalledWith({
      agentType,
      name,
      domain: 'SaaS',
      description: '',
      ...(agentType === 'TESTING_VALIDATION' ? { agentStage: 'TEST_GENERATION' } : {}),
    })
    expect(getAgentProjects).toHaveBeenCalledTimes(2)
    expect(screen.getByRole('link', { name: new RegExp(name) })).toHaveAttribute(
      'href',
      '/agent-projects/AGP-009',
    )
    expect(screen.getAllByRole('link', { name: /Existing Project/ })).toHaveLength(1)
    expect(screen.getAllByRole('link', { name: new RegExp(name) })).toHaveLength(1)
  })

  it('keeps existing sidebar data and does not navigate when creation fails', async () => {
    const user = userEvent.setup()
    getAgentProjects.mockResolvedValue({ data: [{
      agent_project_id: 'AGP-001', agent_type: 'REQUIREMENTS', name: 'Existing Project', status: 'ACTIVE',
    }] })
    createAgentProject.mockRejectedValue({ status: 503 })
    renderLayout('/agents/requirements/new')
    await screen.findByRole('link', { name: /Existing Project/ })

    await user.type(screen.getByRole('textbox', { name: /project name/i }), 'Failed Project')
    await user.type(screen.getByRole('textbox', { name: /domain/i }), 'SaaS')
    await user.click(screen.getByRole('button', { name: 'Create Project' }))

    expect(await screen.findByText(/couldn't create this agent project/i)).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Create Requirements Project' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /Existing Project/ })).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: /Failed Project/ })).not.toBeInTheDocument()
    expect(getAgentProjects).toHaveBeenCalledOnce()
  })
})
