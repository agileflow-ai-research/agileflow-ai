import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { getAgentProjects } from '../services/agentProjectService.js'
import AgentProjectListPage from './AgentProjectListPage.jsx'

vi.mock('../services/agentProjectService.js', () => ({ getAgentProjects: vi.fn() }))

const projects = [
  { agent_project_id: 'AGP-001', agent_type: 'REQUIREMENTS', name: 'Checkout', domain: 'Commerce', description: 'Requirements workspace', status: 'ACTIVE', updated_at: '2026-10-14T08:00:00Z' },
  { agent_project_id: 'AGP-002', agent_type: 'REQUIREMENTS', name: 'Legacy', domain: 'Finance', status: 'ARCHIVED', updated_at: '2026-10-13T08:00:00Z' },
]

function renderList(path = '/agents/requirements') {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/agents" element={<h1>Hub</h1>} />
        <Route path="/agents/:agentSlug" element={<AgentProjectListPage />} />
        <Route path="/agents/:agentSlug/new" element={<h1>Create destination</h1>} />
        <Route path="/agent-projects/:agentProjectId" element={<h1>Overview destination</h1>} />
      </Routes>
    </MemoryRouter>,
  )
}

describe('AgentProjectListPage', () => {
  beforeEach(() => vi.clearAllMocks())

  it('shows loading then renders real ACTIVE and ARCHIVED projects for the routed type', async () => {
    let resolve
    getAgentProjects.mockReturnValue(new Promise((done) => { resolve = done }))
    renderList()
    expect(screen.getByRole('status', { name: 'Loading Requirements Agent projects' })).toBeInTheDocument()
    resolve({ data: projects })
    expect(await screen.findByText('Checkout')).toBeInTheDocument()
    expect(screen.getAllByText('Active').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Archived').length).toBeGreaterThan(0)
    expect(getAgentProjects).toHaveBeenCalledWith({ agentType: 'REQUIREMENTS', status: undefined })
  })

  it('requests a real status filter and opens a real project ID', async () => {
    const user = userEvent.setup()
    getAgentProjects.mockResolvedValue({ data: projects })
    renderList('/agents/requirements')
    await screen.findByText('Checkout')
    await user.selectOptions(screen.getByRole('combobox', { name: 'Project status' }), 'ARCHIVED')
    await waitFor(() => expect(getAgentProjects).toHaveBeenLastCalledWith({ agentType: 'REQUIREMENTS', status: 'ARCHIVED' }))
    await user.click(screen.getByRole('button', { name: 'Open Checkout' }))
    expect(screen.getByRole('heading', { name: 'Overview destination' })).toBeInTheDocument()
  })

  it('renders the truthful empty state and create destination', async () => {
    const user = userEvent.setup()
    getAgentProjects.mockResolvedValue({ data: [] })
    renderList('/agents/testing-validation')
    expect(await screen.findByText('No Testing & Validation Agent projects yet.')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Create Testing & Validation Project' }))
    expect(screen.getByRole('heading', { name: 'Create destination' })).toBeInTheDocument()
  })

  it('shows safe error/retry and handles an unknown slug without a service call', async () => {
    const user = userEvent.setup()
    getAgentProjects.mockRejectedValueOnce(new Error('private detail')).mockResolvedValueOnce({ data: [] })
    const view = renderList('/agents/implementation')
    expect(await screen.findByRole('alert')).not.toHaveTextContent('private detail')
    await user.click(screen.getByRole('button', { name: 'Try again' }))
    await waitFor(() => expect(getAgentProjects).toHaveBeenCalledTimes(2))

    view.unmount()
    vi.clearAllMocks()
    renderList('/agents/unknown')
    expect(screen.getByRole('alert')).toHaveTextContent('Unknown agent')
    expect(getAgentProjects).not.toHaveBeenCalled()
  })
})
