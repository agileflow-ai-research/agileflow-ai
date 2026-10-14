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

vi.mock('../services/agentProjectService.js', () => ({
  getAgentProjects: vi.fn().mockResolvedValue({ data: [] }),
  getAgentProjectById: vi.fn().mockResolvedValue({
    data: {
      agent_project_id: 'AGP-001',
      agent_type: 'REQUIREMENTS',
      name: 'Agent Project Overview',
      domain: 'Education',
      description: '',
      status: 'ACTIVE',
      created_at: '2026-10-13T08:00:00Z',
      updated_at: '2026-10-13T08:00:00Z',
    },
  }),
  getAgentProjectRuns: vi.fn().mockResolvedValue({ data: [] }),
  getAgentProjectRun: vi.fn(),
  createAgentProject: vi.fn(),
  updateAgentProject: vi.fn(),
}))

describe('AppRouter F1.2 route regression', () => {
  it.each([
    ['/login', 'Welcome back'],
    ['/register', 'Create your account'],
    ['/projects', 'Projects'],
    ['/projects/new', 'Create Project'],
    ['/projects/PRJ-001', 'Project Overview'],
    ['/agents', 'AI Agents'],
    ['/agents/requirements', 'Requirements Agent Projects'],
    ['/agents/design-planning', 'Design & Planning Agent Projects'],
    ['/agents/implementation', 'Implementation Agent Projects'],
    ['/agents/testing-validation', 'Testing & Validation Agent Projects'],
    ['/agents/requirements/new', 'Create Requirements Project'],
    ['/agent-projects/AGP-001', 'Agent Project Overview'],
  ])('renders %s', async (path, heading) => {
    window.history.pushState({}, '', path)

    render(<AppRouter />)

    expect(await screen.findByRole('heading', { level: 1, name: heading })).toBeInTheDocument()
  })
})
