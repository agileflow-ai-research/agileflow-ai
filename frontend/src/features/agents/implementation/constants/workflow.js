export const WORKFLOW_NODE_IDS = Object.freeze({
  PROJECT_SOURCES: 'PROJECT_SOURCES',
  INPUT_ANALYSIS: 'INPUT_ANALYSIS',
  SPECIFICATION_VERIFICATION: 'SPECIFICATION_VERIFICATION',
  IMPLEMENTATION_READINESS: 'IMPLEMENTATION_READINESS',
  DELIVERY_SETUP: 'DELIVERY_SETUP',
  GENERATE_IMPLEMENTATION: 'GENERATE_IMPLEMENTATION',
  BUILD_EXECUTE: 'BUILD_EXECUTE',
  CORRECTION_VALIDATION: 'CORRECTION_VALIDATION',
  DELIVERY: 'DELIVERY',
})

export const WORKFLOW_MODAL_ORIGINS = Object.freeze({
  AUTO: 'AUTO',
  MANUAL: 'MANUAL',
})

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
