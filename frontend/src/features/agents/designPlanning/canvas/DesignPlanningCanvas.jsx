import { forwardRef, useMemo } from 'react'

import WorkflowCanvas from '../../../../components/agents/workflow/WorkflowCanvas.jsx'
import { DESIGN_PLANNING_DEFAULT_NODE_POSITIONS } from './layout.js'
import { createDesignPlanningWorkflowNodes, DESIGN_PLANNING_WORKFLOW_EDGES } from './workflowGraph.js'

const DesignPlanningCanvas = forwardRef(function DesignPlanningCanvas(
  { presentation = {}, selectedNodeId, onSelectNode, onLayoutChange },
  ref,
) {
  const nodes = useMemo(() => createDesignPlanningWorkflowNodes(presentation), [presentation])

  return (
    <WorkflowCanvas
      ref={ref}
      nodes={nodes}
      edges={DESIGN_PLANNING_WORKFLOW_EDGES}
      defaultPositions={DESIGN_PLANNING_DEFAULT_NODE_POSITIONS}
      selectedNodeId={selectedNodeId}
      onSelectNode={onSelectNode}
      onLayoutChange={onLayoutChange}
      ariaLabel="Agent 2 design and planning workflow canvas"
    />
  )
})

export default DesignPlanningCanvas
