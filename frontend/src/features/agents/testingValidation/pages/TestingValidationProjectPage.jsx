import { useCallback, useEffect, useMemo, useRef, useState } from 'react'

import WorkflowControls from '../../../../components/agents/workflow/WorkflowControls.jsx'
import WorkflowNodeModal from '../../../../components/agents/workflow/WorkflowNodeModal.jsx'
import ErrorState from '../../../../components/feedback/ErrorState.jsx'
import LoadingState from '../../../../components/feedback/LoadingState.jsx'
import { getWorkflowStatePresentation } from '../../../../components/agents/workflowState.js'
import StatusBadge from '../../../../components/ui/StatusBadge.jsx'
import TestingValidationCanvas from '../canvas/TestingValidationCanvas.jsx'
import useTestingValidationWorkflow from '../hooks/useTestingValidationWorkflow.js'
import ContextTestabilityPanel from '../panels/ContextTestabilityPanel.jsx'
import InputOutputSetupPanel from '../panels/InputOutputSetupPanel.jsx'
import InputPreparationPanel from '../panels/InputPreparationPanel.jsx'
import TestGenerationResultsPanel from '../panels/TestGenerationResultsPanel.jsx'
import TestingIntelligencePanel from '../panels/TestingIntelligencePanel.jsx'
import TestingFactExtractionPanel from '../panels/TestingFactExtractionPanel.jsx'
import TestPlanningReviewPanel from '../panels/TestPlanningReviewPanel.jsx'
import {
  getTestingValidationNodeDefinition,
  TESTING_VALIDATION_NODE_IDS,
} from '../workflow/nodeDefinitions.js'
import { createTestingValidationWorkflowPresentation } from '../workflow/presentation.js'

const panelByNodeId = Object.freeze({
  [TESTING_VALIDATION_NODE_IDS.INPUT_OUTPUT_SETUP]: InputOutputSetupPanel,
  [TESTING_VALIDATION_NODE_IDS.INPUT_PREPARATION]: InputPreparationPanel,
  [TESTING_VALIDATION_NODE_IDS.TESTING_INTELLIGENCE]: TestingIntelligencePanel,
  [TESTING_VALIDATION_NODE_IDS.TESTING_FACT_EXTRACTION]: TestingFactExtractionPanel,
  [TESTING_VALIDATION_NODE_IDS.CONTEXT_TESTABILITY]: ContextTestabilityPanel,
  [TESTING_VALIDATION_NODE_IDS.TEST_PLANNING_REVIEW]: TestPlanningReviewPanel,
  [TESTING_VALIDATION_NODE_IDS.TEST_GENERATION_RESULTS]: TestGenerationResultsPanel,
})

function TestingValidationProjectPage({ project, projectStatus, projectActions, entryMode = 'created' }) {
  const canvasRef = useRef(null)
  const enteringExistingProject = entryMode === 'existing'
  const [selectedNodeId, setSelectedNodeId] = useState(
    enteringExistingProject ? null : TESTING_VALIDATION_NODE_IDS.INPUT_OUTPUT_SETUP,
  )
  const {
    confirmationError,
    confirmationSubmitting,
    confirmN1,
    loadError,
    loadStatus,
    outputSaveError,
    outputSaving,
    preparationError,
    intelligenceError,
    intelligenceReview,
    contextActionSubmitting,
    contextError,
    contextResult,
    retry,
    retryPreparationSource,
    retryIntelligenceSource,
    retryContextAnalysis,
    retryingIntelligenceSourceId,
    retryingSourceId,
    reviewSubmitting,
    saveOutputs,
    submitIntelligenceReview,
    acknowledgeContextWarnings,
    workflowState,
  } = useTestingValidationWorkflow(project.agent_project_id)
  const presentation = useMemo(
    () => workflowState
      ? createTestingValidationWorkflowPresentation(workflowState)
      : null,
    [workflowState],
  )
  const selectedDefinition = presentation
    ? getTestingValidationNodeDefinition(selectedNodeId)
    : null
  const selectedPresentation = selectedDefinition
    ? { ...selectedDefinition, ...presentation[selectedDefinition.id] }
    : null
  const SelectedPanel = selectedDefinition ? panelByNodeId[selectedDefinition.id] : null

  const handleSelectNode = useCallback((nodeId) => {
    setSelectedNodeId(nodeId)
  }, [])

  const handleCloseModal = useCallback(() => {
    setSelectedNodeId(null)
  }, [])

  const handleConfirmN1 = useCallback(async () => {
    const workflow = await confirmN1()
    if (workflow) setSelectedNodeId(TESTING_VALIDATION_NODE_IDS.INPUT_PREPARATION)
    return workflow
  }, [confirmN1])

  useEffect(() => {
    if (!enteringExistingProject && loadStatus === 'success') {
      canvasRef.current?.focusNode(TESTING_VALIDATION_NODE_IDS.INPUT_OUTPUT_SETUP)
    }
  }, [enteringExistingProject, loadStatus, project.agent_project_id])

  return (
    <section className="min-w-0 space-y-4" aria-labelledby="testing-validation-canvas-title">
      <header className="flex flex-col gap-4 border-b border-default pb-4 xl:flex-row xl:items-center xl:justify-between">
        <div>
          <div className="flex flex-wrap items-center gap-3">
            <h1 id="testing-validation-canvas-title" className="text-page-heading font-semibold text-content-primary">{project.name}</h1>
            <StatusBadge label={projectStatus.label} tone={projectStatus.tone} />
          </div>
          <p className="mt-1 text-sm text-content-secondary">Agent 4 — Test Generation</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <WorkflowControls
            onAutoArrange={() => canvasRef.current?.autoArrange()}
            onResetLayout={() => canvasRef.current?.resetLayout()}
          />
          {projectActions}
        </div>
      </header>

      <div className="overflow-hidden rounded-panel border border-default bg-surface">
        {loadStatus === 'loading' ? (
          <LoadingState message="Loading Test Generation workflow" />
        ) : loadStatus === 'error' ? (
          <div className="p-4 sm:p-6">
            <ErrorState
              title="Unable to load Test Generation workflow"
              message={loadError}
              onRetry={retry}
              retryLabel="Retry"
            />
          </div>
        ) : (
          <div className="min-w-0 bg-canvas">
            <TestingValidationCanvas
              ref={canvasRef}
              presentation={presentation}
              selectedNodeId={selectedNodeId ?? workflowState.current_node_id}
              onSelectNode={handleSelectNode}
            />
          </div>
        )}
        <WorkflowNodeModal
          node={selectedPresentation}
          open={Boolean(selectedDefinition)}
          onClose={handleCloseModal}
          eyebrow="Agent 4 · Test Generation workflow"
        >
          {SelectedPanel ? (
            <SelectedPanel
              agentProjectId={project.agent_project_id}
              confirmationError={confirmationError}
              confirmationSubmitting={confirmationSubmitting}
              definition={selectedDefinition}
              n1Confirmation={workflowState.n1_confirmation}
              onConfirmN1={handleConfirmN1}
              onSaveOutputs={saveOutputs}
              outputSaveError={outputSaveError}
              outputSaving={outputSaving}
              selectedOutputs={workflowState.selected_outputs}
              selectionRevision={workflowState.selection_revision}
              pipelineStatus={workflowState.pipeline_status}
              n2Execution={workflowState.n2_execution}
              n3Execution={workflowState.n3_execution}
              n4Execution={workflowState.n4_execution}
              contextActionSubmitting={contextActionSubmitting}
              contextError={contextError}
              contextResult={contextResult}
              onAcknowledgeContextWarnings={acknowledgeContextWarnings}
              onRetryContextAnalysis={retryContextAnalysis}
              onRetryPreparationSource={retryPreparationSource}
              preparationError={preparationError}
              intelligenceError={intelligenceError}
              intelligenceReview={intelligenceReview}
              onRetryIntelligenceSource={retryIntelligenceSource}
              onSubmitIntelligenceReview={submitIntelligenceReview}
              retryingIntelligenceSourceId={retryingIntelligenceSourceId}
              reviewSubmitting={reviewSubmitting}
              retryingSourceId={retryingSourceId}
              workflowNodeStatus={workflowState.nodes.find(
                (node) => node.node_id === selectedDefinition.id,
              )?.status}
              statusLabel={selectedPresentation.statusLabel ?? getWorkflowStatePresentation(
                selectedPresentation.status,
              ).label}
            />
          ) : null}
        </WorkflowNodeModal>
      </div>

      <p className="text-xs text-content-muted">Workflow status and Input Preparation progress are loaded from the persisted Stage 1 record. Node positions remain visual only.</p>
    </section>
  )
}

export default TestingValidationProjectPage
