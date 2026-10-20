import { forwardRef, useMemo } from 'react'

import WorkflowCanvas from '../../../../components/agents/workflow/WorkflowCanvas.jsx'
import { TESTING_VALIDATION_DEFAULT_NODE_POSITIONS } from './layout.js'
import { createTestingValidationWorkflowNodes, TESTING_VALIDATION_WORKFLOW_EDGES } from './workflowGraph.js'

const TestingValidationCanvas = forwardRef(function TestingValidationCanvas(
  { presentation, selectedNodeId, onSelectNode, onLayoutChange },
  ref,
) {
  const nodes = useMemo(
    () => createTestingValidationWorkflowNodes(presentation),
    [presentation],
  )

  return (
    <WorkflowCanvas
      ref={ref}
      nodes={nodes}
      edges={TESTING_VALIDATION_WORKFLOW_EDGES}
      defaultPositions={TESTING_VALIDATION_DEFAULT_NODE_POSITIONS}
      selectedNodeId={selectedNodeId}
      onSelectNode={onSelectNode}
      onLayoutChange={onLayoutChange}
      ariaLabel="Agent 4 test generation workflow canvas"
    />
  )
})

export default TestingValidationCanvas
