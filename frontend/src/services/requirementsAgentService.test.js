import { beforeEach, describe, expect, it, vi } from 'vitest'

import { apiClient } from './apiClient.js'
import {
  getClarificationResponses,
  runRequirementsAgent,
  saveClarificationResponse,
} from './requirementsAgentService.js'

vi.mock('./apiClient.js', () => ({
  apiClient: { get: vi.fn(), post: vi.fn() },
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

  it('loads and saves run-scoped clarification responses', () => {
    getClarificationResponses('AGP-007', 'RUN-003')
    saveClarificationResponse('AGP-007', 'RUN-003', {
      question_id: 'CQ-001', answer: 'Twelve hours.',
    })

    expect(apiClient.get).toHaveBeenCalledWith(
      '/agents/requirements/AGP-007/runs/RUN-003/clarification-responses',
      { authenticated: true },
    )
    expect(apiClient.post).toHaveBeenLastCalledWith(
      '/agents/requirements/AGP-007/runs/RUN-003/clarification-responses',
      { question_id: 'CQ-001', answer: 'Twelve hours.' },
      { authenticated: true },
    )
  })
})
