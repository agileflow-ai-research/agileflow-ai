import { WORKFLOW_NODE_IDS } from '../constants/workflow.js'

export const IMPLEMENTATION_NODE_REGISTRY = Object.freeze([
  { id: WORKFLOW_NODE_IDS.PROJECT_SOURCES, title: 'Project & Sources', active: true, purpose: 'What information and outputs define this implementation project?', summary: 'Add trusted implementation inputs.' },
  { id: WORKFLOW_NODE_IDS.INPUT_ANALYSIS, title: 'Input Analysis', active: true, purpose: 'How well have this project’s input sources been analyzed?', summary: 'Prepare and classify supplied sources.' },
  { id: WORKFLOW_NODE_IDS.SPECIFICATION_VERIFICATION, title: 'Specification Verification', active: true, purpose: 'What should be implemented, and what still requires human confirmation?', summary: 'Review and verify extracted specifications.' },
  { id: WORKFLOW_NODE_IDS.IMPLEMENTATION_READINESS, title: 'Implementation Readiness', active: true, purpose: 'Is there enough trusted information to implement the selected outputs?', summary: 'Evaluate whether implementation can proceed.' },
  { id: WORKFLOW_NODE_IDS.DELIVERY_SETUP, title: 'Delivery Setup', active: true, purpose: 'Where should the generated implementation eventually be delivered?', summary: 'Connect GitHub and prepare a repository.' },
  { id: WORKFLOW_NODE_IDS.GENERATE_IMPLEMENTATION, title: 'Generate Implementation', active: true, purpose: 'Approve the final implementation plan and create an immutable AgentRun.', summary: 'Awaiting final pre-code approval.' },
  { id: WORKFLOW_NODE_IDS.BUILD_EXECUTE, title: 'Build & Execute', active: false, purpose: 'Generated implementation execution is planned for a later development phase.', summary: 'Reserved for future development.', reservedStatus: 'Reserved — future development', reservedHeadline: 'Reserved — build and execution', reservedDescription: 'Automated code generation, build execution, and runtime verification are not included in the current PP1 prototype.' },
  { id: WORKFLOW_NODE_IDS.CORRECTION_VALIDATION, title: 'Correction & Validation', active: false, purpose: 'Automated correction and validation are planned for a later development phase.', summary: 'Reserved for future development.', reservedStatus: 'Reserved — future development', reservedHeadline: 'Reserved — correction and validation', reservedDescription: 'Generated implementation corrections and validation cycles will be introduced after build execution is implemented.' },
  { id: WORKFLOW_NODE_IDS.DELIVERY, title: 'Delivery', active: false, purpose: 'Final implementation delivery is planned for a later development phase.', summary: 'Reserved for future development.', reservedStatus: 'Reserved — future development', reservedHeadline: 'Reserved — final delivery', reservedDescription: 'No generated code or final delivery artifact is produced by the current PP1 workflow.' },
])

export function getWorkflowNodeDefinition(nodeId) {
  return IMPLEMENTATION_NODE_REGISTRY.find((node) => node.id === nodeId) ?? null
}
