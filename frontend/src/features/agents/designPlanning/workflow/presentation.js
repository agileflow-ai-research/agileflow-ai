import { DESIGN_PLANNING_NODE_IDS, WORKFLOW_NODE_STATES } from '../constants/workflow.js'
import { DESIGN_PLANNING_NODE_REGISTRY } from './nodeDefinitions.js'
import {
  getPlanningErrors,
  specificationFields,
} from '../constants/agent2Config.js'

export function deriveDesignPlanningPresentation(workspaceSnapshot = {}) {
  const presentation = {}

  // Check if explicit node status overrides were supplied
  const explicitN1 = workspaceSnapshot[DESIGN_PLANNING_NODE_IDS.PROJECT_SPECIFICATIONS]
  const explicitN2 = workspaceSnapshot[DESIGN_PLANNING_NODE_IDS.OUTPUT_SELECTION]
  const explicitN3 = workspaceSnapshot[DESIGN_PLANNING_NODE_IDS.TECHNICAL_PLANNING]

  const input = workspaceSnapshot.input ?? {}
  const uploadStatus = workspaceSnapshot.uploadStatus ?? {}
  const selectedOutputs = workspaceSnapshot.selectedOutputs ?? []
  const specSourceCount = specificationFields.filter((field) => Boolean(input[field]?.trim())).length

  // Node 1: Project & Specifications
  let n1Status = WORKFLOW_NODE_STATES.NOT_STARTED
  let n1Label
  let n1Summary = 'Add or upload specification sources.'
  let n1Attention

  const isUploadingOrExtracting = Object.values(uploadStatus).some(
    (status) => status === 'UPLOADING' || status === 'EXTRACTING',
  )
  const hasUploadFailure = Object.values(uploadStatus).some((status) => status === 'FAILED')

  if (isUploadingOrExtracting) {
    n1Status = WORKFLOW_NODE_STATES.RUNNING
    n1Label = 'Extracting text...'
    n1Summary = 'Extracting specification text from document.'
  } else if (specSourceCount > 0) {
    n1Status = WORKFLOW_NODE_STATES.COMPLETE
    n1Summary = `${specSourceCount} ${specSourceCount === 1 ? 'source' : 'sources'} provided`
  } else if (hasUploadFailure) {
    n1Status = WORKFLOW_NODE_STATES.FAILED
    n1Summary = 'Document extraction failed.'
    n1Attention = 1
  }

  presentation[DESIGN_PLANNING_NODE_IDS.PROJECT_SPECIFICATIONS] = {
    status: explicitN1?.status ?? n1Status,
    statusLabel: explicitN1?.statusLabel ?? n1Label,
    summary: explicitN1?.summary ?? n1Summary,
    attentionCount: explicitN1?.attentionCount ?? n1Attention,
  }

  // Node 2: Output Selection
  const outputCount = selectedOutputs.length
  let n2Status = WORKFLOW_NODE_STATES.NOT_STARTED
  let n2Summary = 'Select desired design and planning outputs.'

  if (outputCount > 0) {
    n2Status = WORKFLOW_NODE_STATES.COMPLETE
    n2Summary = `${outputCount} of 14 outputs selected`
  }

  presentation[DESIGN_PLANNING_NODE_IDS.OUTPUT_SELECTION] = {
    status: explicitN2?.status ?? n2Status,
    statusLabel: explicitN2?.statusLabel,
    summary: explicitN2?.summary ?? n2Summary,
    attentionCount: explicitN2?.attentionCount,
  }

  // Node 3: Technical & Planning
  const planningErrors = getPlanningErrors(input, selectedOutputs)
  const hasPlanningErrors = Object.keys(planningErrors).length > 0
  const hasTechnicalInput = Boolean(
    input.preferred_technology_stack ||
    input.technical_constraints ||
    input.deployment_preference ||
    input.database_preference ||
    input.ui_ux_constraints ||
    input.architecture_notes,
  )
  const hasPlanningInput = Boolean(
    input.development_team_count ||
    input.sprint_duration ||
    input.expected_project_duration ||
    input.project_start_date ||
    input.developer_roles ||
    input.developer_skills ||
    input.team_composition,
  )

  let n3Status = WORKFLOW_NODE_STATES.NOT_STARTED
  let n3Label
  let n3Summary = 'Configure technical context and team parameters.'
  let n3Attention

  if (outputCount > 0) {
    if (hasPlanningErrors) {
      n3Status = WORKFLOW_NODE_STATES.WAITING_FOR_HUMAN
      n3Label = 'Action Required'
      n3Attention = Object.keys(planningErrors).length
      n3Summary = Object.values(planningErrors)[0]
    } else {
      n3Status = WORKFLOW_NODE_STATES.COMPLETE
      n3Summary = (hasTechnicalInput || hasPlanningInput)
        ? 'Technical context and team parameters configured.'
        : 'Contract-required inputs satisfied.'
    }
  } else if (hasTechnicalInput || hasPlanningInput) {
    n3Status = WORKFLOW_NODE_STATES.COMPLETE
    n3Summary = 'Technical context and team parameters configured.'
  }

  presentation[DESIGN_PLANNING_NODE_IDS.TECHNICAL_PLANNING] = {
    status: explicitN3?.status ?? n3Status,
    statusLabel: explicitN3?.statusLabel ?? n3Label,
    summary: explicitN3?.summary ?? n3Summary,
    attentionCount: explicitN3?.attentionCount ?? n3Attention,
  }

  // Node 4: Human Review
  const explicitN4 = workspaceSnapshot[DESIGN_PLANNING_NODE_IDS.HUMAN_REVIEW]
  const isN4Blocked = specSourceCount === 0 || outputCount === 0 || hasPlanningErrors
  const humanReviewApproved = Boolean(workspaceSnapshot.humanReviewApproved)

  let n4Status
  let n4Summary
  let n4Attention

  if (specSourceCount === 0 && outputCount === 0) {
    n4Status = WORKFLOW_NODE_STATES.NOT_STARTED
    n4Summary = 'Configure specifications and outputs before review.'
  } else if (isN4Blocked) {
    n4Status = WORKFLOW_NODE_STATES.BLOCKED
    n4Summary = specSourceCount === 0
      ? 'Blocked: Specification sources required'
      : outputCount === 0
        ? 'Blocked: Output selection required'
        : 'Blocked: Planning parameters required'
    n4Attention = hasPlanningErrors ? Object.keys(planningErrors).length : 1
  } else if (humanReviewApproved) {
    n4Status = WORKFLOW_NODE_STATES.COMPLETE
    n4Summary = 'Human review completed · Ready for generation.'
  } else {
    n4Status = WORKFLOW_NODE_STATES.WAITING_FOR_HUMAN
    n4Summary = 'Ready for human review before execution.'
  }

  presentation[DESIGN_PLANNING_NODE_IDS.HUMAN_REVIEW] = {
    status: explicitN4?.status ?? n4Status,
    statusLabel: explicitN4?.statusLabel,
    summary: explicitN4?.summary ?? n4Summary,
    attentionCount: explicitN4?.attentionCount ?? n4Attention,
  }

  // Node 5: Generate Design & Planning
  const explicitN5 = workspaceSnapshot[DESIGN_PLANNING_NODE_IDS.GENERATE_DESIGN_PLANNING]
  const runState = workspaceSnapshot.runState ?? 'idle'
  const runResult = workspaceSnapshot.runResult ?? null
  const runError = workspaceSnapshot.runError ?? ''
  const canRunNode5 = !isN4Blocked && humanReviewApproved

  let n5Status
  let n5Label
  let n5Summary
  let n5Attention

  if (runState === 'running') {
    n5Status = WORKFLOW_NODE_STATES.RUNNING
    n5Label = 'Generating...'
    n5Summary = 'Processing with local Qwen...'
  } else if (runState === 'completed') {
    n5Status = WORKFLOW_NODE_STATES.COMPLETE
    n5Summary = runResult?.run_id ? `Run ${runResult.run_id} completed` : 'Generation completed successfully'
  } else if (runState === 'failed') {
    n5Status = WORKFLOW_NODE_STATES.FAILED
    n5Summary = runError || 'Model execution failed.'
    n5Attention = 1
  } else if (!canRunNode5) {
    if (specSourceCount === 0 && outputCount === 0) {
      n5Status = WORKFLOW_NODE_STATES.NOT_STARTED
      n5Summary = 'Blocked until Human Review is approved'
    } else {
      n5Status = WORKFLOW_NODE_STATES.BLOCKED
      n5Summary = 'Blocked until Human Review is approved'
      n5Attention = 1
    }
  } else {
    n5Status = WORKFLOW_NODE_STATES.WAITING_FOR_HUMAN
    n5Summary = 'Ready to launch execution'
  }

  presentation[DESIGN_PLANNING_NODE_IDS.GENERATE_DESIGN_PLANNING] = {
    status: explicitN5?.status ?? n5Status,
    statusLabel: explicitN5?.statusLabel ?? n5Label,
    summary: explicitN5?.summary ?? n5Summary,
    attentionCount: explicitN5?.attentionCount ?? n5Attention,
  }

  // Nodes 6 to 8: Design Results, Planning Results, Validation & Traceability
  const isExecutionCompleted = runState === 'completed'
  const isExecutionFailed = runState === 'failed'
  const runsList = Array.isArray(workspaceSnapshot.runs) ? workspaceSnapshot.runs : []

  DESIGN_PLANNING_NODE_REGISTRY.slice(5).forEach((definition) => {
    const current = workspaceSnapshot[definition.id]
    let nodeStatus = WORKFLOW_NODE_STATES.NOT_STARTED
    let nodeSummary = definition.summary
    let nodeAttention

    const hasHistoricalCompleted = runsList.some((r) => r.status === 'COMPLETED')
    const hasResultsAvailable = isExecutionCompleted || hasHistoricalCompleted

    if (hasResultsAvailable) {
      nodeStatus = WORKFLOW_NODE_STATES.COMPLETE
      if (definition.id === DESIGN_PLANNING_NODE_IDS.DESIGN_RESULTS) {
        nodeSummary = 'Structured technical design deliverables ready'
      } else if (definition.id === DESIGN_PLANNING_NODE_IDS.PLANNING_RESULTS) {
        nodeSummary = 'Agile planning hierarchy and sprint schedule ready'
      } else if (definition.id === DESIGN_PLANNING_NODE_IDS.VALIDATION_TRACEABILITY) {
        nodeSummary = runsList.length > 0
          ? `${runsList.length} historical run${runsList.length === 1 ? '' : 's'} available`
          : 'Traceability matrix and quality metrics ready'
      }
    } else if (isExecutionFailed && definition.id === DESIGN_PLANNING_NODE_IDS.VALIDATION_TRACEABILITY) {
      nodeStatus = WORKFLOW_NODE_STATES.FAILED
      nodeSummary = 'Run failed validation · Review findings'
      nodeAttention = 1
    } else if (definition.id === DESIGN_PLANNING_NODE_IDS.VALIDATION_TRACEABILITY && runsList.length > 0) {
      nodeSummary = `${runsList.length} historical run${runsList.length === 1 ? '' : 's'} available`
    }

    presentation[definition.id] = {
      status: current?.status ?? nodeStatus,
      statusLabel: current?.statusLabel,
      summary: current?.summary ?? nodeSummary,
      attentionCount: current?.attentionCount ?? nodeAttention,
    }
  })

  return presentation
}
