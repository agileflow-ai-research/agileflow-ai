import { render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { MemoryRouter, Outlet, Route, Routes } from 'react-router-dom'

import ProtectedRoute from './ProtectedRoute.jsx'
import PublicOnlyRoute from './PublicOnlyRoute.jsx'

let authState

vi.mock('./useAuth.js', () => ({
  useAuth: () => authState,
}))

function TestRoutes({ initialPath }) {
  return (
    <MemoryRouter initialEntries={[initialPath]}>
      <Routes>
        <Route element={<PublicOnlyRoute />}>
          <Route path="/login" element={<h1>Login form</h1>} />
          <Route path="/register" element={<h1>Register form</h1>} />
        </Route>
        <Route element={<ProtectedRoute />}>
          <Route element={<Outlet />}>
            <Route path="/projects" element={<h1>Projects page</h1>} />
            <Route path="/projects/new" element={<h1>Create project page</h1>} />
            <Route path="/projects/:projectId" element={<h1>Project overview page</h1>} />
          </Route>
        </Route>
      </Routes>
    </MemoryRouter>
  )
}

describe('authentication route guards', () => {
  beforeEach(() => {
    authState = {
      status: 'unauthenticated',
      user: null,
      sessionError: null,
      retrySession: vi.fn(),
    }
  })

  it.each(['/projects', '/projects/new', '/projects/PRJ-001'])(
    'redirects unauthenticated access to %s into login',
    (path) => {
      render(<TestRoutes initialPath={path} />)

      expect(screen.getByRole('heading', { name: 'Login form' })).toBeInTheDocument()
    },
  )

  it('renders protected content for an authenticated user', () => {
    authState.status = 'authenticated'
    authState.user = { user_id: 'USR-001' }

    render(<TestRoutes initialPath="/projects" />)

    expect(screen.getByRole('heading', { name: 'Projects page' })).toBeInTheDocument()
  })

  it('does not render protected content while session bootstrap is loading', () => {
    authState.status = 'loading'

    render(<TestRoutes initialPath="/projects" />)

    expect(screen.getByRole('status', { name: 'Verifying your session' })).toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: 'Projects page' })).not.toBeInTheDocument()
  })

  it('shows a retryable session error without rendering protected content', () => {
    authState.status = 'error'
    authState.sessionError = "We couldn't verify your session right now. Please try again."

    render(<TestRoutes initialPath="/projects" />)

    expect(screen.getByRole('alert')).toHaveTextContent(authState.sessionError)
    expect(screen.getByRole('button', { name: 'Try again' })).toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: 'Projects page' })).not.toBeInTheDocument()
  })

  it.each([
    ['/login', 'Login form'],
    ['/register', 'Register form'],
  ])('allows unauthenticated access to %s', (path, heading) => {
    render(<TestRoutes initialPath={path} />)

    expect(screen.getByRole('heading', { name: heading })).toBeInTheDocument()
  })

  it.each(['/login', '/register'])(
    'redirects authenticated access from %s to projects',
    (path) => {
      authState.status = 'authenticated'
      authState.user = { user_id: 'USR-001' }

      render(<TestRoutes initialPath={path} />)

      expect(screen.getByRole('heading', { name: 'Projects page' })).toBeInTheDocument()
    },
  )

  it('does not flash a public form while session bootstrap is loading', () => {
    authState.status = 'loading'

    render(<TestRoutes initialPath="/login" />)

    expect(screen.getByRole('status', { name: 'Verifying your session' })).toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: 'Login form' })).not.toBeInTheDocument()
  })

  it('restores the intended internal route after authentication', () => {
    const view = render(<TestRoutes initialPath="/projects/PRJ-001" />)
    expect(screen.getByRole('heading', { name: 'Login form' })).toBeInTheDocument()

    authState.status = 'authenticated'
    authState.user = { user_id: 'USR-001' }
    view.rerender(<TestRoutes initialPath="/projects/PRJ-001" />)

    expect(screen.getByRole('heading', { name: 'Project overview page' })).toBeInTheDocument()
  })
})
