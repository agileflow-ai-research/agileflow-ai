import { render, screen } from '@testing-library/react'
import { Outlet } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'

import AppRouter from './AppRouter.jsx'

vi.mock('../features/auth/AuthProvider.jsx', () => ({
  default: ({ children }) => children,
}))

vi.mock('../features/auth/ProtectedRoute.jsx', () => ({
  default: () => <Outlet />,
}))

vi.mock('../features/auth/PublicOnlyRoute.jsx', () => ({
  default: () => <Outlet />,
}))

vi.mock('../features/auth/useAuth.js', () => ({
  useAuth: () => ({
    establishSession: vi.fn(),
    logout: vi.fn(),
    user: { name: 'Ada Lovelace', email: 'ada@example.com' },
  }),
}))

vi.mock('../services/projectService.js', () => ({
  getProjects: vi.fn().mockResolvedValue({ data: [] }),
}))

describe('AppRouter F1.2 route regression', () => {
  it.each([
    ['/login', 'Welcome back'],
    ['/register', 'Create your account'],
    ['/projects', 'Projects'],
    ['/projects/new', 'Create Project'],
    ['/projects/PRJ-001', 'Project Overview'],
  ])('renders %s', (path, heading) => {
    window.history.pushState({}, '', path)

    render(<AppRouter />)

    expect(screen.getByRole('heading', { level: 1, name: heading })).toBeInTheDocument()
  })
})
