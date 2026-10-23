import { describe, expect, it } from 'vitest'

import { deriveDesignPlanningPresentation } from './presentation.js'
import { DESIGN_PLANNING_NODE_IDS, WORKFLOW_NODE_STATES } from '../constants/workflow.js'

describe('deriveDesignPlanningPresentation', () => {
  const baseSnapshot = {
    input: {
      requirements: 'Users can register, book rooms, and cancel reservations.',
      project_start_date: '2026-11-01',
      expected_project_duration: '3 months',
      development_team_count: '',
      sprint_duration: '',
    },
    selectedOutputs: [],
    uploadStatus: {},
    humanReviewApproved: false,
  }

  it('derives Node 2 (Output Selection) status as NOT_STARTED when 0 selected, COMPLETE when outputs selected', () => {
    const p1 = deriveDesignPlanningPresentation(baseSnapshot)
    expect(p1[DESIGN_PLANNING_NODE_IDS.OUTPUT_SELECTION].status).toBe(WORKFLOW_NODE_STATES.NOT_STARTED)
    expect(p1[DESIGN_PLANNING_NODE_IDS.OUTPUT_SELECTION].summary).toBe('Select desired design and planning outputs.')

    const p2 = deriveDesignPlanningPresentation({
      ...baseSnapshot,
      selectedOutputs: ['SYSTEM_ARCHITECTURE', 'DATABASE_SCHEMA'],
    })
    expect(p2[DESIGN_PLANNING_NODE_IDS.OUTPUT_SELECTION].status).toBe(WORKFLOW_NODE_STATES.COMPLETE)
    expect(p2[DESIGN_PLANNING_NODE_IDS.OUTPUT_SELECTION].summary).toBe('2 of 14 outputs selected')
  })

  it('derives Node 3 status as ACTION REQUIRED when SPRINT_PLAN is selected without sprint duration (Rule 2)', () => {
    const presentation = deriveDesignPlanningPresentation({
      ...baseSnapshot,
      input: {
        ...baseSnapshot.input,
        project_start_date: '2026-11-01',
        expected_project_duration: '3 months',
        sprint_duration: '',
      },
      selectedOutputs: ['SPRINT_PLAN'],
    })

    const node3 = presentation[DESIGN_PLANNING_NODE_IDS.TECHNICAL_PLANNING]
    expect(node3.status).toBe(WORKFLOW_NODE_STATES.WAITING_FOR_HUMAN)
    expect(node3.statusLabel).toBe('Action Required')
    expect(node3.summary).toBe('Sprint duration is required because SPRINT_PLAN was selected.')
  })

  it('derives Node 3 status as ACTION REQUIRED when SPRINT_PLAN is selected without project start date (Rule 3)', () => {
    const presentation = deriveDesignPlanningPresentation({
      ...baseSnapshot,
      input: {
        ...baseSnapshot.input,
        project_start_date: '',
        expected_project_duration: '3 months',
        sprint_duration: '14',
      },
      selectedOutputs: ['SPRINT_PLAN'],
    })

    const node3 = presentation[DESIGN_PLANNING_NODE_IDS.TECHNICAL_PLANNING]
    expect(node3.status).toBe(WORKFLOW_NODE_STATES.WAITING_FOR_HUMAN)
    expect(node3.statusLabel).toBe('Action Required')
    expect(node3.summary).toBe('Project start date is required because SPRINT_PLAN was selected.')
  })

  it('derives Node 3 status as ACTION REQUIRED when CAPACITY_AWARE + SPRINT_PLAN is missing team count (Rule 4)', () => {
    const presentation = deriveDesignPlanningPresentation({
      ...baseSnapshot,
      input: {
        ...baseSnapshot.input,
        planning_mode: 'CAPACITY_AWARE',
        project_start_date: '2026-11-01',
        expected_project_duration: '3 months',
        sprint_duration: '14',
        development_team_count: '',
      },
      selectedOutputs: ['SPRINT_PLAN'],
    })

    const node3 = presentation[DESIGN_PLANNING_NODE_IDS.TECHNICAL_PLANNING]
    expect(node3.status).toBe(WORKFLOW_NODE_STATES.WAITING_FOR_HUMAN)
    expect(node3.statusLabel).toBe('Action Required')
    expect(node3.summary).toBe('Development team count is required for capacity-aware sprint planning.')
  })

  it('derives Node 3 status as ACTION REQUIRED when TASK_ASSIGNMENT is selected without team count (Rule 5)', () => {
    const presentation = deriveDesignPlanningPresentation({
      ...baseSnapshot,
      input: {
        ...baseSnapshot.input,
        development_team_count: '',
      },
      selectedOutputs: ['TASK_ASSIGNMENT'],
    })

    const node3 = presentation[DESIGN_PLANNING_NODE_IDS.TECHNICAL_PLANNING]
    expect(node3.status).toBe(WORKFLOW_NODE_STATES.WAITING_FOR_HUMAN)
    expect(node3.statusLabel).toBe('Action Required')
    expect(node3.summary).toBe('Development team count is required because TASK_ASSIGNMENT was selected.')
  })

  it('derives Node 3 status as COMPLETE when JIRA_PLAN is selected alone without team count (Rule 6)', () => {
    const presentation = deriveDesignPlanningPresentation({
      ...baseSnapshot,
      input: {
        ...baseSnapshot.input,
        development_team_count: '',
      },
      selectedOutputs: ['JIRA_PLAN'],
    })

    const node3 = presentation[DESIGN_PLANNING_NODE_IDS.TECHNICAL_PLANNING]
    expect(node3.status).toBe(WORKFLOW_NODE_STATES.COMPLETE)
    expect(node3.statusLabel).toBeUndefined()
  })

  it('derives Node 3 status as COMPLETE when TIMELINE_BASED SPRINT_PLAN + JIRA_PLAN is selected without TASK_ASSIGNMENT (Rule 7)', () => {
    const presentation = deriveDesignPlanningPresentation({
      ...baseSnapshot,
      input: {
        ...baseSnapshot.input,
        planning_mode: 'TIMELINE_BASED',
        project_start_date: '2026-11-01',
        expected_project_duration: '3 months',
        sprint_duration: '14',
        development_team_count: '',
      },
      selectedOutputs: ['SPRINT_PLAN', 'JIRA_PLAN'],
    })

    const node3 = presentation[DESIGN_PLANNING_NODE_IDS.TECHNICAL_PLANNING]
    expect(node3.status).toBe(WORKFLOW_NODE_STATES.COMPLETE)
    expect(node3.statusLabel).toBeUndefined()
  })

  it('derives Node 3 status as COMPLETE for architecture-only outputs without requiring planning fields', () => {
    const presentation = deriveDesignPlanningPresentation({
      ...baseSnapshot,
      input: {
        ...baseSnapshot.input,
        project_start_date: '',
        expected_project_duration: '',
        development_team_count: '',
        sprint_duration: '',
      },
      selectedOutputs: ['SYSTEM_ARCHITECTURE', 'DATABASE_SCHEMA', 'API_SPECIFICATION'],
    })

    const node3 = presentation[DESIGN_PLANNING_NODE_IDS.TECHNICAL_PLANNING]
    expect(node3.status).toBe(WORKFLOW_NODE_STATES.COMPLETE)
    expect(node3.statusLabel).toBeUndefined()
  })

  it('derives Node 3 status as COMPLETE when all contract-required planning inputs are satisfied', () => {
    const presentation = deriveDesignPlanningPresentation({
      ...baseSnapshot,
      input: {
        ...baseSnapshot.input,
        project_start_date: '2026-11-01',
        expected_project_duration: '3 months',
        development_team_count: '6',
        sprint_duration: '14',
      },
      selectedOutputs: ['SPRINT_PLAN', 'TASK_ASSIGNMENT'],
    })

    const node3 = presentation[DESIGN_PLANNING_NODE_IDS.TECHNICAL_PLANNING]
    expect(node3.status).toBe(WORKFLOW_NODE_STATES.COMPLETE)
    expect(node3.statusLabel).toBeUndefined()
  })

  it('gates Node 4 (Human Review): blocked when required planning inputs are missing, unlocks when valid (Rules 9, 10)', () => {
    // Missing outputs
    const p1 = deriveDesignPlanningPresentation({
      ...baseSnapshot,
      selectedOutputs: [],
    })
    expect(p1[DESIGN_PLANNING_NODE_IDS.HUMAN_REVIEW].status).toBe(WORKFLOW_NODE_STATES.BLOCKED)
    expect(p1[DESIGN_PLANNING_NODE_IDS.HUMAN_REVIEW].summary).toBe('Blocked: Output selection required')

    // Rule 9: Human Review is blocked when required planning inputs are missing (e.g. missing sprint duration)
    const p2 = deriveDesignPlanningPresentation({
      ...baseSnapshot,
      selectedOutputs: ['SPRINT_PLAN'],
      input: {
        ...baseSnapshot.input,
        project_start_date: '2026-11-01',
        expected_project_duration: '3 months',
        sprint_duration: '',
      },
    })
    expect(p2[DESIGN_PLANNING_NODE_IDS.HUMAN_REVIEW].status).toBe(WORKFLOW_NODE_STATES.BLOCKED)
    expect(p2[DESIGN_PLANNING_NODE_IDS.HUMAN_REVIEW].summary).toBe('Blocked: Planning parameters required')

    // Rule 10: Human Review unlocks when required inputs are valid
    const p3 = deriveDesignPlanningPresentation({
      ...baseSnapshot,
      selectedOutputs: ['SPRINT_PLAN'],
      input: {
        ...baseSnapshot.input,
        planning_mode: 'TIMELINE_BASED',
        project_start_date: '2026-11-01',
        expected_project_duration: '3 months',
        sprint_duration: '14',
        development_team_count: '', // not required for timeline-based
      },
    })
    expect(p3[DESIGN_PLANNING_NODE_IDS.HUMAN_REVIEW].status).toBe(WORKFLOW_NODE_STATES.WAITING_FOR_HUMAN)
    expect(p3[DESIGN_PLANNING_NODE_IDS.HUMAN_REVIEW].summary).toBe('Ready for human review before execution.')

    // Approved -> COMPLETE
    const p4 = deriveDesignPlanningPresentation({
      ...baseSnapshot,
      selectedOutputs: ['SPRINT_PLAN'],
      input: {
        ...baseSnapshot.input,
        planning_mode: 'TIMELINE_BASED',
        project_start_date: '2026-11-01',
        expected_project_duration: '3 months',
        sprint_duration: '14',
      },
      humanReviewApproved: true,
    })
    expect(p4[DESIGN_PLANNING_NODE_IDS.HUMAN_REVIEW].status).toBe(WORKFLOW_NODE_STATES.COMPLETE)
    expect(p4[DESIGN_PLANNING_NODE_IDS.HUMAN_REVIEW].summary).toBe('Human review completed · Ready for generation.')
  })
})
