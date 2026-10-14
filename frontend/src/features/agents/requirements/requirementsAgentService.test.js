import { beforeEach, describe, expect, it, vi } from 'vitest'

import { apiClient } from '../../../services/apiClient.js'
import { runRequirementsAgent } from './requirementsAgentService.js'

vi.mock('../../../services/apiClient.js', () => ({
  apiClient: { post: vi.fn() },
}))

describe('requirementsAgentService', () => {
  beforeEach(() => vi.clearAllMocks())

  it('calls the real Agent 1 execution route with authentication', () => {
    const payload = { text: 'The system shall search.', selected_outputs: ['SRS'] }
    runRequirementsAgent('AGP-007', payload)
    expect(apiClient.post).toHaveBeenCalledWith(
      '/agents/requirements/AGP-007/run',
      payload,
      { authenticated: true },
    )
  })
})
