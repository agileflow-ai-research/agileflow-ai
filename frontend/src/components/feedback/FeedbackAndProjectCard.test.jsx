import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import ProjectCard from '../projects/ProjectCard.jsx'
import Button from '../ui/Button.jsx'
import EmptyState from './EmptyState.jsx'
import ErrorState from './ErrorState.jsx'

describe('feedback components', () => {
  it('renders an optional EmptyState action', async () => {
    const user = userEvent.setup()
    const onAction = vi.fn()
    render(
      <EmptyState
        title="No projects yet"
        description="Create a project to begin."
        action={<Button onClick={onAction}>Create project</Button>}
      />,
    )

    await user.click(screen.getByRole('button', { name: 'Create project' }))
    expect(onAction).toHaveBeenCalledOnce()
  })

  it('runs an ErrorState retry action', async () => {
    const user = userEvent.setup()
    const onRetry = vi.fn()
    render(<ErrorState message="Projects could not be loaded." onRetry={onRetry} />)

    await user.click(screen.getByRole('button', { name: 'Try again' }))
    expect(onRetry).toHaveBeenCalledOnce()
  })
})

describe('ProjectCard', () => {
  it('renders only provided project data and opens the selected project', async () => {
    const user = userEvent.setup()
    const onOpen = vi.fn()
    render(
      <ProjectCard
        projectId="PRJ-001"
        name="Book Management"
        domain="Education"
        description="Manage catalogue and lending workflows."
        currentStage="PROJECT_CREATED"
        status="IN_PROGRESS"
        updatedAt="2026-10-13T08:00:00Z"
        onOpen={onOpen}
      />,
    )

    const card = screen.getByText('Book Management').closest('[data-variant]')
    expect(card).toHaveTextContent('PRJ-001')
    expect(card).toHaveTextContent('Education')
    expect(card).toHaveTextContent('Manage catalogue and lending workflows.')
    expect(card).toHaveTextContent('Project created')
    expect(card).toHaveTextContent('In Progress')
    expect(card).not.toHaveTextContent(/requirements count|test count|approval count|progress percentage/i)

    await user.click(screen.getByRole('button', { name: 'Open Book Management' }))
    expect(onOpen).toHaveBeenCalledWith('PRJ-001')
  })
})
