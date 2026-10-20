export const REQUIREMENTS_NODE_IDS = Object.freeze({
  INPUT_COLLECTION: 'INPUT_COLLECTION',
  PROCESSING_AND_CHUNKING: 'PROCESSING_AND_CHUNKING',
  DISCOVERY_AND_STRUCTURING: 'DISCOVERY_AND_STRUCTURING',
  QUALITY_ENGINEERING: 'QUALITY_ENGINEERING',
  CLARIFICATION_AND_REFINEMENT: 'CLARIFICATION_AND_REFINEMENT',
  QUALITY_RECHECK_AND_ARTIFACTS: 'QUALITY_RECHECK_AND_ARTIFACTS',
  REVIEW_AND_BASELINE: 'REVIEW_AND_BASELINE',
})

export const REQUIREMENTS_NODE_DEFINITIONS = Object.freeze([
  Object.freeze({
    id: REQUIREMENTS_NODE_IDS.INPUT_COLLECTION,
    shortTitle: 'Input Collection',
    title: 'Project & Client Input Collection',
    implemented: true,
  }),
  Object.freeze({
    id: REQUIREMENTS_NODE_IDS.PROCESSING_AND_CHUNKING,
    shortTitle: 'Processing & Chunking',
    title: 'Multimodal Processing & Chunking',
    implemented: true,
  }),
  Object.freeze({
    id: REQUIREMENTS_NODE_IDS.DISCOVERY_AND_STRUCTURING,
    shortTitle: 'Discovery & Structuring',
    title: 'Requirement Discovery & Structuring',
    implemented: false,
  }),
  Object.freeze({
    id: REQUIREMENTS_NODE_IDS.QUALITY_ENGINEERING,
    shortTitle: 'Quality Engineering',
    title: 'Requirement Quality Engineering',
    implemented: false,
  }),
  Object.freeze({
    id: REQUIREMENTS_NODE_IDS.CLARIFICATION_AND_REFINEMENT,
    shortTitle: 'Clarification & Refinement',
    title: 'Human Clarification & Refinement',
    implemented: false,
  }),
  Object.freeze({
    id: REQUIREMENTS_NODE_IDS.QUALITY_RECHECK_AND_ARTIFACTS,
    shortTitle: 'Re-check & Artifacts',
    title: 'Quality Re-check & Artifact Generation',
    implemented: false,
  }),
  Object.freeze({
    id: REQUIREMENTS_NODE_IDS.REVIEW_AND_BASELINE,
    shortTitle: 'Review & Baseline',
    title: 'Human Review & Requirement Baseline',
    implemented: false,
  }),
])
