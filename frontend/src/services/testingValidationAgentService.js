import { apiClient } from './apiClient.js'

export function runTestingValidationAgent(agentProjectId, input) {
  return apiClient.post(
    `/agents/testing-validation/${encodeURIComponent(agentProjectId)}/run`,
    input,
    { authenticated: true },
  )
}
