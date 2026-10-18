import { forwardRef, useEffect, useImperativeHandle, useRef } from 'react'
import {
  Background,
  BackgroundVariant,
  Controls,
  ReactFlow,
  ReactFlowProvider,
  useNodesState,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'

import WorkflowNode from '../nodes/WorkflowNode.jsx'
import { positionWorkflowNodes } from './layout.js'
import { createWorkflowNodes, IMPLEMENTATION_WORKFLOW_EDGES } from './nodeRegistry.js'

const nodeTypes = Object.freeze({ workflow: WorkflowNode })

const ImplementationCanvasInner = forwardRef(function ImplementationCanvasInner(
  { presentation, selectedNodeId, onSelectNode, onLayoutChange },
  ref,
) {
  const initialNodes = useRef(createWorkflowNodes(presentation, onSelectNode))
  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes.current)
  const flowInstance = useRef(null)

  useEffect(() => {
    const updatedNodes = new Map(
      createWorkflowNodes(presentation, onSelectNode).map((node) => [node.id, node]),
    )
    setNodes((current) => current.map((node) => {
      const definition = updatedNodes.get(node.id)
      return {
        ...node,
        selected: node.id === selectedNodeId,
        data: definition.data,
      }
    }))
  }, [onSelectNode, presentation, selectedNodeId, setNodes])

  function arrange() {
    setNodes((current) => positionWorkflowNodes(current))
    window.setTimeout(() => flowInstance.current?.fitView({ padding: 0.16, duration: 250 }), 0)
  }

  useImperativeHandle(ref, () => ({
    autoArrange: arrange,
    resetLayout: arrange,
    fitView: () => flowInstance.current?.fitView({ padding: 0.16, duration: 250 }),
  }))

  function handleNodesChange(changes) {
    onNodesChange(changes)
    if (changes.some((change) => change.type === 'position' && change.position)) {
      onLayoutChange?.(changes)
    }
  }

  return (
    <div className="h-[36rem] min-h-[28rem] w-full" aria-label="Agent 3 implementation workflow canvas">
      <ReactFlow
        nodes={nodes}
        edges={IMPLEMENTATION_WORKFLOW_EDGES}
        nodeTypes={nodeTypes}
        onNodesChange={handleNodesChange}
        onNodeClick={(_, node) => onSelectNode(node.id)}
        onInit={(instance) => { flowInstance.current = instance }}
        fitView
        fitViewOptions={{ padding: 0.16 }}
        minZoom={0.45}
        maxZoom={1.5}
        nodesConnectable={false}
        edgesReconnectable={false}
        nodesDraggable
        elementsSelectable
        deleteKeyCode={null}
        colorMode="dark"
        proOptions={{ hideAttribution: true }}
      >
        <Background variant={BackgroundVariant.Dots} gap={22} size={1} color="var(--color-border-default)" />
        <Controls position="bottom-left" showInteractive={false} />
      </ReactFlow>
    </div>
  )
})

const ImplementationCanvas = forwardRef(function ImplementationCanvas(props, ref) {
  return (
    <ReactFlowProvider>
      <ImplementationCanvasInner {...props} ref={ref} />
    </ReactFlowProvider>
  )
})

export default ImplementationCanvas
