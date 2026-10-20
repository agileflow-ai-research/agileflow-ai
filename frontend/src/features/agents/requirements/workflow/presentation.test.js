import { describe, expect, it } from 'vitest'

import { WORKFLOW_NODE_STATES } from '../../../../components/agents/workflowState.js'
import { REQUIREMENTS_NODE_IDS, REQUIREMENTS_NODE_REGISTRY } from './nodeDefinitions.js'
import { deriveRequirementsCurrentNodeId, deriveRequirementsWorkflowPresentation } from './presentation.js'

const source = { source_id: 'DOC-001', source_type: 'DOCUMENT' }

function nodeState(presentation, id) {
  return presentation[id].status
}

describe('requirements workflow presentation', () => {
  it('keeps N1 and N2 incomplete when there are no sources', () => {
    const result = deriveRequirementsWorkflowPresentation({
      loadStatus: 'success', sources: [], processingStates: {}, preparationStates: {},
    })
    expect(nodeState(result, REQUIREMENTS_NODE_IDS.INPUT_COLLECTION)).toBe(WORKFLOW_NODE_STATES.NOT_STARTED)
    expect(nodeState(result, REQUIREMENTS_NODE_IDS.PROCESSING_AND_CHUNKING)).toBe(WORKFLOW_NODE_STATES.NOT_STARTED)
    expect(deriveRequirementsCurrentNodeId({ loadStatus: 'success', workflowState: { n1_state: 'NOT_STARTED' } })).toBe(REQUIREMENTS_NODE_IDS.INPUT_COLLECTION)
  })

  it('does not complete N1 for malformed or unsupported persisted sources', () => {
    const result = deriveRequirementsWorkflowPresentation({
      sources: [
        { source_id: '', source_type: 'DOCUMENT' },
        { source_id: 'TXT-001', source_type: 'TEXT' },
      ],
      processingStates: {},
      preparationStates: {},
    })
    expect(nodeState(result, REQUIREMENTS_NODE_IDS.INPUT_COLLECTION)).toBe(WORKFLOW_NODE_STATES.NOT_STARTED)
  })

  it('requires completed processing, completed preparation, and a valid chunk result', () => {
    const incomplete = deriveRequirementsWorkflowPresentation({
      loadStatus: 'success',
      sources: [source],
      processingStates: { 'DOC-001': { status: 'COMPLETED' } },
      preparationStates: { 'DOC-001': { status: 'COMPLETED', chunks: null } },
    })
    expect(nodeState(incomplete, REQUIREMENTS_NODE_IDS.PROCESSING_AND_CHUNKING)).toBe(WORKFLOW_NODE_STATES.RUNNING)

    const complete = deriveRequirementsWorkflowPresentation({
      loadStatus: 'success',
      sources: [source],
      processingStates: { 'DOC-001': { status: 'COMPLETED' } },
      preparationStates: { 'DOC-001': { status: 'COMPLETED', chunks: { chunks: [{ chunk_id: 'CHK-1' }] } } },
      workflowState: { n1_state: 'COMPLETE' },
    })
    expect(nodeState(complete, REQUIREMENTS_NODE_IDS.INPUT_COLLECTION)).toBe(WORKFLOW_NODE_STATES.COMPLETE)
    expect(nodeState(complete, REQUIREMENTS_NODE_IDS.PROCESSING_AND_CHUNKING)).toBe(WORKFLOW_NODE_STATES.COMPLETE)
  })

  it('uses authoritative N1 gate state and presents the human gate as ready to continue', () => {
    const waiting = deriveRequirementsWorkflowPresentation({
      sources: [source],
      processingStates: { 'DOC-001': { status: 'READY' } },
      preparationStates: { 'DOC-001': { status: 'READY' } },
      workflowState: { n1_state: 'WAITING_FOR_HUMAN' },
    })
    expect(waiting[REQUIREMENTS_NODE_IDS.INPUT_COLLECTION]).toMatchObject({
      status: WORKFLOW_NODE_STATES.WAITING_FOR_HUMAN,
      statusLabel: 'Ready to Continue',
    })
    expect(deriveRequirementsCurrentNodeId({
      loadStatus: 'success', workflowState: { n1_state: 'COMPLETE' },
    })).toBe(REQUIREMENTS_NODE_IDS.PROCESSING_AND_CHUNKING)
  })

  it('propagates failures and permanently locks all unimplemented nodes', () => {
    const result = deriveRequirementsWorkflowPresentation({
      loadStatus: 'success',
      sources: [source],
      processingStates: { 'DOC-001': { status: 'FAILED' } },
      preparationStates: { 'DOC-001': { status: 'READY' } },
    })
    expect(nodeState(result, REQUIREMENTS_NODE_IDS.PROCESSING_AND_CHUNKING)).toBe(WORKFLOW_NODE_STATES.FAILED)
    expect(REQUIREMENTS_NODE_REGISTRY.slice(2).every(
      (node) => nodeState(result, node.id) === WORKFLOW_NODE_STATES.LOCKED,
    )).toBe(true)
  })

  it('reports persisted partial progress as running while untouched sources stay not started', () => {
    const untouched = deriveRequirementsWorkflowPresentation({
      loadStatus: 'success',
      sources: [source],
      processingStates: { 'DOC-001': { status: 'READY' } },
      preparationStates: { 'DOC-001': { status: 'READY' } },
    })
    expect(nodeState(untouched, REQUIREMENTS_NODE_IDS.PROCESSING_AND_CHUNKING)).toBe(WORKFLOW_NODE_STATES.NOT_STARTED)

    const partial = deriveRequirementsWorkflowPresentation({
      loadStatus: 'success',
      sources: [source],
      processingStates: { 'DOC-001': { status: 'COMPLETED' } },
      preparationStates: { 'DOC-001': { status: 'READY' } },
    })
    expect(nodeState(partial, REQUIREMENTS_NODE_IDS.PROCESSING_AND_CHUNKING)).toBe(WORKFLOW_NODE_STATES.RUNNING)
  })

  it('gives validation/load errors precedence over completion', () => {
    const result = deriveRequirementsWorkflowPresentation({
      loadStatus: 'success',
      sources: [source],
      processingStates: { 'DOC-001': { status: 'COMPLETED' } },
      preparationStates: {
        'DOC-001': {
          status: 'COMPLETED',
          chunks: { chunks: [{ chunk_id: 'CHK-1' }] },
          requestError: 'Invalid prepared evidence.',
        },
      },
    })
    expect(nodeState(result, REQUIREMENTS_NODE_IDS.PROCESSING_AND_CHUNKING)).toBe(WORKFLOW_NODE_STATES.FAILED)
  })
})
