import { useCallback, useEffect, useMemo, useRef, useState } from 'react'

import WorkflowControls from '../../../../components/agents/workflow/WorkflowControls.jsx'
import WorkflowNodeModal from '../../../../components/agents/workflow/WorkflowNodeModal.jsx'
import StatusBadge from '../../../../components/ui/StatusBadge.jsx'
import { WORKFLOW_MODAL_ORIGINS, WORKFLOW_NODE_IDS } from '../constants/workflow.js'
import ImplementationCanvas from '../canvas/ImplementationCanvas.jsx'
import ImplementationWorkspace from '../ImplementationWorkspace.jsx'
import WorkflowNextStepNotice from '../components/common/WorkflowNextStepNotice.jsx'
import ProjectOverviewModal from '../components/ProjectOverviewModal.jsx'
import {
  getWorkflowNodeDefinition,
  IMPLEMENTATION_NODE_REGISTRY,
} from '../workflow/nodeDefinitions.js'
import { deriveWorkflowPresentation } from '../workflow/presentation.js'
import { inputHasSource } from '../workflow/sourceState.js'
import { deriveWorkflowTransition } from '../workflow/workflowProgression.js'

function ImplementationProjectPage({ project, projectStatus, projectActions, entryMode = 'created' }) {
  const canvasRef = useRef(null)
  const enteringExistingProject = entryMode === 'existing'
  const initialVisibleModal = enteringExistingProject
    ? null
    : { nodeId: WORKFLOW_NODE_IDS.PROJECT_SOURCES, origin: WORKFLOW_MODAL_ORIGINS.AUTO }
  const [projectOverviewOpen, setProjectOverviewOpen] = useState(enteringExistingProject)
  const [visibleModal, setVisibleModal] = useState(initialVisibleModal)
  const [workspaceSnapshot, setWorkspaceSnapshot] = useState(null)
  const workspaceSnapshotRef = useRef(null)
  const visibleModalRef = useRef(visibleModal)
  const projectOverviewOpenRef = useRef(enteringExistingProject)
  const lastAutoPresentedTransitionKeyRef = useRef(null)
  const presentation = useMemo(() => deriveWorkflowPresentation(workspaceSnapshot), [workspaceSnapshot])
  const activeWorkflowTransition = useMemo(
    () => deriveWorkflowTransition(workspaceSnapshot),
    [workspaceSnapshot],
  )
  const activeWorkflowNodeId = activeWorkflowTransition?.nodeId ?? null
  const currentWorkflowNodeId = activeWorkflowNodeId ?? IMPLEMENTATION_NODE_REGISTRY.find((node) => (
    node.active && presentation[node.id]?.status !== 'COMPLETE'
  ))?.id
  const currentWorkflowNode = getWorkflowNodeDefinition(currentWorkflowNodeId)
  const visibleModalNodeId = visibleModal?.nodeId ?? null
  const selectedDefinition = getWorkflowNodeDefinition(visibleModalNodeId)
  const selectedPresentation = selectedDefinition
    ? {
        ...selectedDefinition,
        ...(presentation[selectedDefinition.id] ?? {}),
        status: selectedDefinition.active
          ? presentation[selectedDefinition.id]?.status ?? 'NOT_STARTED'
          : 'LOCKED',
      }
    : null
  const handlePresentationChange = useCallback((snapshot) => {
    workspaceSnapshotRef.current = snapshot
    setWorkspaceSnapshot(snapshot)
    const next = deriveWorkflowTransition(snapshot)
    if (!next || lastAutoPresentedTransitionKeyRef.current === next.key) return
    lastAutoPresentedTransitionKeyRef.current = next.key
    if (projectOverviewOpenRef.current) return
    if (visibleModalRef.current) return
    canvasRef.current?.focusNode(next.nodeId)
    if (next.requiresUserAction) {
      const nextModal = { nodeId: next.nodeId, origin: WORKFLOW_MODAL_ORIGINS.AUTO }
      visibleModalRef.current = nextModal
      setVisibleModal(nextModal)
    }
  }, [])
  const handleCloseModal = useCallback(() => {
    visibleModalRef.current = null
    setVisibleModal(null)
  }, [])
  const handleManualNavigation = useCallback((nodeId) => {
    const nextModal = { nodeId, origin: WORKFLOW_MODAL_ORIGINS.MANUAL }
    visibleModalRef.current = nextModal
    setVisibleModal(nextModal)
  }, [])
  const handleCloseProjectOverview = useCallback(() => {
    projectOverviewOpenRef.current = false
    const currentTransition = deriveWorkflowTransition(workspaceSnapshotRef.current)
    if (currentTransition) lastAutoPresentedTransitionKeyRef.current = currentTransition.key
    visibleModalRef.current = null
    setVisibleModal(null)
    setProjectOverviewOpen(false)
  }, [])

  useEffect(() => {
    lastAutoPresentedTransitionKeyRef.current = null
    if (!enteringExistingProject) canvasRef.current?.focusNode(WORKFLOW_NODE_IDS.PROJECT_SOURCES)
  }, [enteringExistingProject, project.agent_project_id])

  const nextStepNotice = useMemo(() => {
    if (!activeWorkflowNodeId || activeWorkflowNodeId === visibleModalNodeId) return null
    const target = getWorkflowNodeDefinition(activeWorkflowNodeId)
    if (!target) return null
    const targetState = presentation[activeWorkflowNodeId]?.status
    const needsAttention = activeWorkflowTransition?.requiresUserAction
    const description = needsAttention
      ? `${target.title} needs your attention.`
      : `${target.title} is continuing automatically.`
    const actionLabel = {
      [WORKFLOW_NODE_IDS.SPECIFICATION_VERIFICATION]: 'Go to Specification Verification',
      [WORKFLOW_NODE_IDS.IMPLEMENTATION_READINESS]: targetState === 'WAITING_FOR_HUMAN' ? 'Review Readiness' : 'Go to Implementation Readiness',
      [WORKFLOW_NODE_IDS.DELIVERY_SETUP]: 'Go to Delivery Setup',
      [WORKFLOW_NODE_IDS.GENERATE_IMPLEMENTATION]: 'Review Implementation Plan',
      [WORKFLOW_NODE_IDS.INPUT_ANALYSIS]: 'Go to Input Analysis',
    }[activeWorkflowNodeId] ?? `Go to ${target.title}`
    return { description, actionLabel, targetNodeId: activeWorkflowNodeId }
  }, [activeWorkflowNodeId, activeWorkflowTransition?.requiresUserAction, presentation, visibleModalNodeId])

  return (
    <section className="min-w-0 space-y-4" aria-labelledby="implementation-canvas-title">
      <header className="flex flex-col gap-4 border-b border-default pb-4 xl:flex-row xl:items-center xl:justify-between">
        <div>
          <div className="flex flex-wrap items-center gap-3">
            <h1 id="implementation-canvas-title" className="text-page-heading font-semibold text-content-primary">{project.name}</h1>
            <StatusBadge label={projectStatus.label} tone={projectStatus.tone} />
          </div>
          <p className="mt-1 text-sm text-content-secondary">Agent 3 — Implementation</p>
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
        <div className="min-w-0 bg-canvas">
          <ImplementationCanvas
            ref={canvasRef}
            presentation={presentation}
            selectedNodeId={visibleModalNodeId}
            onSelectNode={handleManualNavigation}
          />
        </div>
          <WorkflowNodeModal
            node={selectedPresentation}
            open={Boolean(selectedDefinition)}
            onClose={handleCloseModal}
            eyebrow="Agent 3 workflow"
          >
            {nextStepNotice ? (
              <WorkflowNextStepNotice {...nextStepNotice} onNavigate={handleManualNavigation} />
            ) : null}
            {selectedDefinition?.active ? null : (
              <div className="rounded-control border border-default bg-elevated p-4">
                <p className="font-semibold text-content-primary">Not implemented yet</p>
                <p className="mt-2 text-sm text-content-secondary">This required workflow stage is reserved for a future milestone. No execution or delivery behavior is available in this slice.</p>
              </div>
            )}
            <div className={selectedDefinition?.active ? '' : 'hidden'}>
              <ImplementationWorkspace
                project={project}
                activeSection={selectedDefinition?.active ? selectedDefinition.id : WORKFLOW_NODE_IDS.PROJECT_SOURCES}
                initialArtifactReviewQueue={workspaceSnapshot?.artifactReviewQueue ?? []}
                onPresentationChange={handlePresentationChange}
                onNavigateNode={handleManualNavigation}
              />
            </div>
          </WorkflowNodeModal>
      </div>

      <ProjectOverviewModal
        open={projectOverviewOpen}
        project={project}
        projectStatus={projectStatus}
        currentStage={currentWorkflowNode?.title ?? 'Workflow complete'}
        currentStatus={activeWorkflowTransition?.requiresUserAction
          ? `Waiting for ${currentWorkflowNode?.title ?? 'your review'}`
          : currentWorkflowNode?.title ?? projectStatus.label}
        completedNodeCount={IMPLEMENTATION_NODE_REGISTRY.filter((node) => presentation[node.id]?.status === 'COMPLETE').length}
        totalNodeCount={IMPLEMENTATION_NODE_REGISTRY.length}
        sourceCount={workspaceSnapshot?.preparationState?.result?.source_count
          ?? (workspaceSnapshot?.inputs ?? []).filter(inputHasSource).length}
        analyzedCount={workspaceSnapshot?.preparationState?.result?.completed_source_count
          ?? workspaceSnapshot?.preparationState?.result?.processed_source_count}
        selectedOutputs={workspaceSnapshot?.selectedOutputs ?? []}
        repository={workspaceSnapshot?.repositoryState?.repository}
        onClose={handleCloseProjectOverview}
      />

      <p className="text-xs text-content-muted">Node positions are visual only. Moving a node does not change workflow order, status, or backend behavior.</p>
    </section>
  )
}

export default ImplementationProjectPage
