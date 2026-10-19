import { WORKFLOW_NODE_STATES } from './workflow.js'

export const PROJECT_PREPARATION_STATES = Object.freeze({
  NOT_STARTED: 'NOT_STARTED',
  RUNNING: 'RUNNING',
  WAITING_FOR_HUMAN: 'WAITING_FOR_HUMAN',
  ANALYSIS_READY: 'ANALYSIS_READY',
  PARTIAL_FAILURE: 'PARTIAL_FAILURE',
  FAILED: 'FAILED',
})

export const PREPARATION_STATE_PRESENTATION = Object.freeze({
  NOT_STARTED: Object.freeze({ label: 'Not Started', tone: 'neutral' }),
  RUNNING: Object.freeze({ label: 'In Progress', tone: 'info' }),
  WAITING_FOR_HUMAN: Object.freeze({ label: 'Waiting for You', tone: 'warning' }),
  ANALYSIS_READY: Object.freeze({ label: 'Analysis Ready', tone: 'success' }),
  PARTIAL_FAILURE: Object.freeze({ label: 'Needs Attention', tone: 'warning' }),
  FAILED: Object.freeze({ label: 'Failed', tone: 'danger' }),
})

export const SOURCE_PREPARATION_LABELS = Object.freeze({
  QUEUED: 'Queued',
  EXTRACTING: 'Reading document',
  CHUNKING: 'Preparing content',
  CLASSIFYING_RULES: 'Analyzing content',
  CLASSIFYING_MODEL: 'Analyzing content',
  BUILDING_HYBRID: 'Preparing specification',
  WAITING_FOR_HUMAN: 'Needs your review',
  READY: 'Complete',
  FAILED: 'Failed',
  SKIPPED: 'Not analyzed',
})

export const SOURCE_PREPARATION_STAGE_LABELS = Object.freeze({
  TEXT_NORMALIZATION: 'Preparing text',
  EXTRACTION: 'Reading document',
  CHUNKING: 'Preparing content',
  RULE_CLASSIFICATION: 'Analyzing content',
  MODEL_CLASSIFICATION: 'Analyzing content',
  HYBRID: 'Preparing specification',
  HUMAN_REVIEW: 'Needs your review',
})

export function sourcePreparationLabel(source) {
  return SOURCE_PREPARATION_LABELS[source?.status]
    ?? SOURCE_PREPARATION_STAGE_LABELS[source?.status]
    ?? SOURCE_PREPARATION_LABELS[source?.current_stage]
    ?? SOURCE_PREPARATION_STAGE_LABELS[source?.current_stage]
    ?? (source?.status ? source.status.replaceAll('_', ' ').toLowerCase() : 'Queued')
}

export function preparationToWorkflowState(status) {
  return {
    NOT_STARTED: WORKFLOW_NODE_STATES.NOT_STARTED,
    RUNNING: WORKFLOW_NODE_STATES.RUNNING,
    WAITING_FOR_HUMAN: WORKFLOW_NODE_STATES.WAITING_FOR_HUMAN,
    ANALYSIS_READY: WORKFLOW_NODE_STATES.COMPLETE,
    PARTIAL_FAILURE: WORKFLOW_NODE_STATES.NEEDS_ATTENTION,
    FAILED: WORKFLOW_NODE_STATES.FAILED,
  }[status] ?? WORKFLOW_NODE_STATES.NOT_STARTED
}

export function preparationPresentation(status) {
  return PREPARATION_STATE_PRESENTATION[status]
    ?? PREPARATION_STATE_PRESENTATION.NOT_STARTED
}
