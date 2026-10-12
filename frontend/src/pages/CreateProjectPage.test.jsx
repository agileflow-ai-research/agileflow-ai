import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { MemoryRouter, Route, Routes } from 'react-router-dom'

import { createProject } from '../services/projectService.js'
import CreateProjectPage from './CreateProjectPage.jsx'

vi.mock('../services/projectService.js', () => ({
  createProject: vi.fn(),
}))

function renderCreateProjectPage() {
  return render(
    <MemoryRouter initialEntries={['/projects/new']}>
      <Routes>
        <Route path="/projects/new" element={<CreateProjectPage />} />
        <Route path="/projects" element={<h1>Projects destination</h1>} />
        <Route
          path="/projects/:projectId"
          element={<h1>Project Overview destination</h1>}
        />
      </Routes>
    </MemoryRouter>,
  )
}

async function completeForm(user, values = {}) {
  await user.type(
    screen.getByRole('textbox', { name: /project name/i }),
    values.name ?? 'Book Management',
  )
  await user.type(
    screen.getByRole('textbox', { name: /domain/i }),
    values.domain ?? 'Education',
  )
}

describe('CreateProjectPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders only the supported required project fields', () => {
    renderCreateProjectPage()

    expect(screen.getByRole('heading', { level: 1, name: 'Create Project' })).toBeInTheDocument()
    expect(screen.getByRole('textbox', { name: /project name/i })).toBeRequired()
    expect(screen.getByRole('textbox', { name: /domain/i })).toBeRequired()
    expect(screen.queryByLabelText(/initial client idea/i)).not.toBeInTheDocument()
    expect(screen.queryByLabelText(/description/i)).not.toBeInTheDocument()
  })

  it('does not submit blank required fields', async () => {
    const user = userEvent.setup()
    renderCreateProjectPage()

    await user.click(screen.getByRole('button', { name: 'Create Project' }))

    expect(createProject).not.toHaveBeenCalled()
    expect(screen.getByText('Enter a project name.')).toBeInTheDocument()
    expect(screen.getByText('Enter a project domain.')).toBeInTheDocument()
  })

  it('trims values and submits no server-controlled ownership fields', async () => {
    const user = userEvent.setup()
    createProject.mockResolvedValue({ data: { project_id: 'PRJ-001' } })
    renderCreateProjectPage()

    await completeForm(user, { name: '  Book Management  ', domain: '  Education  ' })
    await user.click(screen.getByRole('button', { name: 'Create Project' }))

    expect(createProject).toHaveBeenCalledWith({
      name: 'Book Management',
      domain: 'Education',
    })
    const payload = createProject.mock.calls[0][0]
    expect(payload).not.toHaveProperty('created_by')
    expect(payload).not.toHaveProperty('owner_user_id')
    expect(payload).not.toHaveProperty('description')
    expect(screen.getByRole('heading', { name: 'Project Overview destination' })).toBeInTheDocument()
  })

  it('disables submission and prevents duplicate creation while pending', async () => {
    const user = userEvent.setup()
    createProject.mockReturnValue(new Promise(() => {}))
    renderCreateProjectPage()
    await completeForm(user)

    const submit = screen.getByRole('button', { name: 'Create Project' })
    await user.click(submit)

    expect(screen.getByRole('button', { name: 'Creating project' })).toBeDisabled()
    await user.click(screen.getByRole('button', { name: 'Creating project' }))
    expect(createProject).toHaveBeenCalledOnce()
  })

  it('does not navigate when a nominal success lacks project_id', async () => {
    const user = userEvent.setup()
    createProject.mockResolvedValue({ data: {} })
    renderCreateProjectPage()
    await completeForm(user)

    await user.click(screen.getByRole('button', { name: 'Create Project' }))

    expect(await screen.findByRole('alert')).toHaveTextContent(
      "We couldn't create your project right now. Please try again.",
    )
    expect(screen.getByRole('heading', { level: 1, name: 'Create Project' })).toBeInTheDocument()
  })

  it.each([
    ['name', 'Project name is invalid.'],
    ['domain', 'Project domain is invalid.'],
  ])('maps a backend %s error to its field', async (field, message) => {
    const user = userEvent.setup()
    createProject.mockRejectedValue({
      status: 422,
      errors: [{ field: `body.${field}`, message }],
    })
    renderCreateProjectPage()
    await completeForm(user)

    await user.click(screen.getByRole('button', { name: 'Create Project' }))

    const control = screen.getByRole('textbox', {
      name: field === 'name' ? /project name/i : /domain/i,
    })
    expect(await screen.findByText(message)).toBeInTheDocument()
    expect(control).toHaveAttribute('aria-invalid', 'true')
  })

  it('shows a safe form error for network and non-field failures', async () => {
    const user = userEvent.setup()
    createProject.mockRejectedValue(new Error('Database connection detail'))
    renderCreateProjectPage()
    await completeForm(user)

    await user.click(screen.getByRole('button', { name: 'Create Project' }))

    expect(await screen.findByRole('alert')).toHaveTextContent(
      "We couldn't create your project right now. Please try again.",
    )
    expect(screen.queryByText('Database connection detail')).not.toBeInTheDocument()
  })

  it('returns to Projects when Cancel is selected', async () => {
    const user = userEvent.setup()
    renderCreateProjectPage()

    await user.click(screen.getByRole('button', { name: 'Cancel' }))

    expect(screen.getByRole('heading', { name: 'Projects destination' })).toBeInTheDocument()
    expect(createProject).not.toHaveBeenCalled()
  })

  it('leaves authenticated 401 handling to the shared session layer', async () => {
    const user = userEvent.setup()
    createProject.mockRejectedValue({ status: 401 })
    renderCreateProjectPage()
    await completeForm(user)

    await user.click(screen.getByRole('button', { name: 'Create Project' }))
    await waitFor(() => expect(createProject).toHaveBeenCalledOnce())

    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })
})
