import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import Input from './Input.jsx'
import PasswordInput from './PasswordInput.jsx'
import Select from './Select.jsx'
import Textarea from './Textarea.jsx'

describe('form controls', () => {
  it('associates Input labels, errors, and required state', () => {
    render(
      <Input
        label="Email"
        name="email"
        required
        error="Enter a valid email"
        helperText="Use your work email"
      />,
    )

    const input = screen.getByLabelText(/Email/)
    expect(input).toBeRequired()
    expect(input).toHaveAttribute('aria-invalid', 'true')
    expect(input).toHaveAccessibleDescription(
      'Use your work email Enter a valid email',
    )
  })

  it('starts PasswordInput hidden and toggles visibility accessibly', async () => {
    const user = userEvent.setup()
    render(<PasswordInput label="Password" name="password" />)

    const input = screen.getByLabelText('Password')
    expect(input).toHaveAttribute('type', 'password')

    await user.click(screen.getByRole('button', { name: 'Show password' }))
    expect(input).toHaveAttribute('type', 'text')
    expect(screen.getByRole('button', { name: 'Hide password' })).toBeInTheDocument()
  })

  it('associates Textarea labels and errors', () => {
    render(
      <Textarea
        label="Project description"
        error="Description is too long"
        rows={6}
      />,
    )

    const textarea = screen.getByLabelText('Project description')
    expect(textarea).toHaveAttribute('rows', '6')
    expect(textarea).toHaveAttribute('aria-invalid', 'true')
    expect(textarea).toHaveAccessibleDescription('Description is too long')
  })

  it('renders Select options and reports changes', async () => {
    const user = userEvent.setup()
    const onChange = vi.fn()
    render(
      <Select
        label="Domain"
        name="domain"
        options={[
          { value: 'education', label: 'Education' },
          { value: 'healthcare', label: 'Healthcare' },
        ]}
        onChange={onChange}
      />,
    )

    const select = screen.getByLabelText('Domain')
    expect(screen.getByRole('option', { name: 'Education' })).toBeInTheDocument()
    await user.selectOptions(select, 'healthcare')
    expect(select).toHaveValue('healthcare')
    expect(onChange).toHaveBeenCalled()
  })
})
