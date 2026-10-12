import { act, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { MemoryRouter, Route, Routes } from 'react-router-dom'

import { getProjects } from '../services/projectService.js'
import ProjectsPage from './ProjectsPage.jsx'

vi.mock('../services/projectService.js', () => ({
  getProjects: vi.fn(),
}))

const projects = [
  {
    project_id: 'PRJ-001',
    owner_user_id: 'USR-001',
    name: 'Book Management',
    domain: 'Education',
    description: 'Manage catalogue and lending workflows.',
    current_stage: 'PROJECT_CREATED',
    status: 'IN_PROGRESS',
    created_by: 'USR-001',
    created_at: '2026-10-01T08:00:00Z',
    updated_at: '2026-10-13T08:00:00Z',
  },
  {
    project_id: 'PRJ-002',
    owner_user_id: 'USR-001',
    name: 'Clinical Portal',
    domain: 'Healthcare',
    description: 'Coordinate clinical appointment workflows.',
    current_stage: 'COMPLETED',
    status: 'COMPLETED',
    created_by: 'USR-001',
    created_at: '2026-09-01T08:00:00Z',
    updated_at: '2026-10-12T08:00:00Z',
  },
]

function renderProjectsPage() {
  return render(
    <MemoryRouter initialEntries={['/projects']}>
      <Routes>
        <Route path="/projects" element={<ProjectsPage />} />
        <Route path="/projects/new" element={<h1>Create Project destination</h1>} />
        <Route path="/projects/:projectId" element={<h1>Project Overview destination</h1>} />
      </Routes>
    </MemoryRouter>,
  )
}

describe('ProjectsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('shows a loading state without flashing empty content', () => {
    getProjects.mockReturnValue(new Promise(() => {}))
    renderProjectsPage()

    expect(screen.getByRole('status', { name: 'Loading projects' })).toBeInTheDocument()
    expect(screen.queryByText('No projects yet')).not.toBeInTheDocument()
  })

  it('renders only real supplied project fields and honest derived data', async () => {
    getProjects.mockResolvedValue({ data: projects })
    renderProjectsPage()

    expect(await screen.findByText('Book Management')).toBeInTheDocument()
    const bookCard = screen.getByText('Book Management').closest('[data-variant]')
    expect(bookCard).toHaveTextContent('Education')
    expect(bookCard).toHaveTextContent('Project created')
    expect(bookCard).toHaveTextContent('In Progress')
    expect(screen.getByText('Clinical Portal')).toBeInTheDocument()
    expect(screen.getByText('Healthcare')).toBeInTheDocument()
    expect(screen.getByText('Total projects').parentElement).toHaveTextContent('2')
    expect(document.body).not.toHaveTextContent(
      /requirements generated|tests passed|pending approvals|security findings|recent agent activity/i,
    )
    expect(getProjects).toHaveBeenCalledOnce()
  })

  it('renders an empty state whose action opens Create Project', async () => {
    const user = userEvent.setup()
    getProjects.mockResolvedValue({ data: [] })
    renderProjectsPage()

    expect(await screen.findByText('No projects yet')).toBeInTheDocument()
    const emptyState = screen.getByText('No projects yet').closest('section')
    await user.click(within(emptyState).getByRole('button', { name: 'Create Project' }))

    expect(screen.getByRole('heading', { name: 'Create Project destination' })).toBeInTheDocument()
  })

  it('opens Create Project from the dashboard header', async () => {
    const user = userEvent.setup()
    getProjects.mockResolvedValue({ data: projects })
    renderProjectsPage()
    await screen.findByText('Book Management')

    await user.click(screen.getByRole('button', { name: 'Create Project' }))

    expect(screen.getByRole('heading', { name: 'Create Project destination' })).toBeInTheDocument()
  })

  it('shows a safe error and retries without reloading the browser', async () => {
    const user = userEvent.setup()
    getProjects
      .mockRejectedValueOnce(new Error('Database implementation detail'))
      .mockResolvedValueOnce({ data: projects })
    renderProjectsPage()

    expect(await screen.findByRole('alert')).toHaveTextContent(
      "We couldn't load your projects right now. Please try again.",
    )
    expect(screen.queryByText('Database implementation detail')).not.toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Try again' }))

    expect(await screen.findByText('Book Management')).toBeInTheDocument()
    expect(getProjects).toHaveBeenCalledTimes(2)
  })

  it.each([
    ['Book', 'Book Management', 'Clinical Portal'],
    ['healthcare', 'Clinical Portal', 'Book Management'],
    ['lending', 'Book Management', 'Clinical Portal'],
  ])('searches loaded projects for %s', async (query, visible, hidden) => {
    const user = userEvent.setup()
    getProjects.mockResolvedValue({ data: projects })
    renderProjectsPage()
    await screen.findByText('Book Management')

    await user.type(screen.getByRole('searchbox', { name: 'Search projects' }), query)

    expect(screen.getByText(visible)).toBeInTheDocument()
    expect(screen.queryByText(hidden)).not.toBeInTheDocument()
    expect(getProjects).toHaveBeenCalledOnce()
  })

  it('shows an honest no-results state distinct from an empty account', async () => {
    const user = userEvent.setup()
    getProjects.mockResolvedValue({ data: projects })
    renderProjectsPage()
    await screen.findByText('Book Management')

    await user.type(screen.getByRole('searchbox', { name: 'Search projects' }), 'missing')

    expect(screen.getByText('No matching projects')).toBeInTheDocument()
    expect(screen.queryByText('No projects yet')).not.toBeInTheDocument()
  })

  it('filters the loaded projects by a real status value', async () => {
    const user = userEvent.setup()
    getProjects.mockResolvedValue({ data: projects })
    renderProjectsPage()
    await screen.findByText('Book Management')

    await user.selectOptions(screen.getByRole('combobox', { name: 'Status' }), 'COMPLETED')

    expect(screen.getByText('Clinical Portal')).toBeInTheDocument()
    expect(screen.queryByText('Book Management')).not.toBeInTheDocument()
    expect(getProjects).toHaveBeenCalledOnce()
  })

  it('opens a project through its semantic action without a card API call', async () => {
    const user = userEvent.setup()
    getProjects.mockResolvedValue({ data: projects })
    renderProjectsPage()
    await screen.findByText('Book Management')

    await user.click(screen.getByRole('button', { name: 'Open Book Management' }))

    expect(screen.getByRole('heading', { name: 'Project Overview destination' })).toBeInTheDocument()
    expect(getProjects).toHaveBeenCalledOnce()
  })

  it('does not replace a centralized 401 with a local projects error', async () => {
    getProjects.mockRejectedValue({ status: 401 })
    renderProjectsPage()

    await act(async () => {})
    await waitFor(() => expect(getProjects).toHaveBeenCalledOnce())
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })
})
