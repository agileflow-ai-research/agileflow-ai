import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { MemoryRouter, Route, Routes } from 'react-router-dom'

import { getProjectById } from '../services/projectService.js'
import { getEvents, getWorkflow } from '../services/workflowService.js'
import ProjectOverviewPage from './ProjectOverviewPage.jsx'

vi.mock('../services/projectService.js', () => ({
  getProjectById: vi.fn(),
}))

vi.mock('../services/workflowService.js', () => ({
  getWorkflow: vi.fn(),
  getEvents: vi.fn(),
}))

const project = {
  project_id: 'PRJ-001',
  owner_user_id: 'USR-001',
  name: 'Book Management',
  domain: 'Education',
  description: '',
  current_stage: 'PROJECT_CREATED',
  status: 'PENDING',
  created_by: 'USR-001',
  created_at: '2026-10-13T08:00:00Z',
  updated_at: '2026-10-13T09:00:00Z',
}

const workflow = {
  project_id: 'PRJ-001',
  current_stage: 'PROJECT_CREATED',
  current_stage_owner: 'Central SDLC Orchestrator',
  next_stage: 'REQUIREMENTS_IN_PROGRESS',
  next_stage_owner: 'Requirement Gathering and Analysis Agent',
  next_transition_available: true,
  approval_gate: null,
}

const events = [
  {
    event_id: 'EVT-001',
    project_id: 'PRJ-001',
    event_type: 'STAGE_CHANGED',
    source_component: 'Central SDLC Orchestrator',
    target_component: 'Requirement Gathering and Analysis Agent',
    stage_before: 'PROJECT_CREATED',
    stage_after: 'REQUIREMENTS_IN_PROGRESS',
    message: 'Project advanced after an explicit workflow action.',
    metadata: { internal_detail: 'not for display' },
    created_at: '2026-10-13T10:00:00Z',
  },
]

function mockOverview(overrides = {}) {
  getProjectById.mockResolvedValue({
    data: { ...project, ...overrides.project },
  })
  getWorkflow.mockResolvedValue({
    data: { ...workflow, ...overrides.workflow },
  })
  getEvents.mockResolvedValue({ data: overrides.events ?? events })
}

function renderOverview(path = '/projects/PRJ-001') {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/projects" element={<h1>Projects destination</h1>} />
        <Route path="/projects/:projectId" element={<ProjectOverviewPage />} />
      </Routes>
    </MemoryRouter>,
  )
}

describe('ProjectOverviewPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    sessionStorage.clear()
    mockOverview()
  })

  it('shows the initial loading state without placeholder workflow data', () => {
    getProjectById.mockReturnValue(new Promise(() => {}))
    getWorkflow.mockReturnValue(new Promise(() => {}))
    getEvents.mockReturnValue(new Promise(() => {}))

    renderOverview()

    expect(screen.getByText('Loading project overview')).toBeInTheDocument()
    expect(screen.queryByText('Book Management')).not.toBeInTheDocument()
    expect(screen.queryByText(/H1 awaiting approval/i)).not.toBeInTheDocument()
  })

  it('loads all Overview sources in parallel for the route project ID', async () => {
    renderOverview()

    await screen.findByRole('heading', { level: 1, name: 'Book Management' })

    expect(getProjectById).toHaveBeenCalledWith('PRJ-001')
    expect(getWorkflow).toHaveBeenCalledWith('PRJ-001')
    expect(getEvents).toHaveBeenCalledWith('PRJ-001')
    expect(getProjectById).toHaveBeenCalledOnce()
    expect(getWorkflow).toHaveBeenCalledOnce()
    expect(getEvents).toHaveBeenCalledOnce()
  })

  it('renders real project metadata and the authoritative workflow snapshot', async () => {
    renderOverview()

    expect(await screen.findByRole('heading', { level: 1, name: 'Book Management' })).toBeInTheDocument()
    expect(screen.getAllByText('Education').length).toBeGreaterThan(0)
    expect(screen.getByText('Pending')).toHaveAttribute('data-tone', 'neutral')
    expect(screen.getAllByText('Project created').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Central SDLC Orchestrator').length).toBeGreaterThan(0)
    expect(screen.getByText('Requirements in progress')).toBeInTheDocument()
    expect(screen.getByText('Requirement Gathering and Analysis Agent')).toBeInTheDocument()
    expect(screen.getAllByText('Ready to continue').length).toBeGreaterThan(0)
  })

  it('shows transition unavailability and a non-null approval gate honestly', async () => {
    mockOverview({
      workflow: {
        current_stage: 'H2_WAITING_APPROVAL',
        current_stage_owner: 'Human Stakeholder / Reviewer',
        next_stage: 'TEST_PLANNING_IN_PROGRESS',
        next_stage_owner: 'Testing, Validation and Security Agent',
        next_transition_available: false,
        approval_gate: 'H2',
      },
    })

    renderOverview()

    expect((await screen.findAllByText('Waiting for prerequisite')).length).toBeGreaterThan(0)
    expect(screen.getByText('H2')).toBeInTheDocument()
    expect(screen.getAllByText('H2 awaiting approval').length).toBeGreaterThan(0)
  })

  it('shows a terminal workflow without inventing a next stage', async () => {
    mockOverview({
      workflow: {
        current_stage: 'COMPLETED',
        current_stage_owner: 'Central SDLC Orchestrator',
        next_stage: null,
        next_stage_owner: null,
        next_transition_available: false,
        approval_gate: null,
      },
    })

    renderOverview()

    expect((await screen.findAllByText('Workflow complete')).length).toBeGreaterThan(0)
    expect(screen.getByText('No next stage')).toBeInTheDocument()
  })

  it('does not invent an H1 gate for a newly created project', async () => {
    renderOverview()
    await screen.findByRole('heading', { level: 1, name: 'Book Management' })

    expect(screen.queryByText(/^H1$/)).not.toBeInTheDocument()
    expect(screen.queryByText(/H1 awaiting approval/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/H1 requirements/i)).not.toBeInTheDocument()
  })

  it('omits an empty description and displays a non-empty description', async () => {
    const { unmount } = renderOverview()
    await screen.findByRole('heading', { level: 1, name: 'Book Management' })
    expect(screen.queryByText('Description')).not.toBeInTheDocument()
    unmount()

    mockOverview({ project: { description: 'Tracks lending and returns.' } })
    renderOverview()

    expect(await screen.findByText('Description')).toBeInTheDocument()
    expect(screen.getByText('Tracks lending and returns.')).toBeInTheDocument()
  })

  it('renders real events without exposing raw metadata', async () => {
    renderOverview()

    expect(await screen.findByText('Project advanced after an explicit workflow action.')).toBeInTheDocument()
    expect(screen.getByText('Stage Changed')).toBeInTheDocument()
    expect(screen.getByText(/Central SDLC Orchestrator → Requirement Gathering/)).toBeInTheDocument()
    expect(screen.getByText(/Project Created → Requirements In Progress/)).toBeInTheDocument()
    expect(screen.queryByText('internal_detail')).not.toBeInTheDocument()
    expect(screen.queryByText('not for display')).not.toBeInTheDocument()
  })

  it('shows an honest empty state when no events exist', async () => {
    mockOverview({ events: [] })
    renderOverview()

    expect(await screen.findByText('No workflow activity yet')).toBeInTheDocument()
    expect(screen.queryByText('Project workspace created')).not.toBeInTheDocument()
    expect(screen.queryByText('Client idea received')).not.toBeInTheDocument()
  })

  it('handles invalid and missing dates without displaying Invalid Date', async () => {
    mockOverview({
      project: { created_at: 'not-a-date', updated_at: null },
      events: [{ ...events[0], created_at: 'not-a-date' }],
    })
    renderOverview()

    await screen.findByRole('heading', { level: 1, name: 'Book Management' })
    expect(screen.getAllByText('Not available')).toHaveLength(2)
    expect(screen.queryByText(/Invalid Date/i)).not.toBeInTheDocument()
  })

  it('navigates back to Projects using an internal route', async () => {
    const user = userEvent.setup()
    renderOverview()
    await screen.findByRole('heading', { level: 1, name: 'Book Management' })

    await user.click(screen.getByRole('button', { name: 'Back to Projects' }))

    expect(screen.getByRole('heading', { name: 'Projects destination' })).toBeInTheDocument()
  })

  it('shows a privacy-preserving not-found state for a 404', async () => {
    getProjectById.mockRejectedValue({ status: 404, message: 'private detail' })
    renderOverview()

    expect(await screen.findByRole('heading', { name: 'Project not found' })).toBeInTheDocument()
    expect(screen.getByText('The requested project could not be found.')).toBeInTheDocument()
    expect(screen.queryByText(/do not own|another user|foreign-owned|private detail/i)).not.toBeInTheDocument()
  })

  it('shows a safe retryable error and retries all Overview reads', async () => {
    const user = userEvent.setup()
    getWorkflow.mockRejectedValueOnce(new Error('database topology detail'))
    renderOverview()

    expect(await screen.findByRole('heading', { name: 'Project overview unavailable' })).toBeInTheDocument()
    expect(screen.queryByText('database topology detail')).not.toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Try again' }))

    expect(await screen.findByRole('heading', { level: 1, name: 'Book Management' })).toBeInTheDocument()
    expect(getProjectById).toHaveBeenCalledTimes(2)
    expect(getWorkflow).toHaveBeenCalledTimes(2)
    expect(getEvents).toHaveBeenCalledTimes(2)
  })

  it('leaves 401 handling to the central session flow', async () => {
    getProjectById.mockRejectedValue({ status: 401 })
    renderOverview()

    await waitFor(() => expect(getProjectById).toHaveBeenCalledOnce())
    expect(screen.getByText('Loading project overview')).toBeInTheDocument()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })

  it('keeps session data intact during a temporary failure', async () => {
    sessionStorage.setItem('agileflow_access_token', 'existing-token')
    getEvents.mockRejectedValue({ status: 503 })
    renderOverview()

    await screen.findByRole('heading', { name: 'Project overview unavailable' })
    expect(sessionStorage.getItem('agileflow_access_token')).toBe('existing-token')
  })

  it('rejects an invalid route ID without guessing or making requests', async () => {
    renderOverview('/projects/not-a-project')

    expect(await screen.findByRole('heading', { name: 'Project unavailable' })).toBeInTheDocument()
    expect(getProjectById).not.toHaveBeenCalled()
    expect(getWorkflow).not.toHaveBeenCalled()
    expect(getEvents).not.toHaveBeenCalled()
  })

  it('does not fabricate unsupported overview content', async () => {
    renderOverview()
    await screen.findByRole('heading', { level: 1, name: 'Book Management' })

    ;[
      'requirement count',
      'test count',
      'security count',
      'acceptance criteria',
      'personas',
      'approval history',
      'reviewer name',
      'progress percentage',
    ].forEach((text) => {
      expect(screen.queryByText(new RegExp(text, 'i'))).not.toBeInTheDocument()
    })
  })
})
