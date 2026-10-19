import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

vi.mock('@xyflow/react', () => ({
  Handle: () => null,
  Position: { Left: 'left', Right: 'right' },
}))

import WorkflowNode from './WorkflowNode.jsx'

function renderNode(status, selected = false) {
  render(<WorkflowNode data={{ title: 'Input Analysis', summary: 'Summary', status, onOpen: vi.fn() }} selected={selected} />)
  return screen.getByRole('button', { name: 'Open Input Analysis' }).parentElement
}

describe('WorkflowNode status presentation', () => {
  it.each([
    ['RUNNING', 'processing'],
    ['WAITING_FOR_HUMAN', 'warning'],
    ['NEEDS_ATTENTION', 'warning'],
    ['FAILED', 'failed'],
    ['BLOCKED', 'blocked'],
    ['COMPLETE', 'success'],
    ['LOCKED', 'locked'],
  ])('maps %s through the reusable visual system', (status, visual) => {
    const node = renderNode(status)
    expect(node).toHaveAttribute('data-workflow-status', status)
    expect(node).toHaveAttribute('data-workflow-visual', visual)
    expect(node).toHaveClass(`implementation-workflow-node--${visual}`)
    expect(node).not.toHaveClass('implementation-workflow-node--selected')
  })

  it('keeps selection independent from processing status', () => {
    const node = renderNode('RUNNING', true)
    expect(node).toHaveClass('implementation-workflow-node--processing')
    expect(node).toHaveClass('implementation-workflow-node--selected')
    expect(node).toHaveAttribute('data-selected', 'true')
  })
})
