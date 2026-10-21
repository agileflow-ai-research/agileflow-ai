import { beforeEach, describe, expect, it, vi } from 'vitest'

import { apiClient } from '../../../services/apiClient.js'
import {
  createTestingValidationTextSource,
  deleteTestingValidationSource,
  getTestGenerationWorkflow,
  listTestingValidationSources,
  runTestingValidationAgent,
  uploadTestingValidationSource,
} from './testingValidationAgentService.js'

vi.mock('../../../services/apiClient.js', () => ({
  apiClient: { delete: vi.fn(), get: vi.fn(), post: vi.fn() },
}))

describe('testingValidationAgentService', () => {
  beforeEach(() => vi.clearAllMocks())

  it('uses the common Agent 4 endpoint with authentication', () => {
    const payload = { run_mode: 'VALIDATION', source_code_or_project: 'source', selected_outputs: ['FINAL_VALIDATION_REPORT'] }
    runTestingValidationAgent('AGP-004', payload)
    expect(apiClient.post).toHaveBeenCalledWith(
      '/agents/testing-validation/AGP-004/run', payload, { authenticated: true },
    )
  })

  it('loads the persisted Test Generation workflow through the feature service', () => {
    getTestGenerationWorkflow('AGP-004')
    expect(apiClient.get).toHaveBeenCalledWith(
      '/agents/testing-validation/AGP-004/test-generation/workflow',
      { authenticated: true },
    )
  })

  it('uses the canonical authenticated source CRUD routes', () => {
    const text = {
      artifact_type: 'FUNCTIONAL_REQUIREMENTS',
      normally_supplied_by: 'AGENT_1',
      content: 'Transfers are supported.',
    }
    listTestingValidationSources('AGP-004')
    createTestingValidationTextSource('AGP-004', text)
    deleteTestingValidationSource('AGP-004', 'A4SRC-source/id')

    expect(apiClient.get).toHaveBeenCalledWith(
      '/agents/testing-validation/AGP-004/test-generation/sources',
      { authenticated: true },
    )
    expect(apiClient.post).toHaveBeenCalledWith(
      '/agents/testing-validation/AGP-004/test-generation/sources/text',
      text,
      { authenticated: true },
    )
    expect(apiClient.delete).toHaveBeenCalledWith(
      '/agents/testing-validation/AGP-004/test-generation/sources/A4SRC-source%2Fid',
      { authenticated: true },
    )
  })

  it('builds a server-controlled multipart file request', () => {
    const file = new File(['diagram'], 'flow.png', { type: 'image/png' })
    uploadTestingValidationSource('AGP-004', {
      artifact_type: 'UI_FLOW', source_type: 'IMAGE',
      normally_supplied_by: 'AGENT_2', label: ' Flow ',
      source_id: 'client-controlled', sha256: 'client-controlled',
    }, file)

    const [, body, options] = apiClient.post.mock.calls[0]
    expect(apiClient.post.mock.calls[0][0]).toBe(
      '/agents/testing-validation/AGP-004/test-generation/sources/files',
    )
    expect(Object.fromEntries(body.entries())).toMatchObject({
      artifact_type: 'UI_FLOW', source_type: 'IMAGE',
      normally_supplied_by: 'AGENT_2', label: 'Flow', file,
    })
    expect(body.has('source_id')).toBe(false)
    expect(body.has('sha256')).toBe(false)
    expect(body.has('supplied_via')).toBe(false)
    expect(options).toEqual({ authenticated: true })
  })
})
