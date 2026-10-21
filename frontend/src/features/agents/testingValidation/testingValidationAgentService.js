import { apiClient } from '../../../services/apiClient.js'

export function getTestGenerationWorkflow(agentProjectId) {
  return apiClient.get(
    `/agents/testing-validation/${encodeURIComponent(agentProjectId)}/test-generation/workflow`,
    { authenticated: true },
  )
}

export function updateTestGenerationOutputs(agentProjectId, selectedOutputs) {
  return apiClient.put(
    `/agents/testing-validation/${encodeURIComponent(agentProjectId)}/test-generation/workflow/outputs`,
    { selected_outputs: selectedOutputs },
    { authenticated: true },
  )
}

export function confirmTestGenerationSetup(agentProjectId) {
  return apiClient.post(
    `/agents/testing-validation/${encodeURIComponent(agentProjectId)}/test-generation/workflow/n1/confirm`,
    undefined,
    { authenticated: true },
  )
}

function sourcesPath(agentProjectId) {
  return `/agents/testing-validation/${encodeURIComponent(agentProjectId)}/test-generation/sources`
}

export function listTestingValidationSources(agentProjectId) {
  return apiClient.get(sourcesPath(agentProjectId), { authenticated: true })
}

export function createTestingValidationTextSource(agentProjectId, input) {
  return apiClient.post(`${sourcesPath(agentProjectId)}/text`, input, { authenticated: true })
}

export function uploadTestingValidationSource(agentProjectId, input, file) {
  const formData = new FormData()
  formData.append('artifact_type', input.artifact_type)
  formData.append('source_type', input.source_type)
  formData.append('normally_supplied_by', input.normally_supplied_by)
  if (input.label?.trim()) formData.append('label', input.label.trim())
  formData.append('file', file)
  return apiClient.post(`${sourcesPath(agentProjectId)}/files`, formData, { authenticated: true })
}

export function deleteTestingValidationSource(agentProjectId, sourceId) {
  return apiClient.delete(
    `${sourcesPath(agentProjectId)}/${encodeURIComponent(sourceId)}`,
    { authenticated: true },
  )
}

export function runTestingValidationAgent(agentProjectId, input) {
  return apiClient.post(
    `/agents/testing-validation/${encodeURIComponent(agentProjectId)}/run`,
    input,
    { authenticated: true },
  )
}
