import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

const flow = vi.hoisted(() => ({ nodes: {}, pathCalls: [] }))

vi.mock('@xyflow/react', () => ({
  BaseEdge: ({ id, path, markerEnd }) => (
    <path data-testid={id} data-path={path} data-marker-end={markerEnd} />
  ),
  getBezierPath: (connection) => {
    flow.pathCalls.push(connection)
    return [`M ${connection.sourceX} ${connection.sourceY} C ${connection.targetX} ${connection.targetY}`]
  },
  Position: { Left: 'left', Right: 'right', Top: 'top', Bottom: 'bottom' },
  useInternalNode: (id) => flow.nodes[id],
}))

import FloatingWorkflowEdge from './FloatingWorkflowEdge.jsx'

function node(x, y) {
  return {
    measured: { width: 240, height: 120 },
    internals: { positionAbsolute: { x, y } },
  }
}

describe('FloatingWorkflowEdge', () => {
  it('renders a marked Bezier path from current internal node bounds', () => {
    flow.nodes = { source: node(0, 0), target: node(300, 0) }
    flow.pathCalls = []
    const view = render(
      <svg><FloatingWorkflowEdge id="edge-1" source="source" target="target" markerEnd="url(#arrow)" /></svg>,
    )

    expect(screen.getByTestId('edge-1')).toHaveAttribute('data-marker-end', 'url(#arrow)')
    expect(flow.pathCalls.at(-1)).toMatchObject({
      sourceX: 240, sourcePosition: 'right', targetX: 300, targetPosition: 'left',
    })

    flow.nodes.target = node(100, 300)
    view.rerender(
      <svg><FloatingWorkflowEdge id="edge-1" source="source" target="target" markerEnd="url(#arrow)" /></svg>,
    )
    expect(flow.pathCalls.at(-1)).toMatchObject({
      sourcePosition: 'bottom', targetPosition: 'top',
    })
  })
})
