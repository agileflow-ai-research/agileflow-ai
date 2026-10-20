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
    <section className="min-w-0 space-y-4" aria-labelledby="requirements-canvas-title">
      <header className="flex flex-col gap-4 border-b border-default pb-4 xl:flex-row xl:items-center xl:justify-between">
        <div>
          <div className="flex flex-wrap items-center gap-3">
            <h1 id="requirements-canvas-title" className="text-page-heading font-semibold text-content-primary">{project.name}</h1>
            <StatusBadge label={projectStatus.label} tone={projectStatus.tone} />
          </div>
          <p className="mt-1 text-sm text-content-secondary">Agent 1 — Requirements &amp; Analysis</p>
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

      <p className="text-xs text-content-muted">Node positions are visual only. Moving a node does not change workflow order, status, or backend behavior.</p>
    </section>
  )
}

export default RequirementsProjectPage
