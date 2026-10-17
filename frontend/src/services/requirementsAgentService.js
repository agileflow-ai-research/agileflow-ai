import { apiClient } from './apiClient.js'

export function runRequirementsAgent(agentProjectId, input) {
  return apiClient.post(
    `/agents/requirements/${encodeURIComponent(agentProjectId)}/run`,
    input,
    { authenticated: true },
  )
}

export function getClarificationResponses(agentProjectId, runId) {
  return apiClient.get(
    `/agents/requirements/${encodeURIComponent(agentProjectId)}/runs/${encodeURIComponent(runId)}/clarification-responses`,
    { authenticated: true },
  )
}

export function saveClarificationResponse(agentProjectId, runId, response) {
  return apiClient.post(
    `/agents/requirements/${encodeURIComponent(agentProjectId)}/runs/${encodeURIComponent(runId)}/clarification-responses`,
    response,
    { authenticated: true },
  )
}
