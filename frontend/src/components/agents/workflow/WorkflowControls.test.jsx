import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import WorkflowControls from './WorkflowControls.jsx'

describe('WorkflowControls', () => {
  it('exposes Auto Arrange and Reset Layout without owning workflow behavior', async () => {
    const user = userEvent.setup()
    const onAutoArrange = vi.fn()
    const onResetLayout = vi.fn()
    render(<WorkflowControls onAutoArrange={onAutoArrange} onResetLayout={onResetLayout} />)

    await user.click(screen.getByRole('button', { name: 'Auto Arrange' }))
    await user.click(screen.getByRole('button', { name: 'Reset Layout' }))

    expect(onAutoArrange).toHaveBeenCalledOnce()
    expect(onResetLayout).toHaveBeenCalledOnce()
  })
})
