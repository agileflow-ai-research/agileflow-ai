import { act, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { setUnauthorizedHandler } from '../../services/apiClient.js'
import { getCurrentUser } from '../../services/authService.js'
import {
  getAccessToken,
  removeAccessToken,
  setAccessToken,
} from '../../services/tokenStorage.js'
import AuthProvider from './AuthProvider.jsx'
import { useAuth } from './useAuth.js'

vi.mock('../../services/authService.js', () => ({
  getCurrentUser: vi.fn(),
}))

vi.mock('../../services/tokenStorage.js', () => ({
  getAccessToken: vi.fn(),
  removeAccessToken: vi.fn(),
  setAccessToken: vi.fn(),
}))

vi.mock('../../services/apiClient.js', () => ({
  setUnauthorizedHandler: vi.fn(() => vi.fn()),
}))

const user = {
  user_id: 'USR-001',
  name: 'Ada Lovelace',
  email: 'ada@example.com',
  is_active: true,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
}

function SessionProbe() {
  const auth = useAuth()

  return (
    <div>
      <p data-testid="status">{auth.status}</p>
      <p data-testid="user">{auth.user?.email ?? 'no-user'}</p>
      {auth.sessionError ? <p role="alert">{auth.sessionError}</p> : null}
      <button type="button" onClick={auth.retrySession}>Retry</button>
      <button type="button" onClick={auth.logout}>Logout</button>
      <button
        type="button"
        onClick={() => auth.establishSession('new-token').catch(() => {})}
      >
        Establish
      </button>
    </div>
  )
}

function renderProvider() {
  return render(
    <AuthProvider>
      <SessionProbe />
    </AuthProvider>,
  )
}

describe('AuthProvider', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    setUnauthorizedHandler.mockReturnValue(vi.fn())
  })

  it('becomes unauthenticated without calling /auth/me when no token exists', async () => {
    getAccessToken.mockReturnValue(null)
    renderProvider()

    await waitFor(() => {
      expect(screen.getByTestId('status')).toHaveTextContent('unauthenticated')
    })
    expect(getCurrentUser).not.toHaveBeenCalled()
    expect(screen.getByTestId('user')).toHaveTextContent('no-user')
  })

  it('bootstraps an authenticated user from an existing valid token', async () => {
    getAccessToken.mockReturnValue('stored-token')
    getCurrentUser.mockResolvedValue({ data: user })
    renderProvider()

    await waitFor(() => {
      expect(screen.getByTestId('status')).toHaveTextContent('authenticated')
    })
    expect(getCurrentUser).toHaveBeenCalledOnce()
    expect(screen.getByTestId('user')).toHaveTextContent(user.email)
  })

  it('removes an invalid token and becomes unauthenticated after /auth/me 401', async () => {
    getAccessToken.mockReturnValue('invalid-token')
    getCurrentUser.mockRejectedValue({ status: 401 })
    renderProvider()

    await waitFor(() => {
      expect(screen.getByTestId('status')).toHaveTextContent('unauthenticated')
    })
    expect(removeAccessToken).toHaveBeenCalled()
    expect(screen.getByTestId('user')).toHaveTextContent('no-user')
  })

  it('preserves the token and exposes a safe error after a temporary failure', async () => {
    getAccessToken.mockReturnValue('stored-token')
    getCurrentUser.mockRejectedValue(new Error('Database implementation detail'))
    renderProvider()

    expect(await screen.findByRole('alert')).toHaveTextContent(
      "We couldn't verify your session right now. Please try again.",
    )
    expect(screen.getByTestId('status')).toHaveTextContent('error')
    expect(removeAccessToken).not.toHaveBeenCalled()
    expect(screen.queryByText('Database implementation detail')).not.toBeInTheDocument()
  })

  it('retries a temporary failure and becomes authenticated', async () => {
    const browserUser = userEvent.setup()
    getAccessToken.mockReturnValue('stored-token')
    getCurrentUser
      .mockRejectedValueOnce(new Error('Temporary outage'))
      .mockResolvedValueOnce({ data: user })
    renderProvider()

    await screen.findByRole('alert')
    await browserUser.click(screen.getByRole('button', { name: 'Retry' }))

    await waitFor(() => {
      expect(screen.getByTestId('status')).toHaveTextContent('authenticated')
    })
    expect(getCurrentUser).toHaveBeenCalledTimes(2)
    expect(removeAccessToken).not.toHaveBeenCalled()
  })

  it('logs out by clearing token and user', async () => {
    const browserUser = userEvent.setup()
    getAccessToken.mockReturnValue('stored-token')
    getCurrentUser.mockResolvedValue({ data: user })
    renderProvider()

    await waitFor(() => {
      expect(screen.getByTestId('status')).toHaveTextContent('authenticated')
    })
    await browserUser.click(screen.getByRole('button', { name: 'Logout' }))

    expect(removeAccessToken).toHaveBeenCalled()
    expect(screen.getByTestId('status')).toHaveTextContent('unauthenticated')
    expect(screen.getByTestId('user')).toHaveTextContent('no-user')
  })

  it('establishes and verifies a session after login', async () => {
    const browserUser = userEvent.setup()
    getAccessToken.mockReturnValue(null)
    getCurrentUser.mockResolvedValue({ data: user })
    renderProvider()
    await screen.findByText('unauthenticated')

    await browserUser.click(screen.getByRole('button', { name: 'Establish' }))

    await waitFor(() => {
      expect(screen.getByTestId('status')).toHaveTextContent('authenticated')
    })
    expect(setAccessToken).toHaveBeenCalledWith('new-token')
    expect(getCurrentUser).toHaveBeenCalledOnce()
    expect(screen.getByTestId('user')).toHaveTextContent(user.email)
  })

  it('does not falsely authenticate when session establishment fails', async () => {
    const browserUser = userEvent.setup()
    getAccessToken.mockReturnValue(null)
    getCurrentUser.mockRejectedValue(new Error('Temporary outage'))
    renderProvider()
    await screen.findByText('unauthenticated')

    await browserUser.click(screen.getByRole('button', { name: 'Establish' }))

    expect(await screen.findByRole('alert')).toHaveTextContent(
      "We couldn't verify your session right now. Please try again.",
    )
    expect(screen.getByTestId('status')).toHaveTextContent('error')
    expect(screen.getByTestId('user')).toHaveTextContent('no-user')
    expect(removeAccessToken).not.toHaveBeenCalled()
  })

  it('clears the session when the authenticated-401 handler is notified', async () => {
    getAccessToken.mockReturnValue('stored-token')
    getCurrentUser.mockResolvedValue({ data: user })
    renderProvider()

    await waitFor(() => {
      expect(screen.getByTestId('status')).toHaveTextContent('authenticated')
    })
    const unauthorizedHandler = setUnauthorizedHandler.mock.calls.at(-1)[0]
    act(() => unauthorizedHandler())

    expect(removeAccessToken).toHaveBeenCalled()
    expect(screen.getByTestId('status')).toHaveTextContent('unauthenticated')
    expect(screen.getByTestId('user')).toHaveTextContent('no-user')
  })
})
