import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { MemoryRouter, Route, Routes } from 'react-router-dom'

import { createClientInput } from '../services/inputService.js'
import { createProject } from '../services/projectService.js'
import CreateProjectPage from './CreateProjectPage.jsx'

vi.mock('../services/inputService.js', () => ({
  createClientInput: vi.fn(),
}))

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
  await user.type(
    screen.getByRole('textbox', { name: /initial client idea/i }),
    values.idea ?? 'A library lending workflow for students.',
  )
}

function mockSuccessfulFlow(projectId = 'PRJ-001') {
  createProject.mockResolvedValue({ data: { project_id: projectId } })
  createClientInput.mockResolvedValue({ data: { input_type: 'TEXT' } })
}

describe('CreateProjectPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders the three required fields without a Project description', () => {
    renderCreateProjectPage()

    expect(screen.getByRole('heading', { level: 1, name: 'Create Project' })).toBeInTheDocument()
    expect(screen.getByRole('textbox', { name: /project name/i })).toBeRequired()
    expect(screen.getByRole('textbox', { name: /domain/i })).toBeRequired()
    expect(screen.getByRole('textbox', { name: /initial client idea/i })).toBeRequired()
    expect(screen.queryByLabelText(/description/i)).not.toBeInTheDocument()
  })

  it('blocks blank and whitespace-only required values', async () => {
    const user = userEvent.setup()
    renderCreateProjectPage()

    await completeForm(user, { name: '   ', domain: '   ', idea: '   ' })
    await user.click(screen.getByRole('button', { name: 'Create Project' }))

    expect(createProject).not.toHaveBeenCalled()
    expect(createClientInput).not.toHaveBeenCalled()
    expect(screen.getByText('Enter a project name.')).toBeInTheDocument()
    expect(screen.getByText('Enter a project domain.')).toBeInTheDocument()
    expect(screen.getByText('Enter the initial client idea.')).toBeInTheDocument()
  })

  it('trims all values, keeps the idea out of Project, and saves an exact TEXT input', async () => {
    const user = userEvent.setup()
    mockSuccessfulFlow()
    renderCreateProjectPage()

    await completeForm(user, {
      name: '  Book Management  ',
      domain: '  Education  ',
      idea: '  A library lending workflow.  ',
    })
    await user.click(screen.getByRole('button', { name: 'Create Project' }))

    expect(createProject).toHaveBeenCalledWith({
      name: 'Book Management',
      domain: 'Education',
    })
    expect(createProject.mock.calls[0][0]).not.toHaveProperty('initialClientIdea')
    expect(createProject.mock.calls[0][0]).not.toHaveProperty('description')
    expect(createProject.mock.calls[0][0]).not.toHaveProperty('created_by')
    expect(createProject.mock.calls[0][0]).not.toHaveProperty('owner_user_id')
    expect(createClientInput).toHaveBeenCalledWith('PRJ-001', {
      input_type: 'TEXT',
      content: 'A library lending workflow.',
    })
    expect(createProject).toHaveBeenCalledOnce()
    expect(createClientInput).toHaveBeenCalledOnce()
    expect(createProject.mock.invocationCallOrder[0]).toBeLessThan(
      createClientInput.mock.invocationCallOrder[0],
    )
    expect(await screen.findByRole('heading', { name: 'Project Overview destination' })).toBeInTheDocument()
  })

  it('navigates only after ClientInput succeeds', async () => {
    const user = userEvent.setup()
    let resolveInput
    createProject.mockResolvedValue({ data: { project_id: 'PRJ-009' } })
    createClientInput.mockReturnValue(
      new Promise((resolve) => {
        resolveInput = resolve
      }),
    )
    renderCreateProjectPage()
    await completeForm(user)

    await user.click(screen.getByRole('button', { name: 'Create Project' }))

    expect(await screen.findByRole('button', { name: 'Saving initial idea' })).toBeDisabled()
    expect(screen.queryByRole('heading', { name: 'Project Overview destination' })).not.toBeInTheDocument()
    resolveInput({ data: {} })
    expect(await screen.findByRole('heading', { name: 'Project Overview destination' })).toBeInTheDocument()
  })

  it('prevents duplicate Project creation while its request is pending', async () => {
    const user = userEvent.setup()
    createProject.mockReturnValue(new Promise(() => {}))
    renderCreateProjectPage()
    await completeForm(user)

    await user.click(screen.getByRole('button', { name: 'Create Project' }))

    const pendingButton = screen.getByRole('button', { name: 'Creating project' })
    expect(pendingButton).toBeDisabled()
    await user.click(pendingButton)
    expect(createProject).toHaveBeenCalledOnce()
    expect(createClientInput).not.toHaveBeenCalled()
  })

  it('keeps the form usable and populated when Project creation fails', async () => {
    const user = userEvent.setup()
    createProject.mockRejectedValue(new Error('private database detail'))
    renderCreateProjectPage()
    await completeForm(user)

    await user.click(screen.getByRole('button', { name: 'Create Project' }))

    expect(await screen.findByRole('alert')).toHaveTextContent(
      "We couldn't create your project right now. Please try again.",
    )
    expect(createClientInput).not.toHaveBeenCalled()
    expect(screen.getByRole('textbox', { name: /initial client idea/i })).toHaveValue(
      'A library lending workflow for students.',
    )
    expect(screen.getByRole('button', { name: 'Create Project' })).toBeEnabled()
    expect(screen.queryByText('private database detail')).not.toBeInTheDocument()
  })

  it('does not save input, navigate, or allow another creation when project_id is missing', async () => {
    const user = userEvent.setup()
    createProject.mockResolvedValue({ data: {} })
    renderCreateProjectPage()
    await completeForm(user)

    await user.click(screen.getByRole('button', { name: 'Create Project' }))

    expect(await screen.findByRole('alert')).toHaveTextContent(
      "Your project may have been created, but its ID wasn't returned.",
    )
    expect(createClientInput).not.toHaveBeenCalled()
    expect(screen.queryByRole('heading', { name: 'Project Overview destination' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Create Project' })).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Go to Projects' })).toBeInTheDocument()
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
    expect(createClientInput).not.toHaveBeenCalled()
  })

  it('enters recovery after input failure and maps content errors to the idea field', async () => {
    const user = userEvent.setup()
    createProject.mockResolvedValue({ data: { project_id: 'PRJ-042' } })
    createClientInput.mockRejectedValue({
      status: 422,
      errors: [{ field: 'body.content', message: 'Initial idea is invalid.' }],
    })
    renderCreateProjectPage()
    await completeForm(user)

    await user.click(screen.getByRole('button', { name: 'Create Project' }))

    expect(await screen.findByRole('alert')).toHaveTextContent(
      "Your project was created, but we couldn't save the initial client idea.",
    )
    expect(screen.getByText('Initial idea is invalid.')).toBeInTheDocument()
    expect(screen.getByRole('textbox', { name: /initial client idea/i })).toHaveAttribute(
      'aria-invalid',
      'true',
    )
    expect(screen.getByRole('button', { name: 'Retry saving idea' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Go to Project' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Cancel' })).not.toBeInTheDocument()
    expect(screen.queryByText('input_type')).not.toBeInTheDocument()
  })

  it('shows safe recovery feedback for input_type and generic ClientInput failures', async () => {
    const user = userEvent.setup()
    createProject.mockResolvedValue({ data: { project_id: 'PRJ-043' } })
    createClientInput.mockRejectedValue({
      status: 422,
      errors: [{ field: 'body.input_type', message: 'Internal enum detail.' }],
    })
    renderCreateProjectPage()
    await completeForm(user)

    await user.click(screen.getByRole('button', { name: 'Create Project' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('Retry saving the idea to continue.')
    expect(screen.queryByText('Internal enum detail.')).not.toBeInTheDocument()
  })

  it('retries only ClientInput with the retained ID and navigates after success', async () => {
    const user = userEvent.setup()
    createProject.mockResolvedValue({ data: { project_id: 'PRJ-077' } })
    createClientInput
      .mockRejectedValueOnce(new Error('network failure'))
      .mockResolvedValueOnce({ data: {} })
    renderCreateProjectPage()
    await completeForm(user, { idea: '  Original client idea.  ' })

    await user.click(screen.getByRole('button', { name: 'Create Project' }))
    await user.click(await screen.findByRole('button', { name: 'Retry saving idea' }))

    expect(createProject).toHaveBeenCalledOnce()
    expect(createClientInput).toHaveBeenCalledTimes(2)
    expect(createClientInput).toHaveBeenLastCalledWith('PRJ-077', {
      input_type: 'TEXT',
      content: 'Original client idea.',
    })
    expect(await screen.findByRole('heading', { name: 'Project Overview destination' })).toBeInTheDocument()
  })

  it('protects retry from duplicate clicks', async () => {
    const user = userEvent.setup()
    createProject.mockResolvedValue({ data: { project_id: 'PRJ-088' } })
    createClientInput.mockRejectedValueOnce(new Error('first failure'))
    renderCreateProjectPage()
    await completeForm(user)
    await user.click(screen.getByRole('button', { name: 'Create Project' }))

    createClientInput.mockReturnValueOnce(new Promise(() => {}))
    await user.click(await screen.findByRole('button', { name: 'Retry saving idea' }))

    const pendingButton = screen.getByRole('button', { name: 'Saving initial idea' })
    expect(pendingButton).toBeDisabled()
    await user.click(pendingButton)
    expect(createClientInput).toHaveBeenCalledTimes(2)
    expect(createProject).toHaveBeenCalledOnce()
  })

  it('keeps the existing Project recovery state when a retry fails', async () => {
    const user = userEvent.setup()
    createProject.mockResolvedValue({ data: { project_id: 'PRJ-089' } })
    createClientInput.mockRejectedValue(new Error('failure'))
    renderCreateProjectPage()
    await completeForm(user)
    await user.click(screen.getByRole('button', { name: 'Create Project' }))

    await user.click(await screen.findByRole('button', { name: 'Retry saving idea' }))

    expect(await screen.findByRole('button', { name: 'Retry saving idea' })).toBeInTheDocument()
    expect(createProject).toHaveBeenCalledOnce()
    expect(screen.queryByRole('heading', { name: 'Project Overview destination' })).not.toBeInTheDocument()
  })

  it('lets recovery navigate to the retained Project without saving again', async () => {
    const user = userEvent.setup()
    createProject.mockResolvedValue({ data: { project_id: 'PRJ-090' } })
    createClientInput.mockRejectedValue(new Error('failure'))
    renderCreateProjectPage()
    await completeForm(user)
    await user.click(screen.getByRole('button', { name: 'Create Project' }))

    await user.click(await screen.findByRole('button', { name: 'Go to Project' }))

    expect(screen.getByRole('heading', { name: 'Project Overview destination' })).toBeInTheDocument()
    expect(createProject).toHaveBeenCalledOnce()
    expect(createClientInput).toHaveBeenCalledOnce()
  })

  it('returns to Projects when Cancel is selected before creation', async () => {
    const user = userEvent.setup()
    renderCreateProjectPage()

    await user.click(screen.getByRole('button', { name: 'Cancel' }))

    expect(screen.getByRole('heading', { name: 'Projects destination' })).toBeInTheDocument()
    expect(createProject).not.toHaveBeenCalled()
  })

  it('leaves a Project 401 to the shared session layer', async () => {
    const user = userEvent.setup()
    createProject.mockRejectedValue({ status: 401 })
    renderCreateProjectPage()
    await completeForm(user)

    await user.click(screen.getByRole('button', { name: 'Create Project' }))
    await waitFor(() => expect(createProject).toHaveBeenCalledOnce())

    expect(createClientInput).not.toHaveBeenCalled()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })
})
