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
    purpose: 'Collect independently traceable document, audio, and video requirement sources.',
    summary: 'Collect client evidence',
    active: true,
  }),
  Object.freeze({
    id: REQUIREMENTS_NODE_IDS.PROCESSING_AND_CHUNKING,
    shortTitle: 'Processing & Chunking',
    title: 'Multimodal Processing & Chunking',
    purpose: 'Process each source and prepare deterministic, provenance-preserving evidence chunks.',
    summary: 'Process and prepare evidence',
    active: true,
  }),
  Object.freeze({
    id: REQUIREMENTS_NODE_IDS.DISCOVERY_AND_STRUCTURING,
    shortTitle: 'Discovery & Structuring',
    title: 'Requirement Discovery & Structuring',
    purpose: 'Discover and structure requirements from prepared evidence.',
    summary: 'Discover structured requirements',
    active: true,
  }),
  Object.freeze({
    id: REQUIREMENTS_NODE_IDS.QUALITY_ENGINEERING,
    shortTitle: 'Quality Engineering',
    title: 'Requirement Quality Engineering',
    purpose: 'Evaluate requirement quality and identify actionable issues.',
    summary: 'Engineer requirement quality',
    active: true,
  }),
  Object.freeze({
    id: REQUIREMENTS_NODE_IDS.CLARIFICATION_AND_REFINEMENT,
    shortTitle: 'Clarification & Refinement',
    title: 'Human Clarification & Refinement',
    purpose: 'Resolve requirement ambiguity with human clarification and refinement.',
    summary: 'Clarify and refine requirements',
    reservedStatus: 'Reserved — next phase',
    reservedHeadline: 'Reserved — human clarification is not implemented in PP1',
    reservedDescription: 'Quality findings identified in Requirement Quality Engineering will eventually be reviewed, confirmed, corrected, and refined here with human input.',
    reservedNote: 'No action is available in the current PP1 workflow.',
    active: false,
  }),
  Object.freeze({
    id: REQUIREMENTS_NODE_IDS.QUALITY_RECHECK_AND_ARTIFACTS,
    shortTitle: 'Re-check & Artifacts',
    title: 'Quality Re-check & Artifact Generation',
    purpose: 'Re-check quality and generate the required requirement artifacts.',
    summary: 'Re-check and generate artifacts',
    reservedStatus: 'Reserved — future development',
    reservedHeadline: 'Reserved — quality re-check and artifact generation',
    reservedDescription: 'After human clarification, requirements will be re-checked and selected artifacts such as User Stories, Acceptance Criteria, Personas, and SRS will be generated here.',
    reservedNote: 'Not included in the current PP1 prototype.',
    active: false,
  }),
  Object.freeze({
    id: REQUIREMENTS_NODE_IDS.REVIEW_AND_BASELINE,
    shortTitle: 'Review & Baseline',
    title: 'Human Review & Requirement Baseline',
    purpose: 'Complete human review and establish the requirement baseline.',
    summary: 'Review and baseline requirements',
    reservedStatus: 'Reserved — future development',
    reservedHeadline: 'Reserved — final review and baseline',
    reservedDescription: 'Final human approval and requirement baseline creation are planned for a later development phase.',
    reservedNote: 'No final approval or baseline is persisted by the current PP1 workflow.',
    active: false,
  }),
])

export const REQUIREMENTS_NODE_REGISTRY = REQUIREMENTS_NODE_DEFINITIONS

export function getRequirementNodeDefinition(nodeId) {
  return REQUIREMENTS_NODE_REGISTRY.find((node) => node.id === nodeId) ?? null
}
