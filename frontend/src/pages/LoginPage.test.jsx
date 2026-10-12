import { act, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { MemoryRouter, Route, Routes } from 'react-router-dom'

import { login } from '../services/authService.js'
import LoginPage from './LoginPage.jsx'

const establishSession = vi.fn()

vi.mock('../services/authService.js', () => ({
  login: vi.fn(),
}))

vi.mock('../features/auth/useAuth.js', () => ({
  useAuth: () => ({ establishSession }),
}))

function renderLogin(initialEntry = '/login') {
  return render(
    <MemoryRouter initialEntries={[initialEntry]}>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<h1>Create your account</h1>} />
        <Route path="/projects" element={<h1>Projects destination</h1>} />
        <Route path="/projects/:projectId" element={<h1>Project destination</h1>} />
      </Routes>
    </MemoryRouter>,
  )
}

async function completeForm(user, values = {}) {
  await user.type(
    screen.getByRole('textbox', { name: /^email/i }),
    values.email ?? '  ada@example.com  ',
  )
  await user.type(
    screen.getByLabelText(/^password/i),
    values.password ?? 'secret',
  )
}

describe('LoginPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    establishSession.mockResolvedValue({ user_id: 'USR-001' })
  })

  it('renders the login fields, action, and runtime illustration', () => {
    renderLogin()

    expect(screen.getByRole('heading', { name: 'Welcome back' })).toBeInTheDocument()
    expect(screen.getByRole('textbox', { name: /^email/i })).toBeRequired()
    expect(screen.getByLabelText(/^password/i)).toBeRequired()
    expect(screen.getByRole('button', { name: 'Sign in' })).toBeInTheDocument()
    expect(screen.getByTestId('auth-illustration')).toHaveAttribute(
      'src',
      expect.stringContaining('login-illustration'),
    )
  })

  it('keeps unsupported login controls hidden', () => {
    renderLogin()

    expect(screen.queryByText(/continue with google/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/continue with microsoft/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/forgot password/i)).not.toBeInTheDocument()
  })

  it('shows and hides the password accessibly', async () => {
    const user = userEvent.setup()
    renderLogin()
    const password = screen.getByLabelText(/^password/i)

    expect(password).toHaveAttribute('type', 'password')
    await user.click(screen.getByRole('button', { name: 'Show password' }))
    expect(password).toHaveAttribute('type', 'text')
    expect(screen.getByRole('button', { name: 'Hide password' })).toBeInTheDocument()
  })

  it('does not submit empty fields and exposes associated field errors', async () => {
    const user = userEvent.setup()
    renderLogin()

    await user.click(screen.getByRole('button', { name: 'Sign in' }))

    expect(login).not.toHaveBeenCalled()
    expect(screen.getByText('Enter your email.')).toBeInTheDocument()
    expect(screen.getByText('Enter your password.')).toBeInTheDocument()
    expect(screen.getByRole('textbox', { name: /^email/i })).toHaveAttribute(
      'aria-invalid',
      'true',
    )
  })

  it('submits trimmed email and password through authService', async () => {
    const user = userEvent.setup()
    login.mockResolvedValue({ data: { access_token: 'jwt-token' } })
    renderLogin()
    await completeForm(user)

    await user.click(screen.getByRole('button', { name: 'Sign in' }))

    await waitFor(() => {
      expect(login).toHaveBeenCalledWith({
        email: 'ada@example.com',
        password: 'secret',
      })
    })
  })

  it('disables the submit action and exposes busy state while logging in', async () => {
    const user = userEvent.setup()
    let resolveLogin
    login.mockReturnValue(
      new Promise((resolve) => {
        resolveLogin = resolve
      }),
    )
    renderLogin()
    await completeForm(user)

    await user.click(screen.getByRole('button', { name: 'Sign in' }))

    const busyButton = screen.getByRole('button', { name: 'Signing in' })
    expect(busyButton).toBeDisabled()
    expect(busyButton).toHaveAttribute('aria-busy', 'true')

    await act(async () => {
      resolveLogin({ data: { access_token: 'jwt-token' } })
    })
  })

  it('establishes the session with only the access token and navigates to projects', async () => {
    const user = userEvent.setup()
    login.mockResolvedValue({
      data: { access_token: 'jwt-token', token_type: 'bearer' },
    })
    renderLogin()
    await completeForm(user)

    await user.click(screen.getByRole('button', { name: 'Sign in' }))

    expect(await screen.findByRole('heading', { name: 'Projects destination' })).toBeInTheDocument()
    expect(establishSession).toHaveBeenCalledOnce()
    expect(establishSession).toHaveBeenCalledWith('jwt-token')
    expect(establishSession).not.toHaveBeenCalledWith('bearer')
  })

  it('returns to the intended protected route after a verified login', async () => {
    const user = userEvent.setup()
    login.mockResolvedValue({ data: { access_token: 'jwt-token' } })
    renderLogin({
      pathname: '/login',
      state: { from: { pathname: '/projects/PRJ-001', search: '', hash: '' } },
    })
    await completeForm(user)

    await user.click(screen.getByRole('button', { name: 'Sign in' }))

    expect(await screen.findByRole('heading', { name: 'Project destination' })).toBeInTheDocument()
  })

  it('shows safe invalid-credentials feedback for a 401 response', async () => {
    const user = userEvent.setup()
    login.mockRejectedValue({ status: 401, message: 'Internal auth detail' })
    renderLogin()
    await completeForm(user)

    await user.click(screen.getByRole('button', { name: 'Sign in' }))

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Invalid email or password.',
    )
    expect(screen.queryByText('Internal auth detail')).not.toBeInTheDocument()
  })

  it.each([
    ['email', 'Email is invalid'],
    ['body.password', 'Password is invalid'],
  ])('maps a backend %s error to its field', async (field, message) => {
    const user = userEvent.setup()
    login.mockRejectedValue({
      status: 422,
      errors: [{ field, message }],
    })
    renderLogin()
    await completeForm(user)

    await user.click(screen.getByRole('button', { name: 'Sign in' }))

    expect(await screen.findByText(message)).toBeInTheDocument()
    const fieldName = field.split('.').at(-1)
    expect(screen.getByLabelText(new RegExp(`^${fieldName}`, 'i'))).toHaveAttribute(
      'aria-invalid',
      'true',
    )
  })

  it('shows safe form feedback for a network failure', async () => {
    const user = userEvent.setup()
    login.mockRejectedValue(new Error('Network implementation detail'))
    renderLogin()
    await completeForm(user)

    await user.click(screen.getByRole('button', { name: 'Sign in' }))

    expect(await screen.findByRole('alert')).toHaveTextContent(
      "We couldn't sign you in right now. Please try again.",
    )
    expect(screen.queryByText('Network implementation detail')).not.toBeInTheDocument()
  })

  it('does not persist or navigate when a successful response has no token', async () => {
    const user = userEvent.setup()
    login.mockResolvedValue({ data: { token_type: 'bearer' } })
    renderLogin()
    await completeForm(user)

    await user.click(screen.getByRole('button', { name: 'Sign in' }))

    expect(await screen.findByRole('alert')).toHaveTextContent(
      "We couldn't sign you in right now. Please try again.",
    )
    expect(establishSession).not.toHaveBeenCalled()
    expect(screen.getByRole('heading', { name: 'Welcome back' })).toBeInTheDocument()
  })

  it('shows safe feedback and does not navigate when session establishment fails', async () => {
    const user = userEvent.setup()
    login.mockResolvedValue({ data: { access_token: 'jwt-token' } })
    establishSession.mockRejectedValue(new Error('Session verification failed'))
    renderLogin()
    await completeForm(user)

    await user.click(screen.getByRole('button', { name: 'Sign in' }))

    expect(await screen.findByRole('alert')).toHaveTextContent(
      "We couldn't sign you in right now. Please try again.",
    )
    expect(establishSession).toHaveBeenCalledWith('jwt-token')
    expect(screen.getByRole('heading', { name: 'Welcome back' })).toBeInTheDocument()
  })

  it('renders the registration success notice only when passed in navigation state', () => {
    const message = 'Account created successfully. Sign in to continue.'
    const { unmount } = renderLogin({
      pathname: '/login',
      state: { registrationSuccess: message },
    })

    expect(screen.getByRole('status')).toHaveTextContent(message)
    unmount()
    renderLogin()
    expect(screen.queryByRole('status')).not.toBeInTheDocument()
  })

  it('routes the create-account link to registration', async () => {
    const user = userEvent.setup()
    renderLogin()

    await user.click(screen.getByRole('link', { name: 'Create account' }))

    expect(screen.getByRole('heading', { name: 'Create your account' })).toBeInTheDocument()
  })
})
