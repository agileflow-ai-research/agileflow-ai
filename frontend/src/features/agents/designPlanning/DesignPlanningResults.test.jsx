import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { getAgentProjectRun } from '../../../services/agentProjectService.js'
import DesignPlanningResults from './DesignPlanningResults.jsx'
import RunDetail from '../../../components/agents/RunDetail.jsx'

vi.mock('../../../services/agentProjectService.js', () => ({ getAgentProjectRun: vi.fn() }))

const jiraPlan = {
  epics: [{ id: 'EPIC-001', title: 'Booking', outcome: 'Guests can book', priority: 'HIGH', source_refs: ['SPEC-001'] }],
  stories: [{ id: 'STORY-001', epic_id: 'EPIC-001', feature_id: 'FEATURE-001', actor: 'guest', goal: 'book', benefit: 'reserve', acceptance_criteria: ['Confirmed'], priority: 'HIGH', estimate_points: 5, source_refs: ['SPEC-001'] }],
  tasks: [{ id: 'TASK-001', epic_id: 'EPIC-001', feature_id: 'FEATURE-001', story_id: 'STORY-001', title: 'Build API', description: 'Implement booking API', required_skills: ['API'], estimate_points: 3, depends_on: [], source_refs: ['SPEC-001'] }],
  sprints: [{ id: 'SPRINT-001', name: 'Sprint 1', duration_days: 10, capacity_points: 20, planned_points: 3, utilization_percent: 15, item_refs: ['TASK-001'], dependency_notes: [], planning_warnings: ['Estimate only'], estimate_basis: 'Estimated capacity formula' }],
  assignments: [{ task_id: 'TASK-001', team_slot: 'Alice', role: 'Backend Developer', rationale: 'API skill match', sprint_id: 'SPRINT-001', matching_reasons: ['Matched API'], role_match: true, skill_matches: ['API'], workload_points_before: 0, confidence_score: 100 }],
  priorities: [{ item_id: 'STORY-001', priority: 'HIGH' }],
  synchronization: 'NOT_PERFORMED',
}

describe('DesignPlanningResults', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    URL.createObjectURL = vi.fn(() => 'blob:test-plan')
    URL.revokeObjectURL = vi.fn()
  })

  it('renders structured design and planning fields in human-readable sections', () => {
    render(<DesignPlanningResults outputs={{
      API_SPECIFICATION: { base_path: '/api/v1', operations: [{ id: 'API-001', method: 'POST', path: '/bookings', summary: 'Create booking', request: 'Booking payload', response: 'Created booking', errors: ['409 conflict'], authentication: 'Bearer', source_refs: ['SPEC-001'], component_refs: ['COMP-001'], entity_refs: ['ENTITY-001'] }], assumptions: [] },
      SPRINT_PLAN: jiraPlan.sprints,
      TASK_ASSIGNMENT: jiraPlan.assignments,
    }} />)
    expect(screen.getByText('POST /bookings')).toBeInTheDocument()
    expect(screen.getByText('COMP-001')).toBeInTheDocument()
    expect(screen.getByText('Estimated capacity')).toBeInTheDocument()
    expect(screen.getByText('15%')).toBeInTheDocument()
    expect(screen.getByText('Alice')).toBeInTheDocument()
    expect(screen.getByText('100/100')).toBeInTheDocument()
  })

  it('downloads the already-generated Jira plan as JSON without synchronization', async () => {
    const user = userEvent.setup()
    const click = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {})
    render(<DesignPlanningResults outputs={{ JIRA_PLAN: jiraPlan }} />)
    await user.click(screen.getByRole('button', { name: 'Download Jira-compatible JSON' }))
    expect(URL.createObjectURL).toHaveBeenCalledWith(expect.any(Blob))
    expect(click).toHaveBeenCalledOnce()
    expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:test-plan')
    expect(screen.getByText(/Synchronization:/)).toHaveTextContent('Not performed')
    click.mockRestore()
  })

  it('renders persisted Agent 2 results and export controls in historical run detail', async () => {
    getAgentProjectRun.mockResolvedValue({ data: {
      run_id: 'RUN-020', agent_type: 'DESIGN_PLANNING', run_mode: 'DEFAULT', status: 'COMPLETED',
      selected_outputs: ['JIRA_PLAN'], created_at: '2026-10-14T10:00:00Z',
      started_at: '2026-10-14T10:00:01Z', completed_at: '2026-10-14T10:00:02Z',
      warnings: [], errors: [], output_manifest: { JIRA_PLAN: jiraPlan },
    } })
    render(<RunDetail agentProjectId="AGP-002" runId="RUN-020" />)
    expect(await screen.findByRole('heading', { name: 'Persisted design and planning outputs' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Download Jira-compatible JSON' })).toBeInTheDocument()
    expect(screen.getAllByText('Booking').length).toBeGreaterThan(0)
  })
})
