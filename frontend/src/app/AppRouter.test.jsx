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
  getProjectById: vi.fn().mockResolvedValue({
    data: {
      project_id: 'PRJ-001',
      name: 'Project Overview',
      domain: 'Education',
      description: '',
      status: 'PENDING',
      created_at: '2026-10-13T08:00:00Z',
      updated_at: '2026-10-13T08:00:00Z',
    },
  }),
  createProject: vi.fn(),
}))

vi.mock('../services/workflowService.js', () => ({
  getWorkflow: vi.fn().mockResolvedValue({
    data: {
      current_stage: 'PROJECT_CREATED',
      current_stage_owner: 'Central SDLC Orchestrator',
      next_stage: 'REQUIREMENTS_IN_PROGRESS',
      next_stage_owner: 'Requirement Gathering and Analysis Agent',
      next_transition_available: true,
      approval_gate: null,
    },
  }),
  getEvents: vi.fn().mockResolvedValue({ data: [] }),
}))

describe('AppRouter F1.2 route regression', () => {
  it.each([
    ['/login', 'Welcome back'],
    ['/register', 'Create your account'],
    ['/projects', 'Projects'],
    ['/projects/new', 'Create Project'],
    ['/projects/PRJ-001', 'Project Overview'],
  ])('renders %s', async (path, heading) => {
    window.history.pushState({}, '', path)

    render(<AppRouter />)

    expect(await screen.findByRole('heading', { level: 1, name: heading })).toBeInTheDocument()
  })
})
