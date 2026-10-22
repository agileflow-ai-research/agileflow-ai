import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

vi.mock('@xyflow/react', () => ({
  Handle: ({ type, className, isConnectable }) => (
    <span data-testid={`handle-${type}`} data-connectable={String(isConnectable)} className={className} />
  ),
  Position: { Left: 'left', Right: 'right' },
}))

import WorkflowNode from './WorkflowNode.jsx'

function renderNode(status, selected = false) {
  render(<WorkflowNode data={{ title: 'Input Analysis', summary: 'Summary', status, locked: status === 'LOCKED' }} selected={selected} />)
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
  ])('maps %s through the shared visual system', (status, visual) => {
    const node = renderNode(status)
    expect(node).toHaveAttribute('data-workflow-status', status)
    expect(node).toHaveAttribute('data-workflow-visual', visual)
    expect(node).toHaveClass(`workflow-node--${visual}`)
    expect(node).not.toHaveClass('workflow-node--selected')
  })

  it('keeps selection independent from processing status', () => {
    const node = renderNode('RUNNING', true)
    expect(node).toHaveClass('workflow-node--processing')
    expect(node).toHaveClass('workflow-node--selected')
    expect(node).toHaveAttribute('data-selected', 'true')
  })

  it('renders locked state and keeps required edge handles non-interactive', () => {
    const node = renderNode('LOCKED')
    expect(node).toHaveTextContent('Not implemented yet')
    ;['target', 'source'].forEach((type) => {
      const handle = screen.getByTestId(`handle-${type}`)
      expect(handle).toHaveClass('pointer-events-none', 'opacity-0')
      expect(handle).toHaveAttribute('data-connectable', 'false')
    })
  })

  it('uses a truthful supplied reason for an implemented locked node', () => {
    render(<WorkflowNode data={{ title: 'Context & Testability', status: 'LOCKED', locked: true, lockedNote: 'Available after Testing Intelligence.' }} />)
    const node = screen.getByRole('button', { name: 'Open Context & Testability' })
    expect(node).toHaveTextContent('Available after Testing Intelligence.')
    expect(node).not.toHaveTextContent('Not implemented yet')
  })

  it('keeps the full card available to React Flow dragging', () => {
    renderNode('WAITING_FOR_HUMAN')
    const card = screen.getByRole('button', { name: 'Open Input Analysis' })
    expect(card).not.toHaveClass('nodrag')
    expect(card).toHaveClass('cursor-grab')
  })
})
