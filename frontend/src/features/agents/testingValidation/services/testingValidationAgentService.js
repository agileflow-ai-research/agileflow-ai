import { apiClient } from '../../../../services/apiClient.js'

// Legacy direct TEST_GENERATION/VALIDATION run endpoint. Deprecated for TEST_GENERATION by contract v1.1,
// and no current UI calls it. Kept for VALIDATION until that rebuild.
export function runTestingValidationAgent(agentProjectId, input) {
  return apiClient.post(
    `/agents/testing-validation/${encodeURIComponent(agentProjectId)}/run`,
    input,
    { authenticated: true },
  )
}

function testGenerationInputsPath(agentProjectId) {
  return `/agents/testing-validation/${encodeURIComponent(agentProjectId)}/test-generation/sources`
}

// Project-level input collection. These calls never create an AgentRun.
export function listTestGenerationInputs(agentProjectId) {
  return apiClient.get(testGenerationInputsPath(agentProjectId), { authenticated: true })
}

export function createTestGenerationTextInput(agentProjectId, input) {
  return apiClient.post(`${testGenerationInputsPath(agentProjectId)}/text`, input, { authenticated: true })
}

export function uploadTestGenerationInputFile(agentProjectId, input) {
  const formData = new FormData()
  formData.append('artifact_type', input.artifact_type)
  formData.append('source_type', input.source_type)
  if (input.origin_agent) formData.append('origin_agent', input.origin_agent)
  if (input.label?.trim()) formData.append('label', input.label.trim())
  formData.append('file', input.file)

  return apiClient.post(`${testGenerationInputsPath(agentProjectId)}/files`, formData, { authenticated: true })
}

export function deleteTestGenerationInput(agentProjectId, sourceId) {
  return apiClient.delete(
    `${testGenerationInputsPath(agentProjectId)}/${encodeURIComponent(sourceId)}`,
    { authenticated: true },
  )
}

// Document extraction. These calls are project-level preparation and never create an AgentRun.
export function extractTestGenerationSource(agentProjectId, sourceId, { force = false } = {}) {
  const suffix = force ? '?force=true' : ''
  return apiClient.post(
    `${testGenerationInputsPath(agentProjectId)}/${encodeURIComponent(sourceId)}/extract${suffix}`,
    undefined,
    { authenticated: true },
  )
}

export function getTestGenerationExtraction(agentProjectId, sourceId) {
  return apiClient.get(
    `${testGenerationInputsPath(agentProjectId)}/${encodeURIComponent(sourceId)}/extraction`,
    { authenticated: true },
  )
}
