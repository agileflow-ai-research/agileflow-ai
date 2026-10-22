import { WORKFLOW_NODE_STATES } from '../../../../components/agents/workflowState.js'
import { REQUIREMENTS_NODE_IDS, REQUIREMENTS_NODE_REGISTRY } from './nodeDefinitions.js'

const completed = (state) => state?.status === 'COMPLETED'
const failed = (state) => state?.status === 'FAILED' || Boolean(state?.requestError)
const hasProgress = (state) => Boolean(state) && ![undefined, null, 'READY'].includes(state.status)
export function deriveRequirementsWorkflowPresentation({
  workflowState,
}) {
  const authoritativeN2 = workflowState?.n2_execution
  let n2State = WORKFLOW_NODE_STATES.NOT_STARTED
  if (authoritativeN2 && workflowState?.n2_is_current === false) {
    n2State = WORKFLOW_NODE_STATES.BLOCKED
  } else if (authoritativeN2?.status) {
    n2State = WORKFLOW_NODE_STATES[authoritativeN2.status]
      ?? WORKFLOW_NODE_STATES.NOT_STARTED
  }

  const states = {
    [REQUIREMENTS_NODE_IDS.INPUT_COLLECTION]: Object.values(WORKFLOW_NODE_STATES).includes(workflowState?.n1_state)
      ? workflowState.n1_state
      : WORKFLOW_NODE_STATES.NOT_STARTED,
    [REQUIREMENTS_NODE_IDS.PROCESSING_AND_CHUNKING]: n2State,
    [REQUIREMENTS_NODE_IDS.DISCOVERY_AND_STRUCTURING]: workflowState?.n3_execution?.status
      ? WORKFLOW_NODE_STATES[workflowState.n3_execution.status]
      : authoritativeN2?.status === 'COMPLETE'
        ? WORKFLOW_NODE_STATES.NOT_STARTED
        : WORKFLOW_NODE_STATES.LOCKED,
    [REQUIREMENTS_NODE_IDS.QUALITY_ENGINEERING]: workflowState?.n4_execution?.status
      ? WORKFLOW_NODE_STATES[workflowState.n4_execution.status]
      : workflowState?.n3_execution?.status === 'COMPLETE'
        ? WORKFLOW_NODE_STATES.NOT_STARTED
        : WORKFLOW_NODE_STATES.LOCKED,
  }

  return Object.fromEntries(REQUIREMENTS_NODE_REGISTRY.map((definition) => [definition.id, {
    status: definition.active ? states[definition.id] : WORKFLOW_NODE_STATES.LOCKED,
    ...(definition.id === REQUIREMENTS_NODE_IDS.INPUT_COLLECTION
      && states[definition.id] === WORKFLOW_NODE_STATES.WAITING_FOR_HUMAN
      ? { statusLabel: 'Ready to Continue' }
      : {}),
    summary: definition.id === REQUIREMENTS_NODE_IDS.QUALITY_ENGINEERING
      ? workflowState?.n4_execution?.status === 'COMPLETE'
        ? `${workflowState.n4_execution.result_summary?.total_finding_count ?? 0} findings · ${workflowState.n4_execution.result_summary?.clarification_candidate_count ?? 0} require human review`
        : workflowState?.n4_execution?.status === 'RUNNING' ? 'Analyzing requirement quality'
          : workflowState?.n4_execution?.status === 'QUEUED' ? 'Quality analysis queued'
            : workflowState?.n4_execution?.status === 'FAILED' ? 'Quality analysis failed'
              : workflowState?.n4_execution?.status === 'BLOCKED' ? 'Quality analysis blocked'
                : states[definition.id] === WORKFLOW_NODE_STATES.LOCKED ? 'Waiting for Requirement Discovery' : definition.summary
      : definition.id === REQUIREMENTS_NODE_IDS.DISCOVERY_AND_STRUCTURING
      && workflowState?.n3_execution?.status === 'COMPLETE'
      ? `${workflowState.n3_execution.result_summary?.candidate_count ?? 0} candidates · ${workflowState.n3_execution.result_summary?.functional_requirement_count ?? 0} FR · ${workflowState.n3_execution.result_summary?.non_functional_requirement_count ?? 0} NFR · ${workflowState.n3_execution.result_summary?.excluded_candidate_count ?? 0} OTHER`
      : definition.summary,
  }]))
}

export function deriveRequirementsCurrentNodeId({ loadStatus, workflowState }) {
  if (loadStatus === 'success' && workflowState?.n4_execution) return REQUIREMENTS_NODE_IDS.QUALITY_ENGINEERING
  if (loadStatus === 'success' && workflowState?.n3_execution) {
    return REQUIREMENTS_NODE_IDS.DISCOVERY_AND_STRUCTURING
  }
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

export function aggregateExecutionStageState(
  workflowState,
  sourceType,
  { preparation = false } = {},
) {
  const execution = workflowState?.n2_execution
  if (!execution) return null
  const sourceIds = (execution.input_sources ?? [])
    .filter((source) => !sourceType || source.source_type === sourceType)
    .map((source) => source.source_id)
  if (sourceIds.length === 0) return null
  if (workflowState?.n2_is_current === false || execution.status === 'BLOCKED') {
    return WORKFLOW_NODE_STATES.BLOCKED
  }

  const progress = sourceIds.map((sourceId) => (
    execution.source_progress?.find((source) => source.source_id === sourceId)
  ))
  const statusField = preparation ? 'preparation_status' : 'processing_status'
  if (progress.some((source) => source?.[statusField] === 'FAILED')) {
    return WORKFLOW_NODE_STATES.FAILED
  }
  const allComplete = progress.every((source) => (
    source?.[statusField] === 'COMPLETE'
    && (!preparation || source.chunk_count > 0)
  ))
  if (allComplete) return WORKFLOW_NODE_STATES.COMPLETE
  if (execution.status === 'COMPLETE') return WORKFLOW_NODE_STATES.FAILED
  if (
    ['QUEUED', 'RUNNING'].includes(execution.status)
    || progress.some((source) => source?.[statusField] === 'RUNNING')
  ) {
    return WORKFLOW_NODE_STATES.RUNNING
  }
  return execution.status === 'FAILED'
    ? WORKFLOW_NODE_STATES.FAILED
    : WORKFLOW_NODE_STATES.NOT_STARTED
}
