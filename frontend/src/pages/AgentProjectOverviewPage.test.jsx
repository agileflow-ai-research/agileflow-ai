import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Outlet, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import {
  getAgentProjectById,
  getAgentProjectRun,
  getAgentProjectRuns,
  updateAgentProject,
} from '../services/agentProjectService.js'
import { listRequirementSources } from '../features/agents/requirements/requirementsAgentService.js'
import { getGitHubConnection } from '../features/agents/implementation/services/implementationAgentService.js'
import AgentProjectOverviewPage from './AgentProjectOverviewPage.jsx'

vi.mock('../services/agentProjectService.js', () => ({
  getAgentProjectById: vi.fn(), getAgentProjectRuns: vi.fn(), getAgentProjectRun: vi.fn(), updateAgentProject: vi.fn(),
}))
vi.mock('../features/agents/requirements/requirementsAgentService.js', () => ({
  deleteRequirementSource: vi.fn(),
  getRequirementAudioProcessingResult: vi.fn(),
  getRequirementAudioProcessingStatus: vi.fn(),
  getRequirementDocumentProcessingResult: vi.fn(),
  getRequirementDocumentProcessingStatus: vi.fn(),
  getNormalizedRequirementEvidence: vi.fn(),
  getRequirementEvidenceChunks: vi.fn(),
  getRequirementPreparationStatus: vi.fn(),
  getRequirementVideoProcessingResult: vi.fn(),
  getRequirementVideoProcessingStatus: vi.fn(),
  listRequirementSources: vi.fn(),
  processRequirementDocument: vi.fn(),
  processRequirementAudio: vi.fn(),
  processRequirementVideo: vi.fn(),
  prepareRequirementEvidence: vi.fn(),
  uploadRequirementSource: vi.fn(),
}))
vi.mock('../features/agents/implementation/pages/ImplementationProjectPage.jsx', () => ({
  default: ({ project, entryMode }) => (
    <section aria-label="Agent 3 implementation project" data-entry-mode={entryMode}>
      <h1>{project.name}</h1>
      <div aria-label="Agent 3 implementation workflow canvas" />
    </section>
  ),
}))
vi.mock('../features/agents/requirements/pages/RequirementsProjectPage.jsx', () => ({
  default: ({ project, entryMode }) => (
    <section aria-label="Agent 1 requirements project" data-entry-mode={entryMode}>
      <h1>{project.name}</h1>
      <div aria-label="Agent 1 requirements workflow canvas" />
    </section>
  ),
}))
vi.mock('../features/agents/testingValidation/pages/TestingValidationProjectPage.jsx', () => ({
  default: ({ project, entryMode }) => (
    <section aria-label="Agent 4 test generation project" data-entry-mode={entryMode}>
      <h1>{project.name}</h1>
      <div aria-label="Agent 4 test generation workflow canvas" />
    </section>
  ),
}))
vi.mock('../features/agents/implementation/services/implementationAgentService.js', () => ({
  uploadImplementationInputFile: vi.fn(),
  deleteImplementationInputFile: vi.fn(),
  evaluateImplementationReadiness: vi.fn(),
  extractImplementationDocument: vi.fn(),
  getImplementationDocumentExtraction: vi.fn(),
  connectGitHub: vi.fn(),
  createGitHubRepository: vi.fn(),
  getGitHubConnection: vi.fn(),
  getGitHubRepository: vi.fn(),
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

function renderOverview(path = '/agent-projects/AGP-001', refreshAgentProjects) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route element={<Outlet context={{ refreshAgentProjects }} />}>
          <Route path="/agent-projects/:agentProjectId" element={<AgentProjectOverviewPage />} />
          <Route path="/agents/:agentSlug" element={<h1>Agent list</h1>} />
          <Route path="/agents" element={<h1>Hub</h1>} />
        </Route>
      </Routes>
    </MemoryRouter>,
  )
}

describe('AgentProjectOverviewPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    getAgentProjectById.mockResolvedValue({ data: project })
    getAgentProjectRuns.mockResolvedValue({ data: runs })
    getGitHubConnection.mockResolvedValue({ data: { connected: false } })
    listRequirementSources.mockResolvedValue({ data: [] })
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
    expect(screen.getByRole('button', { name: /Test Case Generation/ })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Testing & Validation/ })).toBeInTheDocument()
  })

  it('shows a truthful empty run history', async () => {
    getAgentProjectRuns.mockResolvedValue({ data: [] })
    renderOverview()
    expect(await screen.findByText('No runs yet.')).toBeInTheDocument()
  })

  it('mounts the Agent 3 canvas at the compatible project URL', async () => {
    getAgentProjectById.mockResolvedValue({ data: {
      ...project,
      agent_type: 'IMPLEMENTATION',
      name: 'Delivery Portal',
      domain: 'Logistics',
    } })
    getAgentProjectRuns.mockResolvedValue({ data: [] })

    renderOverview()

    expect(await screen.findByRole('heading', { level: 1, name: 'Delivery Portal' })).toBeInTheDocument()
    expect(screen.getByLabelText('Agent 3 implementation project')).toHaveAttribute('data-entry-mode', 'existing')
    expect(screen.getByLabelText('Agent 3 implementation workflow canvas')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Run Agent' })).not.toBeInTheDocument()
  })

  it('routes a staged Agent 4 project to the seven-node canvas page', async () => {
    getAgentProjectById.mockResolvedValue({ data: {
      ...project,
      agent_stage: 'TEST_GENERATION',
    } })
    getAgentProjectRuns.mockResolvedValue({ data: [] })

    renderOverview()

    expect(await screen.findByLabelText('Agent 4 test generation project')).toHaveAttribute('data-entry-mode', 'existing')
    expect(screen.getByLabelText('Agent 4 test generation workflow canvas')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Test Case Generation/ })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Run Agent' })).not.toBeInTheDocument()
  })

  it('keeps the unavailable Validation stage on its safe Coming Soon guard', async () => {
    getAgentProjectById.mockResolvedValue({ data: { ...project, agent_stage: 'VALIDATION' } })
    getAgentProjectRuns.mockResolvedValue({ data: [] })

    renderOverview()

    expect(await screen.findByText(/Coming Soon/)).toBeInTheDocument()
    expect(screen.queryByLabelText('Agent 4 test generation workflow canvas')).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Run Agent' })).not.toBeInTheDocument()
  })

  it('passes explicit creation entry state to Agent 3 onboarding', async () => {
    getAgentProjectById.mockResolvedValue({ data: {
      ...project, agent_type: 'IMPLEMENTATION', name: 'New Delivery Portal',
    } })
    getAgentProjectRuns.mockResolvedValue({ data: [] })

    renderOverview({
      pathname: '/agent-projects/AGP-001',
      state: { agentProjectEntry: 'created' },
    })

    expect(await screen.findByLabelText('Agent 3 implementation project')).toHaveAttribute('data-entry-mode', 'created')
  })

  it('archives after confirmation and reactivates archived projects', async () => {
    const user = userEvent.setup()
    const refreshAgentProjects = vi.fn().mockResolvedValue([])
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    updateAgentProject.mockResolvedValue({ data: { ...project, status: 'ARCHIVED' } })
    const view = renderOverview('/agent-projects/AGP-001', refreshAgentProjects)
    await screen.findByRole('heading', { name: 'Quality Gate' })
    await user.click(screen.getByRole('button', { name: 'Archive Project' }))
    expect(updateAgentProject).toHaveBeenCalledWith('AGP-001', { status: 'ARCHIVED' })
    expect(await screen.findByRole('button', { name: 'Reactivate Project' })).toBeInTheDocument()
    expect(screen.getByText(/execution controls are unavailable while this project is archived/i)).toBeInTheDocument()

    updateAgentProject.mockResolvedValue({ data: project })
    await user.click(screen.getByRole('button', { name: 'Reactivate Project' }))
    expect(updateAgentProject).toHaveBeenLastCalledWith('AGP-001', { status: 'ACTIVE' })
    expect(refreshAgentProjects).toHaveBeenCalledTimes(2)
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

  it('mounts the Agent 1 canvas without starting a run', async () => {
    getAgentProjectById.mockResolvedValue({ data: { ...project, agent_type: 'REQUIREMENTS', name: 'BookEase' } })
    getAgentProjectRuns.mockResolvedValue({ data: [] })
    renderOverview()
    await screen.findByRole('heading', { level: 1, name: 'BookEase' })
    expect(await screen.findByLabelText('Agent 1 requirements project')).toHaveAttribute('data-entry-mode', 'existing')
    expect(screen.getByLabelText('Agent 1 requirements workflow canvas')).toBeInTheDocument()
    expect(screen.getByLabelText('Agent 1 requirements project').compareDocumentPosition(
      screen.getByRole('region', { name: 'Run History' }),
    ) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    expect(listRequirementSources).not.toHaveBeenCalled()
    expect(screen.queryByRole('button', { name: 'Run Agent' })).not.toBeInTheDocument()
  })

  it('mounts the Agent 2 canvas and keeps Run History directly following below', async () => {
    getAgentProjectById.mockResolvedValue({
      data: {
        ...project,
        agent_type: 'DESIGN_PLANNING',
        name: 'BookEase Architecture',
        domain: 'Hospitality',
      },
    })
    getAgentProjectRuns.mockResolvedValue({ data: [] })
    renderOverview()
    await screen.findByRole('heading', { level: 1, name: 'BookEase Architecture' })
    expect(await screen.findByLabelText('Agent 2 design and planning project')).toBeInTheDocument()
    expect(screen.getByLabelText(/Agent 2 design and planning workflow canvas/i)).toBeInTheDocument()
    expect(
      screen.getByLabelText('Agent 2 design and planning project').compareDocumentPosition(
        screen.getByRole('region', { name: 'Run History' }),
      ) & Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy()
    expect(screen.queryByRole('button', { name: 'Run Agent' })).not.toBeInTheDocument()
  })

  it('keeps archived Agent 1 projects read-only and outside the active canvas page', async () => {
    getAgentProjectById.mockResolvedValue({ data: {
      ...project,
      agent_type: 'REQUIREMENTS',
      name: 'Archived Requirements',
      status: 'ARCHIVED',
    } })
    getAgentProjectRuns.mockResolvedValue({ data: [] })
    renderOverview()

    expect(await screen.findByRole('heading', { level: 1, name: 'Archived Requirements' })).toBeInTheDocument()
    expect(screen.queryByLabelText('Agent 1 requirements project')).not.toBeInTheDocument()
    expect(screen.getByText(/execution controls are unavailable while this project is archived/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Reactivate Project' })).toBeInTheDocument()
  })

  it('reloads and renders persisted Agent 1 output_manifest content', async () => {
    const user = userEvent.setup()
    const requirementRun = {
      run_id: 'RUN-201', agent_type: 'REQUIREMENTS', status: 'COMPLETED', run_mode: 'DEFAULT',
      selected_outputs: ['USER_STORIES'], created_at: '2026-10-14T12:00:00Z',
      started_at: '2026-10-14T12:00:01Z', completed_at: '2026-10-14T12:00:02Z',
    }
    getAgentProjectById.mockResolvedValue({ data: { ...project, agent_type: 'REQUIREMENTS', name: 'Clinic Booking' } })
    getAgentProjectRuns.mockResolvedValue({ data: [requirementRun] })
    getAgentProjectRun.mockResolvedValue({ data: {
      ...requirementRun, warnings: [], errors: [],
      output_manifest: { USER_STORIES: [{ id: 'US-001', actor: 'patient', goal: 'book a dental appointment', benefit: 'I avoid telephone booking', source_refs: ['TEXT-001'], requirement_refs: [] }] },
    } })

    renderOverview()
    await screen.findByText('RUN-201')
    await user.click(screen.getByRole('button', { name: 'View details for run RUN-201' }))

    expect(await screen.findByRole('heading', { name: 'Persisted requirements outputs' })).toBeInTheDocument()
    expect(screen.getByText((_, node) => node.tagName === 'P' && node.textContent.includes('I want book a dental appointment'))).toBeInTheDocument()
    expect(screen.getByText((_, node) => node.tagName === 'P' && node.textContent.includes('so that I avoid telephone booking'))).toBeInTheDocument()
    expect(screen.queryByText(/"actor"/)).not.toBeInTheDocument()
  })
})
