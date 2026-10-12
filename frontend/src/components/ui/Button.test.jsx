import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import Button from './Button.jsx'

describe('Button', () => {
  it('renders children and exposes the selected variant', () => {
    render(<Button variant="secondary">Continue</Button>)

    const button = screen.getByRole('button', { name: 'Continue' })
    expect(button).toBeInTheDocument()
    expect(button).toHaveAttribute('data-variant', 'secondary')
  })

  it('runs its click handler when enabled', async () => {
    const user = userEvent.setup()
    const onClick = vi.fn()
    render(<Button onClick={onClick}>Continue</Button>)

    await user.click(screen.getByRole('button', { name: 'Continue' }))

    expect(onClick).toHaveBeenCalledOnce()
  })

  it('does not run its click handler when disabled', async () => {
    const user = userEvent.setup()
    const onClick = vi.fn()
    render(
      <Button disabled onClick={onClick}>
        Continue
      </Button>,
    )

    const button = screen.getByRole('button', { name: 'Continue' })
    expect(button).toBeDisabled()
    await user.click(button)
    expect(onClick).not.toHaveBeenCalled()
  })

  it('disables interaction and exposes loading state', () => {
    render(
      <Button loading loadingLabel="Creating project">
        Create project
      </Button>,
    )

    const button = screen.getByRole('button', { name: 'Creating project' })
    expect(button).toBeDisabled()
    expect(button).toHaveAttribute('aria-busy', 'true')
    expect(screen.getByRole('status', { name: 'Creating project' })).toBeInTheDocument()
  })
})
