import { useCallback, useEffect, useMemo, useRef, useState } from 'react'

import StatusBadge from '../../../../components/ui/StatusBadge.jsx'
import ImplementationCanvas from '../canvas/ImplementationCanvas.jsx'
import WorkflowControls from '../canvas/WorkflowControls.jsx'
import ImplementationWorkspace from '../ImplementationWorkspace.jsx'
import WorkflowNodeModal from '../panels/WorkflowNodeModal.jsx'
import {
  deriveWorkflowPresentation,
  getWorkflowNodeDefinition,
} from '../canvas/nodeRegistry.js'
import { deriveWorkflowTransition } from '../utils/workflowProgression.js'

function ImplementationProjectPage({ project, projectStatus, projectActions }) {
  const canvasRef = useRef(null)
  const [selectedNodeId, setSelectedNodeId] = useState('PROJECT_SOURCES')
  const [workspaceSnapshot, setWorkspaceSnapshot] = useState(null)
  const handledTransitionRef = useRef(null)
  const presentation = useMemo(() => deriveWorkflowPresentation(workspaceSnapshot), [workspaceSnapshot])
  const selectedDefinition = getWorkflowNodeDefinition(selectedNodeId)
  const selectedPresentation = selectedDefinition
    ? {
        ...selectedDefinition,
        ...(presentation[selectedDefinition.id] ?? {}),
        status: selectedDefinition.active
          ? presentation[selectedDefinition.id]?.status ?? 'NOT_STARTED'
          : 'LOCKED',
      }
    : null
  const handlePresentationChange = useCallback((snapshot) => setWorkspaceSnapshot(snapshot), [])
  const handleCloseModal = useCallback(() => setSelectedNodeId(null), [])

  useEffect(() => {
    handledTransitionRef.current = null
    canvasRef.current?.focusNode('PROJECT_SOURCES')
  }, [project.agent_project_id])

  useEffect(() => {
    const next = deriveWorkflowTransition(workspaceSnapshot)
    if (!next || handledTransitionRef.current === next.key) return
    handledTransitionRef.current = next.key
    setSelectedNodeId(next.nodeId)
    canvasRef.current?.focusNode(next.nodeId)
  }, [workspaceSnapshot])

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
            selectedNodeId={selectedNodeId}
            onSelectNode={setSelectedNodeId}
          />
        </div>
          <WorkflowNodeModal node={selectedPresentation} open={Boolean(selectedDefinition)} onClose={handleCloseModal}>
            {selectedDefinition?.active ? null : (
              <div className="rounded-control border border-default bg-elevated p-4">
                <p className="font-semibold text-content-primary">Not implemented yet</p>
                <p className="mt-2 text-sm text-content-secondary">This required workflow stage is reserved for a future milestone. No execution or delivery behavior is available in this slice.</p>
              </div>
            )}
            <div className={selectedDefinition?.active ? '' : 'hidden'}>
              <ImplementationWorkspace
                project={project}
                activeSection={selectedDefinition?.active ? selectedDefinition.id : 'PROJECT_SOURCES'}
                initialArtifactReviewQueue={workspaceSnapshot?.artifactReviewQueue ?? []}
                onPresentationChange={handlePresentationChange}
                onNavigateNode={setSelectedNodeId}
              />
            </div>
          </WorkflowNodeModal>
      </div>

      <p className="text-xs text-content-muted">Node positions are visual only. Moving a node does not change workflow order, status, or backend behavior.</p>
    </section>
  )
}

export default ImplementationProjectPage
