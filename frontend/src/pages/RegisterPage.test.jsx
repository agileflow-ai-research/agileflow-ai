import { act, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { MemoryRouter, Route, Routes } from 'react-router-dom'

import LoginPage from './LoginPage.jsx'
import RegisterPage from './RegisterPage.jsx'
import { register } from '../services/authService.js'

vi.mock('../services/authService.js', () => ({
  login: vi.fn(),
  register: vi.fn(),
}))

vi.mock('../features/auth/useAuth.js', () => ({
  useAuth: () => ({ establishSession: vi.fn() }),
}))

function renderRegistration() {
  return render(
    <MemoryRouter initialEntries={['/register']}>
      <Routes>
        <Route path="/register" element={<RegisterPage />} />
        <Route path="/login" element={<LoginPage />} />
      </Routes>
    </MemoryRouter>,
  )
}

async function completeForm(user, values = {}) {
  await user.type(
    screen.getByRole('textbox', { name: /full name/i }),
    values.name ?? '  Ada Lovelace  ',
  )
  await user.type(
    screen.getByRole('textbox', { name: /work email/i }),
    values.email ?? '  ada@example.com  ',
  )
  await user.type(
    screen.getByLabelText(/^password/i),
    values.password ?? 'secret',
  )
}

describe('RegisterPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    sessionStorage.clear()
  })

  it('renders the registration fields, submit action, and runtime illustration', () => {
    renderRegistration()

    expect(
      screen.getByRole('heading', { name: 'Create your account' }),
    ).toBeInTheDocument()
    expect(screen.getByRole('textbox', { name: /full name/i })).toBeRequired()
    expect(screen.getByRole('textbox', { name: /work email/i })).toBeRequired()
    expect(screen.getByLabelText(/^password/i)).toBeRequired()
    expect(
      screen.getByRole('button', { name: 'Create account' }),
    ).toBeInTheDocument()
    expect(screen.getByTestId('auth-illustration')).toHaveAttribute(
      'src',
      expect.stringContaining('signup-illustration'),
    )
  })

  it('keeps unsupported social login and password-policy controls hidden', () => {
    renderRegistration()

    expect(screen.queryByText(/continue with google/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/continue with microsoft/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/at least 8 characters/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/include a number/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/include a letter/i)).not.toBeInTheDocument()
  })

  it('shows and hides the password accessibly', async () => {
    const user = userEvent.setup()
    renderRegistration()
    const password = screen.getByLabelText(/^password/i)

    expect(password).toHaveAttribute('type', 'password')
    await user.click(screen.getByRole('button', { name: 'Show password' }))
    expect(password).toHaveAttribute('type', 'text')
    expect(
      screen.getByRole('button', { name: 'Hide password' }),
    ).toBeInTheDocument()
  })

  it('does not submit empty fields and exposes associated field errors', async () => {
    const user = userEvent.setup()
    renderRegistration()

    await user.click(screen.getByRole('button', { name: 'Create account' }))

    expect(register).not.toHaveBeenCalled()
    expect(screen.getByText('Enter your full name.')).toBeInTheDocument()
    expect(screen.getByText('Enter your work email.')).toBeInTheDocument()
    expect(screen.getByText('Enter a password.')).toBeInTheDocument()
    expect(screen.getByRole('textbox', { name: /full name/i })).toHaveAttribute(
      'aria-invalid',
      'true',
    )
  })

  it('submits trimmed identity fields through authService', async () => {
    const user = userEvent.setup()
    register.mockResolvedValue({ status: 201, data: { user_id: 'USR-001' } })
    renderRegistration()
    await completeForm(user)

    await user.click(screen.getByRole('button', { name: 'Create account' }))

    await waitFor(() => {
      expect(register).toHaveBeenCalledWith({
        name: 'Ada Lovelace',
        email: 'ada@example.com',
        password: 'secret',
      })
    })
  })

  it('disables the submit action and exposes busy state while registering', async () => {
    const user = userEvent.setup()
    let resolveRegistration
    register.mockReturnValue(
      new Promise((resolve) => {
        resolveRegistration = resolve
      }),
    )
    renderRegistration()
    await completeForm(user)

    await user.click(screen.getByRole('button', { name: 'Create account' }))

    const busyButton = screen.getByRole('button', { name: 'Creating account' })
    expect(busyButton).toBeDisabled()
    expect(busyButton).toHaveAttribute('aria-busy', 'true')

    await act(async () => {
      resolveRegistration({ status: 201 })
    })
  })

  it('navigates to login with a success notice and stores no token', async () => {
    const user = userEvent.setup()
    register.mockResolvedValue({ status: 201, data: { user_id: 'USR-001' } })
    renderRegistration()
    await completeForm(user)

    await user.click(screen.getByRole('button', { name: 'Create account' }))

    expect(
      await screen.findByText('Account created successfully. Sign in to continue.'),
    ).toHaveAttribute('role', 'status')
    expect(screen.getByRole('heading', { name: 'Welcome back' })).toBeInTheDocument()
    expect(sessionStorage.getItem('agileflow_access_token')).toBeNull()
  })

  it('shows duplicate email field errors beside the email control', async () => {
    const user = userEvent.setup()
    register.mockRejectedValue({
      status: 409,
      errors: [{ field: 'email', message: 'Email is already registered' }],
    })
    renderRegistration()
    await completeForm(user)

    await user.click(screen.getByRole('button', { name: 'Create account' }))

    expect(await screen.findByText('Email is already registered')).toBeInTheDocument()
    expect(screen.getByRole('textbox', { name: /work email/i })).toHaveAttribute(
      'aria-invalid',
      'true',
    )
  })

  it('maps backend validation errors to matching fields', async () => {
    const user = userEvent.setup()
    register.mockRejectedValue({
      status: 422,
      errors: [{ field: 'body.name', message: 'Name is invalid' }],
    })
    renderRegistration()
    await completeForm(user)

    await user.click(screen.getByRole('button', { name: 'Create account' }))

    expect(await screen.findByText('Name is invalid')).toBeInTheDocument()
    expect(screen.getByRole('textbox', { name: /full name/i })).toHaveAttribute(
      'aria-invalid',
      'true',
    )
  })

  it('shows safe form feedback for duplicate and unavailable-service failures', async () => {
    const user = userEvent.setup()
    register.mockRejectedValueOnce({ status: 409, errors: [] })
    const { unmount } = renderRegistration()
    await completeForm(user)
    await user.click(screen.getByRole('button', { name: 'Create account' }))
    expect(
      await screen.findByRole('alert'),
    ).toHaveTextContent('An account with this email already exists.')

    unmount()
    register.mockRejectedValueOnce(new Error('Internal connection details'))
    renderRegistration()
    await completeForm(user)
    await user.click(screen.getByRole('button', { name: 'Create account' }))
    expect(await screen.findByRole('alert')).toHaveTextContent(
      "We couldn't create your account right now. Please try again.",
    )
    expect(screen.queryByText('Internal connection details')).not.toBeInTheDocument()
  })

  it('routes the sign-in link to the login placeholder', async () => {
    const user = userEvent.setup()
    renderRegistration()

    await user.click(screen.getByRole('link', { name: 'Sign in' }))

    expect(screen.getByRole('heading', { name: 'Welcome back' })).toBeInTheDocument()
  })
})
