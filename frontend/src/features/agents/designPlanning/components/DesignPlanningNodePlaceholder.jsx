import StatusBadge from '../../../../components/ui/StatusBadge.jsx'
import { getWorkflowStatePresentation } from '../../../../components/agents/workflowState.js'

function DesignPlanningNodePlaceholder({ node }) {
  if (!node) return null
  const presentation = getWorkflowStatePresentation(node.status)

  const nodeDetails = {
    PROJECT_SPECIFICATIONS: {
      screenRef: 'S2-01 · Specification Input',
      description: 'Supports manual text specification input or document upload (DOCX, PDF, TXT, MD) with backend text extraction and normalization.',
      inputs: ['Requirements Text', 'SRS Documents', 'User Stories', 'Acceptance Criteria'],
    },
    TECHNICAL_PLANNING: {
      screenRef: 'S2-02 · Technical Context & S2-03 · Planning Parameters',
      description: 'Collects architectural constraints, stack preferences, deployment options, team size, sprint duration, and developer roles/skills.',
      inputs: ['Architecture Constraints', 'Preferred Stack', 'Database Preference', 'Team Size', 'Sprint Duration', 'Team Roles & Skills'],
    },
    OUTPUT_SELECTION: {
      screenRef: 'S2-04 · Output Selection',
      description: 'Allows choosing only the technical design artifacts and agile planning hierarchy items required for this run.',
      inputs: ['System Architecture', 'UML Diagrams', 'Database Schema', 'API Specification', 'Wireframes', 'UI Flow', 'Agile Backlog', 'Jira Plan'],
    },
    HUMAN_REVIEW: {
      screenRef: 'S2-05 · Review Before Run',
      description: 'Human-in-the-loop review checkpoint summarizing input specifications, technical context, and chosen outputs before execution.',
      inputs: ['Specification Summary', 'Constraints Review', 'Output Deliverables', 'Execution Approval'],
    },
    GENERATE_DESIGN_PLANNING: {
      screenRef: 'S2-06 · Execution View',
      description: 'Executes the Agent 2 generation pipeline with stage progression tracking against local Qwen/llama.cpp inference.',
      inputs: ['Input Validation', 'Normalization', 'Agent2Engine', 'Generation', 'Consistency Validation', 'Correction', 'Persist Results'],
    },
    DESIGN_RESULTS: {
      screenRef: 'S2-07 · Results Overview, S2-08 · Design Artifacts & S2-09 · Wireframes/Flow',
      description: 'Displays structured system architecture, Mermaid UML diagrams, database schema tables, low-fidelity wireframes, and UI flows.',
      inputs: ['System Architecture Card', 'Mermaid Diagrams', 'Database Schema', 'Interactive Wireframes', 'Actor UI Flows'],
    },
    PLANNING_RESULTS: {
      screenRef: 'S2-10 · Planning Hierarchy, Sprint Plan, Task Assignment & S2-11 · Jira Plan',
      description: 'Presents traceable epics, features, user stories, tasks, heuristic sprint plans, skill-aware task assignments, and Jira-compatible plan.',
      inputs: ['Product Backlog Hierarchy', 'Sprint Schedule', 'Role/Skill Task Matrix', 'Jira JSON/CSV Export'],
    },
    VALIDATION_TRACEABILITY: {
      screenRef: 'S2-12 · Validation, Traceability & Run History',
      description: 'Reviews multi-attempt consistency validation, repair logs, requirement-to-task traceability matrix, and run metadata.',
      inputs: ['Validation Status', 'Multi-attempt Correction History', 'Traceability Matrix', 'Run Metadata'],
    },
  }[node.id] ?? {
    screenRef: 'Agent 2 Workflow Node',
    description: node.purpose,
    inputs: [],
  }

  return (
    <div className="space-y-6" data-testid={`agent2-placeholder-${node.id}`}>
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-control border border-default bg-elevated p-4">
        <div>
          <span className="text-xs font-semibold uppercase tracking-wider text-content-muted">{nodeDetails.screenRef}</span>
          <h3 className="mt-1 text-base font-semibold text-content-primary">{node.title}</h3>
          <p className="mt-1 text-sm text-content-secondary">{node.purpose}</p>
        </div>
        <StatusBadge label={node.statusLabel ?? presentation.label} tone={presentation.tone} />
      </div>

      <div className="rounded-control border border-default bg-surface p-4">
        <h4 className="text-sm font-semibold text-content-primary">Planned Workflow Integration</h4>
        <p className="mt-2 text-sm text-content-secondary">{nodeDetails.description}</p>
        {nodeDetails.inputs.length > 0 && (
          <div className="mt-4">
            <h5 className="text-xs font-semibold uppercase tracking-wider text-content-muted">Scope & Elements</h5>
            <div className="mt-2 flex flex-wrap gap-2">
              {nodeDetails.inputs.map((item) => (
                <span key={item} className="rounded-control border border-default bg-elevated px-2.5 py-1 text-xs text-content-primary">
                  {item}
                </span>
              ))}
            </div>
          </div>
        )}
      </div>

      <div className="rounded-control border border-border-accent/40 bg-primary-soft/10 p-4 text-xs text-content-secondary">
        <strong className="text-content-primary">Agent 2 React Flow Skeleton:</strong> This modal shell represents the node checkpoint in the Agent 2 workflow. The full standalone workspace and execution engine remain active below the canvas.
      </div>
    </div>
  )
}

export default DesignPlanningNodePlaceholder
