import { beforeEach, describe, expect, it, vi } from 'vitest'
import { apiClient } from '../../../../services/apiClient.js'
import { getQualityExecution, retryQualityExecution } from './qualityService.js'

vi.mock('../../../../services/apiClient.js', () => ({ apiClient: { get: vi.fn(), post: vi.fn() } }))

describe('quality service', () => {
  beforeEach(() => vi.clearAllMocks())
  it('uses authenticated persisted-read and failed-retry endpoints', () => {
    getQualityExecution('AGP-001', 'N4-AAAA/001')
    retryQualityExecution('AGP-001')
    expect(apiClient.get).toHaveBeenCalledWith('/agents/requirements/AGP-001/quality/N4-AAAA%2F001', { authenticated: true })
    expect(apiClient.post).toHaveBeenCalledWith('/agents/requirements/AGP-001/workflow/n4/retry', undefined, { authenticated: true })
  })
})
