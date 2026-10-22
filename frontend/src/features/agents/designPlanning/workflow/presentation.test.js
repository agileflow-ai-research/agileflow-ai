import { describe, expect, it } from 'vitest'

import { deriveDesignPlanningPresentation } from './presentation.js'
import { DESIGN_PLANNING_NODE_IDS, WORKFLOW_NODE_STATES } from '../constants/workflow.js'

describe('deriveDesignPlanningPresentation', () => {
  const baseSnapshot = {
    input: {
      requirements: 'Users can register, book rooms, and cancel reservations.',
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

  it('derives Node 3 status as ACTION REQUIRED when SPRINT_PLAN is selected without sprint duration', () => {
    const presentation = deriveDesignPlanningPresentation({
      ...baseSnapshot,
      input: {
        ...baseSnapshot.input,
        development_team_count: '5',
        sprint_duration: '',
      },
      selectedOutputs: ['SPRINT_PLAN'],
    })

    const node3 = presentation[DESIGN_PLANNING_NODE_IDS.TECHNICAL_PLANNING]
    expect(node3.status).toBe(WORKFLOW_NODE_STATES.WAITING_FOR_HUMAN)
    expect(node3.statusLabel).toBe('Action Required')
    expect(node3.summary).toBe('Sprint duration is required because SPRINT_PLAN was selected.')
  })

  it('derives Node 3 status as ACTION REQUIRED when TASK_ASSIGNMENT is selected without team count', () => {
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

  it('derives Node 3 status as ACTION REQUIRED when JIRA_PLAN is selected without team count', () => {
    const presentation = deriveDesignPlanningPresentation({
      ...baseSnapshot,
      input: {
        ...baseSnapshot.input,
        development_team_count: '',
      },
      selectedOutputs: ['JIRA_PLAN'],
    })

    const node3 = presentation[DESIGN_PLANNING_NODE_IDS.TECHNICAL_PLANNING]
    expect(node3.status).toBe(WORKFLOW_NODE_STATES.WAITING_FOR_HUMAN)
    expect(node3.statusLabel).toBe('Action Required')
    expect(node3.summary).toBe('Development team count is required because JIRA_PLAN was selected.')
  })

  it('derives Node 3 status as COMPLETE for architecture-only outputs without requiring planning fields', () => {
    const presentation = deriveDesignPlanningPresentation({
      ...baseSnapshot,
      input: {
        ...baseSnapshot.input,
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
        development_team_count: '6',
        sprint_duration: '14',
      },
      selectedOutputs: ['SPRINT_PLAN', 'TASK_ASSIGNMENT'],
    })

    const node3 = presentation[DESIGN_PLANNING_NODE_IDS.TECHNICAL_PLANNING]
    expect(node3.status).toBe(WORKFLOW_NODE_STATES.COMPLETE)
    expect(node3.statusLabel).toBeUndefined()
  })

  it('gates Node 4 (Human Review): blocked if missing spec, missing outputs, or missing required planning fields', () => {
    // Missing outputs
    const p1 = deriveDesignPlanningPresentation({
      ...baseSnapshot,
      selectedOutputs: [],
    })
    expect(p1[DESIGN_PLANNING_NODE_IDS.HUMAN_REVIEW].status).toBe(WORKFLOW_NODE_STATES.BLOCKED)
    expect(p1[DESIGN_PLANNING_NODE_IDS.HUMAN_REVIEW].summary).toBe('Blocked: Output selection required')

    // Missing required planning fields
    const p2 = deriveDesignPlanningPresentation({
      ...baseSnapshot,
      selectedOutputs: ['SPRINT_PLAN'],
      input: { ...baseSnapshot.input, sprint_duration: '' },
    })
    expect(p2[DESIGN_PLANNING_NODE_IDS.HUMAN_REVIEW].status).toBe(WORKFLOW_NODE_STATES.BLOCKED)
    expect(p2[DESIGN_PLANNING_NODE_IDS.HUMAN_REVIEW].summary).toBe('Blocked: Planning parameters required')

    // All required satisfied -> WAITING_FOR_HUMAN (ready for review)
    const p3 = deriveDesignPlanningPresentation({
      ...baseSnapshot,
      selectedOutputs: ['SPRINT_PLAN'],
      input: { ...baseSnapshot.input, development_team_count: '4', sprint_duration: '14' },
    })
    expect(p3[DESIGN_PLANNING_NODE_IDS.HUMAN_REVIEW].status).toBe(WORKFLOW_NODE_STATES.WAITING_FOR_HUMAN)
    expect(p3[DESIGN_PLANNING_NODE_IDS.HUMAN_REVIEW].summary).toBe('Ready for human review before execution.')

    // Approved -> COMPLETE
    const p4 = deriveDesignPlanningPresentation({
      ...baseSnapshot,
      selectedOutputs: ['SPRINT_PLAN'],
      input: { ...baseSnapshot.input, development_team_count: '4', sprint_duration: '14' },
      humanReviewApproved: true,
    })
    expect(p4[DESIGN_PLANNING_NODE_IDS.HUMAN_REVIEW].status).toBe(WORKFLOW_NODE_STATES.COMPLETE)
    expect(p4[DESIGN_PLANNING_NODE_IDS.HUMAN_REVIEW].summary).toBe('Human review completed · Ready for generation.')
  })
})
