import { forwardRef, useMemo } from 'react'

import WorkflowCanvas from '../../../../components/agents/workflow/WorkflowCanvas.jsx'
import { DEFAULT_NODE_POSITIONS } from './layout.js'
import { createWorkflowNodes, IMPLEMENTATION_WORKFLOW_EDGES } from './workflowGraph.js'

const ImplementationCanvas = forwardRef(function ImplementationCanvas(
  { presentation, selectedNodeId, onSelectNode, onLayoutChange },
  ref,
) {
  const nodes = useMemo(() => createWorkflowNodes(presentation), [presentation])

  return (
    <WorkflowCanvas
      ref={ref}
      nodes={nodes}
      edges={IMPLEMENTATION_WORKFLOW_EDGES}
      defaultPositions={DEFAULT_NODE_POSITIONS}
      selectedNodeId={selectedNodeId}
      onSelectNode={onSelectNode}
      onLayoutChange={onLayoutChange}
      ariaLabel="Agent 3 implementation workflow canvas"
    />
  )
})

export default ImplementationCanvas
