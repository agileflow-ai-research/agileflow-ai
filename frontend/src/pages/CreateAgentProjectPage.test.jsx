import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes, useLocation, useNavigate } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { createAgentProject } from '../services/agentProjectService.js'
import CreateAgentProjectPage from './CreateAgentProjectPage.jsx'

vi.mock('../services/agentProjectService.js', () => ({ createAgentProject: vi.fn() }))

function OverviewDestination() {
  const location = useLocation()
  return <h1>Overview destination {location.state?.agentProjectEntry ?? 'existing'}</h1>
}

function SwitchAgentButton() {
  const navigate = useNavigate()
  return <button type="button" onClick={() => navigate('/agents/implementation/new')}>Switch agent</button>
}

function renderCreate(path = '/agents/design-planning/new', { withSwitcher = false } = {}) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/agents/:agentSlug/new" element={<>{withSwitcher ? <SwitchAgentButton /> : null}<CreateAgentProjectPage /></>} />
        <Route path="/agents" element={<h1>Hub</h1>} />
        <Route path="/agents/:agentSlug" element={<h1>List</h1>} />
        <Route path="/agent-projects/:agentProjectId" element={<OverviewDestination />} />
      </Routes>
    </MemoryRouter>,
  )
}

async function fillForm(user, { name = ' Planning ', domain = ' SaaS ', description = ' Context ' } = {}) {
  await user.type(screen.getByRole('textbox', { name: /project name/i }), name)
  await user.type(screen.getByRole('textbox', { name: /domain/i }), domain)
  if (description) await user.type(screen.getByRole('textbox', { name: /description/i }), description)
}

describe('CreateAgentProjectPage', () => {
  beforeEach(() => vi.clearAllMocks())

  it('derives the exact type, submits only allowed values, and redirects', async () => {
    const user = userEvent.setup()
    createAgentProject.mockResolvedValue({ data: { agent_project_id: 'AGP-009' } })
    renderCreate()
    await fillForm(user)
    await user.click(screen.getByRole('button', { name: 'Create Project' }))
    expect(createAgentProject).toHaveBeenCalledWith({
      agentType: 'DESIGN_PLANNING', name: 'Planning', domain: 'SaaS', description: ' Context ',
    })
    const payload = createAgentProject.mock.calls[0][0]
    expect(payload).not.toHaveProperty('agent_project_id')
    expect(payload).not.toHaveProperty('owner_user_id')
    expect(payload).not.toHaveProperty('status')
    expect(payload).not.toHaveProperty('agentStage')
    expect(await screen.findByRole('heading', { name: 'Overview destination created' })).toBeInTheDocument()
  })

  it('requires only name/domain and prevents duplicate pending submission', async () => {
    const user = userEvent.setup()
    createAgentProject.mockReturnValue(new Promise(() => {}))
    renderCreate('/agents/implementation/new')
    await user.click(screen.getByRole('button', { name: 'Create Project' }))
    expect(screen.getByText('Enter a project name.')).toBeInTheDocument()
    expect(screen.getByText('Enter a project domain.')).toBeInTheDocument()
    expect(createAgentProject).not.toHaveBeenCalled()

    await fillForm(user, { description: '' })
    await user.click(screen.getByRole('button', { name: 'Create Project' }))
    const pending = screen.getByRole('button', { name: 'Creating project' })
    expect(pending).toBeDisabled()
    await user.click(pending)
    expect(createAgentProject).toHaveBeenCalledOnce()
  })

  it('maps backend field details without exposing internal failures', async () => {
    const user = userEvent.setup()
    createAgentProject.mockRejectedValue({ status: 422, errors: [{ field: 'body.domain', message: 'Domain is invalid.' }] })
    renderCreate('/agents/requirements/new')
    await fillForm(user)
    await user.click(screen.getByRole('button', { name: 'Create Project' }))
    expect(await screen.findByText('Domain is invalid.')).toBeInTheDocument()
    expect(screen.getByRole('textbox', { name: /domain/i })).toHaveAttribute('aria-invalid', 'true')
  })

  it.each([
    ['/agents/requirements/new', 'Requirements'],
    ['/agents/design-planning/new', 'Design'],
    ['/agents/implementation/new', 'Implementation'],
  ])('hides Agent Stage for non-Agent-4 creation at %s', (path) => {
    renderCreate(path)
    expect(screen.queryByRole('group', { name: /agent stage/i })).not.toBeInTheDocument()
  })

  it('requires an available Agent 4 stage and submits Test Generation', async () => {
    const user = userEvent.setup()
    createAgentProject.mockResolvedValue({ data: { agent_project_id: 'AGP-010' } })
    renderCreate('/agents/testing-validation/new')

    expect(screen.getByRole('group', { name: /agent stage/i })).toBeInTheDocument()
    expect(screen.getByText('Generate planned and traceable test specifications')).toBeInTheDocument()
    expect(screen.getByText('Execute and validate implementation')).toBeInTheDocument()
    expect(screen.getByText('Available')).toBeInTheDocument()
    expect(screen.getByText('Coming Soon')).toBeInTheDocument()
    expect(screen.getByRole('radio', { name: /testing & validation/i })).toBeDisabled()

    await fillForm(user)
    await user.click(screen.getByRole('button', { name: 'Create Project' }))
    expect(screen.getByText('Select an available Agent Stage.')).toBeInTheDocument()
    expect(createAgentProject).not.toHaveBeenCalled()

    await user.click(screen.getByRole('radio', { name: /test generation/i }))
    await user.click(screen.getByRole('button', { name: 'Create Project' }))
    expect(createAgentProject).toHaveBeenCalledWith({
      agentType: 'TESTING_VALIDATION',
      agentStage: 'TEST_GENERATION',
      name: 'Planning',
      domain: 'SaaS',
      description: ' Context ',
    })
  })

  it('clears a selected stage when routing away from Agent 4', async () => {
    const user = userEvent.setup()
    createAgentProject.mockResolvedValue({ data: { agent_project_id: 'AGP-011' } })
    renderCreate('/agents/testing-validation/new', { withSwitcher: true })
    await user.click(screen.getByRole('radio', { name: /test generation/i }))
    await user.click(screen.getByRole('button', { name: 'Switch agent' }))

    expect(screen.queryByRole('group', { name: /agent stage/i })).not.toBeInTheDocument()
    await fillForm(user)
    await user.click(screen.getByRole('button', { name: 'Create Project' }))
    expect(createAgentProject).toHaveBeenCalledWith({
      agentType: 'IMPLEMENTATION', name: 'Planning', domain: 'SaaS', description: ' Context ',
    })
  })
})
