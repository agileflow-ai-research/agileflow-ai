import { useCallback, useEffect, useMemo, useRef, useState } from 'react'

import WorkflowControls from '../../../../components/agents/workflow/WorkflowControls.jsx'
import WorkflowNodeModal from '../../../../components/agents/workflow/WorkflowNodeModal.jsx'
import StatusBadge from '../../../../components/ui/StatusBadge.jsx'
import { getAgentProjectRuns } from '../../../../services/agentProjectService.js'
import DesignPlanningCanvas from '../canvas/DesignPlanningCanvas.jsx'
import DesignPlanningNodePlaceholder from '../components/DesignPlanningNodePlaceholder.jsx'
import {
  DESIGN_PLANNING_NODE_IDS,
  WORKFLOW_MODAL_ORIGINS,
} from '../constants/workflow.js'
import useDesignPlanningWorkflow from '../hooks/useDesignPlanningWorkflow.js'
import GenerateDesignPlanningPanel from '../panels/GenerateDesignPlanningPanel.jsx'
import HumanReviewPanel from '../panels/HumanReviewPanel.jsx'
import OutputSelectionPanel from '../panels/OutputSelectionPanel.jsx'
import ProjectSpecificationsPanel from '../panels/ProjectSpecificationsPanel.jsx'
import TechnicalPlanningPanel from '../panels/TechnicalPlanningPanel.jsx'
import ValidationTraceabilityPanel from '../panels/ValidationTraceabilityPanel.jsx'
import {
  getDesignPlanningNodeDefinition,
} from '../workflow/nodeDefinitions.js'
import { deriveDesignPlanningPresentation } from '../workflow/presentation.js'

function DesignPlanningProjectPage({
  project,
  projectStatus,
  projectActions,
  entryMode = 'created',
  onRunCompleted,
  runs,
  onViewRun,
}) {
  const canvasRef = useRef(null)
  const enteringExistingProject = entryMode === 'existing'
  const initialVisibleModal = enteringExistingProject
    ? null
    : { nodeId: DESIGN_PLANNING_NODE_IDS.PROJECT_SPECIFICATIONS, origin: WORKFLOW_MODAL_ORIGINS.AUTO }
  const [visibleModal, setVisibleModal] = useState(initialVisibleModal)
  const [internalRuns, setInternalRuns] = useState([])

  const projectId = project?.agent_project_id || project?.id

  useEffect(() => {
    if (Array.isArray(runs) && runs.length > 0) return
    if (!projectId) return

    let active = true
    getAgentProjectRuns(projectId)
      .then((res) => {
        if (active && Array.isArray(res?.data)) {
          setInternalRuns(res.data)
        }
      })
      .catch(() => {})

    return () => {
      active = false
    }
  }, [projectId, runs])

  const effectiveRuns = useMemo(() => {
    if (Array.isArray(runs)) return runs
    return internalRuns
  }, [runs, internalRuns])

  const workflow = useDesignPlanningWorkflow(project)

  const presentation = useMemo(
    () =>
      deriveDesignPlanningPresentation({
        ...workflow.workflowState,
        runs: effectiveRuns,
      }),
    [workflow.workflowState, effectiveRuns],
  )

  const visibleModalNodeId = visibleModal?.nodeId ?? null
  const selectedDefinition = getDesignPlanningNodeDefinition(visibleModalNodeId)
  const selectedPresentation = selectedDefinition
    ? {
        ...selectedDefinition,
        ...(presentation[selectedDefinition.id] ?? {}),
      }
    : null

  const handleSelectNode = useCallback((nodeId) => {
    setVisibleModal({ nodeId, origin: WORKFLOW_MODAL_ORIGINS.MANUAL })
  }, [])

  const handleCloseModal = useCallback(() => {
    setVisibleModal(null)
  }, [])

  useEffect(() => {
    if (!enteringExistingProject) {
      canvasRef.current?.focusNode(DESIGN_PLANNING_NODE_IDS.PROJECT_SPECIFICATIONS)
    }
  }, [enteringExistingProject, project?.agent_project_id])

  const handleRunCompleted = useCallback(
    (result) => {
      if (projectId) {
        getAgentProjectRuns(projectId)
          .then((res) => {
            if (Array.isArray(res?.data)) {
              setInternalRuns(res.data)
            }
          })
          .catch(() => {})
      }
      onRunCompleted?.(result)
    },
    [onRunCompleted, projectId],
  )

  return (
    <section className="min-w-0 space-y-6" aria-labelledby="design-planning-canvas-title" aria-label="Agent 2 design and planning project">
      <header className="flex flex-col gap-4 border-b border-default pb-4 xl:flex-row xl:items-center xl:justify-between">
        <div>
          <div className="flex flex-wrap items-center gap-3">
            <h1 id="design-planning-canvas-title" className="text-page-heading font-semibold text-content-primary">
              {project?.name}
            </h1>
            {projectStatus && <StatusBadge label={projectStatus.label} tone={projectStatus.tone} />}
          </div>
          <p className="mt-1 text-sm text-content-secondary">Agent 2 — Design & Planning</p>
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
          <DesignPlanningCanvas
            ref={canvasRef}
            presentation={presentation}
            selectedNodeId={visibleModalNodeId}
            onSelectNode={handleSelectNode}
          />
        </div>

        <WorkflowNodeModal
          node={selectedPresentation}
          open={Boolean(selectedDefinition)}
          onClose={handleCloseModal}
          eyebrow="Agent 2 workflow"
        >
          {visibleModalNodeId === DESIGN_PLANNING_NODE_IDS.PROJECT_SPECIFICATIONS ? (
            <ProjectSpecificationsPanel
              project={project}
              input={workflow.input}
              activeSource={workflow.activeSource}
              sourceModes={workflow.sourceModes}
              uploadStatus={workflow.uploadStatus}
              uploadProvenance={workflow.uploadProvenance}
              uploadErrors={workflow.uploadErrors}
              errors={workflow.errors}
              onUpdateField={workflow.updateField}
              onSetActiveSource={workflow.setActiveSource}
              onSetSourceMode={workflow.setSourceMode}
              onFileUpload={workflow.handleFileUpload}
              onRemoveFile={workflow.handleRemoveFile}
              onNavigate={handleSelectNode}
              onValidate={workflow.validateNode1}
            />
          ) : visibleModalNodeId === DESIGN_PLANNING_NODE_IDS.TECHNICAL_PLANNING ? (
            <TechnicalPlanningPanel
              input={workflow.input}
              errors={workflow.errors}
              onUpdateField={workflow.updateField}
              onNavigate={handleSelectNode}
              onValidate={workflow.validateNode2}
            />
          ) : visibleModalNodeId === DESIGN_PLANNING_NODE_IDS.OUTPUT_SELECTION ? (
            <OutputSelectionPanel
              input={workflow.input}
              selectedOutputs={workflow.selectedOutputs}
              errors={workflow.errors}
              onToggleOutput={workflow.toggleOutput}
              onSelectAll={workflow.selectAllOutputs}
              onClearAll={workflow.clearOutputs}
              onNavigate={handleSelectNode}
              onValidate={workflow.validateNode3}
            />
          ) : visibleModalNodeId === DESIGN_PLANNING_NODE_IDS.HUMAN_REVIEW ? (
            <HumanReviewPanel
              project={project}
              input={workflow.input}
              uploadProvenance={workflow.uploadProvenance}
              selectedOutputs={workflow.selectedOutputs}
              humanReviewApproved={workflow.humanReviewApproved}
              onSetHumanReviewApproved={workflow.setHumanReviewApproved}
              onNavigate={handleSelectNode}
            />
          ) : visibleModalNodeId === DESIGN_PLANNING_NODE_IDS.GENERATE_DESIGN_PLANNING ? (
            <GenerateDesignPlanningPanel
              project={project}
              input={workflow.input}
              selectedOutputs={workflow.selectedOutputs}
              humanReviewApproved={workflow.humanReviewApproved}
              runState={workflow.runState}
              runResult={workflow.runResult}
              runError={workflow.runError}
              onExecuteRun={() => workflow.executeRun(handleRunCompleted)}
              onNavigate={handleSelectNode}
              onResetRun={workflow.resetRun}
            />
          ) : visibleModalNodeId === DESIGN_PLANNING_NODE_IDS.VALIDATION_TRACEABILITY ? (
            <ValidationTraceabilityPanel
              project={project}
              runResult={workflow.runResult}
              runState={workflow.runState}
              runError={workflow.runError}
              runs={effectiveRuns}
              onViewRun={onViewRun}
              onNavigate={handleSelectNode}
            />
          ) : (
            <DesignPlanningNodePlaceholder
              node={selectedPresentation}
            />
          )}
        </WorkflowNodeModal>
      </div>

      <p className="text-xs text-content-muted">
        Node positions are visual only. Moving a node does not change workflow order, status, or backend behavior.
      </p>
    </section>
  )
}

export default DesignPlanningProjectPage
