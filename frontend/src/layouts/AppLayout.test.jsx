import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { MemoryRouter, Route, Routes } from 'react-router-dom'

import AppLayout from './AppLayout.jsx'
import { getAgentProjects } from '../services/agentProjectService.js'
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
vi.mock('../services/agentProjectService.js', () => ({ getAgentProjects: vi.fn() }))

function renderLayout(path = '/projects') {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route element={<AppLayout />}>
          <Route path="/projects" element={<h1>Protected projects</h1>} />
          <Route path="/projects/new" element={<h1>Create project</h1>} />
          <Route path="/agents" element={<h1>AI agents</h1>} />
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
    expect(await screen.findByRole('button', { name: 'Agent 1 — Requirements & Analysis' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Agent 2 — Design & Planning' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Agent 3 — Implementation' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Agent 4 — Testing & Validation' })).toBeInTheDocument()
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
})
