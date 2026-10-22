import { useCallback, useEffect, useMemo, useRef, useState } from 'react'

import WorkflowControls from '../../../../components/agents/workflow/WorkflowControls.jsx'
import WorkflowNodeModal from '../../../../components/agents/workflow/WorkflowNodeModal.jsx'
import StatusBadge from '../../../../components/ui/StatusBadge.jsx'
import RequirementsCanvas from '../canvas/RequirementsCanvas.jsx'
import RequirementsWorkspace from '../RequirementsWorkspace.jsx'
import {
  getRequirementNodeDefinition,
  REQUIREMENTS_NODE_IDS,
} from '../workflow/nodeDefinitions.js'
import {
  deriveRequirementsCurrentNodeId,
  deriveRequirementsWorkflowPresentation,
} from '../workflow/presentation.js'

function RequirementsProjectPage({ project, projectStatus, projectActions, entryMode = 'created' }) {
  const canvasRef = useRef(null)
  const enteringExistingProject = entryMode === 'existing'
  const [visibleNodeId, setVisibleNodeId] = useState(
    enteringExistingProject ? null : REQUIREMENTS_NODE_IDS.INPUT_COLLECTION,
  )
  const [workspaceSnapshot, setWorkspaceSnapshot] = useState(null)
  const presentation = useMemo(
    () => deriveRequirementsWorkflowPresentation(workspaceSnapshot ?? {}),
    [workspaceSnapshot],
  )
  const selectedDefinition = getRequirementNodeDefinition(visibleNodeId)
  const selectedPresentation = selectedDefinition
    ? {
        ...selectedDefinition,
        ...(presentation[selectedDefinition.id] ?? {}),
      }
    : null

  const handlePresentationChange = useCallback((snapshot) => {
    setWorkspaceSnapshot(snapshot)
  }, [])

  const handleNavigation = useCallback((nodeId) => {
    setVisibleNodeId(nodeId)
  }, [])

  const handleCloseModal = useCallback(() => {
    setVisibleNodeId(null)
  }, [])

  useEffect(() => {
    if (!enteringExistingProject) {
      canvasRef.current?.focusNode(REQUIREMENTS_NODE_IDS.INPUT_COLLECTION)
    }
  }, [enteringExistingProject, project.agent_project_id])

  const currentNodeId = deriveRequirementsCurrentNodeId(workspaceSnapshot ?? {})

  return (
    <section className="min-w-0 space-y-3" aria-labelledby="requirements-canvas-title">
      <header className="flex flex-col gap-3 rounded-panel border border-default/80 bg-surface px-4 py-3.5 shadow-surface xl:flex-row xl:items-center xl:justify-between">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2.5">
            <h1 id="requirements-canvas-title" className="truncate text-page-heading font-semibold leading-tight tracking-tight text-content-primary">{project.name}</h1>
            <StatusBadge label={projectStatus.label} tone={projectStatus.tone} />
          </div>
          <p className="mt-1 text-xs font-medium uppercase tracking-[0.1em] text-content-muted">Requirements</p>
        </div>
        <div className="flex flex-wrap items-center gap-2 xl:justify-end">
          <WorkflowControls
            onAutoArrange={() => canvasRef.current?.autoArrange()}
            onResetLayout={() => canvasRef.current?.resetLayout()}
          />
          {projectActions}
        </div>
      </header>

      <div className="overflow-hidden rounded-panel border border-default/80 bg-surface shadow-surface">
        <div className="min-w-0 bg-canvas">
          <RequirementsCanvas
            ref={canvasRef}
            presentation={presentation}
            selectedNodeId={visibleNodeId}
            onSelectNode={handleNavigation}
          />
        </div>
        <WorkflowNodeModal
          node={selectedPresentation}
          open={Boolean(selectedDefinition)}
          onClose={handleCloseModal}
          eyebrow="Agent 1 workflow"
        >
          <RequirementsWorkspace
            project={project}
            activeSection={selectedDefinition?.id ?? currentNodeId}
            onPresentationChange={handlePresentationChange}
            onNavigateNode={handleNavigation}
          />
        </WorkflowNodeModal>
      </div>

      <p className="px-1 text-[0.6875rem] text-content-muted">Node positions are visual only. Moving a node does not change workflow order, status, or backend behavior.</p>
    </section>
  )
}

export default RequirementsProjectPage
