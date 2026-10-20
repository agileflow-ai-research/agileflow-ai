import { WORKFLOW_NODE_STATES } from '../../../../components/agents/workflowState.js'
import { REQUIREMENTS_NODE_DEFINITIONS, REQUIREMENTS_NODE_IDS } from './nodeDefinitions.js'

const completed = (state) => state?.status === 'COMPLETED'
const failed = (state) => state?.status === 'FAILED' || Boolean(state?.requestError)

export function deriveRequirementsWorkflowPresentation({
  loadStatus,
  sources,
  processingStates,
  preparationStates,
}) {
  const sourceList = Array.isArray(sources) ? sources : []
  const hasSources = sourceList.length > 0
  const sourceStates = sourceList.map((source) => ({
    processing: processingStates[source.source_id],
    preparation: preparationStates[source.source_id],
  }))

  const hasFailure = sourceStates.some(({ processing, preparation }) => (
    failed(processing) || failed(preparation)
  ))
  const hasRunning = sourceStates.some(({ processing, preparation }) => (
    processing?.status === 'PROCESSING' || preparation?.status === 'PROCESSING'
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
  else if (hasRunning) n2State = WORKFLOW_NODE_STATES.RUNNING
  else if (hasSources) n2State = WORKFLOW_NODE_STATES.NOT_STARTED

  const states = {
    [REQUIREMENTS_NODE_IDS.INPUT_COLLECTION]: hasSources
      ? WORKFLOW_NODE_STATES.COMPLETE
      : WORKFLOW_NODE_STATES.NOT_STARTED,
    [REQUIREMENTS_NODE_IDS.PROCESSING_AND_CHUNKING]: n2State,
  }

  const nodes = REQUIREMENTS_NODE_DEFINITIONS.map((definition) => ({
    ...definition,
    state: definition.implemented
      ? states[definition.id]
      : WORKFLOW_NODE_STATES.LOCKED,
  }))

  return {
    nodes,
    currentNodeId: loadStatus === 'success' && hasSources
      ? REQUIREMENTS_NODE_IDS.PROCESSING_AND_CHUNKING
      : REQUIREMENTS_NODE_IDS.INPUT_COLLECTION,
    n2Complete: allPrepared,
  }
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
  return allComplete ? WORKFLOW_NODE_STATES.COMPLETE : WORKFLOW_NODE_STATES.NOT_STARTED
}
