import { useEffect, useMemo, useRef, useState } from 'react'

import WorkflowPipelineNavigation from '../../../components/agents/WorkflowPipelineNavigation.jsx'
import ErrorState from '../../../components/feedback/ErrorState.jsx'
import LoadingState from '../../../components/feedback/LoadingState.jsx'
import EvidenceProcessingNode from './nodes/EvidenceProcessingNode.jsx'
import LockedNodeState from './nodes/LockedNodeState.jsx'
import RequirementSourcesNode from './nodes/RequirementSourcesNode.jsx'
import useRequirementEvidenceWorkflow from './hooks/useRequirementEvidenceWorkflow.js'
import { REQUIREMENTS_NODE_IDS } from './workflow/nodeDefinitions.js'
import { deriveRequirementsWorkflowPresentation } from './workflow/presentation.js'

function RequirementsWorkspace({ project }) {
  const workflow = useRequirementEvidenceWorkflow(project.agent_project_id)
  const manualSelection = useRef(false)
  const initialSelectionApplied = useRef(false)
  const [activeNodeId, setActiveNodeId] = useState(REQUIREMENTS_NODE_IDS.INPUT_COLLECTION)
  const presentation = useMemo(() => deriveRequirementsWorkflowPresentation({
    loadStatus: workflow.loadStatus,
    sources: workflow.sources,
    processingStates: workflow.processingStates,
    preparationStates: workflow.preparationStates,
  }), [
    workflow.loadStatus,
    workflow.preparationStates,
    workflow.processingStates,
    workflow.sources,
  ])

  useEffect(() => {
    if (
      workflow.loadStatus === 'success'
      && !manualSelection.current
      && !initialSelectionApplied.current
    ) {
      setActiveNodeId(presentation.currentNodeId)
      initialSelectionApplied.current = true
    }
  }, [presentation.currentNodeId, workflow.loadStatus])

  function selectNode(nodeId) {
    manualSelection.current = true
    setActiveNodeId(nodeId)
  }

  const activeNode = presentation.nodes.find((node) => node.id === activeNodeId)

  return (
    <div className="space-y-6">
      <section aria-labelledby="agent1-pipeline-title" className="space-y-3">
        <div>
          <h2 id="agent1-pipeline-title" className="text-section-title font-semibold text-content-primary">
            Requirements Agent Pipeline
          </h2>
          <p className="mt-1 text-sm text-content-secondary">
            Review completed nodes and continue the current evidence workflow. Future nodes remain locked until implemented.
          </p>
        </div>
        <WorkflowPipelineNavigation
          nodes={presentation.nodes}
          activeNodeId={activeNodeId}
          currentNodeId={presentation.currentNodeId}
          onSelect={selectNode}
        />
      </section>

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

      {workflow.loadStatus === 'success' && activeNodeId === REQUIREMENTS_NODE_IDS.INPUT_COLLECTION ? (
        <RequirementSourcesNode
          sources={workflow.sources}
          uploadingType={workflow.uploadingType}
          removingId={workflow.removingId}
          onAddFiles={workflow.addFiles}
          onRemoveSource={workflow.removeSource}
        />
      ) : null}

      {workflow.loadStatus === 'success' && activeNodeId === REQUIREMENTS_NODE_IDS.PROCESSING_AND_CHUNKING ? (
        <EvidenceProcessingNode
          sources={workflow.sources}
          processingStates={workflow.processingStates}
          preparationStates={workflow.preparationStates}
          onProcessSource={workflow.processSource}
          onLoadProcessingResult={workflow.loadProcessingResult}
          onPrepareSource={workflow.prepareSource}
          onLoadPreparedEvidence={workflow.loadPreparedEvidence}
          onOpenCollection={() => selectNode(REQUIREMENTS_NODE_IDS.INPUT_COLLECTION)}
        />
      ) : null}

      {workflow.loadStatus === 'success' && activeNode && !activeNode.implemented ? (
        <LockedNodeState node={activeNode} />
      ) : null}
    </div>
  )
}

export default RequirementsWorkspace
