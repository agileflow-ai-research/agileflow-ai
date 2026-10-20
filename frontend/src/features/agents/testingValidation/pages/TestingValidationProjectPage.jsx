import { useCallback, useEffect, useMemo, useRef, useState } from 'react'

import WorkflowControls from '../../../../components/agents/workflow/WorkflowControls.jsx'
import WorkflowNodeModal from '../../../../components/agents/workflow/WorkflowNodeModal.jsx'
import StatusBadge from '../../../../components/ui/StatusBadge.jsx'
import TestingValidationCanvas from '../canvas/TestingValidationCanvas.jsx'
import ContextTestabilityPanel from '../panels/ContextTestabilityPanel.jsx'
import InputOutputSetupPanel from '../panels/InputOutputSetupPanel.jsx'
import InputPreparationPanel from '../panels/InputPreparationPanel.jsx'
import TestGenerationResultsPanel from '../panels/TestGenerationResultsPanel.jsx'
import TestingIntelligencePanel from '../panels/TestingIntelligencePanel.jsx'
import TestPlanningReviewPanel from '../panels/TestPlanningReviewPanel.jsx'
import {
  getTestingValidationNodeDefinition,
  TESTING_VALIDATION_NODE_IDS,
} from '../workflow/nodeDefinitions.js'
import { createTestingValidationShellPresentation } from '../workflow/presentation.js'

const panelByNodeId = Object.freeze({
  [TESTING_VALIDATION_NODE_IDS.INPUT_OUTPUT_SETUP]: InputOutputSetupPanel,
  [TESTING_VALIDATION_NODE_IDS.INPUT_PREPARATION]: InputPreparationPanel,
  [TESTING_VALIDATION_NODE_IDS.TESTING_INTELLIGENCE]: TestingIntelligencePanel,
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
  const presentation = useMemo(() => createTestingValidationShellPresentation(), [])
  const selectedDefinition = getTestingValidationNodeDefinition(selectedNodeId)
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

  useEffect(() => {
    if (!enteringExistingProject) {
      canvasRef.current?.focusNode(TESTING_VALIDATION_NODE_IDS.INPUT_OUTPUT_SETUP)
    }
  }, [enteringExistingProject, project.agent_project_id])

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
        <div className="min-w-0 bg-canvas">
          <TestingValidationCanvas
            ref={canvasRef}
            presentation={presentation}
            selectedNodeId={selectedNodeId}
            onSelectNode={handleSelectNode}
          />
        </div>
        <WorkflowNodeModal
          node={selectedPresentation}
          open={Boolean(selectedDefinition)}
          onClose={handleCloseModal}
          eyebrow="Agent 4 · Test Generation workflow"
        >
          {SelectedPanel ? <SelectedPanel definition={selectedDefinition} /> : null}
        </WorkflowNodeModal>
      </div>

      <p className="text-xs text-content-muted">This canvas is a presentation-only Stage 1 shell. Node positions are visual, and no workflow state or processing is persisted yet.</p>
    </section>
  )
}

export default TestingValidationProjectPage
