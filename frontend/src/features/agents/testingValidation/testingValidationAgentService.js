import { apiClient } from '../../../services/apiClient.js'

export function getTestGenerationWorkflow(agentProjectId) {
  return apiClient.get(
    `/agents/testing-validation/${encodeURIComponent(agentProjectId)}/test-generation/workflow`,
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
