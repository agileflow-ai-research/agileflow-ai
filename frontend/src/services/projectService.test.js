import { beforeEach, describe, expect, it, vi } from 'vitest'

import { apiClient } from './apiClient.js'
import { createProject, getProjectById, getProjects } from './projectService.js'

vi.mock('./apiClient.js', () => ({
  apiClient: { get: vi.fn(), post: vi.fn() },
}))

describe('projectService', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('gets the owner-scoped project list as an authenticated request', async () => {
    const response = { status: 200, data: [] }
    apiClient.get.mockResolvedValue(response)

    await expect(getProjects()).resolves.toBe(response)
    expect(apiClient.get).toHaveBeenCalledWith('/projects', { authenticated: true })
    expect(apiClient.get).toHaveBeenCalledOnce()
  })

  it('gets one owner-scoped project by ID as an authenticated request', async () => {
    const response = { status: 200, data: { project_id: 'PRJ-001' } }
    apiClient.get.mockResolvedValue(response)

    await expect(getProjectById('PRJ-001')).resolves.toBe(response)

    expect(apiClient.get).toHaveBeenCalledWith('/projects/PRJ-001', {
      authenticated: true,
    })
    expect(apiClient.get).toHaveBeenCalledOnce()
    expect(apiClient.get.mock.calls[0]).toHaveLength(2)
  })

  it('creates a project using only the authenticated client-owned fields', async () => {
    const response = { status: 201, data: { project_id: 'PRJ-001' } }
    apiClient.post.mockResolvedValue(response)

    await expect(
      createProject({ name: 'Book Management', domain: 'Education' }),
    ).resolves.toBe(response)

    expect(apiClient.post).toHaveBeenCalledWith(
      '/projects',
      { name: 'Book Management', domain: 'Education' },
      { authenticated: true },
    )
    const payload = apiClient.post.mock.calls[0][1]
    expect(payload).not.toHaveProperty('created_by')
    expect(payload).not.toHaveProperty('owner_user_id')
    expect(payload).not.toHaveProperty('project_id')
    expect(payload).not.toHaveProperty('current_stage')
    expect(payload).not.toHaveProperty('status')
    expect(payload).not.toHaveProperty('created_at')
    expect(payload).not.toHaveProperty('updated_at')
  })

  it('includes a supplied description and omits a blank description', async () => {
    apiClient.post.mockResolvedValue({ status: 201, data: { project_id: 'PRJ-001' } })

    await createProject({
      name: 'Book Management',
      domain: 'Education',
      description: '  Lending workflow  ',
    })
    await createProject({
      name: 'Book Management',
      domain: 'Education',
      description: '   ',
    })

    expect(apiClient.post).toHaveBeenNthCalledWith(
      1,
      '/projects',
      {
        name: 'Book Management',
        domain: 'Education',
        description: 'Lending workflow',
      },
      { authenticated: true },
    )
    expect(apiClient.post).toHaveBeenNthCalledWith(
      2,
      '/projects',
      { name: 'Book Management', domain: 'Education' },
      { authenticated: true },
    )
  })
})
