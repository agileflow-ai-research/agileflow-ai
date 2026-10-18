import { WORKFLOW_NODE_STATES } from './workflow.js'

export const SPECIFICATION_STATUS_PRESENTATION = Object.freeze({
  NOT_STARTED: Object.freeze({ label: 'Not Started', tone: 'neutral' }),
  WAITING_FOR_ARTIFACT_REVIEW: Object.freeze({ label: 'Waiting for Artifact Verification', tone: 'warning' }),
  PREPARING_SPECIFICATION: Object.freeze({ label: 'Preparing Structured Specification', tone: 'info' }),
  WAITING_FOR_SEMANTIC_REVIEW: Object.freeze({ label: 'Semantic Review Required', tone: 'warning' }),
  SPECIFICATION_READY: Object.freeze({ label: 'Specification Prepared', tone: 'success' }),
  PARTIAL_FAILURE: Object.freeze({ label: 'Needs Attention', tone: 'warning' }),
  FAILED: Object.freeze({ label: 'Failed', tone: 'danger' }),
})

export function specificationToWorkflowState(status) {
  return ({
    WAITING_FOR_ARTIFACT_REVIEW: WORKFLOW_NODE_STATES.WAITING_FOR_HUMAN,
    PREPARING_SPECIFICATION: WORKFLOW_NODE_STATES.RUNNING,
    WAITING_FOR_SEMANTIC_REVIEW: WORKFLOW_NODE_STATES.WAITING_FOR_HUMAN,
    SPECIFICATION_READY: WORKFLOW_NODE_STATES.COMPLETE,
    PARTIAL_FAILURE: WORKFLOW_NODE_STATES.NEEDS_ATTENTION,
    FAILED: WORKFLOW_NODE_STATES.FAILED,
  })[status] ?? WORKFLOW_NODE_STATES.NOT_STARTED
}

export function specificationPresentation(status) {
  return SPECIFICATION_STATUS_PRESENTATION[status]
    ?? SPECIFICATION_STATUS_PRESENTATION.NOT_STARTED
}
