import { describe, expect, it } from 'vitest'

import { WORKFLOW_NODE_STATES } from '../../../../components/agents/workflowState.js'
import { REQUIREMENTS_NODE_IDS } from './nodeDefinitions.js'
import { deriveRequirementsWorkflowPresentation } from './presentation.js'

const source = { source_id: 'DOC-001', source_type: 'DOCUMENT' }

function nodeState(presentation, id) {
  return presentation.nodes.find((node) => node.id === id).state
}

describe('requirements workflow presentation', () => {
  it('keeps N1 and N2 incomplete when there are no sources', () => {
    const result = deriveRequirementsWorkflowPresentation({
      loadStatus: 'success', sources: [], processingStates: {}, preparationStates: {},
    })
    expect(nodeState(result, REQUIREMENTS_NODE_IDS.INPUT_COLLECTION)).toBe(WORKFLOW_NODE_STATES.NOT_STARTED)
    expect(nodeState(result, REQUIREMENTS_NODE_IDS.PROCESSING_AND_CHUNKING)).toBe(WORKFLOW_NODE_STATES.NOT_STARTED)
    expect(result.currentNodeId).toBe(REQUIREMENTS_NODE_IDS.INPUT_COLLECTION)
  })

  it('requires completed processing, completed preparation, and a valid chunk result', () => {
    const incomplete = deriveRequirementsWorkflowPresentation({
      loadStatus: 'success',
      sources: [source],
      processingStates: { 'DOC-001': { status: 'COMPLETED' } },
      preparationStates: { 'DOC-001': { status: 'COMPLETED', chunks: null } },
    })
    expect(nodeState(incomplete, REQUIREMENTS_NODE_IDS.PROCESSING_AND_CHUNKING)).toBe(WORKFLOW_NODE_STATES.NOT_STARTED)

    const complete = deriveRequirementsWorkflowPresentation({
      loadStatus: 'success',
      sources: [source],
      processingStates: { 'DOC-001': { status: 'COMPLETED' } },
      preparationStates: { 'DOC-001': { status: 'COMPLETED', chunks: { chunks: [{ chunk_id: 'CHK-1' }] } } },
    })
    expect(nodeState(complete, REQUIREMENTS_NODE_IDS.INPUT_COLLECTION)).toBe(WORKFLOW_NODE_STATES.COMPLETE)
    expect(nodeState(complete, REQUIREMENTS_NODE_IDS.PROCESSING_AND_CHUNKING)).toBe(WORKFLOW_NODE_STATES.COMPLETE)
  })

  it('propagates failures and permanently locks all unimplemented nodes', () => {
    const result = deriveRequirementsWorkflowPresentation({
      loadStatus: 'success',
      sources: [source],
      processingStates: { 'DOC-001': { status: 'FAILED' } },
      preparationStates: { 'DOC-001': { status: 'READY' } },
    })
    expect(nodeState(result, REQUIREMENTS_NODE_IDS.PROCESSING_AND_CHUNKING)).toBe(WORKFLOW_NODE_STATES.FAILED)
    expect(result.nodes.slice(2).every((node) => node.state === WORKFLOW_NODE_STATES.LOCKED)).toBe(true)
  })
})
