export const WORKFLOW_NODE_STATES = Object.freeze({
  NOT_STARTED: 'NOT_STARTED',
  QUEUED: 'QUEUED',
  RUNNING: 'RUNNING',
  WAITING_FOR_HUMAN: 'WAITING_FOR_HUMAN',
  NEEDS_ATTENTION: 'NEEDS_ATTENTION',
  BLOCKED: 'BLOCKED',
  COMPLETE: 'COMPLETE',
  FAILED: 'FAILED',
  LOCKED: 'LOCKED',
})

export const WORKFLOW_STATE_PRESENTATION = Object.freeze({
  NOT_STARTED: Object.freeze({ label: 'Not Started', tone: 'neutral' }),
  QUEUED: Object.freeze({ label: 'Queued', tone: 'warning' }),
  RUNNING: Object.freeze({ label: 'In Progress', tone: 'info' }),
  WAITING_FOR_HUMAN: Object.freeze({ label: 'Waiting for You', tone: 'warning' }),
  NEEDS_ATTENTION: Object.freeze({ label: 'Needs Attention', tone: 'warning' }),
  BLOCKED: Object.freeze({ label: 'Blocked', tone: 'danger' }),
  COMPLETE: Object.freeze({ label: 'Complete', tone: 'success' }),
  FAILED: Object.freeze({ label: 'Failed', tone: 'danger' }),
  LOCKED: Object.freeze({ label: 'Locked', tone: 'neutral' }),
})

export function getWorkflowStatePresentation(state) {
  return WORKFLOW_STATE_PRESENTATION[state] ?? WORKFLOW_STATE_PRESENTATION.NOT_STARTED
}
