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

import FloatingWorkflowEdge from './FloatingWorkflowEdge.jsx'
import WorkflowNode from './WorkflowNode.jsx'
import { positionWorkflowNodes } from './layout.js'

const sharedNodeTypes = Object.freeze({ workflow: WorkflowNode })
const sharedEdgeTypes = Object.freeze({ floating: FloatingWorkflowEdge })

const WorkflowCanvasInner = forwardRef(function WorkflowCanvasInner(
  {
    nodes: suppliedNodes,
    edges,
    defaultPositions,
    selectedNodeId,
    onSelectNode,
    onLayoutChange,
    ariaLabel = 'Workflow canvas',
  },
  ref,
) {
  const initialNodes = useRef(suppliedNodes)
  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes.current)
  const flowInstance = useRef(null)

  useEffect(() => {
    setNodes((current) => {
      const currentNodes = new Map(current.map((node) => [node.id, node]))
      return suppliedNodes.map((node) => {
        const existing = currentNodes.get(node.id)
        return {
          ...existing,
          ...node,
          position: existing?.position ?? node.position,
          selected: node.id === selectedNodeId,
          data: node.data,
        }
      })
    })
  }, [selectedNodeId, setNodes, suppliedNodes])

  function arrange() {
    setNodes((current) => positionWorkflowNodes(current, defaultPositions))
    window.setTimeout(() => flowInstance.current?.fitView({ padding: 0.16, duration: 250 }), 0)
  }

  useImperativeHandle(ref, () => ({
    autoArrange: arrange,
    resetLayout: arrange,
    fitView: () => flowInstance.current?.fitView({ padding: 0.16, duration: 250 }),
    focusNode: (nodeId) => {
      const node = nodes.find((item) => item.id === nodeId)
      if (node) flowInstance.current?.fitView({ nodes: [node], padding: 0.8, duration: 250, maxZoom: 1 })
    },
  }))

  function handleNodesChange(changes) {
    onNodesChange(changes)
    if (changes.some((change) => change.type === 'position' && change.position)) {
      onLayoutChange?.(changes)
    }
  }

  return (
    <div className="h-[33rem] min-h-[26rem] w-full" aria-label={ariaLabel}>
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={sharedNodeTypes}
        edgeTypes={sharedEdgeTypes}
        onNodesChange={handleNodesChange}
        onNodeClick={(_, node) => onSelectNode?.(node.id)}
        onInit={(instance) => { flowInstance.current = instance }}
        fitView
        fitViewOptions={{ padding: 0.16 }}
        minZoom={0.45}
        maxZoom={1.5}
        nodesConnectable={false}
        connectOnClick={false}
        edgesReconnectable={false}
        nodesDraggable
        panOnDrag
        selectionOnDrag={false}
        nodeClickDistance={4}
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

const WorkflowCanvas = forwardRef(function WorkflowCanvas(props, ref) {
  return (
    <ReactFlowProvider>
      <WorkflowCanvasInner {...props} ref={ref} />
    </ReactFlowProvider>
  )
})

export default WorkflowCanvas
