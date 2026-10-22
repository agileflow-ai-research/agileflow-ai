import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import WorkflowNodeModal from './WorkflowNodeModal.jsx'

const node = {
  id: 'REVIEW',
  title: 'Review',
  purpose: 'Review supplied evidence.',
  status: 'WAITING_FOR_HUMAN',
}

describe('WorkflowNodeModal', () => {
  it('keeps children mounted while hidden and accepts a caller-owned eyebrow', () => {
    const view = render(
      <WorkflowNodeModal node={node} open={false} onClose={vi.fn()} eyebrow="Agent workflow">
        <span>Mounted workspace</span>
      </WorkflowNodeModal>,
    )

    expect(screen.getByText('Mounted workspace')).toBeInTheDocument()
    expect(screen.getByTestId('workflow-modal-backdrop')).toHaveAttribute('hidden')

    view.rerender(
      <WorkflowNodeModal node={node} open onClose={vi.fn()} eyebrow="Agent workflow">
        <span>Mounted workspace</span>
      </WorkflowNodeModal>,
    )
    expect(screen.getByRole('dialog', { name: 'Review' })).toBeInTheDocument()
    expect(screen.getByText('Agent workflow')).toBeInTheDocument()
    expect(screen.getByText('Needs Your Review')).toBeInTheDocument()
    expect(screen.getByTestId('workflow-modal-body')).toHaveClass('overflow-y-auto')
    expect(screen.getByRole('dialog')).toHaveClass('max-h-[calc(100dvh-1rem)]')
  })

  it('closes from the button and Escape', async () => {
    const user = userEvent.setup()
    const onClose = vi.fn()
    render(
      <WorkflowNodeModal node={node} open onClose={onClose}>
        <span>Content</span>
      </WorkflowNodeModal>,
    )

    await user.click(screen.getByRole('button', { name: 'Close workflow modal' }))
    expect(onClose).toHaveBeenCalledOnce()
    await user.keyboard('{Escape}')
    expect(onClose).toHaveBeenCalledTimes(2)
  })
})
