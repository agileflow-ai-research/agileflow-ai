import { beforeEach, describe, expect, it, vi } from 'vitest'

import { apiClient } from '../../../services/apiClient.js'
import { runTestingValidationAgent } from './testingValidationAgentService.js'

vi.mock('../../../services/apiClient.js', () => ({ apiClient: { post: vi.fn() } }))

describe('testingValidationAgentService', () => {
  beforeEach(() => vi.clearAllMocks())

  it('uses the common Agent 4 endpoint with authentication', () => {
    const payload = { run_mode: 'VALIDATION', source_code_or_project: 'source', selected_outputs: ['FINAL_VALIDATION_REPORT'] }
    runTestingValidationAgent('AGP-004', payload)
    expect(apiClient.post).toHaveBeenCalledWith(
      '/agents/testing-validation/AGP-004/run', payload, { authenticated: true },
    )
  })
})
