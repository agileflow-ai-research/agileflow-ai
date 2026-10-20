import { BaseEdge, getBezierPath, useInternalNode } from '@xyflow/react'

import { calculateFloatingConnection } from './floatingEdgeGeometry.js'

export default function FloatingWorkflowEdge({ id, source, target, markerEnd, style }) {
  const sourceNode = useInternalNode(source)
  const targetNode = useInternalNode(target)
  const connection = sourceNode && targetNode
    ? calculateFloatingConnection(sourceNode, targetNode)
    : null

  if (!connection) return null
  const [path] = getBezierPath({ ...connection, curvature: 0.28 })

  return (
    <BaseEdge
      id={id}
      path={path}
      markerEnd={markerEnd}
      style={style}
      interactionWidth={0}
    />
  )
}
