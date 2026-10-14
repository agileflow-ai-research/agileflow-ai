import { beforeEach, describe, expect, it, vi } from 'vitest'

import { apiClient } from './apiClient.js'
import {
  createAgentProject,
  getAgentProjectById,
  getAgentProjectRun,
  getAgentProjectRuns,
  getAgentProjects,
  updateAgentProject,
} from './agentProjectService.js'

vi.mock('./apiClient.js', () => ({
  apiClient: { get: vi.fn(), post: vi.fn(), patch: vi.fn() },
}))

describe('agentProjectService', () => {
  beforeEach(() => vi.clearAllMocks())

  it('uses the S1 endpoints and exact create fields', () => {
    createAgentProject({ agentType: 'REQUIREMENTS', name: 'A', domain: 'B', description: '  Context  ' })
    expect(apiClient.post).toHaveBeenCalledWith('/agent-projects', {
      agent_type: 'REQUIREMENTS', name: 'A', domain: 'B', description: 'Context',
    }, { authenticated: true })

    getAgentProjects({ agentType: 'TESTING_VALIDATION', status: 'ARCHIVED' })
    expect(apiClient.get).toHaveBeenCalledWith('/agent-projects?agent_type=TESTING_VALIDATION&status=ARCHIVED', { authenticated: true })
  })

  it('omits blank descriptions and allows only patch contract fields', () => {
    createAgentProject({ agentType: 'IMPLEMENTATION', name: 'A', domain: 'B', description: ' ' })
    expect(apiClient.post.mock.calls[0][1]).toEqual({ agent_type: 'IMPLEMENTATION', name: 'A', domain: 'B' })

    updateAgentProject('AGP-001', { status: 'ARCHIVED', owner_user_id: 'USR-999', agent_type: 'REQUIREMENTS' })
    expect(apiClient.patch).toHaveBeenCalledWith('/agent-projects/AGP-001', { status: 'ARCHIVED' }, { authenticated: true })
  })

  it('addresses project and run reads without assuming database IDs', () => {
    getAgentProjectById('AGP-001')
    getAgentProjectRuns('AGP-001')
    getAgentProjectRun('AGP-001', 'RUN-002')
    expect(apiClient.get).toHaveBeenNthCalledWith(1, '/agent-projects/AGP-001', { authenticated: true })
    expect(apiClient.get).toHaveBeenNthCalledWith(2, '/agent-projects/AGP-001/runs', { authenticated: true })
    expect(apiClient.get).toHaveBeenNthCalledWith(3, '/agent-projects/AGP-001/runs/RUN-002', { authenticated: true })
  })
})
