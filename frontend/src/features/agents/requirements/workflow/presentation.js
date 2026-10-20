import { WORKFLOW_NODE_STATES } from '../../../../components/agents/workflowState.js'
import { REQUIREMENTS_NODE_IDS, REQUIREMENTS_NODE_REGISTRY } from './nodeDefinitions.js'

const completed = (state) => state?.status === 'COMPLETED'
const failed = (state) => state?.status === 'FAILED' || Boolean(state?.requestError)
const hasProgress = (state) => Boolean(state) && ![undefined, null, 'READY'].includes(state.status)
const validSource = (source) => (
  typeof source?.source_id === 'string'
  && source.source_id.trim().length > 0
  && ['DOCUMENT', 'AUDIO', 'VIDEO'].includes(source?.source_type)
)

export function deriveRequirementsWorkflowPresentation({
  sources,
  processingStates,
  preparationStates,
  workflowState,
}) {
  const sourceList = Array.isArray(sources)
    ? sources.filter(validSource)
    : []
  const processingBySource = processingStates ?? {}
  const preparationBySource = preparationStates ?? {}
  const hasSources = sourceList.length > 0
  const sourceStates = sourceList.map((source) => ({
    processing: processingBySource[source.source_id],
    preparation: preparationBySource[source.source_id],
  }))

  const hasFailure = sourceStates.some(({ processing, preparation }) => (
    failed(processing) || failed(preparation)
  ))
  const hasActiveWork = sourceStates.some(({ processing, preparation }) => (
    processing?.status === 'PROCESSING' || preparation?.status === 'PROCESSING'
  ))
  const hasPersistedProgress = sourceStates.some(({ processing, preparation }) => (
    hasProgress(processing) || hasProgress(preparation)
  ))
  const allPrepared = hasSources && sourceStates.every(({ processing, preparation }) => (
    completed(processing)
    && completed(preparation)
    && Array.isArray(preparation?.chunks?.chunks)
    && preparation.chunks.chunks.length > 0
  ))

  let n2State = WORKFLOW_NODE_STATES.NOT_STARTED
  if (hasFailure) n2State = WORKFLOW_NODE_STATES.FAILED
  else if (allPrepared) n2State = WORKFLOW_NODE_STATES.COMPLETE
  else if (hasActiveWork || hasPersistedProgress) n2State = WORKFLOW_NODE_STATES.RUNNING

  const states = {
    [REQUIREMENTS_NODE_IDS.INPUT_COLLECTION]: Object.values(WORKFLOW_NODE_STATES).includes(workflowState?.n1_state)
      ? workflowState.n1_state
      : WORKFLOW_NODE_STATES.NOT_STARTED,
    [REQUIREMENTS_NODE_IDS.PROCESSING_AND_CHUNKING]: n2State,
  }

  return Object.fromEntries(REQUIREMENTS_NODE_REGISTRY.map((definition) => [definition.id, {
    status: definition.active ? states[definition.id] : WORKFLOW_NODE_STATES.LOCKED,
    ...(definition.id === REQUIREMENTS_NODE_IDS.INPUT_COLLECTION
      && states[definition.id] === WORKFLOW_NODE_STATES.WAITING_FOR_HUMAN
      ? { statusLabel: 'Ready to Continue' }
      : {}),
    summary: definition.summary,
  }]))
}

export function deriveRequirementsCurrentNodeId({ loadStatus, workflowState }) {
  return loadStatus === 'success' && workflowState?.n1_state === WORKFLOW_NODE_STATES.COMPLETE
    ? REQUIREMENTS_NODE_IDS.PROCESSING_AND_CHUNKING
    : REQUIREMENTS_NODE_IDS.INPUT_COLLECTION
}

export function aggregateStageState(sources, stateBySource, { requireChunks = false } = {}) {
  if (sources.length === 0) return WORKFLOW_NODE_STATES.NOT_STARTED
  const states = sources.map((source) => stateBySource[source.source_id])
  if (states.some(failed)) return WORKFLOW_NODE_STATES.FAILED
  if (states.some((state) => state?.status === 'PROCESSING')) return WORKFLOW_NODE_STATES.RUNNING
  const allComplete = states.every((state) => (
    completed(state)
    && (!requireChunks || (Array.isArray(state?.chunks?.chunks) && state.chunks.chunks.length > 0))
  ))
  if (allComplete) return WORKFLOW_NODE_STATES.COMPLETE
  return states.some(hasProgress) ? WORKFLOW_NODE_STATES.RUNNING : WORKFLOW_NODE_STATES.NOT_STARTED
}
