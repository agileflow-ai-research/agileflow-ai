export const PLANNING_MODES = Object.freeze({
  TIMELINE_BASED: 'TIMELINE_BASED',
  CAPACITY_AWARE: 'CAPACITY_AWARE',
})

export const initialInput = Object.freeze({
  requirements: '',
  SRS: '',
  user_stories: '',
  acceptance_criteria: '',
  technical_constraints: '',
  preferred_technology_stack: '',
  deployment_preference: '',
  database_preference: '',
  ui_ux_constraints: '',
  architecture_notes: '',
  planning_mode: PLANNING_MODES.TIMELINE_BASED,
  project_start_date: '',
  development_team_count: '',
  sprint_duration: '',
  expected_project_duration: '',
  developer_roles: '',
  developer_skills: '',
  team_composition: '',
})

export const specificationFields = Object.freeze([
  'requirements',
  'SRS',
  'user_stories',
  'acceptance_criteria',
])

export const specificationSources = Object.freeze([
  {
    id: 'requirements',
    sourceType: 'REQUIREMENTS',
    stateKey: 'requirements',
    shortLabel: 'Requirements',
    label: 'Requirements',
    cardTitle: 'Requirements',
    helperText: 'Manual input or document upload — functional or business requirements text.',
    placeholder:
      'Users can register and log in.\nUsers can browse available services and time slots.\nUsers can create or cancel an appointment.\nAdmins can manage services and booking availability.',
  },
  {
    id: 'srs',
    sourceType: 'SRS',
    stateKey: 'SRS',
    shortLabel: 'SRS',
    label: 'Software Requirements Specification (SRS)',
    cardTitle: 'Software Requirements Specification (SRS)',
    helperText: 'Detailed SRS documentation or system specifications.',
    placeholder: 'Paste SRS documentation, system constraints, or specification sections...',
  },
  {
    id: 'user_stories',
    sourceType: 'USER_STORIES',
    stateKey: 'user_stories',
    shortLabel: 'User Stories',
    label: 'User Stories',
    cardTitle: 'User Stories',
    helperText: 'Agile user stories in actor/goal/benefit format.',
    placeholder: 'As a [role], I want [goal], so that [benefit]...',
  },
  {
    id: 'acceptance_criteria',
    sourceType: 'ACCEPTANCE_CRITERIA',
    stateKey: 'acceptance_criteria',
    shortLabel: 'Acceptance Criteria',
    label: 'Acceptance Criteria',
    cardTitle: 'Acceptance Criteria',
    helperText: 'Testable conditions or verification criteria.',
    placeholder: 'Given [context], when [action], then [outcome]...',
  },
])

export const outputGroups = Object.freeze([
  {
    id: 'design_outputs',
    title: 'Design outputs',
    subtitle: 'Structured technical design artifacts.',
    outputs: [
      {
        value: 'SYSTEM_ARCHITECTURE',
        label: 'System Architecture',
        description: 'Components, boundaries, interactions, constraints, and assumptions.',
      },
      {
        value: 'UML_DIAGRAMS',
        label: 'UML Diagrams',
        description: 'Structured Mermaid or PlantUML diagram source.',
      },
      {
        value: 'DATABASE_SCHEMA',
        label: 'Database Schema',
        description: 'Entities, fields, relationships, and constraints.',
      },
      {
        value: 'API_SPECIFICATION',
        label: 'API Specification',
        description: 'Operations, inputs, outputs, errors, and authentication assumptions.',
      },
      {
        value: 'WIREFRAMES',
        label: 'Wireframes',
        description: 'Structured low-fidelity screen and layout specifications.',
      },
      {
        value: 'UI_FLOW',
        label: 'UI Flow',
        description: 'Actor-oriented navigation and task flows.',
      },
    ],
  },
  {
    id: 'agile_planning',
    title: 'Agile planning',
    subtitle: 'Traceable planning hierarchy.',
    outputs: [
      {
        value: 'PRODUCT_BACKLOG',
        label: 'Product Backlog',
        description: 'Prioritized, traceable backlog items.',
      },
      {
        value: 'EPICS',
        label: 'Epics',
        description: 'Outcome-oriented bodies of work.',
      },
      {
        value: 'FEATURES',
        label: 'Features',
        description: 'Capabilities linked to parent epics.',
      },
      {
        value: 'USER_STORIES',
        label: 'User Stories',
        description: 'Estimated stories linked to features and epics.',
      },
      {
        value: 'TASKS',
        label: 'Tasks',
        description: 'Implementable work with estimates and dependencies.',
      },
    ],
  },
  {
    id: 'planning_jira',
    title: 'Planning & Jira',
    subtitle: 'Execution-ready planning data.',
    outputs: [
      {
        value: 'SPRINT_PLAN',
        label: 'Sprint Plan',
        description: 'Timeline-based or capacity-aware sprint organization.',
        dependencyHint: 'project_start_date + expected_project_duration + sprint_duration',
      },
      {
        value: 'TASK_ASSIGNMENT',
        label: 'Task Assignment',
        description: 'Heuristic recommendations using supplied team information.',
        dependencyHint: 'development_team_count',
      },
      {
        value: 'JIRA_PLAN',
        label: 'Jira-ready Plan',
        description: 'Structured export data; no Jira Cloud synchronization.',
        dependencyHint: 'SPRINT_PLAN (unassigned by default)',
      },
    ],
  },
])

export const allOutputValues = Object.freeze(
  outputGroups.flatMap((group) => group.outputs.map((out) => out.value)),
)

export function getRequiredPlanningFields(selectedOutputs = [], input = {}) {
  const required = {}
  const planningMode = input.planning_mode || PLANNING_MODES.TIMELINE_BASED
  const hasSprintPlan = selectedOutputs.includes('SPRINT_PLAN')
  const hasTaskAssignment = selectedOutputs.includes('TASK_ASSIGNMENT')

  if (hasSprintPlan) {
    required.project_start_date = {
      field: 'project_start_date',
      label: 'Project start date',
      triggers: ['SPRINT_PLAN'],
      reason: 'Project start date is required because SPRINT_PLAN was selected.',
    }
    required.expected_project_duration = {
      field: 'expected_project_duration',
      label: 'Expected project duration',
      triggers: ['SPRINT_PLAN'],
      reason: 'Expected project duration is required because SPRINT_PLAN was selected.',
    }
    required.sprint_duration = {
      field: 'sprint_duration',
      label: 'Sprint duration',
      triggers: ['SPRINT_PLAN'],
      reason: 'Sprint duration is required because SPRINT_PLAN was selected.',
    }
  }

  const teamTriggers = []
  if (hasSprintPlan && planningMode === PLANNING_MODES.CAPACITY_AWARE) {
    teamTriggers.push('SPRINT_PLAN (Capacity-aware)')
  }
  if (hasTaskAssignment) {
    teamTriggers.push('TASK_ASSIGNMENT')
  }

  if (teamTriggers.length > 0) {
    const reason =
      hasSprintPlan && planningMode === PLANNING_MODES.CAPACITY_AWARE && !hasTaskAssignment
        ? 'Development team count is required for capacity-aware sprint planning.'
        : `Development team count is required because ${teamTriggers.join(', ')} was selected.`
    required.development_team_count = {
      field: 'development_team_count',
      label: 'Development team count',
      triggers: teamTriggers,
      reason,
    }
  }

  return required
}

export function getPlanningErrors(input = {}, selectedOutputs = []) {
  const nextErrors = {}
  const planningMode = input.planning_mode || PLANNING_MODES.TIMELINE_BASED
  const hasSprintPlan = selectedOutputs.includes('SPRINT_PLAN')
  const hasTaskAssignment = selectedOutputs.includes('TASK_ASSIGNMENT')

  if (hasSprintPlan) {
    if (!input.project_start_date?.trim()) {
      nextErrors.project_start_date =
        'Project start date is required because SPRINT_PLAN was selected.'
    }
    if (!input.expected_project_duration?.trim()) {
      nextErrors.expected_project_duration =
        'Expected project duration is required because SPRINT_PLAN was selected.'
    }
    if (!(Number(input.sprint_duration) > 0)) {
      nextErrors.sprint_duration =
        'Sprint duration is required because SPRINT_PLAN was selected.'
    }
    if (planningMode === PLANNING_MODES.CAPACITY_AWARE && !(Number(input.development_team_count) > 0)) {
      nextErrors.development_team_count =
        'Development team count is required for capacity-aware sprint planning.'
    }
  }

  if (hasTaskAssignment && !(Number(input.development_team_count) > 0)) {
    nextErrors.development_team_count =
      'Development team count is required because TASK_ASSIGNMENT was selected.'
  }

  return nextErrors
}

export function hasAtLeastOneSpecification(input = {}) {
  return specificationFields.some((field) => Boolean(input[field]?.trim()))
}

export function getValidationIssues(input = {}, selectedOutputs = []) {
  const issues = []
  if (!hasAtLeastOneSpecification(input)) {
    issues.push({
      id: 'spec_missing',
      targetNodeId: 'PROJECT_SPECIFICATIONS',
      message: 'At least one usable specification source is required (Requirements, SRS, User Stories, or Acceptance Criteria).',
    })
  }
  if (selectedOutputs.length === 0) {
    issues.push({
      id: 'output_missing',
      targetNodeId: 'OUTPUT_SELECTION',
      message: 'At least one output artifact must be selected.',
    })
  }
  const planning = getPlanningErrors(input, selectedOutputs)
  if (planning.project_start_date) {
    issues.push({
      id: 'project_start_date_missing',
      targetNodeId: 'TECHNICAL_PLANNING',
      message: planning.project_start_date,
    })
  }
  if (planning.expected_project_duration) {
    issues.push({
      id: 'expected_project_duration_missing',
      targetNodeId: 'TECHNICAL_PLANNING',
      message: planning.expected_project_duration,
    })
  }
  if (planning.sprint_duration) {
    issues.push({
      id: 'sprint_missing',
      targetNodeId: 'TECHNICAL_PLANNING',
      message: planning.sprint_duration,
    })
  }
  if (planning.development_team_count) {
    issues.push({
      id: 'team_missing',
      targetNodeId: 'TECHNICAL_PLANNING',
      message: planning.development_team_count,
    })
  }
  return issues
}

