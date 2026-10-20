import { useEffect } from 'react'

import ErrorState from '../../../components/feedback/ErrorState.jsx'
import LoadingState from '../../../components/feedback/LoadingState.jsx'
import EvidenceProcessingNode from './nodes/EvidenceProcessingNode.jsx'
import LockedNodeState from './nodes/LockedNodeState.jsx'
import RequirementSourcesNode from './nodes/RequirementSourcesNode.jsx'
import N2OrchestrationStatus from './nodes/N2OrchestrationStatus.jsx'
import useRequirementEvidenceWorkflow from './hooks/useRequirementEvidenceWorkflow.js'
import { getRequirementNodeDefinition, REQUIREMENTS_NODE_IDS } from './workflow/nodeDefinitions.js'

function RequirementsWorkspace({
  project,
  activeSection = REQUIREMENTS_NODE_IDS.INPUT_COLLECTION,
  onPresentationChange,
  onNavigateNode,
}) {
  const workflow = useRequirementEvidenceWorkflow(project.agent_project_id)

  useEffect(() => {
    onPresentationChange?.({
      loadStatus: workflow.loadStatus,
      sources: workflow.sources,
      processingStates: workflow.processingStates,
      preparationStates: workflow.preparationStates,
      workflowState: workflow.workflowState,
    })
  }, [
    onPresentationChange,
    workflow.loadStatus,
    workflow.preparationStates,
    workflow.processingStates,
    workflow.sources,
    workflow.workflowState,
  ])

  const activeNode = getRequirementNodeDefinition(activeSection)

  return (
    <div className="space-y-6">
      {workflow.error ? (
        <ErrorState
          title="Requirements workspace unavailable"
          message={workflow.error}
          onRetry={workflow.loadStatus === 'error' ? workflow.reload : undefined}
        />
      ) : null}

      {workflow.loadStatus === 'loading' ? (
        <LoadingState message="Loading requirements workflow" />
      ) : null}

      {workflow.loadStatus === 'success' && activeSection === REQUIREMENTS_NODE_IDS.INPUT_COLLECTION ? (
        <RequirementSourcesNode
          sources={workflow.sources}
          uploadingType={workflow.uploadingType}
          removingId={workflow.removingId}
          onAddFiles={workflow.addFiles}
          onRemoveSource={workflow.removeSource}
          selectedOutputs={workflow.workflowState?.selected_outputs ?? []}
          outputSaving={workflow.outputSaving}
          continueSubmitting={workflow.continueSubmitting}
          workflowError={workflow.workflowError}
          n1State={workflow.workflowState?.n1_state}
          onSelectedOutputsChange={workflow.changeSelectedOutputs}
          onContinue={workflow.continueN1}
        />
      ) : null}

      {workflow.loadStatus === 'success' && activeSection === REQUIREMENTS_NODE_IDS.PROCESSING_AND_CHUNKING ? (
        <div className="space-y-5">
          <N2OrchestrationStatus
            workflowState={workflow.workflowState}
            retrying={workflow.n2Retrying}
            error={workflow.workflowError}
            onRetry={workflow.retryN2}
          />
          {workflow.detailsLoading ? (
            <p role="status" className="text-sm text-content-secondary">
              Refreshing persisted source details...
            </p>
          ) : null}
          <EvidenceProcessingNode
            sources={workflow.sources}
            processingStates={workflow.processingStates}
            preparationStates={workflow.preparationStates}
            orchestrationManaged={Boolean(workflow.workflowState?.n2_execution)}
            workflowState={workflow.workflowState}
            onProcessSource={workflow.processSource}
            onLoadProcessingResult={workflow.loadProcessingResult}
            onPrepareSource={workflow.prepareSource}
            onLoadPreparedEvidence={workflow.loadPreparedEvidence}
            onOpenCollection={() => onNavigateNode?.(REQUIREMENTS_NODE_IDS.INPUT_COLLECTION)}
          />
        </div>
      ) : null}

      {workflow.loadStatus === 'success' && activeNode && !activeNode.active ? (
        <LockedNodeState node={activeNode} />
      ) : null}
    </div>
  )
}

export default RequirementsWorkspace
