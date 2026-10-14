import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import {
  getAgentProjectById,
  getAgentProjectRun,
  getAgentProjectRuns,
  updateAgentProject,
} from '../services/agentProjectService.js'
import AgentProjectOverviewPage from './AgentProjectOverviewPage.jsx'

vi.mock('../services/agentProjectService.js', () => ({
  getAgentProjectById: vi.fn(), getAgentProjectRuns: vi.fn(), getAgentProjectRun: vi.fn(), updateAgentProject: vi.fn(),
}))

const project = {
  agent_project_id: 'AGP-001', agent_type: 'TESTING_VALIDATION', name: 'Quality Gate', domain: 'Fintech',
  description: 'Persisted description', status: 'ACTIVE', created_at: '2026-10-13T08:00:00Z', updated_at: '2026-10-14T08:00:00Z',
}
const runs = [
  { run_id: 'RUN-004', run_mode: 'VALIDATION', status: 'FAILED', selected_outputs: ['SECURITY_REPORT'], created_at: '2026-10-14T12:00:00Z', started_at: '2026-10-14T12:01:00Z', completed_at: '2026-10-14T12:02:00Z' },
  { run_id: 'RUN-003', run_mode: 'TEST_GENERATION', status: 'COMPLETED', selected_outputs: ['TEST_CASES'], created_at: '2026-10-14T11:00:00Z', started_at: '2026-10-14T11:01:00Z', completed_at: '2026-10-14T11:02:00Z' },
  { run_id: 'RUN-002', run_mode: 'VALIDATION', status: 'RUNNING', selected_outputs: ['QUALITY_REPORT'], created_at: '2026-10-14T10:00:00Z', started_at: '2026-10-14T10:01:00Z' },
  { run_id: 'RUN-001', run_mode: 'DEFAULT', status: 'QUEUED', selected_outputs: ['SUMMARY'], created_at: '2026-10-14T09:00:00Z' },
]

function renderOverview(path = '/agent-projects/AGP-001') {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/agent-projects/:agentProjectId" element={<AgentProjectOverviewPage />} />
        <Route path="/agents/:agentSlug" element={<h1>Agent list</h1>} />
        <Route path="/agents" element={<h1>Hub</h1>} />
      </Routes>
    </MemoryRouter>,
  )
}

describe('AgentProjectOverviewPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    getAgentProjectById.mockResolvedValue({ data: project })
    getAgentProjectRuns.mockResolvedValue({ data: runs })
  })

  it('loads the AGP project and real run history with all shared presentations', async () => {
    renderOverview()
    expect(await screen.findByRole('heading', { level: 1, name: 'Quality Gate' })).toBeInTheDocument()
    expect(getAgentProjectById).toHaveBeenCalledWith('AGP-001')
    expect(getAgentProjectRuns).toHaveBeenCalledWith('AGP-001')
    expect(screen.getAllByText('Testing & Validation Agent').length).toBeGreaterThan(0)
    ;['Queued', 'Running', 'Completed', 'Failed', 'Standard run', 'Test Case Generation', 'Testing & Validation'].forEach((text) => {
      expect(screen.getAllByText(text).length).toBeGreaterThan(0)
    })
    expect(screen.getByText('RUN-004')).toBeInTheDocument()
    expect(screen.getByText('SECURITY_REPORT')).toBeInTheDocument()
    expect(screen.getByText('Agent-specific input and execution controls will appear here.')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /start run|execute agent|generate outputs/i })).not.toBeInTheDocument()
  })

  it('shows a truthful empty run history', async () => {
    getAgentProjectRuns.mockResolvedValue({ data: [] })
    renderOverview()
    expect(await screen.findByText('No runs yet.')).toBeInTheDocument()
  })

  it('archives after confirmation and reactivates archived projects', async () => {
    const user = userEvent.setup()
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    updateAgentProject.mockResolvedValue({ data: { ...project, status: 'ARCHIVED' } })
    const view = renderOverview()
    await screen.findByRole('heading', { name: 'Quality Gate' })
    await user.click(screen.getByRole('button', { name: 'Archive Project' }))
    expect(updateAgentProject).toHaveBeenCalledWith('AGP-001', { status: 'ARCHIVED' })
    expect(await screen.findByRole('button', { name: 'Reactivate Project' })).toBeInTheDocument()
    expect(screen.getByText(/execution controls are unavailable while this project is archived/i)).toBeInTheDocument()

    updateAgentProject.mockResolvedValue({ data: project })
    await user.click(screen.getByRole('button', { name: 'Reactivate Project' }))
    expect(updateAgentProject).toHaveBeenLastCalledWith('AGP-001', { status: 'ACTIVE' })
    view.unmount()
    vi.restoreAllMocks()
  })

  it('loads persisted run detail with warnings, errors, and an honest manifest', async () => {
    const user = userEvent.setup()
    getAgentProjectRun.mockResolvedValue({ data: {
      ...runs[0], warnings: [{ code: 'PARTIAL', message: 'Some evidence is partial', details: { source: 'scanner' } }],
      errors: [{ code: 'VALIDATION_FAILED', message: 'A quality gate failed' }],
      output_manifest: { SECURITY_REPORT: { reference: 'artifact-1' } },
    } })
    renderOverview()
    await screen.findByText('RUN-004')
    const failedCard = screen.getByText('RUN-004').closest('[data-variant]')
    await user.click(within(failedCard).getByRole('button', { name: 'View details for run RUN-004' }))
    expect(await screen.findByRole('heading', { name: 'Run details' })).toBeInTheDocument()
    expect(getAgentProjectRun).toHaveBeenCalledWith('AGP-001', 'RUN-004')
    expect(screen.getByText('Some evidence is partial')).toBeInTheDocument()
    expect(screen.getByText('A quality gate failed')).toBeInTheDocument()
    expect(screen.getByText(/artifact-1/)).toBeInTheDocument()
    expect(document.body).not.toHaveTextContent('undefined')
  })

  it('handles invalid, missing, and retryable project states safely', async () => {
    const invalidView = renderOverview('/agent-projects/not-an-id')
    expect(await screen.findByRole('alert')).toHaveTextContent('Invalid project address')
    expect(getAgentProjectById).not.toHaveBeenCalled()
    invalidView.unmount()

    getAgentProjectById.mockRejectedValue({ status: 404 })
    renderOverview()
    expect(await screen.findByRole('alert')).toHaveTextContent('Agent project not found')
    await waitFor(() => expect(getAgentProjectRuns).toHaveBeenCalled())
  })
})
