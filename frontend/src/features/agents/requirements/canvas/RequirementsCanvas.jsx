import { forwardRef, useMemo } from 'react'

import WorkflowCanvas from '../../../../components/agents/workflow/WorkflowCanvas.jsx'
import { REQUIREMENTS_DEFAULT_NODE_POSITIONS } from './layout.js'
import { createRequirementsWorkflowNodes, REQUIREMENTS_WORKFLOW_EDGES } from './workflowGraph.js'

const RequirementsCanvas = forwardRef(function RequirementsCanvas(
  { presentation, selectedNodeId, onSelectNode, onLayoutChange },
  ref,
) {
  const nodes = useMemo(() => createRequirementsWorkflowNodes(presentation), [presentation])

  return (
    <WorkflowCanvas
      ref={ref}
      nodes={nodes}
      edges={REQUIREMENTS_WORKFLOW_EDGES}
      defaultPositions={REQUIREMENTS_DEFAULT_NODE_POSITIONS}
      selectedNodeId={selectedNodeId}
      onSelectNode={onSelectNode}
      onLayoutChange={onLayoutChange}
      ariaLabel="Agent 1 requirements workflow canvas"
    />
  )
})

export default RequirementsCanvas
