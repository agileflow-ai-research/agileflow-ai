import { describe, expect, it } from 'vitest'

import { positionWorkflowNodes } from './layout.js'

describe('positionWorkflowNodes', () => {
  it('applies supplied defaults without mutating agent-owned nodes or positions', () => {
    const originalPosition = { x: 90, y: 80 }
    const nodes = [
      { id: 'ONE', position: originalPosition },
      { id: 'TWO', position: { x: 10, y: 20 } },
    ]
    const positions = { ONE: { x: 0, y: 20 } }

    const positioned = positionWorkflowNodes(nodes, positions)

    expect(positioned.map((node) => node.position)).toEqual([{ x: 0, y: 20 }, { x: 10, y: 20 }])
    expect(nodes[0].position).toBe(originalPosition)
    expect(positioned[0].position).not.toBe(positions.ONE)
  })
})
