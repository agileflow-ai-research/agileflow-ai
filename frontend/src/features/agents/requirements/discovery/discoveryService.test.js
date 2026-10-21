import { beforeEach, describe, expect, it, vi } from 'vitest'

import { apiClient } from '../../../../services/apiClient.js'
import { getDiscoveryResults, retryDiscovery } from './discoveryService.js'

vi.mock('../../../../services/apiClient.js', () => ({ apiClient: { get: vi.fn(), post: vi.fn() } }))

describe('discovery service', () => {
  beforeEach(() => vi.clearAllMocks())

  it('uses the centralized authenticated client for persisted results and retry', () => {
    getDiscoveryResults('AGP-001', 'N3-AAAA/001')
    retryDiscovery('AGP-001')
    expect(apiClient.get).toHaveBeenCalledWith('/agents/requirements/AGP-001/discovery/N3-AAAA%2F001', { authenticated: true })
    expect(apiClient.post).toHaveBeenCalledWith('/agents/requirements/AGP-001/workflow/n3/retry', undefined, { authenticated: true })
  })
})
