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
        description: 'Capacity-aware sprint organization.',
        dependencyHint: 'development_team_count + sprint_duration',
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
        dependencyHint: 'development_team_count',
      },
    ],
  },
])

export const allOutputValues = Object.freeze(
  outputGroups.flatMap((group) => group.outputs.map((out) => out.value)),
)

export function getPlanningErrors(input = {}, selectedOutputs = []) {
  const nextErrors = {}
  const needsTeam = selectedOutputs.some((code) =>
    ['SPRINT_PLAN', 'TASK_ASSIGNMENT', 'JIRA_PLAN'].includes(code),
  )
  if (needsTeam && !(Number(input.development_team_count) > 0)) {
    nextErrors.development_team_count =
      'A positive team count is required for capacity or assignment planning.'
  }
  if (selectedOutputs.includes('SPRINT_PLAN') && !(Number(input.sprint_duration) > 0)) {
    nextErrors.sprint_duration =
      'A positive sprint duration is required for sprint planning.'
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
  if (planning.development_team_count) {
    issues.push({
      id: 'team_missing',
      targetNodeId: 'TECHNICAL_PLANNING',
      message: planning.development_team_count,
    })
  }
  if (planning.sprint_duration) {
    issues.push({
      id: 'sprint_missing',
      targetNodeId: 'TECHNICAL_PLANNING',
      message: planning.sprint_duration,
    })
  }
  return issues
}

