import { MarkerType } from '@xyflow/react'

import { WORKFLOW_NODE_STATES } from '../constants/workflow.js'
import { DEFAULT_NODE_POSITIONS } from './layout.js'

export const IMPLEMENTATION_NODE_REGISTRY = Object.freeze([
  { id: 'PROJECT_SOURCES', title: 'Project & Sources', active: true, summary: 'Add trusted implementation inputs.' },
  { id: 'INPUT_ANALYSIS', title: 'Input Analysis', active: true, summary: 'Prepare and classify supplied sources.' },
  { id: 'SPECIFICATION_VERIFICATION', title: 'Specification Verification', active: true, summary: 'Review and verify extracted specifications.' },
  { id: 'IMPLEMENTATION_READINESS', title: 'Implementation Readiness', active: true, summary: 'Evaluate whether implementation can proceed.' },
  { id: 'DELIVERY_SETUP', title: 'Delivery Setup', active: true, summary: 'Connect GitHub and prepare a repository.' },
  { id: 'GENERATE_IMPLEMENTATION', title: 'Generate Implementation', active: false, summary: 'Not implemented yet.' },
  { id: 'BUILD_EXECUTE', title: 'Build & Execute', active: false, summary: 'Not implemented yet.' },
  { id: 'CORRECTION_VALIDATION', title: 'Correction & Validation', active: false, summary: 'Not implemented yet.' },
  { id: 'DELIVERY', title: 'Delivery', active: false, summary: 'Not implemented yet.' },
])

const edgePairs = [
  ['PROJECT_SOURCES', 'INPUT_ANALYSIS'],
  ['INPUT_ANALYSIS', 'SPECIFICATION_VERIFICATION'],
  ['SPECIFICATION_VERIFICATION', 'IMPLEMENTATION_READINESS'],
  ['IMPLEMENTATION_READINESS', 'DELIVERY_SETUP'],
  ['DELIVERY_SETUP', 'GENERATE_IMPLEMENTATION'],
  ['GENERATE_IMPLEMENTATION', 'BUILD_EXECUTE'],
  ['BUILD_EXECUTE', 'CORRECTION_VALIDATION'],
  ['CORRECTION_VALIDATION', 'DELIVERY'],
]

export const IMPLEMENTATION_WORKFLOW_EDGES = Object.freeze(edgePairs.map(([source, target]) => ({
  id: `${source}-${target}`,
  source,
  target,
  type: 'smoothstep',
  selectable: false,
  focusable: false,
  markerEnd: { type: MarkerType.ArrowClosed },
})))

function inputHasSource(input) {
  return input?.source_type === 'TEXT' ? Boolean(input.content?.trim()) : Boolean(input?.file)
}

export function deriveWorkflowPresentation(snapshot) {
  const inputs = snapshot?.inputs ?? []
  const sourceCount = inputs.filter(inputHasSource).length
  const preparedCount = inputs.filter((item) => ['SUCCESS', 'PARTIAL'].includes(item.chunks?.status)).length
  const verifiedCount = inputs.filter((item) => item.humanReviews?.review?.review_status === 'COMPLETE').length
  const attentionCount = inputs.filter((item) => item.error || item.extraction?.status === 'FAILED' || item.chunks?.status === 'FAILED').length
  const outputCount = snapshot?.selectedOutputs?.length ?? 0
  const readiness = snapshot?.readinessState
  const github = snapshot?.githubState
  const repository = snapshot?.repositoryState

  let readinessStatus = WORKFLOW_NODE_STATES.NOT_STARTED
  if (readiness?.status === 'evaluating') readinessStatus = WORKFLOW_NODE_STATES.RUNNING
  else if (readiness?.error || readiness?.stale) readinessStatus = WORKFLOW_NODE_STATES.NEEDS_ATTENTION
  else if (readiness?.result?.status === 'READY') readinessStatus = WORKFLOW_NODE_STATES.COMPLETE
  else if (readiness?.result?.status === 'READY_WITH_WARNINGS') readinessStatus = WORKFLOW_NODE_STATES.NEEDS_ATTENTION
  else if (readiness?.result?.status === 'NOT_READY') readinessStatus = WORKFLOW_NODE_STATES.BLOCKED

  let deliveryStatus = WORKFLOW_NODE_STATES.NOT_STARTED
  if (github?.status === 'loading' || repository?.status === 'loading' || repository?.status === 'creating') deliveryStatus = WORKFLOW_NODE_STATES.QUEUED
  else if (github?.status === 'error' || repository?.status === 'error') deliveryStatus = WORKFLOW_NODE_STATES.FAILED
  else if (repository?.status === 'created') deliveryStatus = WORKFLOW_NODE_STATES.COMPLETE
  else if (github?.status === 'connected') deliveryStatus = WORKFLOW_NODE_STATES.RUNNING

  return {
    PROJECT_SOURCES: {
      status: sourceCount > 0 || outputCount > 0 ? WORKFLOW_NODE_STATES.RUNNING : WORKFLOW_NODE_STATES.NOT_STARTED,
      summary: `${sourceCount} ${sourceCount === 1 ? 'source' : 'sources'} · ${outputCount} selected ${outputCount === 1 ? 'output' : 'outputs'}`,
      attentionCount,
    },
    INPUT_ANALYSIS: {
      status: preparedCount > 0 ? WORKFLOW_NODE_STATES.RUNNING : attentionCount > 0 ? WORKFLOW_NODE_STATES.NEEDS_ATTENTION : WORKFLOW_NODE_STATES.NOT_STARTED,
      summary: `${preparedCount} ${preparedCount === 1 ? 'source' : 'sources'} prepared · ${Math.max(sourceCount - preparedCount, 0)} pending`,
      attentionCount,
    },
    SPECIFICATION_VERIFICATION: {
      status: verifiedCount > 0 ? WORKFLOW_NODE_STATES.RUNNING : preparedCount > 0 ? WORKFLOW_NODE_STATES.WAITING_FOR_HUMAN : WORKFLOW_NODE_STATES.NOT_STARTED,
      summary: `${verifiedCount} verified · ${Math.max(preparedCount - verifiedCount, 0)} awaiting review`,
    },
    IMPLEMENTATION_READINESS: {
      status: readinessStatus,
      summary: readiness?.result ? `Latest result: ${readiness.result.status.replaceAll('_', ' ').toLowerCase()}` : 'No readiness evaluation yet.',
    },
    DELIVERY_SETUP: {
      status: deliveryStatus,
      summary: repository?.repository?.full_name ?? (github?.connection?.connected ? 'GitHub connected · repository not created' : 'GitHub is not connected.'),
    },
  }
}

export function createWorkflowNodes(presentation, onOpen) {
  return IMPLEMENTATION_NODE_REGISTRY.map((definition) => {
    const current = presentation[definition.id]
    return {
      id: definition.id,
      type: 'workflow',
      position: { ...DEFAULT_NODE_POSITIONS[definition.id] },
      data: {
        title: definition.title,
        summary: current?.summary ?? definition.summary,
        status: definition.active ? current?.status ?? WORKFLOW_NODE_STATES.NOT_STARTED : WORKFLOW_NODE_STATES.LOCKED,
        attentionCount: current?.attentionCount,
        locked: !definition.active,
        onOpen: () => onOpen(definition.id),
      },
    }
  })
}

export function getWorkflowNodeDefinition(nodeId) {
  return IMPLEMENTATION_NODE_REGISTRY.find((node) => node.id === nodeId) ?? null
}
