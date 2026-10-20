import { Position } from '@xyflow/react'

function dimensions(node) {
  return {
    width: node?.measured?.width ?? node?.width ?? 0,
    height: node?.measured?.height ?? node?.height ?? 0,
  }
}

export function getNodeBorderIntersection(node, towardNode) {
  const { width, height } = dimensions(node)
  const target = dimensions(towardNode)
  if (!width || !height || !target.width || !target.height) return null

  const position = node.internals.positionAbsolute
  const towardPosition = towardNode.internals.positionAbsolute
  const halfWidth = width / 2
  const halfHeight = height / 2
  const centerX = position.x + halfWidth
  const centerY = position.y + halfHeight
  const towardCenterX = towardPosition.x + target.width / 2
  const towardCenterY = towardPosition.y + target.height / 2
  const normalizedX = (towardCenterX - centerX) / (2 * halfWidth)
    - (towardCenterY - centerY) / (2 * halfHeight)
  const normalizedY = (towardCenterX - centerX) / (2 * halfWidth)
    + (towardCenterY - centerY) / (2 * halfHeight)
  const scale = 1 / (Math.abs(normalizedX) + Math.abs(normalizedY))
  const borderX = scale * normalizedX
  const borderY = scale * normalizedY

  return {
    x: halfWidth * (borderX + borderY) + centerX,
    y: halfHeight * (-borderX + borderY) + centerY,
  }
}

export function getBorderPosition(node, point) {
  const { width } = dimensions(node)
  const position = node.internals.positionAbsolute
  const tolerance = 1
  if (point.x <= position.x + tolerance) return Position.Left
  if (point.x >= position.x + width - tolerance) return Position.Right
  if (point.y <= position.y + tolerance) return Position.Top
  return Position.Bottom
}

export function calculateFloatingConnection(sourceNode, targetNode) {
  const source = getNodeBorderIntersection(sourceNode, targetNode)
  const target = getNodeBorderIntersection(targetNode, sourceNode)
  if (!source || !target) return null

  return {
    sourceX: source.x,
    sourceY: source.y,
    sourcePosition: getBorderPosition(sourceNode, source),
    targetX: target.x,
    targetY: target.y,
    targetPosition: getBorderPosition(targetNode, target),
  }
}
