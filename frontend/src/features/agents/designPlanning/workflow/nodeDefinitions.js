import { DESIGN_PLANNING_NODE_IDS } from '../constants/workflow.js'

export const DESIGN_PLANNING_NODE_REGISTRY = Object.freeze([
  {
    id: DESIGN_PLANNING_NODE_IDS.PROJECT_SPECIFICATIONS,
    title: 'Project & Specifications',
    stepNumber: 1,
    active: true,
    purpose: 'Provide requirement sources, SRS documents, user stories, or acceptance criteria.',
    summary: 'Add or upload specification sources.',
  },
  {
    id: DESIGN_PLANNING_NODE_IDS.OUTPUT_SELECTION,
    title: 'Output Selection',
    stepNumber: 2,
    active: true,
    purpose: 'Select required technical design and agile planning outputs for Agent 2 execution.',
    summary: 'Select desired design and planning outputs.',
  },
  {
    id: DESIGN_PLANNING_NODE_IDS.TECHNICAL_PLANNING,
    title: 'Technical & Planning',
    stepNumber: 3,
    active: true,
    purpose: 'Provide the additional technical and planning information required for your selected outputs.',
    summary: 'Configure technical context and team parameters.',
  },
  {
    id: DESIGN_PLANNING_NODE_IDS.HUMAN_REVIEW,
    title: 'Human Review',
    stepNumber: 4,
    active: true,
    purpose: 'Inspect normalized specifications, constraints, and selected outputs before launching execution.',
    summary: 'Human-in-the-loop review checkpoint.',
  },
  {
    id: DESIGN_PLANNING_NODE_IDS.GENERATE_DESIGN_PLANNING,
    title: 'Generate Design & Planning',
    stepNumber: 5,
    active: true,
    purpose: 'Trigger autonomous Agent 2 execution pipeline and observe real-time progression.',
    summary: 'Autonomous generation and validation pipeline.',
  },
  {
    id: DESIGN_PLANNING_NODE_IDS.DESIGN_RESULTS,
    title: 'Design Results',
    stepNumber: 6,
    active: true,
    purpose: 'Review generated architecture, UML diagrams, DB schema, and UI flows.',
    summary: 'Structured technical design deliverables.',
  },
  {
    id: DESIGN_PLANNING_NODE_IDS.PLANNING_RESULTS,
    title: 'Planning Results',
    stepNumber: 7,
    active: true,
    purpose: 'Explore epics, user stories, sprint schedule, task assignment, and Jira-compatible plan.',
    summary: 'Agile planning hierarchy and sprint schedule.',
  },
  {
    id: DESIGN_PLANNING_NODE_IDS.VALIDATION_TRACEABILITY,
    title: 'Validation & Traceability',
    stepNumber: 8,
    active: true,
    purpose: 'Verify consistency validation, repair attempts, and requirement-to-task traceability matrix.',
    summary: 'Traceability matrix and quality metrics.',
  },
])

export function getDesignPlanningNodeDefinition(nodeId) {
  return DESIGN_PLANNING_NODE_REGISTRY.find((node) => node.id === nodeId) ?? null
}
