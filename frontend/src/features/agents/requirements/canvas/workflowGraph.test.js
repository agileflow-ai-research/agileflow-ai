import { MarkerType } from '@xyflow/react'
import { describe, expect, it } from 'vitest'

import { WORKFLOW_NODE_STATES } from '../../../../components/agents/workflowState.js'
import { REQUIREMENTS_NODE_IDS, REQUIREMENTS_NODE_REGISTRY } from '../workflow/nodeDefinitions.js'
import { REQUIREMENTS_DEFAULT_NODE_POSITIONS, positionRequirementsNodes } from './layout.js'
import {
  createRequirementsWorkflowNodes,
  REQUIREMENTS_EDGE_PAIRS,
  REQUIREMENTS_WORKFLOW_EDGES,
} from './workflowGraph.js'

describe('Agent 1 workflow graph', () => {
  it('defines exactly seven top-level nodes and six directional edges', () => {
    expect(REQUIREMENTS_NODE_REGISTRY).toHaveLength(7)
    expect(REQUIREMENTS_WORKFLOW_EDGES).toHaveLength(6)
    expect(REQUIREMENTS_EDGE_PAIRS).toEqual([
      [REQUIREMENTS_NODE_IDS.INPUT_COLLECTION, REQUIREMENTS_NODE_IDS.PROCESSING_AND_CHUNKING],
      [REQUIREMENTS_NODE_IDS.PROCESSING_AND_CHUNKING, REQUIREMENTS_NODE_IDS.DISCOVERY_AND_STRUCTURING],
      [REQUIREMENTS_NODE_IDS.DISCOVERY_AND_STRUCTURING, REQUIREMENTS_NODE_IDS.QUALITY_ENGINEERING],
      [REQUIREMENTS_NODE_IDS.QUALITY_ENGINEERING, REQUIREMENTS_NODE_IDS.CLARIFICATION_AND_REFINEMENT],
      [REQUIREMENTS_NODE_IDS.CLARIFICATION_AND_REFINEMENT, REQUIREMENTS_NODE_IDS.QUALITY_RECHECK_AND_ARTIFACTS],
      [REQUIREMENTS_NODE_IDS.QUALITY_RECHECK_AND_ARTIFACTS, REQUIREMENTS_NODE_IDS.REVIEW_AND_BASELINE],
    ])
    expect(REQUIREMENTS_WORKFLOW_EDGES.every(
      (edge) => edge.type === 'floating' && edge.markerEnd.type === MarkerType.ArrowClosed,
    )).toBe(true)
    expect(REQUIREMENTS_NODE_REGISTRY.map((node) => node.title)).toEqual([
      'Project & Client Input Collection',
      'Multimodal Processing & Chunking',
      'Requirement Discovery & Structuring',
      'Requirement Quality Engineering',
      'Human Clarification & Refinement',
      'Quality Re-check & Artifact Generation',
      'Human Review & Requirement Baseline',
    ])
    expect(REQUIREMENTS_NODE_REGISTRY.some((node) => /Document Processing|Audio Transcription|Video Processing|Evidence Preparation/.test(node.title))).toBe(false)
  })

  it('uses the Agent 1-owned snake layout and locks N3 through N7', () => {
    const presentation = {
      [REQUIREMENTS_NODE_IDS.INPUT_COLLECTION]: { status: WORKFLOW_NODE_STATES.COMPLETE },
      [REQUIREMENTS_NODE_IDS.PROCESSING_AND_CHUNKING]: { status: WORKFLOW_NODE_STATES.RUNNING },
    }
    const nodes = createRequirementsWorkflowNodes(presentation)
    expect(nodes.map((node) => node.position)).toEqual([
      { x: 0, y: 20 },
      { x: 270, y: 20 },
      { x: 540, y: 20 },
      { x: 810, y: 20 },
      { x: 810, y: 250 },
      { x: 540, y: 250 },
      { x: 270, y: 250 },
    ])
    expect(nodes.slice(2).every(
      (node) => node.data.status === WORKFLOW_NODE_STATES.LOCKED && node.data.locked,
    )).toBe(true)
  })

  it('restores supplied nodes to the default layout without mutating input', () => {
    const nodes = [{ id: REQUIREMENTS_NODE_IDS.INPUT_COLLECTION, position: { x: 99, y: 99 } }]
    const positioned = positionRequirementsNodes(nodes)
    expect(positioned[0].position).toEqual(REQUIREMENTS_DEFAULT_NODE_POSITIONS[REQUIREMENTS_NODE_IDS.INPUT_COLLECTION])
    expect(nodes[0].position).toEqual({ x: 99, y: 99 })
  })
})
