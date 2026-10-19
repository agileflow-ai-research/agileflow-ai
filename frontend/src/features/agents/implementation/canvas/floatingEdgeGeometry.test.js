import { describe, expect, it } from 'vitest'

import { calculateFloatingConnection } from './floatingEdgeGeometry.js'

function node(x, y, width = 240, height = 120) {
  return {
    measured: { width, height },
    internals: { positionAbsolute: { x, y } },
  }
}

describe('floating workflow edge geometry', () => {
  it('attaches horizontal dependencies to the facing node borders', () => {
    expect(calculateFloatingConnection(node(0, 0), node(300, 0))).toMatchObject({
      sourceX: 240,
      sourceY: 60,
      sourcePosition: 'right',
      targetX: 300,
      targetY: 60,
      targetPosition: 'left',
    })
  })

  it('uses measured dimensions and changes both endpoints when a node moves', () => {
    const source = node(0, 0, 200, 80)
    const before = calculateFloatingConnection(source, node(260, 0, 300, 160))
    const after = calculateFloatingConnection(source, node(80, 260, 300, 160))

    expect(after).not.toEqual(before)
    expect(after.sourcePosition).toBe('bottom')
    expect(after.targetPosition).toBe('top')
    expect(after.sourceY).toBe(80)
    expect(after.targetY).toBe(260)
  })

  it('recalculates edge geometry when the source node moves', () => {
    const target = node(500, 0)
    const before = calculateFloatingConnection(node(0, 0), target)
    const after = calculateFloatingConnection(node(260, 260), target)

    expect(after).not.toEqual(before)
    expect(after.sourcePosition).toBe('top')
    expect(after.targetPosition).toBe('bottom')
  })

  it('recalculates incoming and outgoing geometry for a moved middle node', () => {
    const upstream = node(0, 0)
    const downstream = node(600, 0)
    const middleBefore = node(300, 0)
    const middleAfter = node(300, 260)

    const incomingBefore = calculateFloatingConnection(upstream, middleBefore)
    const outgoingBefore = calculateFloatingConnection(middleBefore, downstream)
    const incomingAfter = calculateFloatingConnection(upstream, middleAfter)
    const outgoingAfter = calculateFloatingConnection(middleAfter, downstream)

    expect(incomingAfter).not.toEqual(incomingBefore)
    expect(outgoingAfter).not.toEqual(outgoingBefore)
    expect(incomingAfter.targetY).toBe(260)
    expect(outgoingAfter.sourceY).toBe(260)
  })
})
