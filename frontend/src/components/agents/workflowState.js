export const WORKFLOW_NODE_STATES = Object.freeze({
  NOT_STARTED: 'NOT_STARTED',
  QUEUED: 'QUEUED',
  RUNNING: 'RUNNING',
  WAITING_FOR_HUMAN: 'WAITING_FOR_HUMAN',
  NEEDS_ATTENTION: 'NEEDS_ATTENTION',
  BLOCKED: 'BLOCKED',
  COMPLETE: 'COMPLETE',
  FAILED: 'FAILED',
  INTERRUPTED: 'INTERRUPTED',
  LOCKED: 'LOCKED',
  READY: 'READY',
  READY_WITH_WARNINGS: 'READY_WITH_WARNINGS',
  NOT_APPLICABLE: 'NOT_APPLICABLE',
})

export const WORKFLOW_STATE_PRESENTATION = Object.freeze({
  NOT_STARTED: Object.freeze({ label: 'Not Started', tone: 'neutral', visual: 'neutral' }),
  QUEUED: Object.freeze({ label: 'Queued', tone: 'neutral', visual: 'queued' }),
  RUNNING: Object.freeze({ label: 'In Progress', tone: 'info', visual: 'processing' }),
  WAITING_FOR_HUMAN: Object.freeze({ label: 'Needs Your Review', tone: 'warning', visual: 'warning' }),
  NEEDS_ATTENTION: Object.freeze({ label: 'Needs Attention', tone: 'warning', visual: 'warning' }),
  BLOCKED: Object.freeze({ label: 'Blocked', tone: 'danger', visual: 'blocked' }),
  COMPLETE: Object.freeze({ label: 'Complete', tone: 'success', visual: 'success' }),
  COMPLETED: Object.freeze({ label: 'Complete', tone: 'success', visual: 'success' }),
  FAILED: Object.freeze({ label: 'Failed', tone: 'danger', visual: 'failed' }),
  INTERRUPTED: Object.freeze({ label: 'Interrupted / Retry needed', tone: 'danger', visual: 'failed' }),
  LOCKED: Object.freeze({ label: 'Locked', tone: 'neutral', visual: 'locked' }),
  READY: Object.freeze({ label: 'Ready', tone: 'success', visual: 'success' }),
  READY_WITH_WARNINGS: Object.freeze({ label: 'Ready with limitations', tone: 'warning', visual: 'warning' }),
  NOT_APPLICABLE: Object.freeze({ label: 'Not required', tone: 'neutral', visual: 'neutral' }),
})

export function getWorkflowStatePresentation(state) {
  return WORKFLOW_STATE_PRESENTATION[state] ?? WORKFLOW_STATE_PRESENTATION.NOT_STARTED
}
