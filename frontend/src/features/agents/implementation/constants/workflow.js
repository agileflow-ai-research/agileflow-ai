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
  NOT_STARTED: Object.freeze({ label: 'Not Started', tone: 'neutral', visual: 'neutral' }),
  QUEUED: Object.freeze({ label: 'Queued', tone: 'neutral', visual: 'queued' }),
  RUNNING: Object.freeze({ label: 'In Progress', tone: 'info', visual: 'processing' }),
  WAITING_FOR_HUMAN: Object.freeze({ label: 'Needs Your Review', tone: 'warning', visual: 'warning' }),
  NEEDS_ATTENTION: Object.freeze({ label: 'Needs Attention', tone: 'warning', visual: 'warning' }),
  BLOCKED: Object.freeze({ label: 'Blocked', tone: 'danger', visual: 'blocked' }),
  COMPLETE: Object.freeze({ label: 'Complete', tone: 'success', visual: 'success' }),
  FAILED: Object.freeze({ label: 'Failed', tone: 'danger', visual: 'failed' }),
  LOCKED: Object.freeze({ label: 'Locked', tone: 'neutral', visual: 'locked' }),
})

export function getWorkflowStatePresentation(state) {
  return WORKFLOW_STATE_PRESENTATION[state] ?? WORKFLOW_STATE_PRESENTATION.NOT_STARTED
}
